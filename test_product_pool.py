import unittest
from modules.weimob_admin_client import WeimobClient, WeimobAPIError
from modules.pool import goods_values

class PoolTests(unittest.TestCase):
    def test_missing_is_not_zero(self):
        self.assertEqual(goods_values({})[3], '未返回')
        self.assertEqual(goods_values({'goodsStock':{'goodsStockNum':0}})[3], '0')

    def test_exact_id_and_failed_store(self):
        client = WeimobClient('unit-test')
        def products(bos, store, *args):
            if store['vid'] == 2:
                raise WeimobAPIError('读取失败')
            return {'totalCount':2, 'pageList':[{'goodsId':9}, {'goodsId':7}]}
        client.products = products
        result = client.product_stores(1, [{'vid':1,'vidType':10}, {'vid':2,'vidType':10}], {'goodsId':7,'title':'同名'})
        self.assertEqual(result['matches'][0]['product']['goodsId'], 7)
        self.assertEqual(len(result['errors']), 1)

    def test_store_pagination(self):
        client = WeimobClient('unit-test')
        pages = iter([{'subListVos':[{'vid':1}], 'more':True,'scrollId':'a'},
                      {'subListVos':[{'vid':2}], 'more':False}])
        client.call = lambda *args: next(pages)
        self.assertEqual(len(client.stores(1)), 2)

if __name__ == '__main__':
    unittest.main()
