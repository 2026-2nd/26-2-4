"""Reconcile downloaded row counts with the official download form's count endpoint."""
import concurrent.futures,json,datetime as dt,urllib.parse,urllib.request
from collect_seoul_sales import ROOT,REPORT
def verify(meta):
 year=meta['year'];result=dict(year=year,downloaded_rows=meta['rows'])
 try:
  req=urllib.request.Request('https://rt.molit.go.kr/pt/xls/ptXlsDownDataCheck.do',data=urllib.parse.urlencode(meta['params']).encode(),headers={'User-Agent':'Mozilla/5.0','Referer':'https://rt.molit.go.kr/pt/xls/xls.do'})
  with urllib.request.urlopen(req,timeout=90) as r:data=r.read()
  (REPORT/f'official_count_{year}.json').write_bytes(data)
  body=json.loads(data);result.update(official_count=body.get('cnt'),response=body,retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat())
  result['count_match']=int(body['cnt'])==meta['rows'] if 'cnt' in body else None
 except Exception as e:result.update(error=str(e),count_match=None)
 return result
if __name__=='__main__':
 manifest=json.loads((REPORT/'download_manifest.json').read_text(encoding='utf-8'))
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(verify,manifest))
 (REPORT/'official_count_reconciliation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(results,ensure_ascii=True,indent=2))
