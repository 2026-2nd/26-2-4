"""Extend the dataset with 2017-2019 official CSVs supplied by the user (same download form as 2020-2026).

Reproduces, for the new years, exactly the stages that built the 2020-2026 crosswalk-v3 CSV:
 raw validation -> record_id/fingerprint -> unit features -> district/time controls
 -> complex match v1 -> crosswalk v2 rules -> crosswalk v3 rules -> static-assumption policy v3
Existing 2020-2026 decisions are never changed: combo keys already present in crosswalk_v3.csv reuse
their recorded decision; only keys first seen in 2017-2019 are evaluated with the same rule code.
Output columns are identical (same order) to the 2020-2026 v3 CSV.
"""
import collections,csv,datetime as dt,hashlib,json,pathlib,re,shutil,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import collect_seoul_sales as C
import build_unit_features as U
import build_market_features as MK
import build_internal_features as BI
import improve_complex_crosswalk as V2R
import improve_complex_crosswalk_v3 as V3R
from apply_internal_static_assumption import transform
csv.field_size_limit(sys.maxsize)
ROOT=BI.ROOT
import os
YEARS=[int(x) for x in os.environ.get('EXT_YEARS','2017,2018,2019').split(',')]
RAW=pathlib.Path(os.environ.get('EXT_RAW',ROOT/'data/raw/seoul_sales_2017_2019'));OUT=pathlib.Path(os.environ.get('EXT_OUT',ROOT/'data/processed/seoul_sales_2017_2019'));REPORT=pathlib.Path(os.environ.get('EXT_REPORT',ROOT/'reports/seoul_sales_2017_2019'))
V3CSV=ROOT/'data/processed/seoul_sales_2020_2026/seoul_apt_sales_2020_2026_internal_static_assumption_crosswalk_v3.csv'
OUTPUT=OUT/'seoul_apt_sales_2017_2019_internal_static_assumption_crosswalk_v3.csv'
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def year_of(data):
 m=re.search(r'계약일자 : (\d{4})-01-01 ~ (\d{4})-12-31',data.decode('cp949'))
 if not m or m[1]!=m[2]:raise ValueError('Unexpected search condition header (need one full calendar year)')
 return int(m[1])
