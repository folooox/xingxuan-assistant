"""Only the two read endpoints observed in the user's supplied HAR are allowed.

HAR response import works offline. Live replay requires the user's session;
credentials stay in memory and are never written into the catalog or logs.
"""
import base64
import copy
import json
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

HOST = 'master.weimob.com'
GOODS_PATH = '/api3/mall/mgr/promotion/activityGoodsList'
DETAIL_PATH = '/api3/mp/promotion/adapter/queryPromotionDetail'
ALLOWED = {GOODS_PATH, DETAIL_PATH}


class PromotionError(RuntimeError):
    pass


def validate_goods_query(body):
    query = body.get('queryParameter') or {}
    if set(query) - {'activityType', 'activityId', 'saleChannelType', 'filterType'} or query.get('saleChannelType') is not None:
        raise PromotionError('捕获请求含额外筛选，不能视为全量。请清除商品筛选后重新采集。')
    if query.get('activityType') != 3 or query.get('filterType') != 6 or not query.get('activityId'):
        raise PromotionError('尚未验证此类活动查询参数，请使用限时折扣商品设置页的完整列表请求。')


def response_json(entry):
    content = entry.get('response', {}).get('content', {})
    raw = content.get('text', '')
    if content.get('encoding') == 'base64':
        raw = base64.b64decode(raw).decode('utf-8')
    return json.loads(raw)


def load_har(path, bos_id=None):
    payload = json.loads(Path(path).read_text(encoding='utf-8-sig'))
    requests, goods, detail, pages = {}, {}, None, set()
    total, activity_id, merchant, capture_time = None, None, None, ''
    for entry in payload.get('log', {}).get('entries', []):
        request = entry.get('request', {})
        url = urlsplit(request.get('url', ''))
        if url.scheme != 'https' or url.hostname != HOST or url.path not in ALLOWED or request.get('method') != 'POST':
            continue
        body = json.loads(request.get('postData', {}).get('text', '{}'))
        bos = str((body.get('basicInfo') or {}).get('bosId', ''))
        if bos_id is not None and bos != str(bos_id):
            continue
        if url.path == GOODS_PATH:
            validate_goods_query(body)
        current_activity = str((body.get('queryParameter') or body.get('activityInfo') or {}).get('activityId', ''))
        if activity_id and activity_id != current_activity:
            raise PromotionError('HAR包含多个活动，请分别采集，避免混合不同活动')
        activity_id, merchant = current_activity, bos
        # Keep request in memory for optional live reads. No generic replay API.
        requests[url.path] = copy.deepcopy(request)
        response = response_json(entry)
        if str(response.get('errcode')) != '0':
            continue
        data = response.get('data') or {}
        capture_time = entry.get('startedDateTime', capture_time)
        if url.path == DETAIL_PATH:
            detail = data
        else:
            total = int(data['totalCount'])
            pages.add(int(data.get('pageNum', body.get('pageNum', 1))))
            for row in data.get('pageList') or []:
                goods[str(row['goodsId'])] = row
    if GOODS_PATH not in requests:
        raise PromotionError('未找到当前商户的活动商品响应。请在商品设置页采集，并勾选保留响应内容。')
    if not goods:
        raise PromotionError('HAR没有成功返回活动商品数据')
    return {'requests': requests, 'snapshot': {
        'bos_id': merchant, 'activity_id': activity_id, 'goods': list(goods.values()),
        'detail': detail, 'total': total, 'pages': sorted(pages),
        'complete': len(goods) == total, 'captured_at': capture_time,
        'source': 'HAR离线响应：' + Path(path).name,
    }}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PromotionError('登录失效或接口重定向，请重新登录后导入新HAR')


class PromotionClient:
    def __init__(self, requests, timeout=30):
        self.requests = requests
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect())

    def call(self, path, body=None):
        if path not in ALLOWED or path not in self.requests:
            raise PromotionError('只允许已捕获的活动详情和商品列表查询')
        template = self.requests[path]
        url = urlsplit(template['url'])
        if url.scheme != 'https' or url.hostname != HOST or url.path != path or url.port not in (None, 443):
            raise PromotionError('查询地址不在微盟只读白名单内')
        headers = {}
        for header in template.get('headers', []):
            name = header['name'].lower()
            if name in ('content-type', 'accept', 'accept-language', 'user-agent', 'origin', 'referer', 'apiclient', 'weimob-bosid', 'cookie', 'authorization'):
                headers[name] = header['value']
        headers['accept-encoding'] = 'identity'
        req = urllib.request.Request(template['url'], data=json.dumps(body if body is not None else json.loads(template['postData']['text']), ensure_ascii=False).encode('utf-8'), headers=headers, method='POST')
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                payload = json.load(response)
        except PromotionError:
            raise
        except urllib.error.HTTPError as exc:
            raise PromotionError('活动查询HTTP %s，登录可能已过期或缺少权限；没有执行修改。' % exc.code) from None
        except (ValueError, urllib.error.URLError, TimeoutError):
            raise PromotionError('未收到有效活动响应，请检查网络或重新登录后采集') from None
        if str(payload.get('errcode')) != '0':
            # Do not echo arbitrary server content that could contain credentials.
            raise PromotionError('微盟未授权本次活动查询（未返回成功状态）。请使用本机登录会话重新采集。')
        return payload.get('data') or {}

    def sync(self, progress=None):
        body = json.loads(self.requests[GOODS_PATH]['postData']['text'])
        validate_goods_query(body)
        activity = str(body['queryParameter']['activityId'])
        detail = self.call(DETAIL_PATH) if DETAIL_PATH in self.requests else None
        records, seen, expected, page = [], set(), None, 1
        size = int(body['pageSize'])
        if size < 1 or size > 100:
            raise PromotionError('捕获分页大小异常，未发送请求')
        while True:
            body['pageNum'] = page
            data = self.call(GOODS_PATH, body)
            total = int(data['totalCount'])
            if expected is None:
                expected = total
            if total != expected:
                raise PromotionError('读取期间活动商品数量变化，请重试；未覆盖上次快照')
            rows = data.get('pageList') or []
            ids = {str(r['goodsId']) for r in rows}
            if rows and ids.intersection(seen):
                raise PromotionError('活动分页有重复，无法确认完整性，请重试')
            if not rows and len(records) < total:
                raise PromotionError('活动分页提前结束，未覆盖上次快照')
            records.extend(rows)
            seen.update(ids)
            if progress:
                progress('活动商品 %s / %s · 第 %s 页' % (len(records), total, page))
            if len(records) >= total:
                if len(records) != total:
                    raise PromotionError('活动商品总数不一致')
                break
            page += 1
        return {'bos_id': str(body['basicInfo']['bosId']), 'activity_id': activity,
            'goods': records, 'detail': detail, 'total': expected,
            'pages': list(range(1, page + 1)), 'complete': True,
            'captured_at': datetime.now().isoformat(timespec='seconds'), 'source': '微盟后台只读接口全分页'}
