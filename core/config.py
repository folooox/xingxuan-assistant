# -*- coding: utf-8 -*-
"""配置加载：业务规则尽量放 config/ 目录，改配置不改代码
打包成 exe 后，config 目录放在 exe 同级即可生效
"""
import json
import os
import sys


def app_dir():
    """开发时=项目根目录；打包后=exe所在目录"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_json(name, default):
    """从 config/<name> 读 json，不存在或读坏了就用内置默认值"""
    path = os.path.join(app_dir(), "config", name)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return default


def save_json(name, data):
    """写回 config/<name>，返回文件路径"""
    d = os.path.join(app_dir(), "config")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return path
