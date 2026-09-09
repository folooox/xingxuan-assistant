"""Shared filtering for displayed records and their exports."""
from decimal import Decimal, InvalidOperation
from modules.product_status import status_values

def cost_bound(text):
    if not text.strip(): return None
    try:
        value = Decimal(text.strip())
        if not value.is_finite() or value < 0: raise InvalidOperation
        return value
    except InvalidOperation:
        raise ValueError('成本筛选请输入不小于0的数字')

def matches(row, store, filters):
    keyword = filters.get('keyword','').casefold()
    field = str(row.get('outerGoodsCode') or row.get('goodsCode') or '') if filters.get('by_code') else str(row.get('title') or '')
    if keyword and keyword not in field.casefold(): return False
    if filters.get('store') and filters['store'].casefold() not in str(store.get('vidName','')).casefold(): return False
    state = filters.get('online','全部')
    pool, online, effective = status_values(row, store)
    if state != '全部' and state != online: return False
    if filters.get('pool_state', '全部') not in ('全部', pool): return False
    if filters.get('effective', '全部') not in ('全部', effective): return False
    price = row.get('goodsPrice') or {}
    lo, hi = price.get('minCostPrice'), price.get('maxCostPrice')
    cost_state = filters.get('cost_state','全部成本')
    if cost_state == '成本未返回' and (lo is not None or hi is not None): return False
    if cost_state == '零成本' and not (lo == hi == 0): return False
    if cost_state == '有正成本' and not any(v is not None and Decimal(str(v)) > 0 for v in (lo,hi)): return False
    low, high = filters.get('low'), filters.get('high')
    # Intersect the product's returned cost range; unknown bounds cannot prove a match.
    if low is not None and (hi is None or Decimal(str(hi)) < low): return False
    if high is not None and (lo is None or Decimal(str(lo)) > high): return False
    return True
