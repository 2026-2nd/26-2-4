import concurrent.futures,json,urllib.parse
from collect_pilot import fetch,ROOT
jobs=[]
station=json.loads((ROOT/'data/raw/station_download_info.json').read_text(encoding='utf-8'))
if station.get('status') is not True:raise RuntimeError('Official station download metadata is not successful')
jobs.append(('stations.csv','https://www.data.go.kr/cmm/cmm/fileDownload.do?'+urllib.parse.urlencode(dict(atchFileId=station['atchFileId'],fileDetailSn=station['fileDetailSn'])),None))
for name,pk in [('schools','15021148')]:
 meta=json.loads((ROOT/'data/raw'/f'{name}_columns.json').read_text(encoding='utf-8'))
 for page in range(1,(meta['totalCount']+9999)//10000+1):
  params=dict(publicDataPk=pk,svcTableNm=meta['tableVO']['svcTableNm'],colNmList=meta['tableVO']['colNmList'],totalCount=meta['totalCount'],perPage=10000,page=page)
  jobs.append((f'{name}_page{page}.json','https://www.data.go.kr/download/standard.json?'+urllib.parse.urlencode(params,doseq=True),None))
jobs += [('common_functions.js','https://www.data.go.kr/js/biz/cmm/cmm/script_cmmFunction.js',None),('rone_guide.html','https://www.reb.or.kr/r-one/portal/openapi/openApiDevPage.do',None),('vworld_api.html','https://www.vworld.kr/v4po_openapi_s001.do',None)]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(fetch,jobs))
(ROOT/'reports/spatial_full_log.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps([dict(name=x['name'],bytes=x.get('bytes'),error=x.get('error')) for x in results]))
