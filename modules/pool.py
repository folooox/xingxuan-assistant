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


def display(value):
    return "未返回" if value is None or value == "" else str(value)


def goods_values(row):
    price = row.get("goodsPrice") or {}
    stock = row.get("goodsStock") or {}
    lo, hi = price.get("minSalePrice"), price.get("maxSalePrice")
    sale = display(lo) if lo == hi or hi is None else "%s ～ %s" % (display(lo), display(hi))
    online = row.get("isOnline")
    return (display(row.get("outerGoodsCode") or row.get("goodsCode")), "未提供",
            sale, display(stock.get("goodsStockNum")),
            "未返回" if online is None else ("已上架" if online else "已下架"))


class PoolFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f0f2f5")
        self.processor, self.folder = PoolProcessor(), None
        self.client, self.merchants, self.stores = None, [], []
        self.rows, self.loaded = {}, set()
        self.page, self.total, self.busy = 1, 0, False
        self.events = queue.Queue()
        self.config = load_json("weimob_admin.json", {})
        self.setup_ui()
        self.after(100, self._poll)

    def setup_ui(self):
        tk.Label(self, text="商品池", font=ui.font(18, True), bg="#f0f2f5").pack(anchor="w", padx=16, pady=12)
        tabs = ttk.Notebook(self)
        tabs.pack(fill="both", expand=True, padx=10, pady=8)
        self._build_live_tab(tabs)
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
        box = ttk.Frame(tab)
        box.pack(fill="both", expand=True, pady=6)
        self.tree = ttk.Treeview(box, columns=("code", "cost", "sale", "stock", "status"), show="tree headings")
        self.tree.heading("#0", text="商品 / 门店（双击商品展开）")
        self.tree.column("#0", width=350, minwidth=200)
        for name, label in zip(("code", "cost", "sale", "stock", "status"), ("编码", "成本", "售价（元）", "接口库存", "状态")):
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
        ttk.Label(tab, text="当前接口支持查询；成本、SKU 明细和编辑写入尚未提供。商城库存与门店库存分开展示。", wraplength=780).pack(anchor="w", pady=6)
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
                iid = self.tree.insert("", "end", text=product.get("title") or "未返回名称", values=goods_values(product))
                self.rows[iid] = product
            self.page_var.set("第 %s 页 · 共 %s 个商品" % (page, self.total))
            self.status_var.set("%s · 已读取本页 %s 个商品" % (store.get("vidName", ""), len(self.rows)))
        self._run(lambda: self.client.products(bos, store, page, 50, search, search_type), success, "正在读取商品…")

    def expand_selected_product(self, event=None):
        if self.busy:
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
                child = self.tree.insert(iid, "end", text=match["store"].get("vidName"), values=goods_values(row))
                self.rows[child] = row
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
