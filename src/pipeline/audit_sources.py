"""Download public source pages; preserve evidence and errors without credentials."""
import concurrent.futures, datetime, hashlib, json, pathlib, re, urllib.request
ROOT = pathlib.Path(__file__).resolve().parents[2]
URLS = {
 'molit_sales':'https://www.data.go.kr/data/15126469/openapi.do',
 'molit_detail':'https://www.data.go.kr/data/15126468/openapi.do',
 'complex_csv':'https://www.data.go.kr/data/15073271/fileData.do',
 'kapt_api':'https://www.data.go.kr/data/15058453/openapi.do',
 'stations':'https://www.data.go.kr/data/15099316/fileData.do',
 'schools':'https://www.data.go.kr/data/15021148/standard.do',
 'parks':'https://www.data.go.kr/data/15012890/standard.do',
 'rone':'https://www.reb.or.kr/r-one/',
 'vworld':'https://www.vworld.kr/',
 'molit_csv':'https://rt.molit.go.kr/pt/xls/xls.do',
 'seoul_sales':'https://data.seoul.go.kr/dataList/OA-21275/S/1/datasetView.do',
}
def fetch(pair):
 name,url=pair
 entry=dict(name=name,url=url,retrieved_at=datetime.datetime.now(datetime.timezone.utc).isoformat())
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
  with urllib.request.urlopen(req,timeout=35) as r:
   data=r.read(); entry.update(status=r.status,final_url=r.url,content_type=r.headers.get('Content-Type'),bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
  (ROOT/'data/raw'/f'{name}.html').write_bytes(data)
  txt=data.decode('utf-8',errors='replace')
  txt=re.sub(r'<script\b[^>]*>.*?</script>|<style\b[^>]*>.*?</style>','',txt,flags=re.S|re.I)
  txt=re.sub('<[^>]+>',' ',txt)
  (ROOT/'data/raw'/f'{name}.txt').write_text(re.sub(r'[ \t]+',' ',txt),encoding='utf-8')
 except Exception as e: entry.update(error=str(e))
 return entry
if __name__=='__main__':
 (ROOT/'data/raw').mkdir(parents=True,exist_ok=True)
 with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: entries=list(pool.map(fetch,URLS.items()))
 (ROOT/'reports/access_log.json').write_text(json.dumps(entries,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(entries,ensure_ascii=False,indent=2))
