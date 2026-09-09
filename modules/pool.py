# -*- coding: utf-8 -*-
"""本地商品池：微盟 Admin Skills 连接及门店导出合并。"""
import json
import queue
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from core import ui
from core.config import load_json, save_json
from modules.pool_core import PoolProcessor
from modules.weimob_admin_client import WeimobClient
from modules.pool_export import export_records
from modules.pool_filter import matches, cost_bound
from modules.product_status import status_values, attach_pool_status
from modules.pricing import PricingFrame
from modules.promotions import PromotionsFrame


def display(value):
    return "未返回" if value is None or value == "" else str(value)


def goods_values(row, store=None):
    price = row.get("goodsPrice") or {}
    stock = row.get("goodsStock") or {}
    lo, hi = price.get("minSalePrice"), price.get("maxSalePrice")
    sale = display(lo) if lo == hi or hi is None else "%s ～ %s" % (display(lo), display(hi))
    cost_lo, cost_hi = price.get('minCostPrice'), price.get('maxCostPrice')
    cost = display(cost_lo) if cost_lo == cost_hi else '%s ～ %s' % (display(cost_lo), display(cost_hi))
    return (display(row.get("outerGoodsCode") or row.get("goodsCode")), cost,
            sale, display(stock.get("goodsStockNum")),
            *status_values(row, store))


class PoolFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f0f2f5")
        self.processor, self.folder = PoolProcessor(), None
        self.client, self.merchants, self.stores = None, [], []
        self.rows, self.loaded = {}, set()
        self.row_stores = {}
        self.source_records = []
        self.full_mode = False
        self.applied_filters = {}
        self.page, self.total, self.busy = 1, 0, False
        self.events = queue.Queue()
        self.config = load_json("weimob_admin.json", {})
        self.setup_ui()
        saved_bos = (self.config.get('current_merchant') or {}).get('bos_id')
        if saved_bos:
            try:
                self.pricing.select_merchant(saved_bos)
                self.promotions.select_merchant(saved_bos)
            except ValueError as exc:
                self.status_var.set(str(exc))
        self.after(100, self._poll)

    def setup_ui(self):
        tk.Label(self, text="商品池", font=ui.font(18, True), bg="#f0f2f5").pack(anchor="w", padx=16, pady=12)
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=8)
        self._build_live_tab(tabs)
        self.pricing = PricingFrame(tabs, self)
        tabs.add(self.pricing, text=' 采购定价核对 ')
        self.promotions = PromotionsFrame(tabs, self)
        tabs.add(self.promotions, text=' 活动价格核对 ')
        self._build_merge_tab(tabs)

    def _build_live_tab(self, tabs):
        tab = ttk.Frame(tabs, padding=10)
        tabs.add(tab, text=" 微盟商品池 ")
        self.token_var = tk.StringVar(value=self.config.get("apikey") or self.config.get("token", ""))
        self.status_var = tk.StringVar(value="填写微盟 Admin Skills 的 API Key，连接后选择商户和商城。")
        self.search_var, self.page_var = tk.StringVar(), tk.StringVar(value="第 1 页")
        self.controls = []
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="API Key").pack(side="left")
        entry = ttk.Entry(row, textvariable=self.token_var, show="●")
        entry.pack(side="left", fill="x", expand=True, padx=8)
        self.controls.append((entry, "normal"))
        self.button(row, "连接并保存", self.connect)
        self.button(row, "清除连接", self.clear_connection)
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="商户").pack(side="left")
        self.merchant_box = ttk.Combobox(row, state="readonly", width=24)
        self.merchant_box.pack(side="left", padx=6)
        self.merchant_box.bind("<<ComboboxSelected>>", self.select_merchant)
        ttk.Label(row, text="商城 / 门店").pack(side="left")
        self.store_box = ttk.Combobox(row, state="readonly", width=28)
        self.store_box.pack(side="left", fill="x", expand=True, padx=6)
        self.store_box.bind("<<ComboboxSelected>>", self.select_store)
        self.controls.extend([(self.merchant_box, "readonly"), (self.store_box, "readonly")])
        row = ttk.Frame(tab)
        row.pack(fill="x", pady=6)
        self.search_type = ttk.Combobox(row, values=["商品名称", "商品编码"], state="readonly", width=10)
        self.search_type.current(0)
        self.search_type.pack(side="left")
        self.controls.append((self.search_type, "readonly"))
        entry = ttk.Entry(row, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True, padx=6)
        entry.bind("<Return>", lambda e: self.load_products(1))
        self.controls.append((entry, "normal"))
        self.button(row, "查询", lambda: self.load_products(1))
        self.button(row, "上一页", lambda: self.load_products(self.page - 1))
        self.button(row, "下一页", lambda: self.load_products(self.page + 1))
        ttk.Label(tab, textvariable=self.page_var).pack(anchor="w")
        filters = ttk.Frame(tab)
        filters.pack(fill='x', pady=4)
        self.filter_store = tk.StringVar()
        self.cost_low, self.cost_high = tk.StringVar(), tk.StringVar()
        for label,var,width in [('门店包含',self.filter_store,12),('成本从',self.cost_low,7),('到',self.cost_high,7)]:
            ttk.Label(filters,text=label).pack(side='left')
            entry=ttk.Entry(filters,textvariable=var,width=width)
            entry.pack(side='left',padx=3)
            self.controls.append((entry,'normal'))
        self.cost_state=ttk.Combobox(filters,values=['全部成本','有正成本','零成本','成本未返回'],state='readonly',width=11)
        self.cost_state.current(0)
        self.cost_state.pack(side='left',padx=3)
        self.online_state=ttk.Combobox(filters,values=['全部','已上架','已下架'],state='readonly',width=8)
        self.online_state.current(0)
        self.online_state.pack(side='left',padx=3)
        self.controls.extend([(self.cost_state,'readonly'),(self.online_state,'readonly')])
        self.button(filters,'应用筛选',self.apply_filters)
        self.button(filters,'重置',self.clear_filters)
        status_filters = ttk.Frame(tab)
        status_filters.pack(fill='x', pady=3)
        ttk.Label(status_filters, text='商城禁售控制').pack(side='left')
        self.pool_state = ttk.Combobox(status_filters, values=['全部', '允许销售', '商城禁售', '未读取商城状态'], state='readonly', width=18)
        self.pool_state.current(0)
        self.pool_state.pack(side='left', padx=4)
        ttk.Label(status_filters, text='两级状态').pack(side='left')
        self.effective_state = ttk.Combobox(status_filters, values=['全部', '商城禁售优先', '门店已下架', '两级状态允许', '待核对'], state='readonly', width=18)
        self.effective_state.current(0)
        self.effective_state.pack(side='left', padx=4)
        self.controls.extend([(self.pool_state, 'readonly'), (self.effective_state, 'readonly')])
        box = ttk.Frame(tab)
        box.pack(fill="both", expand=True, pady=6)
        self.tree = ttk.Treeview(box, columns=("code", "cost", "sale", "stock", "pool", "online", "effective"), show="tree headings")
        self.tree.heading("#0", text="商品 / 门店（双击商品展开）")
        self.tree.column("#0", width=350, minwidth=200)
        for name, label in zip(("code", "cost", "sale", "stock", "pool", "online", "effective"), ("编码", "成本", "商品销售价（非活动价）", "接口库存", "商城禁售控制", "门店上下架", "两级状态")):
            self.tree.heading(name, text=label)
            self.tree.column(name, width=100, minwidth=65)
        y = ttk.Scrollbar(box, command=self.tree.yview)
        x = ttk.Scrollbar(box, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=y.set, xscrollcommand=x.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y.grid(row=0, column=1, sticky="ns")
        x.grid(row=1, column=0, sticky="ew")
        box.rowconfigure(0, weight=1)
        box.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self.expand_selected_product)
        row = ttk.Frame(tab)
        row.pack(fill="x")
        self.button(row, "读取选中商品各门店", self.expand_selected_product)
        self.button(row, "查看原始记录", self.show_raw)
        row = ttk.Frame(tab)
        row.pack(fill='x', pady=4)
        self.button(row, '导出当前展示', self.export_visible)
        self.button(row, '读取全部门店', self.load_all)
        self.button(row, '导出全部门店成本', self.export_all)
        ttk.Label(tab, text="商城禁售优先于门店上架。两级状态允许不代表有库存或必然可下单；未读取商城状态不推断为允许。成本0需核实，多规格为区间；只读不修改。", wraplength=780).pack(anchor="w", pady=6)
        ttk.Label(tab, textvariable=self.status_var, wraplength=780).pack(anchor="w")

    def button(self, parent, label, command):
        button = ttk.Button(parent, text=label, command=command)
        button.pack(side="left", padx=3)
        self.controls.append((button, "normal"))

    def _busy(self, value):
        self.busy = value
        for widget, state in self.controls:
            widget.configure(state="disabled" if value else state)

    def _run(self, work, success, text):
        if self.busy:
            return
        self._busy(True)
        self.status_var.set(text)
        def worker():
            try:
                self.events.put(("done", success, work()))
            except Exception as exc:
                self.events.put(("error", None, str(exc)))
        threading.Thread(target=worker, daemon=True).start()

    def _poll(self):
        try:
            while True:
                kind, callback, value = self.events.get_nowait()
                if kind == "progress":
                    self.status_var.set("正在读取门店：" + value)
                else:
                    self._busy(False)
                    if kind == "error":
                        self.status_var.set("读取失败：" + value)
                    else:
                        try:
                            callback(value)
                        except Exception as exc:
                            self.status_var.set("处理失败：" + str(exc))
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def connect(self):
        if self.busy:
            return
        try:
            client = WeimobClient(self.token_var.get())
        except Exception as exc:
            self.status_var.set(str(exc))
            return
        self.client = None
        self.reset_rows()
        self.merchants, self.stores = [], []
        self.merchant_box.set("")
        self.store_box.set("")
        def success(merchants):
            self.client, self.merchants = client, merchants
            self.config["apikey"] = client.api_key
            self.config.pop("token", None)
            save_json("weimob_admin.json", self.config)
            self.merchant_box.configure(values=[m.get("merchantName", "") for m in merchants])
            if not merchants:
                self.status_var.set("Key 已验证，但未返回可访问商户。")
                return
            saved = self.config.get("current_merchant") or {}
            index = next((i for i,m in enumerate(merchants) if str(m.get("id") or m.get("bosId")) == str(saved.get("bos_id"))), None)
            if index is not None or len(merchants) == 1:
                self.merchant_box.current(index if index is not None else 0)
                self.select_merchant()
            else:
                self.status_var.set("请选择商户。")
        self._run(client.merchants, success, "正在验证 Key 并读取商户…")

    def bos_id(self):
        m = self.merchants[self.merchant_box.current()]
        return m.get("id") or m.get("bosId")

    def select_merchant(self, event=None):
        if self.busy or self.merchant_box.current() < 0:
            return
        bos = self.bos_id()
        self.reset_rows()
        self.stores = []
        self.store_box.set("")
        self.config["current_merchant"] = {"bos_id": bos, "name": self.merchant_box.get()}
        self.pricing.select_merchant(bos)
        self.promotions.select_merchant(bos)
        def success(stores):
            self.stores = stores
            self.store_box.configure(values=["%s · %s" % (s.get("vidName", ""), s.get("vidTypeName", "")) for s in stores])
            saved = self.config.get("current_store") or {}
            index = next((i for i,s in enumerate(stores) if str(s["vid"]) == str(saved.get("vid"))), None)
            if index is None:
                malls = [i for i,s in enumerate(stores) if str(s.get("vidType")) == "5"]
                index = malls[0] if len(malls) == 1 else (0 if len(stores) == 1 else None)
            if index is not None:
                self.store_box.current(index)
                self.select_store()
            else:
                self.status_var.set("请选择商城或门店。" if stores else "该商户未返回门店。")
        self._run(lambda: self.client.stores(bos), success, "正在读取商城和门店…")

    def select_store(self, event=None):
        if self.busy or self.store_box.current() < 0:
            return
        store = self.stores[self.store_box.current()]
        self.config["current_store"] = {"vid": store["vid"], "vid_type": store["vidType"], "name": store.get("vidName")}
        save_json("weimob_admin.json", self.config)
        self.reset_rows()
        self.load_products(1)

    def reset_rows(self):
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.row_stores.clear()
        self.source_records = []
        self.full_mode = False
        self.loaded.clear()
        self.page, self.total = 1, 0
        self.page_var.set("第 1 页")

    def load_products(self, page=1):
        if self.busy:
            return
        if not self.client or self.store_box.current() < 0:
            self.status_var.set("请先连接并选择商城 / 门店。")
            return
        if page < 1 or (page > 1 and (page - 1) * 50 >= self.total):
            return
        bos, store = self.bos_id(), self.stores[self.store_box.current()]
        search, search_type = self.search_var.get().strip(), self.search_type.current() + 1
        def success(data):
            self.reset_rows()
            self.page, self.total = page, int(data.get("totalCount", 0))
            for product in data.get("pageList") or []:
                iid = self.tree.insert("", "end", text=product.get("title") or "未返回名称", values=goods_values(product, store))
                self.rows[iid] = product
                self.row_stores[iid] = store
                self.source_records.append((store,product))
            self.page_var.set("第 %s 页 · 共 %s 个商品" % (page, self.total))
            self.status_var.set("%s · 已读取本页 %s 个商品" % (store.get("vidName", ""), len(self.rows)))
            self.apply_filters()
        self._run(lambda: self.client.products(bos, store, page, 50, search, search_type), success, "正在读取商品…")

    def expand_selected_product(self, event=None):
        if self.busy:
            return
        if self.full_mode:
            return
        selected = self.tree.selection()
        iid = selected[0] if selected else ""
        if iid not in self.rows or self.tree.parent(iid):
            return
        if iid in self.loaded:
            self.tree.item(iid, open=True)
            return
        product, bos, stores = self.rows[iid], self.bos_id(), list(self.stores)
        for child in self.tree.get_children(iid):
            self.tree.delete(child)
        def success(data):
            for match in data["matches"]:
                row = match["product"]
                parent_store = self.row_stores.get(iid, {})
                if str(parent_store.get('vidType')) == '5':
                    row = attach_pool_status([(match['store'], row)], [(parent_store, product)])[0][1]
                child = self.tree.insert(iid, "end", text=match["store"].get("vidName"), values=goods_values(row, match['store']))
                self.rows[child] = row
                self.row_stores[child] = match['store']
                record=(match['store'],row)
                key=(str(match['store']['vid']),str(row['goodsId']))
                if not any((str(s['vid']),str(r['goodsId'])) == key for s,r in self.source_records):
                    self.source_records.append(record)
            for error in data["errors"]:
                self.tree.insert(iid, "end", text=error["store"].get("vidName") + "：读取失败", values=("", "", "", "", error["error"]))
            if not data["matches"] and not data["errors"]:
                self.tree.insert(iid, "end", text="当前可访问门店的名称搜索结果中未找到相同商品 ID")
            if not data["errors"]:
                self.loaded.add(iid)
            self.tree.item(iid, open=True)
            self.status_var.set("已查询 %s 个门店，匹配 %s 个；失败 %s 个。按名称检索后核对商品 ID，门店改名可能导致漏匹配。" %
                (data["checked"], len(data["matches"]), len(data["errors"])))
        self._run(lambda: self.client.product_stores(bos, stores, product,
                  lambda value: self.events.put(("progress", None, value))), success, "正在逐店查询同一商品…")

    def filter_values(self):
        low,high=cost_bound(self.cost_low.get()),cost_bound(self.cost_high.get())
        if low is not None and high is not None and low > high:
            raise ValueError('成本起始值不能大于结束值')
        return dict(low=low,high=high,store=self.filter_store.get().strip(),
            online=self.online_state.get(),cost_state=self.cost_state.get(),
            pool_state=self.pool_state.get(),effective=self.effective_state.get(),
            keyword=self.search_var.get().strip(),by_code=self.search_type.current()==1)

    def apply_filters(self):
        if self.busy: return
        try: values=self.filter_values()
        except ValueError as exc:
            self.status_var.set(str(exc))
            return
        records=[(s,r) for s,r in self.source_records if matches(r,s,values)]
        self.applied_filters = values
        self.tree.delete(*self.tree.get_children())
        self.rows.clear()
        self.row_stores.clear()
        self.loaded.clear()
        groups={}
        for store,row in records:
            key=str(row['goodsId'])
            parent=''
            if self.full_mode:
                if key not in groups:
                    groups[key]=self.tree.insert('','end',text=row.get('title') or '未返回名称',open=False)
                parent=groups[key]
            iid=self.tree.insert(parent,'end',text=store.get('vidName','') if parent else row.get('title','') + ' · ' + store.get('vidName',''),values=goods_values(row, store))
            self.rows[iid]=row
            self.row_stores[iid]=store
        scope='全部门店已读取数据' if self.full_mode else '当前页及已读取门店'
        self.status_var.set('%s：显示 %s / %s 条；成本范围按区间相交筛选。' % (scope,len(records),len(self.source_records)))

    def clear_filters(self):
        self.filter_store.set('')
        self.cost_low.set('')
        self.cost_high.set('')
        self.search_var.set('')
        self.cost_state.current(0)
        self.online_state.current(0)
        self.pool_state.current(0)
        self.effective_state.current(0)
        self.apply_filters()

    def load_all(self):
        if self.busy: return
        if not self.client or self.merchant_box.current()<0:
            self.status_var.set('请先在“微盟商品池”点击连接并选择商户，再刷新全部门店。')
            return
        bos,stores=self.bos_id(),list(self.stores)
        malls=[s for s in stores if str(s.get('vidType')) == '5']
        if len(malls) != 1:
            messagebox.showinfo('需确认商城', '当前商户不止一个或没有商城节点，不能跨商城合并禁售状态。请先联系维护者确认范围。')
            return
        def success(result):
            records,errors=result
            self.reset_rows()
            self.full_mode=True
            self.source_records=records
            self.page_var.set('全部门店 · %s 条 · 读取失败 %s 个门店' % (len(records),len(errors)))
            self.apply_filters()
            self.pricing.update_catalog(records, '全部可访问门店；失败节点 %s 个' % len(errors))
            self.promotions.refresh()
            if errors:
                messagebox.showwarning('部分门店读取失败','\n'.join(e['store'].get('vidName','')+'：'+e['error'] for e in errors))
        self._run(lambda:self.client.catalog_with_status(bos,stores,malls[0],
            lambda value:self.events.put(('progress',None,value))),success,'正在读取全部门店…')

    def export_visible(self):
        if self.busy or not self.rows: return
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='商品池当前展示.xlsx')
        if not path: return
        records = [(self.row_stores[iid], row) for iid,row in self.rows.items() if self.tree.exists(iid)]
        merchant = (self.config.get('current_merchant') or {}).get('name','')
        scope=('全部门店已读取数据的筛选结果' if self.full_mode else '当前页及已读取门店的筛选结果；不代表全量')+'；已应用筛选条件：'+str(self.applied_filters)
        self._run(lambda: export_records(path,merchant,records,scope=scope),
                  lambda n:self.status_var.set('已导出 %s 行：%s' % (n,path)), '正在导出当前展示…')

    def export_all(self):
        if self.busy or not self.client or self.merchant_box.current() < 0: return
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='全部门店商品成本.xlsx')
        if not path: return
        bos, stores = self.bos_id(), list(self.stores)
        malls=[s for s in stores if str(s.get('vidType')) == '5']
        if len(malls) != 1:
            self.status_var.set('需要唯一商城节点才能核对两级状态')
            return
        merchant = (self.config.get('current_merchant') or {}).get('name','')
        def work():
            records, errors = self.client.catalog_with_status(bos,stores,malls[0],
                lambda value:self.events.put(('progress',None,value)))
            if not records: raise RuntimeError('未读取到商品，未生成文件。' + str([e['error'] for e in errors][:2]))
            export_records(path,merchant,records,errors,scope='当前商户全部可访问门店，逐店全分页；不受页面搜索条件影响')
            return len(records),len(errors)
        self._run(work,lambda result:self.status_var.set('已导出 %s 行，失败 %s 个门店（详见工作表）：%s' % (*result,path)),
                  '正在读取全部门店，可能需要几分钟…')

    def show_raw(self):
        selected = self.tree.selection()
        if not selected or selected[0] not in self.rows:
            return
        window = tk.Toplevel(self)
        window.title("微盟原始商品记录")
        text = scrolledtext.ScrolledText(window, width=100, height=30)
        text.pack(fill="both", expand=True)
        text.insert("1.0", json.dumps(self.rows[selected[0]], ensure_ascii=False, indent=2))
        text.configure(state="disabled")

    def clear_connection(self):
        if self.busy:
            return
        if not messagebox.askyesno("清除连接", "清除本机保存的微盟 Key 和当前商户、门店？"):
            return
        self.config = {}
        save_json("weimob_admin.json", {})
        self.token_var.set("")
        self.client, self.merchants, self.stores = None, [], []
        self.merchant_box.set("")
        self.store_box.set("")
        self.merchant_box.configure(values=[])
        self.store_box.configure(values=[])
        self.reset_rows()
        self.promotions.clear_session()
        self.status_var.set("已清除本机连接配置。")

    # -------------------- 原 Excel 合并功能 --------------------
    def _build_merge_tab(self, notebook):
        tab = tk.Frame(notebook, bg="#f0f2f5")
        notebook.add(tab, text=" 门店导出合并 ")
        f_bold = ui.font(14, True)
        p1 = tk.LabelFrame(tab, text="合并汇总", font=f_bold, bg="#e3f2fd",
                           padx=ui.px(10), pady=ui.px(10))
        p1.pack(fill="x", padx=ui.px(10), pady=ui.px(10))
        f1 = tk.Frame(p1, bg="#e3f2fd")
        f1.pack(fill="x")
        ttk.Button(f1, text="📂 选择 [门店导出文件夹]", command=self.load_folder).pack(side="left")
        self.lb = tk.Label(f1, text="未选择", bg="#e3f2fd", fg="blue", font=ui.font(11), anchor="w")
        self.lb.pack(side="left", fill="x", expand=True, padx=ui.px(8))
        tk.Button(p1, text="⬇️ 生成 [汇总表]", command=self.run,
                  bg="white", font=f_bold).pack(fill="x", pady=ui.px(5))
        self.logt = scrolledtext.ScrolledText(tab, height=18, state="disabled", font=("Consolas", -ui.px(12)))
        self.logt.pack(fill="both", expand=True, padx=ui.px(10), pady=ui.px(10))

    def log(self, message):
        self.logt.config(state="normal")
        self.logt.insert(tk.END, message + "\n")
        self.logt.see(tk.END)
        self.logt.config(state="disabled")

    def load_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.folder = folder
            self.lb.config(text=folder, fg="green")

    def run(self):
        if not self.folder:
            messagebox.showwarning("!", "请先选择门店导出文件夹")
            return
        save_path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                                 initialdir=self.folder, initialfile="汇总.xlsx")
        if save_path:
            threading.Thread(target=self._merge_thread, args=(save_path,), daemon=True).start()

    def _merge_thread(self, save_path):
        try:
            self.processor.merge(self.folder, save_path, self.log)
            self.after(0, lambda: messagebox.showinfo("完成", "汇总表已生成"))
        except Exception as exc:
            self.after(0, lambda error=exc: self.log("❌ 错误: %s" % error))
