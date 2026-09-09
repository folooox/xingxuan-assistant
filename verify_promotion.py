"""One read-only replay of the exact activity request provided by the user."""
import sys
from modules.promotion_client import load_har, PromotionClient, GOODS_PATH, PromotionError

loaded = load_har(sys.argv[1])
snapshot = loaded['snapshot']
print('captured_goods', len(snapshot['goods']), 'total', snapshot['total'], 'complete', snapshot['complete'])
try:
    data = PromotionClient(loaded['requests']).call(GOODS_PATH)
    print('live_success', len(data.get('pageList', [])), 'total', data.get('totalCount'))
except PromotionError as exc:
    print('live_unavailable', str(exc))
