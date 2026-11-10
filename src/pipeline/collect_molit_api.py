"""Optional authenticated API collector. Reads user's own decoded key from environment.
Keeps every page, validates service result and advertised count, never logs the key.
"""
import argparse,os,json,pathlib,urllib.request,urllib.parse,xml.etree.ElementTree as ET
BASE='https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev'
def main():
 p=argparse.ArgumentParser();p.add_argument('--gu',required=True);p.add_argument('--month',required=True);p.add_argument('--out',default='data/raw/api');a=p.parse_args()
 if len(a.gu)!=5 or not a.gu.isdigit() or len(a.month)!=6 or not a.month.isdigit():raise ValueError('Expected 5-digit gu and YYYYMM')
 key=os.environ.get('MOLIT_SERVICE_KEY')
 if not key:raise SystemExit('Set MOLIT_SERVICE_KEY to your decoded key; no request sent.')
 dest=pathlib.Path(a.out);dest.mkdir(parents=True,exist_ok=True)
 rows=[];page=1
 while True:
  params=dict(serviceKey=key,LAWD_CD=a.gu,DEAL_YMD=a.month,numOfRows=1000,pageNo=page)
  req=urllib.request.Request(BASE+'?'+urllib.parse.urlencode(params))
  try:
   with urllib.request.urlopen(req,timeout=45) as response:data=response.read()
  except Exception:raise SystemExit('API transport failed; request URL suppressed to protect key.')
  root=ET.fromstring(data);code=root.findtext('.//resultCode')
  if code not in ('000','00','0'):raise SystemExit('API returned non-success result code: '+str(code))
  (dest/f'{a.gu}_{a.month}_{page}.xml').write_bytes(data)
  items=root.findall('.//item');rows.extend([{c.tag:c.text for c in item} for item in items]);total=int(root.findtext('.//totalCount','0'))
  if len(rows)>=total:break
  if not items:raise RuntimeError('Premature empty page')
  page+=1
 if len(rows)!=total:raise RuntimeError('Count mismatch')
 (dest/f'{a.gu}_{a.month}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(dict(gu=a.gu,month=a.month,pages=page,rows=len(rows))))
if __name__=='__main__':main()
