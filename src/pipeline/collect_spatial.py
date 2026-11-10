import concurrent.futures,json
from collect_pilot import fetch,ROOT
JOBS=[('station_download_info.json','https://www.data.go.kr/tcs/dss/selectFileDataDownload.do',dict(publicDataDetailPk='uddi:bc51de47-d3ea-4aa1-8ac2-d70f2b5e701e',publicDataPk='15099316',atchFileId='',fileDetailSn='1',publicDataTyCode='PR0051'))]
for name,pk in [('schools','15021148')]:
 JOBS.append((name+'_columns.json',f'https://www.data.go.kr/download/columList.json?pk={pk}&ext=JSON',None))
 JOBS.append((name+'_data.json',f'https://www.data.go.kr/download/standard.json?publicDataPk={pk}&page=1&perPage=1000',None))
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(fetch,JOBS))
 (ROOT/'reports/spatial_download_log.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(results,ensure_ascii=True,indent=2))
