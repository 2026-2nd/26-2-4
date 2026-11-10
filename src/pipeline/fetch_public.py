"""Fetch an explicitly supplied public URL, preserving headers and raw bytes."""
import sys,pathlib,urllib.request,urllib.parse,json,hashlib
url,out=sys.argv[1:3]
payload=urllib.parse.urlencode(json.loads(sys.argv[3])).encode() if len(sys.argv)>3 else None
req=urllib.request.Request(url,data=payload,headers={'User-Agent':'Mozilla/5.0','Referer':'https://rt.molit.go.kr/pt/xls/xls.do'})
with urllib.request.urlopen(req,timeout=90) as r:
 data=r.read(); meta={'url':url,'status':r.status,'headers':dict(r.headers),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}
pathlib.Path(out).write_bytes(data)
pathlib.Path(out+'.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(meta,ensure_ascii=True))
