import json, concurrent.futures
from collect_pilot import fetch,ROOT
params=dict(srvType='S',infId='OA-15818',serviceKind='1',pageNo='1',ssUserId='SAMPLE_VIEW',strWhere='',strOrderby='SN ASC',filterCol='',txtFilter='')
jobs=[('seoul_complex.csv','https://datafile.seoul.go.kr/bigfile/iot/sheet/csv/download.do',params),('seoul_complex_preview.json','https://data.seoul.go.kr/dataList/dataView.do?onepagerow=1000',params)]
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(fetch,jobs))
(ROOT/'reports/complex_download_log.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([dict(name=x['name'],bytes=x.get('bytes'),error=x.get('error')) for x in results]))
