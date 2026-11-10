"""Save the official Seoul district list used by the MOLIT download form."""
import datetime as dt,hashlib,json,pathlib,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
def main():
 url='https://rt.molit.go.kr/data/sgg.do';params={'signguCode':'11'}
 req=urllib.request.Request(url,data=urllib.parse.urlencode(params).encode(),headers={'User-Agent':'Mozilla/5.0','Referer':'https://rt.molit.go.kr/pt/xls/xls.do'})
 with urllib.request.urlopen(req,timeout=45) as r:
  data=r.read();meta=dict(url=url,params=params,status=r.status,content_type=r.headers.get('Content-Type'),retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),sha256=hashlib.sha256(data).hexdigest())
 dest=ROOT/'data/raw/region_codes';dest.mkdir(parents=True,exist_ok=True)
 parsed=json.loads(data)
 if not isinstance(parsed,list) or len(parsed)!=25:raise ValueError('Expected 25 official Seoul districts')
 (dest/'molit_seoul_districts.json').write_bytes(data)
 (dest/'molit_seoul_districts.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(parsed,ensure_ascii=True))
if __name__=='__main__':main()
