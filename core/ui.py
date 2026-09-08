# -*- coding: utf-8 -*-
"""界面缩放：按屏幕分辨率算一个整体缩放系数，
所有字号/间距都乘这个系数，不同分辨率下布局不变、整体等比缩放。
字号用负数=像素单位，保证和 px() 同步缩放。
"""

SCALE = 1.0
_BASE_W, _BASE_H = 1600, 900  # 参考分辨率


def init(root, base_w=1060, base_h=880):
    """在创建任何控件之前调用一次"""
    global SCALE
    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
    SCALE = min(sw / _BASE_W, sh / _BASE_H)
    SCALE = max(0.8, min(SCALE, 1.8))
    root.geometry(f"{int(base_w * SCALE)}x{int(base_h * SCALE)}")
    root.minsize(int(base_w * SCALE * 0.9), int(base_h * SCALE * 0.9))


def px(n):
    return int(round(n * SCALE))


def font(size=13, bold=False):
    """size 按像素给（参考分辨率下的视觉大小）"""
    return ("Microsoft YaHei UI", -max(10, px(size)), "bold" if bold else "normal")
