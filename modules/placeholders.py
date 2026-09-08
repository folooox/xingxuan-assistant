# -*- coding: utf-8 -*-
"""未开发功能的占位页"""
import tkinter as tk

from core import ui


class PlaceholderFrame(tk.Frame):
    def __init__(self, parent, title, desc, planned):
        super().__init__(parent, bg="#f0f2f5")
        tk.Label(self, text=title, bg="#f0f2f5", fg="#333",
                 font=ui.font(19, True)).pack(pady=(ui.px(40), ui.px(6)))
        tk.Label(self, text=desc, bg="#f0f2f5", fg="#888",
                 font=ui.font(12)).pack(pady=(0, ui.px(24)))

        box = tk.Frame(self, bg="white", padx=ui.px(30), pady=ui.px(24),
                       highlightbackground="#dde3ec", highlightthickness=1)
        box.pack(padx=ui.px(60), fill="x")
        tk.Label(box, text="规划中的能力", bg="white", fg="#555",
                 font=ui.font(14, True), anchor="w").pack(fill="x", pady=(0, ui.px(10)))
        for p in planned:
            tk.Label(box, text=f"·  {p}", bg="white", fg="#666",
                     font=ui.font(12), anchor="w").pack(fill="x", pady=ui.px(3))
        tk.Label(self, text="该功能尚未开发，先用手工流程", bg="#f0f2f5", fg="#aaa",
                 font=ui.font(11)).pack(pady=ui.px(18))
