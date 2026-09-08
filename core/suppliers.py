# -*- coding: utf-8 -*-
"""供应商编码前缀识别：映射表在 config/suppliers.json，改配置不改代码
匹配规则：取商品编码开头的字母段，按最长前缀优先匹配
"""
import re

from core.config import load_json

DEFAULT_MAP = {"YX": "燕翔", "RD": "睿丁"}


def load_map():
    m = load_json("suppliers.json", DEFAULT_MAP)
    return {str(k).upper(): v for k, v in m.items()}


def code_prefix(code):
    """'RD\\t' → 'RD'；空/纯数字 → ''"""
    s = str(code or '').strip().replace('\t', '').upper()
    m = re.match(r'^([A-Z]+)', s)
    return m.group(1) if m else ''


def match_supplier(code, sup_map):
    """返回 (供应商名, 前缀)；识别不了返回 (None, 前缀)"""
    p = code_prefix(code)
    if not p:
        return None, ''
    # 最长前缀优先：YXWD 先于 YX
    for k in sorted(sup_map.keys(), key=len, reverse=True):
        if p.startswith(k):
            return sup_map[k], p
    return None, p
