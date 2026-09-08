# -*- coding: utf-8 -*-
"""星选助手 - 表格工作自动化工具箱"""
import ctypes
import tkinter as tk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from core import ui
from modules.milk import MilkFrame
from modules.groupbuy import GroupbuyFrame
from modules.ship import ShipFrame
from modules.reconcile import ReconcileFrame
from modules.pool import PoolFrame
from modules.settings import SettingsFrame
from modules.placeholders import PlaceholderFrame

APP_NAME = "星选助手"

# ============ 模块注册表：新功能加一行 ============
MODULES = [
    {
        "key": "milk", "icon": "🥛", "name": "牛奶团购",
        "desc": "导出数据一键生成班级明细、箱贴标签、供应商采购清单",
        "frame": MilkFrame,
    },
    {
        "key": "groupbuy", "icon": "🚚", "name": "团购配送",
        "desc": "山姆/水果团购订单 → 核对表 → 配送明细、发放标签",
        "frame": GroupbuyFrame,
    },
    {
        "key": "ship", "icon": "📦", "name": "订单发货",
        "desc": "全量导出 → 按供应商编码拆分发货单",
        "frame": ShipFrame,
    },
    {
        "key": "reconcile", "icon": "🧾", "name": "对账分析",
        "desc": "月度全量导出 → 供应商账单 + 自查导出",
        "frame": ReconcileFrame,
    },
    {
        "key": "pool", "icon": "📊", "name": "商品池分析",
        "desc": "微盟商城商品查询、各门店折叠对照、门店导出合并",
        "frame": PoolFrame,
    },
    {
        "key": "settings", "icon": "⚙️", "name": "设置",
        "desc": "供应商编码映射、排除组织、牛奶关键词、团购清洗口径",
        "frame": SettingsFrame,
    },
]

SIDEBAR_BG = "#1f2a3c"
SIDEBAR_FG = "#cfd8e6"
SIDEBAR_ACTIVE = "#2f4058"
CONTENT_BG = "#f0f2f5"


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        ui.init(self, base_w=1080, base_h=880)
        self.configure(bg=CONTENT_BG)

        self.frames = {}
        self.nav_btns = {}
        self._current = None

        self._build_sidebar()
        self.container = tk.Frame(self, bg=CONTENT_BG)
        self.container.pack(side="left", fill="both", expand=True)

        self.show(MODULES[0]["key"])

    def _build_sidebar(self):
        sb = tk.Frame(self, bg=SIDEBAR_BG, width=ui.px(180))
        sb.pack(side="left", fill="y")
        sb.pack_propagate(False)

        tk.Label(sb, text=APP_NAME, bg=SIDEBAR_BG, fg="white",
                 font=ui.font(20, True)).pack(pady=(ui.px(26), ui.px(20)))

        for m in MODULES:
            b = tk.Label(sb, text=f'{m["icon"]}  {m["name"]}', bg=SIDEBAR_BG, fg=SIDEBAR_FG,
                         font=ui.font(14), anchor="w", padx=ui.px(24), pady=ui.px(12))
            b.pack(fill="x")
            b.bind("<Button-1>", lambda e, k=m["key"]: self.show(k))
            b.bind("<Enter>", lambda e, w=b: w.config(bg=SIDEBAR_ACTIVE))
            b.bind("<Leave>", lambda e, w=b, k=m["key"]: w.config(
                bg=SIDEBAR_ACTIVE if self._current == k else SIDEBAR_BG))
            self.nav_btns[m["key"]] = b

    def show(self, key):
        if key not in self.frames:
            mod = next((m for m in MODULES if m["key"] == key), None)
            if mod is None:
                return
            if mod["frame"]:
                self.frames[key] = mod["frame"](self.container)
            else:
                self.frames[key] = PlaceholderFrame(
                    self.container, f'{mod["icon"]} {mod["name"]}',
                    mod["desc"], mod.get("planned", []))
        for f in self.frames.values():
            f.pack_forget()
        self.frames[key].pack(fill="both", expand=True)
        self._current = key
        for k, b in self.nav_btns.items():
            b.config(bg=SIDEBAR_ACTIVE if k == key else SIDEBAR_BG)


if __name__ == "__main__":
    App().mainloop()
