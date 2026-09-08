# -*- coding: utf-8 -*-
"""团购配送 - 界面层（两阶段，与牛奶助手操作习惯一致）"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core import ui
from modules.groupbuy_core import GroupbuyProcessor


def _default_prefix(path):
    """'6.26山姆导出.csv' → '6.26山姆'"""
    base = os.path.splitext(os.path.basename(path))[0]
    base = base.replace('（核对）', '').replace('(核对)', '')
    if '导出' in base:
        base = base.split('导出')[0]
    return base.strip()


class GroupbuyFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f0f2f5")
        self.processor = GroupbuyProcessor()
        self.raw_path = None
        self.vf_path = None
        self.setup_ui()

    def setup_ui(self):
        f_bold = ui.font(14, True)

        tk.Label(self, text="🚚 团购配送", bg="#f0f2f5", fg="#333",
                 font=ui.font(17, True)).pack(anchor="w", padx=ui.px(14), pady=(ui.px(12), ui.px(2)))
        tk.Label(self, text="适用：山姆/水果等团购订单导出（已取消自动剔除，售后单保留人工判断；地址自动归位清洗）",
                 bg="#f0f2f5", fg="#888", font=ui.font(11)).pack(anchor="w", padx=ui.px(15))

        p1 = tk.LabelFrame(self, text="阶段一：原始导出 → 核对表", font=f_bold,
                           bg="#e3f2fd", padx=ui.px(10), pady=ui.px(10))
        p1.pack(fill='x', padx=ui.px(10), pady=ui.px(10))

        f1 = tk.Frame(p1, bg="#e3f2fd")
        f1.pack(fill='x')
        ttk.Button(f1, text="📂 导入 [订单导出文件]", command=self.load_raw).pack(side='left')
        self.lb_raw = tk.Label(f1, text="未选择", bg="#e3f2fd", fg="blue",
                               font=ui.font(11), anchor="w")
        self.lb_raw.pack(side='left', fill='x', expand=True, padx=ui.px(8))

        tk.Button(p1, text="⬇️ 生成 [核对表]（同名 .xlsx）", command=self.run_p1,
                  bg="white", font=f_bold).pack(fill='x', pady=ui.px(5))

        p2 = tk.LabelFrame(self, text="阶段二：核对后的表 → 明细 / 标签", font=f_bold,
                           bg="#fff3e0", padx=ui.px(10), pady=ui.px(10))
        p2.pack(fill='x', padx=ui.px(10), pady=ui.px(5))

        f2 = tk.Frame(p2, bg="#fff3e0")
        f2.pack(fill='x', pady=ui.px(4))
        ttk.Button(f2, text="📂 导入 [核对后的表]", command=self.load_vf).pack(side='left')
        self.lb_vf = tk.Label(f2, text="未选择", bg="#fff3e0", fg="red",
                              font=ui.font(11), anchor="w")
        self.lb_vf.pack(side='left', fill='x', expand=True, padx=ui.px(8))

        f3 = tk.Frame(p2, bg="#fff3e0")
        f3.pack(fill='x', pady=ui.px(4))
        tk.Label(f3, text="输出前缀:", bg="#fff3e0", font=ui.font(12)).pack(side='left')
        self.ep = ttk.Entry(f3, width=18, font=ui.font(12))
        self.ep.pack(side='left', padx=ui.px(6))
        tk.Label(f3, text="→ 生成「前缀团购明细.xlsx」「前缀团购标签.xlsx」",
                 bg="#fff3e0", fg="gray", font=ui.font(11)).pack(side='left')

        f_btns = tk.Frame(p2, bg="#fff3e0")
        f_btns.pack(fill='x', pady=ui.px(5))
        self.b1 = ttk.Button(f_btns, text="📄 团购明细", command=self.exp_detail, state='disabled')
        self.b1.pack(side='left', expand=True, fill='x', padx=ui.px(2))
        self.b2 = ttk.Button(f_btns, text="🏷️ 团购标签（不含自提）", command=self.exp_label, state='disabled')
        self.b2.pack(side='left', expand=True, fill='x', padx=ui.px(2))

        self.logt = scrolledtext.ScrolledText(self, height=12, state='disabled', font=("Consolas", -ui.px(12)))
        self.logt.pack(fill='both', expand=True, padx=ui.px(10), pady=ui.px(10))

    def log(self, m):
        self.logt.config(state='normal')
        self.logt.insert(tk.END, m + "\n")
        self.logt.see(tk.END)
        self.logt.config(state='disabled')

    def load_raw(self):
        f = filedialog.askopenfilename(filetypes=[("表格", "*.csv *.xlsx *.xls")])
        if f:
            self.raw_path = f
            self.lb_raw.config(text=os.path.basename(f), fg="green")

    def run_p1(self):
        if not self.raw_path:
            messagebox.showwarning("!", "请先导入订单导出文件")
            return
        base = os.path.splitext(os.path.basename(self.raw_path))[0]
        f = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                         initialdir=os.path.dirname(self.raw_path),
                                         initialfile=f"{base}.xlsx")
        if not f:
            return
        threading.Thread(target=self._th_p1, args=(f,), daemon=True).start()

    def _th_p1(self, save_path):
        try:
            self.processor.generate_checklist(self.raw_path, save_path, self.log)
            messagebox.showinfo("完成", "核对表已生成！请核对修改后再进行阶段二。")
        except Exception as e:
            self.log(f"❌ 错误: {e}")

    def load_vf(self):
        f = filedialog.askopenfilename(filetypes=[("表格", "*.xlsx *.xls *.csv")])
        if f:
            self.vf_path = f
            self.lb_vf.config(text=os.path.basename(f), fg="green")
            if self.processor.load_verified(f, self.log):
                self.ep.delete(0, tk.END)
                self.ep.insert(0, _default_prefix(f))
                self.b1.config(state='normal')
                self.b2.config(state='normal')

    def _save_as(self, name):
        return filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialdir=os.path.dirname(self.vf_path) if self.vf_path else None,
            initialfile=name)

    def exp_detail(self):
        pre = self.ep.get().strip()
        f = self._save_as(f"{pre}团购明细.xlsx")
        if f:
            try:
                self.processor.export_details(f, self.log)
                messagebox.showinfo("OK", "明细已生成")
            except Exception as e:
                messagebox.showerror("Err", str(e))

    def exp_label(self):
        pre = self.ep.get().strip()
        f = self._save_as(f"{pre}团购标签.xlsx")
        if f:
            try:
                self.processor.export_labels(f, self.log)
                messagebox.showinfo("OK", "标签已生成")
            except Exception as e:
                messagebox.showerror("Err", str(e))
