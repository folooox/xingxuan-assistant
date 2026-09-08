# -*- coding: utf-8 -*-
"""订单发货 - 界面层（两阶段：总表 → 分表）"""
import datetime
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core import ui
from modules.ship_core import ShipProcessor, master_default_name


class ShipFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f0f2f5")
        self.processor = ShipProcessor()
        self.src_path = None
        self.master_path = None
        self.setup_ui()

    def setup_ui(self):
        f_bold = ui.font(14, True)
        tk.Label(self, text="📦 订单发货", bg="#f0f2f5", fg="#333",
                 font=ui.font(17, True)).pack(anchor="w", padx=ui.px(14), pady=(ui.px(12), ui.px(2)))
        tk.Label(self, text="阶段一：全量导出→发货总表（记录发货时间节点）；阶段二：总表→各供应商分表",
                 bg="#f0f2f5", fg="#888", font=ui.font(11)).pack(anchor="w", padx=ui.px(15))

        p1 = tk.LabelFrame(self, text="阶段一：生成发货总表", font=f_bold, bg="#e3f2fd",
                           padx=ui.px(10), pady=ui.px(10))
        p1.pack(fill='x', padx=ui.px(10), pady=ui.px(10))

        f1 = tk.Frame(p1, bg="#e3f2fd")
        f1.pack(fill='x')
        ttk.Button(f1, text="📂 导入 [订单导出文件]", command=self.load_src).pack(side='left')
        self.lb_src = tk.Label(f1, text="未选择", bg="#e3f2fd", fg="blue",
                               font=ui.font(11), anchor="w")
        self.lb_src.pack(side='left', fill='x', expand=True, padx=ui.px(8))
        self.var_md = tk.BooleanVar(value=True)
        tk.Checkbutton(f1, text="只保留商家配送", variable=self.var_md,
                       bg="#e3f2fd", font=ui.font(11)).pack(side='right')

        tk.Button(p1, text="⬇️ 生成 [发货总表]（文件名=当天日期-导出时间）", command=self.run_p1,
                  bg="white", font=f_bold).pack(fill='x', pady=ui.px(5))

        p2 = tk.LabelFrame(self, text="阶段二：总表拆分各供应商发货单", font=f_bold, bg="#fff3e0",
                           padx=ui.px(10), pady=ui.px(10))
        p2.pack(fill='x', padx=ui.px(10), pady=ui.px(5))

        f2 = tk.Frame(p2, bg="#fff3e0")
        f2.pack(fill='x', pady=ui.px(4))
        ttk.Button(f2, text="📂 导入 [发货总表]（核对后）", command=self.load_master).pack(side='left')
        self.lb_ms = tk.Label(f2, text="未选择（生成总表后自动填入）", bg="#fff3e0", fg="red",
                              font=ui.font(11), anchor="w")
        self.lb_ms.pack(side='left', fill='x', expand=True, padx=ui.px(8))

        f3 = tk.Frame(p2, bg="#fff3e0")
        f3.pack(fill='x', pady=ui.px(4))
        tk.Label(f3, text="分表日期:", bg="#fff3e0", font=ui.font(12)).pack(side='left')
        self.ed = ttk.Entry(f3, width=10, font=ui.font(12))
        self.ed.pack(side='left', padx=ui.px(6))
        today = datetime.date.today()
        self.ed.insert(0, f"{today.month}.{today.day}")
        tk.Label(f3, text="（用于文件名和日期列，如 7.3）", bg="#fff3e0", fg="gray",
                 font=ui.font(11)).pack(side='left')

        tk.Button(p2, text="⬇️ 选择输出文件夹并拆分 [各供应商发货单]", command=self.run_p2,
                  bg="white", font=f_bold).pack(fill='x', pady=ui.px(5))

        self.logt = scrolledtext.ScrolledText(self, height=14, state='disabled',
                                              font=("Consolas", -ui.px(12)))
        self.logt.pack(fill='both', expand=True, padx=ui.px(10), pady=ui.px(10))

    def log(self, m):
        self.logt.config(state='normal')
        self.logt.insert(tk.END, m + "\n")
        self.logt.see(tk.END)
        self.logt.config(state='disabled')

    def load_src(self):
        f = filedialog.askopenfilename(filetypes=[("表格", "*.csv *.xlsx *.xls")])
        if f:
            self.src_path = f
            self.lb_src.config(text=os.path.basename(f), fg="green")

    def run_p1(self):
        if not self.src_path:
            messagebox.showwarning("!", "请先导入订单导出文件")
            return
        default = master_default_name(self.src_path)
        f = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                         initialdir=os.path.dirname(self.src_path),
                                         initialfile=f"{default}.xlsx")
        if not f:
            return
        threading.Thread(target=self._th_p1, args=(f,), daemon=True).start()

    def _th_p1(self, save_path):
        try:
            self.processor.build_master(self.src_path, save_path, self.log,
                                        only_merchant_delivery=self.var_md.get())
            self.master_path = save_path
            self.lb_ms.config(text=os.path.basename(save_path), fg="green")
            messagebox.showinfo("完成", "发货总表已生成！可核对后进行阶段二拆分。")
        except Exception as e:
            self.log(f"❌ 错误: {e}")

    def load_master(self):
        f = filedialog.askopenfilename(filetypes=[("表格", "*.xlsx *.xls *.csv")])
        if f:
            self.master_path = f
            self.lb_ms.config(text=os.path.basename(f), fg="green")

    def run_p2(self):
        if not self.master_path:
            messagebox.showwarning("!", "请先生成或导入发货总表")
            return
        d = filedialog.askdirectory(title="选择发货单输出文件夹")
        if not d:
            return
        date_str = self.ed.get().strip() or "0.0"
        threading.Thread(target=self._th_p2, args=(d, date_str), daemon=True).start()

    def _th_p2(self, out_dir, date_str):
        try:
            self.processor.split_master(self.master_path, out_dir, date_str, self.log)
            messagebox.showinfo("完成", "各供应商发货单已生成")
        except Exception as e:
            self.log(f"❌ 错误: {e}")
