# -*- coding: utf-8 -*-
"""设置中心：可视化编辑 config/ 目录下的各项配置
每个功能一个子页；文本格式简单直观，保存时解析回 json。
"""
import tkinter as tk
from tkinter import messagebox, ttk

from core import ui
from core.config import load_json, save_json


def _text_area(parent, height=16):
    t = tk.Text(parent, height=height, font=("Consolas", -ui.px(13)), undo=True)
    t.pack(fill='both', expand=True, pady=ui.px(6))
    return t


def _lines(text):
    return [l.strip() for l in text.splitlines() if l.strip() and not l.strip().startswith('#')]


class SettingsFrame(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent, bg="#f0f2f5")
        tk.Label(self, text="⚙️ 设置", bg="#f0f2f5", fg="#333",
                 font=ui.font(17, True)).pack(anchor="w", padx=ui.px(14), pady=(ui.px(12), ui.px(2)))
        tk.Label(self, text="改完点各页的[保存]即生效（下次执行任务时使用新配置），无需重启程序",
                 bg="#f0f2f5", fg="#888", font=ui.font(11)).pack(anchor="w", padx=ui.px(15))

        nb = ttk.Notebook(self)
        nb.pack(fill='both', expand=True, padx=ui.px(10), pady=ui.px(10))

        self._tab_suppliers(nb)
        self._tab_exclude(nb)
        self._tab_milk(nb)
        self._tab_groupbuy(nb)

    # ---------- 供应商编码映射（发货/对账共用） ----------
    def _tab_suppliers(self, nb):
        f = tk.Frame(nb, bg="white", padx=ui.px(14), pady=ui.px(10))
        nb.add(f, text=" 供应商编码映射 ")
        tk.Label(f, text="商品编码前缀 = 供应商名称（每行一条，发货拆分和对账共用；匹配时长前缀优先）",
                 bg="white", fg="#666", font=ui.font(11), anchor="w").pack(fill='x')
        self.t_sup = _text_area(f)
        self._fill_suppliers()
        bar = tk.Frame(f, bg="white")
        bar.pack(fill='x')
        ttk.Button(bar, text="💾 保存", command=self._save_suppliers).pack(side='left')
        ttk.Button(bar, text="↩️ 重新载入", command=self._fill_suppliers).pack(side='left', padx=ui.px(8))

    def _fill_suppliers(self):
        m = load_json("suppliers.json", {})
        self.t_sup.delete("1.0", tk.END)
        self.t_sup.insert("1.0", "\n".join(f"{k} = {v}" for k, v in m.items()))

    def _save_suppliers(self):
        m = {}
        for ln in _lines(self.t_sup.get("1.0", tk.END)):
            if '=' not in ln:
                messagebox.showerror("格式错误", f"这一行缺少等号：{ln}")
                return
            k, v = ln.split('=', 1)
            if k.strip() and v.strip():
                m[k.strip().upper()] = v.strip()
        save_json("suppliers.json", m)
        messagebox.showinfo("OK", f"已保存 {len(m)} 条映射")

    # ---------- 排除服务组织（发货/对账共用） ----------
    def _tab_exclude(self, nb):
        f = tk.Frame(nb, bg="white", padx=ui.px(14), pady=ui.px(10))
        nb.add(f, text=" 排除服务组织 ")
        tk.Label(f, text="每行一个服务组织名称，发货和对账时这些组织的订单直接排除（如自主发货门店）",
                 bg="white", fg="#666", font=ui.font(11), anchor="w").pack(fill='x')
        self.t_ex = _text_area(f)
        self._fill_exclude()
        bar = tk.Frame(f, bg="white")
        bar.pack(fill='x')
        ttk.Button(bar, text="💾 保存", command=self._save_exclude).pack(side='left')
        ttk.Button(bar, text="↩️ 重新载入", command=self._fill_exclude).pack(side='left', padx=ui.px(8))

    def _fill_exclude(self):
        lst = load_json("exclude_orgs.json", [])
        self.t_ex.delete("1.0", tk.END)
        self.t_ex.insert("1.0", "\n".join(lst))

    def _save_exclude(self):
        lst = _lines(self.t_ex.get("1.0", tk.END))
        save_json("exclude_orgs.json", lst)
        messagebox.showinfo("OK", f"已保存 {len(lst)} 个排除组织")

    # ---------- 牛奶关键词 ----------
    def _tab_milk(self, nb):
        f = tk.Frame(nb, bg="white", padx=ui.px(14), pady=ui.px(10))
        nb.add(f, text=" 牛奶供应商关键词 ")
        tk.Label(f, text="供应商 = 关键词1,关键词2（商品名含关键词时兜底归到该供应商，供应商表匹配不上才启用）",
                 bg="white", fg="#666", font=ui.font(11), anchor="w").pack(fill='x')
        self.t_milk = _text_area(f)
        self._fill_milk()
        bar = tk.Frame(f, bg="white")
        bar.pack(fill='x')
        ttk.Button(bar, text="💾 保存", command=self._save_milk).pack(side='left')
        ttk.Button(bar, text="↩️ 重新载入", command=self._fill_milk).pack(side='left', padx=ui.px(8))

    def _fill_milk(self):
        m = load_json("keywords_milk.json", {})
        self.t_milk.delete("1.0", tk.END)
        self.t_milk.insert("1.0", "\n".join(f"{k} = {','.join(v)}" for k, v in m.items()))

    def _save_milk(self):
        m = {}
        for ln in _lines(self.t_milk.get("1.0", tk.END)):
            if '=' not in ln:
                messagebox.showerror("格式错误", f"这一行缺少等号：{ln}")
                return
            k, v = ln.split('=', 1)
            words = [w.strip() for w in v.replace('，', ',').split(',') if w.strip()]
            if k.strip() and words:
                m[k.strip()] = words
        save_json("keywords_milk.json", m)
        messagebox.showinfo("OK", f"已保存 {len(m)} 家供应商关键词")

    # ---------- 团购地址清洗 ----------
    def _tab_groupbuy(self, nb):
        f = tk.Frame(nb, bg="white", padx=ui.px(14), pady=ui.px(10))
        nb.add(f, text=" 团购地址清洗 ")
        c = load_json("groupbuy.json", {})

        def row(label, key, width=40):
            fr = tk.Frame(f, bg="white")
            fr.pack(fill='x', pady=ui.px(4))
            tk.Label(fr, text=label, bg="white", font=ui.font(12), width=16,
                     anchor="w").pack(side='left')
            e = ttk.Entry(fr, width=width, font=ui.font(12))
            e.pack(side='left', fill='x', expand=True)
            e.insert(0, c.get(key, ''))
            return e

        tk.Label(f, text="团购订单地址清洗的口径（改动会影响自提/公寓的归位判断）",
                 bg="white", fg="#666", font=ui.font(11), anchor="w").pack(fill='x', pady=(0, ui.px(6)))
        self.e_tag = row("门店标签原文", "store_tag_raw")
        self.e_store = row("门店显示名", "store_name")
        self.e_apart = row("公寓显示名", "apart_name")

        fr = tk.Frame(f, bg="white")
        fr.pack(fill='x', pady=ui.px(4))
        tk.Label(fr, text="自提关键词", bg="white", font=ui.font(12), width=16,
                 anchor="w").pack(side='left', anchor="n")
        self.e_words = tk.Text(fr, height=3, font=("Consolas", -ui.px(13)))
        self.e_words.pack(side='left', fill='x', expand=True)
        self.e_words.insert("1.0", ",".join(c.get("pickup_words", [])))
        tk.Label(f, text="逗号分隔；配送位置含这些词且不带门牌数字 → 归教工店自提",
                 bg="white", fg="#999", font=ui.font(10), anchor="w").pack(fill='x')

        bar = tk.Frame(f, bg="white")
        bar.pack(fill='x', pady=ui.px(8))
        ttk.Button(bar, text="💾 保存", command=self._save_groupbuy).pack(side='left')

    def _save_groupbuy(self):
        words = [w.strip() for w in
                 self.e_words.get("1.0", tk.END).replace('，', ',').split(',') if w.strip()]
        c = {
            "store_tag_raw": self.e_tag.get().strip(),
            "store_name": self.e_store.get().strip(),
            "apart_name": self.e_apart.get().strip(),
            "pickup_words": words,
        }
        if not all([c["store_tag_raw"], c["store_name"], c["apart_name"], words]):
            messagebox.showerror("!", "各项都不能为空")
            return
        save_json("groupbuy.json", c)
        messagebox.showinfo("OK", "团购清洗配置已保存")
