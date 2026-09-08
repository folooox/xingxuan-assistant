# -*- coding: utf-8 -*-
"""通用读写：所有模块共用，不要在业务模块里重复写读文件逻辑"""
import os
import pandas as pd


def smart_read(file_path):
    """自动识别 csv/excel，csv 先试 utf-8 再退 gbk"""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        try:
            return pd.read_csv(file_path, encoding="utf-8")
        except Exception:
            return pd.read_csv(file_path, encoding="gbk")
    return pd.read_excel(file_path)
