"""Read-only verification; credentials are read from local config, never printed."""
import json
import sys
from pathlib import Path
from modules.weimob_admin_client import WeimobClient

config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
client = WeimobClient(config.get('apikey') or config['token'])
merchant = config['current_merchant']
stores = client.stores(merchant['bos_id'])
mall = next(s for s in stores if str(s['vid']) == str(config['current_store']['vid']))
data = client.products(merchant['bos_id'], mall, size=5)
assert data.get('pageList'), '商城未返回商品'
product = data['pageList'][0]
target = next(s for s in stores if str(s['vid']) == str(product.get('createVid')))
result = client.product_stores(merchant['bos_id'], [target], product)
assert not result['errors'], result['errors']
assert result['matches'], '创建门店未匹配到相同商品 ID'
print(json.dumps({'merchant':merchant['name'], 'store':mall['vidName'],
 'organizations':len(stores), 'total':data['totalCount'],
 'product':product['title'], 'matched_stores':[r['store']['vidName'] for r in result['matches']],
 'raw_fields':list(product)}, ensure_ascii=False))
