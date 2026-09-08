# -*- coding: utf-8 -*-
"""牛奶团购 - 界面层（从 milk_tool_v28 的 App 迁入，改为 Frame 挂在主程序里）"""
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk

from core import ui
from modules.milk_core import DataProcessor


class MilkFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f0f2f5")
        self.processor = DataProcessor()
        self.hx_path = None
        self.wx_path = None
        self.cfg_path = None
        self.vf_path = None
        self.tch_path = None
        self.setup_ui()

    def setup_ui(self):
        f_bold = ui.font(14, True)

        tk.Label(self, text="🥛 牛奶团购", bg="#f0f2f5", fg="#333",
                 font=ui.font(17, True)).pack(anchor="w", padx=14, pady=(12, 2))

        top = tk.Frame(self, bg="white", pady=10)
        top.pack(fill='x', padx=10, pady=5)
        tk.Label(top, text="前缀:", font=f_bold, bg="white").pack(side='left', padx=10)
        self.ey = ttk.Entry(top, width=8)
        self.ey.pack(side='left')
        tk.Label(top, text="学年", bg="white", font=ui.font(12)).pack(side='left')
        self.et = ttk.Entry(top, width=8)
        self.et.pack(side='left', padx=5)
        tk.Label(top, text="期", bg="white", font=ui.font(12)).pack(side='left', padx=(0, 10))
        tk.Label(top, text="日期:", bg="white", font=ui.font(12)).pack(side='left')
        self.ed = ttk.Entry(top, width=8)
        self.ed.pack(side='left')
        tk.Label(top, text="(用于采购单)", fg="gray", bg="white", font=ui.font(11)).pack(side='left')

        f_cfg = tk.Frame(self, bg="white", pady=5)
        f_cfg.pack(fill='x', padx=10)
        self.btn_cfg = ttk.Button(f_cfg, text="📂 导入 [供应商参数表] (必需)", command=self.load_cfg)
        self.btn_cfg.pack(side='left', padx=10)
        self.lb_cfg = tk.Label(f_cfg, text="未选择", bg="white", fg="blue", font=ui.font(11), anchor="w")
        self.lb_cfg.pack(side='left')

        f_cfg2 = tk.Frame(self, bg="white", pady=5)
        f_cfg2.pack(fill='x', padx=10)
        self.btn_img = ttk.Button(f_cfg2, text="🖼️ 导入 [图片文件夹] (可选)", command=self.load_img)
        self.btn_img.pack(side='left', padx=10)
        self.lb_img = tk.Label(f_cfg2, text="未选择", bg="white", fg="blue", font=ui.font(11), anchor="w")
        self.lb_img.pack(side='left', padx=(0, 20))

        self.btn_tch = ttk.Button(f_cfg2, text="📂 导入 [班主任名单] (可选)", command=self.load_tch)
        self.btn_tch.pack(side='left', padx=10)
        self.lb_tch = tk.Label(f_cfg2, text="未选择", bg="white", fg="blue", font=ui.font(11), anchor="w")
        self.lb_tch.pack(side='left')

        p1 = tk.LabelFrame(self, text="阶段一：生成核对表", font=f_bold, bg="#e3f2fd", padx=10, pady=10)
        p1.pack(fill='x', padx=10, pady=10)

        f1 = tk.Frame(p1, bg="#e3f2fd")
        f1.pack(fill='x')
        self.btn_hx = ttk.Button(f1, text="导入海小", command=self.load_hx)
        self.btn_hx.pack(side='left')
        self.lb_hx = tk.Label(f1, text="...", bg="#e3f2fd", font=ui.font(11), anchor="w")
        self.lb_hx.pack(side='left', padx=6)
        self.btn_wx = ttk.Button(f1, text="导入外小", command=self.load_wx)
        self.btn_wx.pack(side='left', padx=(20, 0))
        self.lb_wx = tk.Label(f1, text="...", bg="#e3f2fd", font=ui.font(11), anchor="w")
        self.lb_wx.pack(side='left')

        self.btn_run = tk.Button(p1, text="⬇️ 生成 [导出明细表]", command=self.run_p1, bg="white", font=f_bold)
        self.btn_run.pack(fill='x', pady=5)

        p2 = tk.LabelFrame(self, text="阶段二：生成最终结果", font=f_bold, bg="#fff3e0", padx=10, pady=10)
        p2.pack(fill='x', padx=10, pady=5)

        f2 = tk.Frame(p2, bg="#fff3e0")
        f2.pack(fill='x', pady=5)
        self.btn_vf = ttk.Button(f2, text="📂 导入 [核对后的明细表]", command=self.load_vf)
        self.btn_vf.pack(side='left')
        self.lb_vf = tk.Label(f2, text="未选择", bg="#fff3e0", fg="red", font=ui.font(11), anchor="w")
        self.lb_vf.pack(side='left', padx=10)

        f_btns = tk.Frame(p2, bg="#fff3e0")
        f_btns.pack(fill='x', pady=5)
        self.b1 = ttk.Button(f_btns, text="📦 供应商清单", command=lambda: self.exp(4), state='disabled')
        self.b1.pack(side='left', expand=True, fill='x', padx=2)
        self.b2 = ttk.Button(f_btns, text="🏷️ 标签", command=lambda: self.exp(2), state='disabled')
        self.b2.pack(side='left', expand=True, fill='x', padx=2)
        self.b3 = ttk.Button(f_btns, text="📄 班级明细", command=lambda: self.exp(1), state='disabled')
        self.b3.pack(side='left', expand=True, fill='x', padx=2)

        self.logt = scrolledtext.ScrolledText(self, height=10, state='disabled', font=("Consolas", -ui.px(12)))
        self.logt.pack(fill='both', expand=True, padx=10, pady=10)

    def log(self, m):
        self.logt.config(state='normal')
        self.logt.insert(tk.END, m + "\n")
        self.logt.see(tk.END)
        self.logt.config(state='disabled')

    def load_hx(self):
        f = filedialog.askopenfilename()
        if f:
            self.hx_path = f
            self.lb_hx.config(text=os.path.basename(f))

    def load_wx(self):
        f = filedialog.askopenfilename()
        if f:
            self.wx_path = f
            self.lb_wx.config(text=os.path.basename(f))

    def load_cfg(self):
        f = filedialog.askopenfilename()
        if f:
            self.cfg_path = f
            self.lb_cfg.config(text=os.path.basename(f), fg="green")
            self.log(f"配置表: {f}")

    def load_img(self):
        d = filedialog.askdirectory()
        if d:
            self.processor.img_folder = d
            self.lb_img.config(text=d, fg="green")

    def load_tch(self):
        f = filedialog.askopenfilename()
        if f:
            self.tch_path = f
            self.lb_tch.config(text=os.path.basename(f), fg="green")
            self.log(f"班主任表: {f}")

    def load_vf(self):
        f = filedialog.askopenfilename()
        if f:
            self.vf_path = f
            self.lb_vf.config(text=os.path.basename(f), fg="green")

            if self.cfg_path:
                self.processor.load_supplier_config(self.cfg_path, self.log)
            else:
                messagebox.showwarning("提示", "请重新导入[供应商表]以确保图片和分类正常")

            if self.tch_path:
                self.processor.load_teacher_config(self.tch_path, self.log)

            if self.processor.load_verified_file(f, self.log):
                self.b1.config(state='normal')
                self.b2.config(state='normal')
                self.b3.config(state='normal')

    def get_prefix(self):
        y = self.ey.get().strip()
        t = self.et.get().strip()
        d = self.ed.get().strip()
        ys = y + "学年" if y and "学年" not in y else y
        ts = ("第" if t and "第" not in t else "") + t + ("期" if t and "期" not in t else "") if t else ""
        self.processor.year_term_prefix = f"{ys}{ts}"
        self.processor.date_str = d
        return f"{ys}{ts}"

    def run_p1(self):
        if not self.hx_path and not self.wx_path:
            messagebox.showwarning("!", "请导入海小/外小数据")
            return
        if not self.cfg_path:
            messagebox.showwarning("!", "请导入供应商表")
            return

        pre = self.get_prefix()
        f = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"{pre}导出明细表.xlsx")
        if not f:
            return

        threading.Thread(target=self.th_p1, args=(f,), daemon=True).start()

    def th_p1(self, save_path):
        try:
            self.processor.load_supplier_config(self.cfg_path, self.log)
            if self.tch_path:
                self.processor.load_teacher_config(self.tch_path, self.log)

            if self.processor.load_raw_files(self.hx_path, self.wx_path, self.log):
                self.processor.generate_checklist(save_path, self.log)
                messagebox.showinfo("完成", "导出明细表已生成！请核对修改后再进行阶段二。")
        except Exception as e:
            self.log(f"❌ 错误: {e}")

    def exp(self, tid):
        pre = self.processor.year_term_prefix

        if tid == 4:
            d = filedialog.askdirectory(title="选择供应商清单保存目录")
            if d:
                try:
                    self.processor.export_supplier(os.path.join(d, "x"), self.log)
                    messagebox.showinfo("OK", "导出完成")
                except Exception as e:
                    messagebox.showerror("Err", str(e))
            return

        n = {1: "班级订单明细", 2: "标签"}
        f = filedialog.asksaveasfilename(defaultextension=".xlsx", initialfile=f"{pre}{n[tid]}.xlsx")
        if f:
            try:
                if tid == 1:
                    self.processor.export_details(f)
                elif tid == 2:
                    self.processor.export_labels(f)
                self.log(f"💾 导出: {os.path.basename(f)}")
                messagebox.showinfo("OK", "成功")
            except Exception as e:
                messagebox.showerror("Err", str(e))