def stage_raw(paths):
 RAW.mkdir(parents=True,exist_ok=True);metas=[];parsed={}
 for p in paths:
  data=pathlib.Path(p).read_bytes();y=year_of(data);fields,rows=C.parse(data,y)
  head=data.decode('cp949').split('"NO","시군구"')[0]
  for need in['실거래구분 : 아파트(매매)','주소구분 : 지번주소','시도 : 서울특별시','시군구 : 전체']:
   if need not in head:raise ValueError(f'{y}: search condition differs: {need}')
  dest=RAW/f'seoul_apt_sales_{y}.csv';dest.write_bytes(data)
  gus=collections.Counter(r['시군구'].split()[1] for r in rows)
  if set(gus)!=C.DISTRICTS:raise ValueError(f'{y}: districts {len(gus)}')
  meta=json.loads(pathlib.Path(p).with_suffix('.meta.json').read_text(encoding='utf-8')) if os.environ.get('EXT_VALIDATE') else None
  meta=meta and dict(meta,received_at=meta['retrieved_at'],original_upload=pathlib.Path(p).name) or dict(year=y,source='user_download_official_rt.molit.go.kr_condition_csv',original_upload=pathlib.Path(p).name,bytes=len(data),sha256=sha_bytes(data),rows=len(rows),received_at=dt.datetime.now(dt.timezone.utc).isoformat(),official_count_reconciled=False,official_count_note='조회 건수 미제공: 공식 화면 건수와의 대조는 사용자 확인 후 기록')
  dest.with_suffix('.meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
  metas.append(meta);parsed[y]=(fields,rows,meta)
 if sorted(parsed)!=YEARS:raise ValueError(f'years found {sorted(parsed)}')
 return parsed
def v3_decide(tx,sources,byroad,bygu,old_code):
 address=tx['시군구'].split();gu=address[1] if len(address)>1 else ''
 txroad=' '.join(address[:2])+' '+tx['도로명'] if tx['도로명'].strip() not in('','-') else ''
 nroad=byroad.get(BI.text_norm(txroad),0) if txroad else 0
 res=[(i,V3R.evaluate(tx,sources[i],nroad)) for i in bygu.get(gu,[])];res=[(i,e) for i,e in res if e is not None]
 ident=[(i,e) for i,e in res if e['method'] in V3R.IDENTITY_RULES];loc=[(i,e) for i,e in res if e['method'] in V3R.LOCATION_ONLY_RULES]
 if len(ident)==1 and not loc:i,e=ident[0];d='v3_rule_supported';scope='identity'
 elif not ident and len(loc)==1:i,e=loc[0];d='v3_location_only';scope='location_only'
 elif len(ident)+len(loc)>1:return None,dict(v3_decision='v3_unresolved_multiple_rule_candidates',v3_rule='|'.join(sorted({e['method'] for _,e in ident+loc})))
 else:return None,None
 code=sources[i]['k-아파트코드']
 if old_code and code!=old_code:d+='_changed_candidate'
 return i,dict(v3_kapt_code=code,v3_match_status=e['method'],v3_decision=d,v3_rule=e['method'],v3_scope=scope)
def main(paths):
 for d in(OUT,REPORT):d.mkdir(parents=True,exist_ok=True)
 parsed=stage_raw(paths)
 with V3CSV.open(encoding='utf-8-sig',newline='') as f:FIELDS=csv.DictReader(f).fieldnames
 with (ROOT/'reports/crosswalk_v3/crosswalk_v3.csv').open(encoding='utf-8-sig',newline='') as f:CW={r['complex_match_key']:r for r in csv.DictReader(f)}
 with (ROOT/'data/raw/seoul_complex.csv').open(encoding='cp949',newline='') as f:sources=list(csv.DictReader(f))
 index={r['k-아파트코드']:i for i,r in enumerate(sources)};indexes=BI.make_indexes(sources)
 byroad=collections.Counter(BI.text_norm(s['kapt도로명주소']) for s in sources if s['kapt도로명주소'].strip())
 bygu=collections.defaultdict(list)
 for i,s in enumerate(sources):bygu[s['주소(시군구)'].strip()].append(i)
 snapshot=json.loads((ROOT/'reports/internal_features/summary.json').read_text(encoding='utf-8'))['complex_snapshot_date']
 policy=json.loads((ROOT/'config/internal_static_assumption_policy_v3.json').read_text(encoding='utf-8'))
 ACC=set(V2R.ACCEPTED)|V3R.IDENTITY_RULES
 entries=json.loads(MK.CODEBOOK.read_text(encoding='utf-8'));mapping={str(r['signguNm']):str(r['signguCode']) for r in entries}
 cache={};newkeys=[];stats=collections.Counter();years=collections.defaultdict(collections.Counter);ids=set();n=0
 with OUTPUT.open('w',encoding='utf-8-sig',newline='') as g:
  w=csv.DictWriter(g,fieldnames=FIELDS);w.writeheader()
  for y in YEARS:
   fields,rows,meta=parsed[y];src_row=0
   for raw in rows:
    src_row+=1;years[y]['raw']+=1
    if raw['해제사유발생일'].strip() not in('','-'):years[y]['cancelled']+=1;continue
    row=dict(raw,source_file=f'seoul_apt_sales_{y}.csv',retrieved_at=meta['received_at'])
    rawfields=list(fields)+['source_file','retrieved_at']
    rid=hashlib.sha256(f"{meta['sha256']}|{src_row}".encode()).hexdigest()
    if rid in ids:raise ValueError('record_id collision')
    ids.add(rid)
    fp=hashlib.sha256(json.dumps({k:row[k] for k in rawfields if k not in['NO','source_file','retrieved_at']},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
    row.update(record_id=rid,record_fingerprint=fp,source_row=src_row,**U.derive(row));row.update(MK.derive(row,mapping))
    key=BI.match_key(row);kh=hashlib.sha256(key.encode()).hexdigest()
    if key not in cache:
     r1=BI.match(row,sources,indexes);c1=sources[r1['selected']]['k-아파트코드'] if r1['selected'] is not None else ''
     tx=dict(zip(['시군구','번지','단지명','도로명','건축년도'],key.split('|')))
     if kh in CW:
      cw=CW[kh];origin='existing_2020_2026_decision'
      dec=dict(v2_code=cw['new_kapt_code'],v2_status=cw['new_match_status'],v2_decision=cw['decision'],v2_evidence=cw['name_evidence'],v3_kapt_code=cw['v3_kapt_code'],v3_match_status=cw['v3_match_status'],v3_decision=cw['v3_decision'],v3_rule=cw['v3_rule'])
     else:
      origin='new_key_rules_applied'
      old=dict(selected_kapt_code=c1,match_status=r1['status'])
      r2=V2R.refine(tx,sources,indexes,old)
      dec=dict(v2_code=r2['code'],v2_status=r2['status'],v2_decision=r2['decision'],v2_evidence=r2['evidence'],v3_kapt_code=r2['code'],v3_match_status=r2['status'],v3_decision='v2_retained' if not r2['decision'].startswith('unresolved') else r2['decision'],v3_rule='')
      if r2['decision'].startswith('unresolved'):
       i3,d3=v3_decide(tx,sources,byroad,bygu,r2['code'])
       if d3:dec.update({k:v for k,v in d3.items() if k!='v3_scope'})
      newkeys.append(dict(complex_match_key=kh,transaction_complex_key=key,v1_code=c1,v1_status=r1['status'],**dec))
     cache[key]=(r1,c1,dec,origin)
    r1,c1,dec,origin=cache[key];stats[origin]+=1
    # v1 strict snapshot (identical to build_internal_features)
    strict=dict(row,**BI.attach(row,r1,sources,snapshot))
    vd=dec['v3_decision'];code=dec['v3_kapt_code'];i=index.get(code) if code else None
    if vd.startswith('v3_rule') or vd=='v3_location_only':
     res=dict(selected=i,status=dec['v3_match_status'],method=dec['v3_match_status'],candidate_count=1,issues=[] if vd.startswith('v3_rule') else['location_only_scope_not_identity'])
    elif dec['v2_decision']=='new_rule_supported':
     res=dict(selected=i,status=dec['v2_status'],method=dec['v2_status'],candidate_count=1,issues=[])
    else:res=r1
    base={c:strict[c] for c in strict}
    for f_ in BI.FEATURES:base[f_]=''
    new=dict(base,**BI.attach(row,res,sources,snapshot))
    if new['complex_match_status'] in ACC:
     new['internal_feature_issues']='|'.join(x for x in new['internal_feature_issues'].split('|') if x!='complex_identity_review_required')
    out=transform(new,sources[i] if i is not None else None,policy)
    out.update(crosswalk_version='3.0' if(vd.startswith('v3_rule') or vd=='v3_location_only') else '2.0',previous_complex_candidate_kapt_code=strict['complex_candidate_kapt_code'],previous_complex_match_status=strict['complex_match_status'],crosswalk_decision=dec['v2_decision'],crosswalk_evidence=dec['v2_evidence'],crosswalk_v3_decision=vd,crosswalk_v3_rule=dec['v3_rule'])
    st=out['complex_match_status'];sc='identity' if st in ACC else('location_only' if st in V3R.LOCATION_ONLY_RULES or(st=='unique_address_review' and out['complex_candidate_kapt_code']) else 'none')
    lon=lat='';pb='no_complex_link'
    if sc!='none':
     s=sources[index[out['complex_candidate_kapt_code']]]
     if s['좌표X'].strip() and s['좌표Y'].strip():lon,lat=s['좌표X'].strip(),s['좌표Y'].strip();pb={'identity':'kapt_snapshot_point_identity_link','location_only':'kapt_snapshot_point_location_only_link'}[sc]
     else:pb='kapt_point_missing'
    out.update(complex_link_scope=sc,complex_point_lon=lon,complex_point_lat=lat,complex_point_basis=pb)
    missing=set(FIELDS)-set(out);extra=set(out)-set(FIELDS)
    if missing or extra:raise ValueError(f'schema mismatch missing={missing} extra={extra}')
    w.writerow({k:out[k] for k in FIELDS});n+=1;years[y]['kept']+=1;years[y][sc]+=1
    years[y]['all4']+=all(out[f_]!='' for f_ in BI.FEATURES)
 with (REPORT/'crosswalk_new_keys_2017_2019.csv').open('w',encoding='utf-8-sig',newline='') as f:
  if newkeys:
   w=csv.DictWriter(f,fieldnames=list(newkeys[0]));w.writeheader();w.writerows(newkeys)
 nk=collections.Counter(k['v3_decision'] for k in newkeys)
 summary=dict(output=str(OUTPUT),output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),rows=n,unique_record_ids=len(ids),columns=len(FIELDS),by_year={str(k):dict(v) for k,v in years.items()},rows_by_decision_origin=dict(stats),combo_keys=len(cache),new_combo_keys=len(newkeys),new_key_v3_decisions=dict(nk),official_count_reconciled=False,raw_files=[dict(year=m['year'],sha256=m['sha256'],rows=m['rows'],upload=m['original_upload']) for _,_,m in parsed.values()],notes=['2020-2026 decisions reused for shared combo keys; new keys evaluated with the same v1/v2/v3 rule code.','Internal complex values are current snapshots assumed unchanged back to 2017 (assumed_time_invariant).','contract_time_index keeps the 2020-01=0 definition, so 2017-2019 rows are negative (-36..-1).'])
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=1))
if __name__=='__main__':main(sys.argv[1:])
