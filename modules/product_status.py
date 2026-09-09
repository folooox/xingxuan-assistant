"""Two independent controls, joined by goods ID within the selected merchant."""


def boolean(value):
    if value is True or value == 1 or str(value).lower() == 'true':
        return True
    if value is False or value == 0 or str(value).lower() == 'false':
        return False
    return None


def status_values(row, store=None):
    store = store or {}
    mall = str(store.get('vidType')) == '5'
    pool = boolean(row.get('isCanSell')) if mall else boolean(row.get('_poolCanSell'))
    online = None if mall else boolean(row.get('isOnline'))
    pool_text = {True: '允许销售', False: '商城禁售', None: '未读取商城状态'}[pool]
    online_text = '不适用（商城行）' if mall else {True: '已上架', False: '已下架', None: '未返回'}[online]
    if pool is False:
        effective = '商城禁售优先'
    elif not mall and online is False:
        effective = '门店已下架'
    elif not mall and online is True and pool is True:
        effective = '两级状态允许'
    else:
        effective = '待核对'
    return pool_text, online_text, effective


def attach_pool_status(records, mall_records):
    lookup = {str(row['goodsId']): row for _, row in mall_records}
    result = []
    for store, row in records:
        copy = dict(row)
        source = lookup.get(str(row.get('goodsId')))
        copy['_poolCanSell'] = source.get('isCanSell') if source else None
        copy['_poolStatusSource'] = '商城 goods.isCanSell' if source else '商城结果未匹配，不推断'
        result.append((store, copy))
    return result
