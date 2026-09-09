"""Activity snapshots with explicit SKU cost provenance and store scope."""
from datetime import datetime
from modules.pricing_core import price_check, text, product_key, expiry_state, money
from modules.product_status import status_values


def activity_info(snapshot):
    form = (((snapshot.get('detail') or {}).get('activityData') or {}).get('tangramFormData') or {})
    place = form.get('useOfPlace') or {}
    scopes = (place.get('data') or {}).get('addScope') or []
    return {'name': form.get('activityName', '未读取活动名称'),
        'time': form.get('activityTime') or {}, 'scope_type': text(place.get('type')),
        'stores': {text(s.get('bizId')): s.get('name', '') for s in scopes if str(s.get('vidType')) == '10'},
        'promotion_status': form.get('promotionStatus'),
        'stacking': form.get('orderPreferential') or []}


def activity_state(snapshot, now=None):
    info = activity_info(snapshot)
    now = now or datetime.now()
    timing = info['time']
    if str(timing.get('type')) != '1':
        return '活动时间规则待核对'
    try:
        start = datetime.fromisoformat(timing['start'])
        end = datetime.fromisoformat(timing['end'])
    except (ValueError, TypeError, KeyError):
        return '活动时间未读取'
    if now < start:
        return '未开始'
    if now > end:
        return '已结束'
    if info['promotion_status'] != 5:
        return '活动状态待核对'
    return '时间内（状态来自快照）'


def store_scope(snapshot, store):
    info = activity_info(snapshot)
    if info['scope_type'] != '203':
        return '适用范围待核对'
    return '适用' if text(store.get('vid')) in info['stores'] else '不适用此活动'


def base_result(snapshot, goods):
    info = activity_info(snapshot)
    return {'活动名称': info['name'], '活动ID': snapshot.get('activity_id'),
        '商品ID': text(goods.get('goodsId')), '商品名称': goods.get('title', ''),
        '商品编码': goods.get('outerGoodsCode', ''),
        '活动起始': info['time'].get('start'), '活动截止': info['time'].get('end'),
        '活动状态': activity_state(snapshot),
        '叠加优惠': '允许满减满折、优惠券（未扣减计算）' if set(map(str, info['stacking'])) == {'27', '30'} else ('有叠加优惠，需核对' if info['stacking'] else '未读取或未配置，需核对'),
        '活动快照时间': snapshot.get('captured_at'), '来源': snapshot.get('source'),
        '采集完整性': '全量' if snapshot.get('complete') else '部分数据，不代表全量',
        '已读取商品数': len(snapshot.get('goods', [])), '活动商品总数': snapshot.get('total')}


def sku_results(snapshot, markup='1.15'):
    results = []
    for goods in snapshot.get('goods', []):
        for sku in goods.get('skuDTOList') or [{}]:
            result = base_result(snapshot, goods)
            cost, sale = sku.get('costPrice'), sku.get('activityPrice')
            check = price_check(cost, cost, sale, sale, markup)
            if sku.get('isSelected') is not True or sku.get('isDisabled') is not False:
                check = {'state': '规格参与状态待核对'}
            if activity_state(snapshot) != '时间内（状态来自快照）':
                check = {'state': '活动有效性待核对'}
            result.update({'SKU编号': text(sku.get('skuId')), '规格编码': sku.get('outerSkuCode'),
                '规格': ' / '.join(text(s.get('name')) + ':' + text(s.get('specValueName')) for s in sku.get('skuSpecList') or []),
                '成本节点ID': text(sku.get('vid')), '成本来源': '活动响应内SKU成本，未替代供应商门店成本',
                '接口SKU成本': cost, '活动价': sale, '核对状态': check['state'],
                '目标售价': check.get('target'), '价差': check.get('difference'),
                '加价率': check.get('markup'), '毛利率': check.get('margin')})
            results.append(result)
    return results


def store_results(snapshot, catalog, markup='1.15', quotes=(), bindings=None):
    indexed = {}
    for store, row in catalog:
        indexed.setdefault(text(row.get('goodsId')), []).append((store, row))
    bindings = bindings or {}
    quote_index = {}
    for quote in quotes:
        for key in bindings.get(quote['uid'], []):
            quote_index.setdefault(key, []).append(quote)
    results = []
    for goods in snapshot.get('goods', []):
        matches = indexed.get(text(goods.get('goodsId'))) or [({}, {})]
        for store, row in matches:
            result = base_result(snapshot, goods)
            price = row.get('goodsPrice') or {}
            lo, hi = price.get('minCostPrice'), price.get('maxCostPrice')
            sale_lo, sale_hi = goods.get('minActivityPrice'), goods.get('maxActivityPrice')
            scope = store_scope(snapshot, store) if row else '门店商品未匹配'
            check = price_check(lo, hi, sale_lo, sale_hi, markup) if scope == '适用' else {'state': scope}
            skus = goods.get('skuDTOList') or []
            if scope == '适用' and skus and not any(s.get('isSelected') is True and s.get('isDisabled') is False for s in skus):
                check = {'state': '规格参与状态待核对'}
            if scope == '适用' and activity_state(snapshot) != '时间内（状态来自快照）':
                check = {'state': '活动有效性待核对'}
            active_quotes = [q for q in quote_index.get(product_key(store, row), []) if expiry_state(q) in ('有效', '30天内到期', '长期有效')]
            purchase_sale, purchase_delta = None, None
            purchase_state = '未匹配有效采购定价'
            if len(active_quotes) > 1:
                purchase_state = '多个定价冲突'
            elif len(active_quotes) == 1:
                purchase_sale = active_quotes[0].get('sale')
                if purchase_sale is None:
                    purchase_state = '未填采购核定售价'
                elif scope != '适用':
                    purchase_state = '活动适用性待核对'
                elif sale_lo is None or sale_hi is None or money(sale_lo) != money(sale_hi):
                    purchase_state = '活动多规格价格待核对'
                elif activity_state(snapshot) != '时间内（状态来自快照）':
                    purchase_state = '活动有效性待核对'
                else:
                    purchase_delta = str(money(sale_lo) - money(purchase_sale))
                    purchase_state = '售价一致' if money(sale_lo) == money(purchase_sale) else '售价不一致'
            result.update({'门店': store.get('vidName', ''), '门店ID': text(store.get('vid')),
                '门店上架品名': row.get('title', ''), '适用范围': scope,
                '最低成本': lo, '最高成本': hi, '成本来源': '门店商品接口成本区间',
                '活动最低价': sale_lo, '活动最高价': sale_hi, '核对状态': check['state'],
                '目标售价': check.get('target'), '价差': check.get('difference'),
                '加价率': check.get('markup'), '毛利率': check.get('margin'),
                '商城禁售控制': status_values(row, store)[0], '门店上下架': status_values(row, store)[1],
                '两级状态': status_values(row, store)[2], '采购核定售价': purchase_sale,
                '核定售价差额': purchase_delta, '采购售价核对': purchase_state})
            results.append(result)
    return results
