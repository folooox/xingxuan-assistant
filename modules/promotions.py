"""Read-only activity import, live session replay, filters and export."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from modules.pricing import table, export_comparisons
from modules.pricing_core import money, text
from modules.promotion_client import load_har, PromotionClient
from modules.promotion_core import activity_info, sku_results, store_results


class PromotionsFrame(ttk.Frame):
    def __init__(self, parent, pool):
        super().__init__(parent, padding=8)
        self.pool, self.client, self.bos = pool, None, None
        self.snapshot = None
        self.results = []
        top = ttk.Frame(self)
        top.pack(fill='x')
        ttk.Button(top, text='导入活动HAR（本机）', command=self.import_har).pack(side='left', padx=3)
        ttk.Button(top, text='一键读取活动全部商品', command=self.sync).pack(side='left', padx=3)
        ttk.Button(top, text='清除内存登录会话', command=self.clear_session).pack(side='left', padx=3)
        ttk.Button(top, text='导出当前筛选', command=self.export).pack(side='left', padx=3)
        self.info = tk.StringVar(value='先连接商户，然后导入该商户的活动HAR；已清理HAR可离线核对，实时查询需要有效登录会话。')
        ttk.Label(self, textvariable=self.info, wraplength=840).pack(anchor='w', pady=5)
        ttk.Label(self, textvariable=self.pool.status_var, wraplength=840).pack(anchor='w')
        self.mode = ttk.Combobox(self, values=['门店成本核对', '活动SKU原始成本'], state='readonly', width=28)
        self.mode.current(0)
        self.mode.pack(anchor='w')
        self.mode.bind('<<ComboboxSelected>>', lambda e: self.refresh())
        row = ttk.Frame(self)
        row.pack(fill='x', pady=5)
        self.query = tk.StringVar()
        self.markup = tk.StringVar(value='1.15')
        ttk.Label(row, text='商品 / 编码 / 门店').pack(side='left')
        ttk.Entry(row, textvariable=self.query, width=20).pack(side='left', padx=3)
        ttk.Label(row, text='目标成本倍数').pack(side='left')
        ttk.Entry(row, textvariable=self.markup, width=6).pack(side='left', padx=3)
        self.state = ttk.Combobox(row, values=['全部', '活动价倒挂', '未达加价目标', '达到加价目标', '多规格区间待核对', '零成本待核实', '缺少成本或活动价', '门店商品未匹配', '不适用此活动', '活动有效性待核对'], state='readonly', width=20)
        self.state.current(0)
        self.state.pack(side='left', padx=3)
        ttk.Button(row, text='应用筛选', command=self.refresh).pack(side='left')
        self.tree_box = ttk.Frame(self)
        self.tree_box.pack(fill='both', expand=True)
        self.tree = None
        ttk.Label(self, text='活动响应内的SKU成本与门店成本分开展示。范围不明、门店未匹配或多规格区间不判定安全。叠加满减/券后的实付价尚未计算；这里核对活动基础价格。', wraplength=840).pack(anchor='w', pady=5)
        self.refresh()

    def select_merchant(self, bos):
        self.bos = str(bos)
        self.client = None
        self.snapshot = self.pool.pricing.data.get('activity_snapshot')
        self.refresh()

    def accept_snapshot(self, snapshot):
        if str(snapshot['bos_id']) != self.bos:
            raise ValueError('活动与当前商户不一致，未保存')
        self.snapshot = snapshot
        self.pool.pricing.data['activity_snapshot'] = snapshot
        self.pool.pricing.save()
        self.refresh()

    def import_har(self):
        if self.pool.busy:
            return
        if not self.bos:
            messagebox.showinfo('先连接商户', '请先在微盟商品池连接并选择商户')
            return
        path = filedialog.askopenfilename(filetypes=[('浏览器网络记录', '*.har')])
        if not path:
            return
        def success(loaded):
            self.client = PromotionClient(loaded['requests'])
            self.accept_snapshot(loaded['snapshot'])
        self.pool._run(lambda: load_har(path, self.bos), success, '正在解析本机活动记录（不上传HAR）…')

    def sync(self):
        if self.pool.busy:
            return
        if not self.client:
            messagebox.showinfo('需要本机登录会话', '请先导入含有效登录信息的本机HAR。程序不保存登录凭证，关闭后需重新导入。')
            return
        self.info.set('正在读取全部活动商品；仅发送已验证的两个只读查询接口。')
        self.pool._run(lambda: self.client.sync(lambda v: self.pool.events.put(('progress', None, v))), self.accept_snapshot, '正在读取活动全部商品…')

    def clear_session(self):
        self.client = None
        self.info.set('已清除内存中的登录会话。已保存的业务快照不含请求头或Cookie。原HAR文件仍在你的本机。')

    def refresh(self):
        if self.tree is not None:
            for child in self.tree_box.winfo_children():
                child.destroy()
        sku = self.mode.get() == '活动SKU原始成本'
        columns = ['商品名称', '规格', '规格编码', '接口SKU成本', '活动价', '核对状态', '目标售价', '价差', '成本来源'] if sku else ['商品名称', '门店', '最低成本', '最高成本', '活动最低价', '活动最高价', '核对状态', '目标售价', '价差', '商城禁售控制', '门店上下架', '采购核定售价', '采购售价核对']
        self.tree = table(self.tree_box, columns, 18)
        self.results = []
        if not self.snapshot:
            return
        try:
            markup = money(self.markup.get())
            if markup is None or markup < 1:
                raise ValueError('目标成本倍数需不小于1，例如1.15')
            data = self.pool.pricing.data
            results = sku_results(self.snapshot, str(markup)) if sku else store_results(self.snapshot, data['catalog'], str(markup), data['quotes'], data['bindings'])
            query = self.query.get().strip().casefold()
            for result in results:
                if query and query not in ' '.join(text(result.get(k)) for k in ('商品名称', '商品编码', '门店', '规格编码')).casefold():
                    continue
                if self.state.get() not in ('全部', result['核对状态']):
                    continue
                result['目标成本倍数'] = str(markup)
                result['门店快照时间'] = data.get('catalog_time', '')
                self.results.append(result)
                self.tree.insert('', 'end', values=[text(result.get(col)) for col in columns])
            info = activity_info(self.snapshot)
            self.info.set('%s：活动已读 %s / %s 个商品（%s）；显示 %s 行。活动时间 %s；门店快照 %s。' % (info['name'], len(self.snapshot['goods']), self.snapshot['total'], '全量' if self.snapshot['complete'] else '部分快照', len(self.results), self.snapshot.get('captured_at'), data.get('catalog_time') or '未读取'))
        except Exception as exc:
            self.info.set(str(exc))

    def export(self):
        self.refresh()
        if not self.results:
            return
        path = filedialog.asksaveasfilename(defaultextension='.xlsx', initialfile='活动价格核对.xlsx')
        if path:
            try:
                export_comparisons(path, self.results)
                self.info.set('已导出当前筛选 %s 行：%s' % (len(self.results), path))
            except Exception as exc:
                messagebox.showerror('导出失败', str(exc))
