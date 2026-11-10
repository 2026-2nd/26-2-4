"""Public downloads discovered from saved official HTML. No authentication bypass."""
import concurrent.futures, pathlib, urllib.request, urllib.parse,json,datetime
ROOT=pathlib.Path(__file__).resolve().parents[2]
JOBS=[
 ('file_detail.js','https://www.data.go.kr/js/biz/datset/script_fileDetail.js',None),
 ('std_download.js','https://www.data.go.kr/js/biz/mvc/std/std-download-manager.js',None),
 ('complex_download','https://www.k-apt.go.kr/web/board/goKaptBasicExcelDownload.do',None),
 ('vworld_main.html','https://www.vworld.kr/v4po_main.do',None),
]
for gu,name in [('11680','gangnam'),('11350','nowon')]:
 for year in [2020,2023]:
  JOBS.append((f'{name}_{year}.csv','https://rt.molit.go.kr/pt/xls/ptXlsCSVDown.do',dict(srhThingNo='A',srhDelngSecd='1',srhAddrGbn='1',srhLfstsSecd='1',srhFromDt=f'{year}-01-01',srhToDt=f'{year}-12-31',srhSidoCd='11',srhSggCd=gu,srhEmdCd='',srhHsmpCd='',srhArea='',srhNewRonSecd='',sidoNm='서울특별시',sggNm='강남구' if name=='gangnam' else '노원구')))
def fetch(job):
 name,url,params=job
 try:
  req=urllib.request.Request(url,data=urllib.parse.urlencode(params).encode() if params else None,headers={'User-Agent':'Mozilla/5.0','Referer':'https://rt.molit.go.kr/pt/xls/xls.do'})
  with urllib.request.urlopen(req,timeout=60) as r:
   data=r.read(); meta=dict(name=name,url=url,params=params,status=r.status,headers=dict(r.headers),bytes=len(data),retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
  (ROOT/'data/raw'/name).write_bytes(data)
 except Exception as e: meta=dict(name=name,url=url,error=str(e))
 return meta
if __name__=='__main__':
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool: results=list(pool.map(fetch,JOBS))
 (ROOT/'reports/pilot_download_log.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(results,ensure_ascii=True,indent=2))
