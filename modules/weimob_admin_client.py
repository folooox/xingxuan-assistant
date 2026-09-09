"""Desktop implementation of Weimob Admin Skills 1.0.1 gateway protocol."""
import json
import urllib.request
import urllib.error

API_ROOT = 'https://wos-skills.weimob.com/weimob/saas/admin'


class WeimobAPIError(RuntimeError):
    pass


class WeimobClient:
    def __init__(self, api_key, timeout=30):
        self.api_key = api_key.strip()
        self.timeout = timeout
        if not self.api_key:
            raise WeimobAPIError('请填写微盟 Admin Skills API Key')

    def call(self, path, body):
        req = urllib.request.Request(API_ROOT,
            data=json.dumps(body, ensure_ascii=False).encode('utf-8'),
            headers={'authorization': self.api_key, 'apipath': path,
                     'Content-Type': 'application/json', 'X-Client-Version': '1.0.1'}, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:
            raise WeimobAPIError('微盟返回 HTTP %s，请检查 Key 或稍后重试' % exc.code) from exc
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            raise WeimobAPIError('微盟连接失败，请检查网络后重试') from exc
        result = payload.get('responseVo', payload)
        if str(result.get('errcode')) != '0':
            message = str(result.get('errmsg') or '接口未返回成功状态').replace(self.api_key, '[已隐藏]')
            raise WeimobAPIError(message)
        return result.get('data')

    def merchants(self):
        return self.call('merchants', {}) or []

    def stores(self, bos_id):
        records, seen = [], set()
        body = {'bosId': str(bos_id)}
        while True:
            data = self.call('stores', body) or {}
            records.extend(data.get('subListVos') or [])
            if not data.get('more'):
                break
            cursor = data.get('scrollId')
            if not cursor or cursor in seen:
                raise WeimobAPIError('门店列表分页不完整，请重新加载')
            seen.add(cursor)
            body['scrollId'] = cursor
        return list({str(x['vid']): x for x in records}.values())

    def products(self, bos_id, store, page=1, size=50, search='', search_type=1):
        query = {'filterOption': {'isQueryManageClassify': True,
                 'isIgnoreBigDataCheck': False, 'queryVidBizType': True}}
        if search:
            query.update(search=search, searchType=search_type, searchOptionType=1)
        return self.call('goods', {'basicInfo': {'bosId': int(bos_id),
            'vid': int(store['vid']), 'vidType': int(store['vidType']), 'productId': 145},
            'solutionType': 2, 'pageNum': page, 'pageSize': min(size, 100),
            'queryParameter': query}) or {}

    def all_store_products(self, bos_id, stores, progress=None):
        records, errors = [], []
        for store in [s for s in stores if str(s.get('vidType')) == '10']:
            page, seen, collected = 1, set(), []
            try:
                while True:
                    if progress: progress('%s · 第 %s 页' % (store.get('vidName',''), page))
                    data = self.products(bos_id, store, page, 100)
                    rows = data.get('pageList') or []
                    ids = {str(r['goodsId']) for r in rows}
                    if rows and ids.issubset(seen):
                        raise WeimobAPIError('分页重复，请重试该门店')
                    collected.extend((store,r) for r in rows if str(r['goodsId']) not in seen)
                    seen.update(ids)
                    if page * 100 >= int(data.get('totalCount',0)): break
                    if not rows: raise WeimobAPIError('分页提前结束，请重试该门店')
                    page += 1
                records.extend(collected)
            except WeimobAPIError as exc:
                errors.append({'store':store,'error':str(exc)})
        return records, errors

    def product_stores(self, bos_id, stores, product, progress=None):
        matches, errors = [], []
        targets = [s for s in stores if str(s.get('vidType')) == '10']
        for index, store in enumerate(targets):
            if progress:
                progress('%s / %s · %s' % (index + 1, len(targets), store.get('vidName', '')))
            try:
                page, seen = 1, set()
                while True:
                    data = self.products(bos_id, store, page, 100, product.get('title') or '')
                    rows = data.get('pageList') or []
                    signature = tuple(str(r.get('goodsId')) for r in rows)
                    if signature in seen:
                        raise WeimobAPIError('商品分页重复，结果不完整')
                    seen.add(signature)
                    found = next((r for r in rows if str(r.get('goodsId')) == str(product['goodsId'])), None)
                    if found:
                        matches.append({'store': store, 'product': found})
                        break
                    if page * 100 >= int(data.get('totalCount', 0)):
                        break
                    if not rows:
                        raise WeimobAPIError('商品分页提前结束')
                    page += 1
            except WeimobAPIError as exc:
                errors.append({'store': store, 'error': str(exc)})
        return {'matches': matches, 'errors': errors, 'checked': len(targets)}
