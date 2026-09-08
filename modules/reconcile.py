# -*- coding: utf-8 -*-
"""对账分析 - 界面层"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core import ui
from modules.reconcile_core import ReconcileProcessor


class ReconcileFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f0f2f5")
        self.processor = ReconcileProcessor()
        self.src_path = None
        self.setup_ui()

    def setup_ui(self):
        f_bold = ui.font(14, True)
        tk.Label(self, text="🧾 对账分析", bg="#f0f2f5", fg="#333",
                 font=ui.font(17, True)).pack(anchor="w", padx=ui.px(14), pady=(ui.px(12), ui.px(2)))
        tk.Label(self, text="月度全量导出 → 供应商『账单』（去敏感列，给供应商）+『导出』（自己看）",
                 bg="#f0f2f5", fg="#888", font=ui.font(11)).pack(anchor="w", padx=ui.px(15))

        p1 = tk.LabelFrame(self, text="第一步：加载全量表", font=f_bold, bg="#e3f2fd",
                           padx=ui.px(10), pady=ui.px(10))
        p1.pack(fill='x', padx=ui.px(10), pady=ui.px(10))
        f1 = tk.Frame(p1, bg="#e3f2fd")
        f1.pack(fill='x')
        ttk.Button(f1, text="📂 导入 [月度全量导出]", command=self.load_src).pack(side='left')
        self.lb_src = tk.Label(f1, text="未选择", bg="#e3f2fd", fg="blue",
                               font=ui.font(11), anchor="w")
        self.lb_src.pack(side='left', fill='x', expand=True, padx=ui.px(8))

        p2 = tk.LabelFrame(self, text="第二步：生成账单+导出", font=f_bold, bg="#fff3e0",
                           padx=ui.px(10), pady=ui.px(10))
        p2.pack(fill='x', padx=ui.px(10), pady=ui.px(5))
        f2 = tk.Frame(p2, bg="#fff3e0")
        f2.pack(fill='x', pady=ui.px(4))
        tk.Label(f2, text="月份前缀:", bg="#fff3e0", font=ui.font(12)).pack(side='left')
        self.em = ttk.Entry(f2, width=8, font=ui.font(12))
        self.em.pack(side='left', padx=ui.px(6))
        tk.Label(f2, text="供应商:", bg="#fff3e0", font=ui.font(12)).pack(side='left', padx=(ui.px(14), 0))
        self.cb = ttk.Combobox(f2, width=14, font=ui.font(12), state='disabled')
        self.cb.pack(side='left', padx=ui.px(6))
        tk.Label(f2, text="→ 生成「N月XX账单.xlsx」「N月XX导出.xlsx」", bg="#fff3e0",
                 fg="gray", font=ui.font(11)).pack(side='left')

        f3 = tk.Frame(p2, bg="#fff3e0")
        f3.pack(fill='x', pady=ui.px(5))
        self.b1 = ttk.Button(f3, text="⬇️ 生成所选供应商", command=self.run_one, state='disabled')
        self.b1.pack(side='left', expand=True, fill='x', padx=ui.px(2))
        self.b2 = ttk.Button(f3, text="⬇️ 全部供应商批量生成", command=self.run_all, state='disabled')
        self.b2.pack(side='left', expand=True, fill='x', padx=ui.px(2))

        self.logt = scrolledtext.ScrolledText(self, height=16, state='disabled',
                                              font=("Consolas", -ui.px(12)))
        self.logt.pack(fill='both', expand=True, padx=ui.px(10), pady=ui.px(10))

    def log(self, m):
        self.logt.config(state='normal')
        self.logt.insert(tk.END, m + "\n")
        self.logt.see(tk.END)
        self.logt.config(state='disabled')

    def load_src(self):
        f = filedialog.askopenfilename(filetypes=[("表格", "*.csv *.xlsx *.xls")])
        if not f:
            return
        self.src_path = f
        self.lb_src.config(text=os.path.basename(f), fg="green")
        self.processor = ReconcileProcessor()
        if self.processor.load_full(f, self.log):
            sups = sorted(self.processor.known, key=lambda k: -self.processor.known[k])
            self.cb.config(values=sups, state='readonly')
            if sups:
                self.cb.set(sups[0])
            # 猜月份前缀
            import re
            m = re.search(r'(\d{1,2})月', os.path.basename(f))
            self.em.delete(0, tk.END)
            self.em.insert(0, f"{m.group(1)}月" if m else "")
            self.b1.config(state='normal')
            self.b2.config(state='normal')

    def _prefix(self):
        return self.em.get().strip()

    def run_one(self):
        sup = self.cb.get()
        if not sup:
            return
        d = filedialog.askdirectory(title="选择输出文件夹")
        if not d:
            return
        pre = self._prefix()
        try:
            self.processor.export_pair(
                sup,
                os.path.join(d, f"{pre}{sup}账单.xlsx"),
                os.path.join(d, f"{pre}{sup}导出.xlsx"),
                self.log)
        except Exception as e:
            self.log(f"❌ 错误: {e}")

    def run_all(self):
        d = filedialog.askdirectory(title="选择输出文件夹（每家供应商两个文件）")
        if not d:
            return
        pre = self._prefix()
        threading.Thread(target=self._th_all, args=(d, pre), daemon=True).start()

    def _th_all(self, d, pre):
        try:
            for sup in sorted(self.processor.known, key=lambda k: -self.processor.known[k]):
                self.processor.export_pair(
                    sup,
                    os.path.join(d, f"{pre}{sup}账单.xlsx"),
                    os.path.join(d, f"{pre}{sup}导出.xlsx"),
                    self.log)
            messagebox.showinfo("完成", "全部供应商账单/导出已生成")
        except Exception as e:
            self.log(f"❌ 错误: {e}")
