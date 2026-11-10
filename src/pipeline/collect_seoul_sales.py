"""Collect Seoul apartment sales via official public CSV, 2020-2026.

Preserves cancelled rows and raw bytes; validates scope before merging. No model runs.
"""
import concurrent.futures,csv,datetime as dt,hashlib,io,json,pathlib,time,urllib.parse,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw/seoul_sales_2020_2026'
OUT=ROOT/'data/processed/seoul_sales_2020_2026'
REPORT=ROOT/'reports/seoul_sales_2020_2026'
CUTOFF=dt.date(2026,11,2)
ENDPOINT='https://rt.molit.go.kr/pt/xls/ptXlsCSVDown.do'
DISTRICTS=set('종로구 중구 용산구 성동구 광진구 동대문구 중랑구 성북구 강북구 도봉구 노원구 은평구 서대문구 마포구 양천구 강서구 구로구 금천구 영등포구 동작구 관악구 서초구 강남구 송파구 강동구'.split())
def parse(data,year):
 text=data.decode('cp949')
 lines=text.splitlines(keepends=True)
 start=next((i for i,l in enumerate(lines) if l.startswith('"NO","시군구"')),None)
 if start is None:raise ValueError('Response is not the expected transaction CSV')
 reader=csv.DictReader(io.StringIO(''.join(lines[start:])))
 fields=reader.fieldnames;rows=list(reader)
 if not rows:raise ValueError('Unexpected empty year')
 end=min(dt.date(year,12,31),CUTOFF)
 for r in rows:
  address=r['시군구'].split()
  if len(address)<3 or address[0]!='서울특별시' or address[1] not in DISTRICTS:raise ValueError('Out-of-scope address')
  d=dt.date(int(r['계약년월'][:4]),int(r['계약년월'][4:]),int(r['계약일']))
  if not dt.date(year,1,1)<=d<=end:raise ValueError('Out-of-scope contract date')
  if None in r or any(v is None for v in r.values()):raise ValueError('Malformed CSV row')
 return fields,rows
def collect(year):
 end=min(dt.date(year,12,31),CUTOFF)
 path=RAW/f'seoul_apt_sales_{year}.csv';meta_path=path.with_suffix('.meta.json')
 if path.exists() and meta_path.exists():
  data=path.read_bytes();fields,rows=parse(data,year)
  meta=json.loads(meta_path.read_text(encoding='utf-8'))
  if hashlib.sha256(data).hexdigest()!=meta['sha256']:raise ValueError('Cached source hash mismatch')
  return meta,fields,rows
 params=dict(srhThingNo='A',srhDelngSecd='1',srhAddrGbn='1',srhLfstsSecd='1',srhFromDt=f'{year}-01-01',srhToDt=end.isoformat(),srhSidoCd='11',srhSggCd='',srhEmdCd='',srhHsmpCd='',srhArea='',srhNewRonSecd='',sidoNm='서울특별시',sggNm='전체')
 for attempt in range(3):
  try:
   req=urllib.request.Request(ENDPOINT,data=urllib.parse.urlencode(params).encode(),headers={'User-Agent':'Mozilla/5.0','Referer':'https://rt.molit.go.kr/pt/xls/xls.do'})
   with urllib.request.urlopen(req,timeout=120) as r:
    data=r.read();status=r.status;ctype=r.headers.get('Content-Type')
   fields,rows=parse(data,year)
   meta=dict(year=year,endpoint=ENDPOINT,params=params,status=status,content_type=ctype,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),retrieved_at=dt.datetime.now(dt.timezone.utc).isoformat(),rows=len(rows))
   path.write_bytes(data);meta_path.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
   print(json.dumps(dict(year=year,rows=len(rows),bytes=len(data))),flush=True)
   return meta,fields,rows
  except Exception:
   if attempt==2:raise
   time.sleep(2*(attempt+1))
def main():
 for d in [RAW,OUT,REPORT]:d.mkdir(parents=True,exist_ok=True)
 results=[];failures=[]
 with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
  jobs={pool.submit(collect,y):y for y in range(2020,2027)}
  for f in concurrent.futures.as_completed(jobs):
   try:results.append(f.result())
   except Exception as e:failures.append(dict(year=jobs[f],error=str(e)))
 if failures:
  (REPORT/'failures.json').write_text(json.dumps(failures,indent=2),encoding='utf-8')
  raise RuntimeError('Some years failed; successful raw files are saved. See failures.json')
 results.sort(key=lambda x:x[0]['year'])
 allfields=list(dict.fromkeys(k for _,fields,_ in results for k in fields))
 counts=[];gu_counts=[];month_counts=[]
 merged=OUT/'seoul_apt_sales_2020_2026_all_status.csv'
 import collections
 with merged.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=allfields+['source_file','retrieved_at']);w.writeheader()
  for meta,fields,rows in results:
   year=meta['year'];gu=collections.Counter();months=collections.Counter();cancel=0;dates=[]
   for r in rows:
    gu[r['시군구'].split()[1]]+=1;months[r['계약년월']]+=1
    cancel+=r['해제사유발생일'].strip() not in ('','-')
    dates.append(f"{r['계약년월'][:4]}-{r['계약년월'][4:]}-{int(r['계약일']):02d}")
    w.writerow(dict(r,source_file=f'seoul_apt_sales_{year}.csv',retrieved_at=meta['retrieved_at']))
   counts.append(dict(year=year,raw_rows=len(rows),cancelled_rows=cancel,non_cancelled_rows=len(rows)-cancel,districts=len(gu),min_contract_date=min(dates),max_contract_date=max(dates),missing_districts='|'.join(sorted(DISTRICTS-set(gu)))))
   gu_counts.extend(dict(year=year,district=g,rows=gu[g]) for g in sorted(DISTRICTS))
   month_counts.extend(dict(contract_month=m,rows=n) for m,n in sorted(months.items()))
 for name,rows in [('year_summary',counts),('district_year_counts',gu_counts),('month_counts',month_counts)]:
  with (REPORT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 summary=dict(requested_start='2020-01-01',requested_end=CUTOFF.isoformat(),downloaded_years=len(results),raw_rows=sum(x['raw_rows'] for x in counts),cancelled_rows=sum(x['cancelled_rows'] for x in counts),non_cancelled_rows=sum(x['non_cancelled_rows'] for x in counts),years=counts,merged_file=str(merged.relative_to(ROOT)),merged_sha256=hashlib.sha256(merged.read_bytes()).hexdigest(),notes=['All disclosed rows retained including cancellations.','Contract dates, not receipt dates. Recent and historical records can be revised.','25 districts and calendar scope checked; source completeness needs independent reconciliation.','2026 is partial through requested cutoff; unreported contracts are not observable.'])
 (REPORT/'collection_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 (REPORT/'download_manifest.json').write_text(json.dumps([x[0] for x in results],ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=True,indent=2),flush=True)
if __name__=='__main__':main()
