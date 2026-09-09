import copy
import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from modules.pricing_core import (parse_quotes, date_range, expiry_state, candidate_products,
    price_check, compare_quote, load_tables, money)
from modules.product_status import status_values, attach_pool_status
from modules.promotion_client import PromotionClient, PromotionError, GOODS_PATH, DETAIL_PATH, load_har
from modules.promotion_core import store_results, sku_results


def snapshot():
    return {'activity_id': '99', 'bos_id': '1', 'goods': [], 'total': 0, 'complete': True,
        'detail': {'activityData': {'tangramFormData': {'activityName': 'test',
            'activityTime': {'type': '1', 'start': '2020-01-01 00:00:00', 'end': '2099-12-31 23:59:59'},
            'promotionStatus': 5, 'orderPreferential': ['27', '30'],
            'useOfPlace': {'type': '203', 'data': {'addScope': [{'bizId': '2', 'vidType': 10, 'name': 'store'}]}}}}}}


class PricingTests(unittest.TestCase):
    def test_dates_and_inclusive_expiry(self):
        self.assertEqual(date_range('2025.8.12-2026.8.11'), ('2025-08-12', '2026-08-11'))
        self.assertEqual(expiry_state({'end': '2026-09-09'}, date(2026, 9, 9)), '30天内到期')
        self.assertEqual(expiry_state({'end': '2026-09-08'}, date(2026, 9, 9)), '已过期')
        self.assertEqual(expiry_state({}), '未填到期日期')
        with self.assertRaises(ValueError):
            date_range('2026.2.30')

    def test_quote_blank_zero_invalid_raw(self):
        rows = [['品名', '供应商', '成本', '有效期'], ['商品', '门店', '0', '长期'], ['坏', '门店', 'NaN', '2026.2.30'], ['', '', '', '']]
        q = parse_quotes(rows, {'name': 0, 'supplier': 1, 'cost': 2, 'end': 3}, 'input.xlsx', 'Sheet1')
        self.assertEqual(len(q), 2)
        self.assertEqual(q[0]['cost'], '0')
        self.assertEqual(q[0]['end'], 'long_term')
        self.assertTrue(q[1]['errors'])
        self.assertEqual(q[1]['raw'][2], 'NaN')
        with self.assertRaises(ValueError):
            parse_quotes(rows, {'name': 0, 'supplier': 1, 'cost': 2, 'sale': 2}, 'x', 's')

    def test_merge_only_explicit_cells(self):
        from openpyxl import Workbook
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'merged.xlsx'
            wb = Workbook()
            ws = wb.active
            ws.append(['品名', '供应商', '供货价'])
            ws.append(['商品', '门店', 10])
            ws.append([None, '门店', 20])
            ws.append([None, '门店', 30])
            ws.merge_cells('A2:A3')
            wb.save(path)
            rows = load_tables(path)['Sheet']
            self.assertEqual(rows[2][0], '商品')
            self.assertEqual(rows[3][0], '')
            self.assertEqual(rows.original_rows[2][0], '')

    def test_names_only_candidates_and_ids_not_float(self):
        records = [({'vid': '2', 'vidName': '供应商'}, {'goodsId': '9999999999999999999', 'title': '精装苹果礼盒', 'outerGoodsCode': '001'})]
        candidates = candidate_products({'name': '苹果', 'supplier': '供应商'}, records)
        self.assertEqual(candidates[0][3]['goodsId'], '9999999999999999999')
        self.assertIn('候选', candidates[0][1])
        self.assertNotIn('bindings', candidates[0][3])

    def test_status_precedence_unknown_not_allowed(self):
        store = {'vidType': 10}
        self.assertEqual(status_values({'isOnline': True, '_poolCanSell': False}, store)[2], '商城禁售优先')
        self.assertEqual(status_values({'isOnline': True}, store)[2], '待核对')
        self.assertEqual(status_values({'isOnline': False, '_poolCanSell': True}, store)[2], '门店已下架')
        self.assertEqual(status_values({'isOnline': True, '_poolCanSell': True}, store)[2], '两级状态允许')
        self.assertEqual(status_values({'isOnline': True, 'isCanSell': False}, {'vidType': 5})[1], '不适用（商城行）')
        joined = attach_pool_status([(store, {'goodsId': '01'})], [({}, {'goodsId': '1', 'isCanSell': True})])
        self.assertIsNone(joined[0][1]['_poolCanSell'])

    def test_exact_price_comparison_boundaries(self):
        self.assertEqual(price_check(100, 100, 99, 99)['state'], '活动价倒挂')
        self.assertEqual(price_check(100, 100, 100, 100)['state'], '未达加价目标')
        self.assertEqual(price_check(100, 100, 115, 115)['state'], '达到加价目标')
        self.assertEqual(price_check(10, 100, 20, 120)['state'], '多规格区间待核对')
        self.assertEqual(price_check(0, 0, 10, 10)['state'], '零成本待核实')
        self.assertEqual(price_check(None, None, 10, 10)['state'], '缺少成本或活动价')

    def test_expired_quote_not_applied(self):
        q = {'name': 'x', 'cost': '10', 'end': '2025-01-01'}
        result = compare_quote(q, {}, {'goodsPrice': {'minCostPrice': 10, 'maxCostPrice': 10}}, date(2026, 1, 1))
        self.assertEqual(result['成本核对'], '定价有效性待核对')
        self.assertIsNone(result['成本差额'])

    def test_activity_scope_and_sku_provenance(self):
        snap = snapshot()
        goods = {'goodsId': '7', 'minActivityPrice': 9, 'maxActivityPrice': 9,
            'skuDTOList': [{'skuId': '71', 'vid': '5', 'costPrice': 10, 'activityPrice': 9, 'isSelected': True, 'isDisabled': False}]}
        snap['goods'] = [goods]
        rows = [({'vid': '2', 'vidType': 10}, {'goodsId': '7', 'goodsPrice': {'minCostPrice': 10, 'maxCostPrice': 10}}),
                ({'vid': '3', 'vidType': 10}, {'goodsId': '7', 'goodsPrice': {'minCostPrice': 10, 'maxCostPrice': 10}})]
        result = store_results(snap, rows)
        self.assertEqual(result[0]['核对状态'], '活动价倒挂')
        self.assertEqual(result[1]['核对状态'], '不适用此活动')
        sku = sku_results(snap)[0]
        self.assertEqual(sku['成本节点ID'], '5')
        self.assertIn('未替代', sku['成本来源'])

    def test_negative_purchase_sale_delta(self):
        snap = snapshot()
        snap['goods'] = [{'goodsId': '7', 'minActivityPrice': 10, 'maxActivityPrice': 10}]
        records = [({'vid': '2'}, {'goodsId': '7', 'goodsPrice': {'minCostPrice': 8, 'maxCostPrice': 8}})]
        quotes = [{'uid': 'a', 'sale': '12', 'end': 'long_term'}]
        result = store_results(snap, records, quotes=quotes, bindings={'a': ['2:7']})[0]
        self.assertEqual(result['核定售价差额'], '-2')
        self.assertEqual(result['采购售价核对'], '售价不一致')

    def test_no_arbitrary_endpoint_replay(self):
        client = PromotionClient({})
        with self.assertRaises(PromotionError):
            client.call('/api/delete')

    def test_replay_complete_and_duplicates(self):
        template = {'postData': {'text': json.dumps({'basicInfo': {'bosId': 1}, 'pageSize': 2, 'queryParameter': {'activityId': '99', 'activityType': 3, 'filterType': 6}})}}
        client = PromotionClient({GOODS_PATH: template})
        pages = iter([{'totalCount': 3, 'pageList': [{'goodsId': 1}, {'goodsId': 2}]}, {'totalCount': 3, 'pageList': [{'goodsId': 3}]}])
        client.call = lambda *args: next(pages)
        self.assertTrue(client.sync()['complete'])
        pages = iter([{'totalCount': 3, 'pageList': [{'goodsId': 1}, {'goodsId': 2}]}, {'totalCount': 3, 'pageList': [{'goodsId': 2}]}])
        client.call = lambda *args: next(pages)
        with self.assertRaises(PromotionError):
            client.sync()

    def test_changed_total_rejected(self):
        template = {'postData': {'text': json.dumps({'basicInfo': {'bosId': 1}, 'pageSize': 1, 'queryParameter': {'activityId': '99', 'activityType': 3, 'filterType': 6}})}}
        client = PromotionClient({GOODS_PATH: template})
        pages = iter([{'totalCount': 2, 'pageList': [{'goodsId': 1}]}, {'totalCount': 3, 'pageList': [{'goodsId': 2}]}])
        client.call = lambda *args: next(pages)
        with self.assertRaises(PromotionError):
            client.sync()


if __name__ == '__main__':
    unittest.main()
