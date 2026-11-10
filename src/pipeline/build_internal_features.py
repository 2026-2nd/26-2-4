"""Match complex snapshots without backdating them into historical features.

Four unqualified internal feature columns require verified effective histories;
current snapshot candidates are explicitly suffixed and never copied into them.
"""
import collections,csv,datetime as dt,decimal,hashlib,json,pathlib,re,unicodedata
ROOT=pathlib.Path(__file__).resolve().parents[2]
BASE=ROOT/'data/processed/seoul_sales_2020_2026'
SOURCE=BASE/'seoul_apt_sales_2020_2026_unit_market_features.csv'
OUTPUT=BASE/'seoul_apt_sales_2020_2026_unit_market_internal_features.csv'
COMPLEX_SOURCE=ROOT/'data/raw/seoul_complex.csv'
REPORT=ROOT/'reports/internal_features'
FEATURES=['household_count','parking_per_household','heating_type','corridor_type']
ADDED=['complex_match_key','complex_candidate_kapt_code','complex_match_status','complex_match_method','complex_match_candidate_count','complex_match_issues']+FEATURES+[f'{f}_snapshot' for f in FEATURES]+['complex_snapshot_date','complex_source_modified_at','complex_approval_date_snapshot','complex_source_file','complex_history_status','internal_feature_status','internal_feature_issues']
HEAT={'개별난방':'individual','지역난방':'district','중앙난방':'central','기타':'other'}
CORRIDOR={'계단식':'staircase','복도식':'corridor','혼합식':'mixed','기타':'other'}
def text_norm(value):return re.sub(r'\s+','',unicodedata.normalize('NFKC',str(value))).replace('서울시','서울특별시').casefold()
def name_norm(value):
 s=text_norm(value)
 s=re.sub(r'[^\w가-힣]','',s)
 return re.sub(r'아파트$','',s)
def nonneg_number(value,positive=False):
 try:
  d=decimal.Decimal(str(value).strip().replace(',',''))
  if not d.is_finite() or d<0 or (positive and d<=0):return None
  return d
 except decimal.InvalidOperation:return None
def approval_date(row):
 try:return dt.date.fromisoformat(row.get('k-사용검사일-사용승인일','')[:10])
 except ValueError:return None
def make_indexes(rows):
 byroad=collections.defaultdict(list);byname=collections.defaultdict(list)
 for i,r in enumerate(rows):
  if r['kapt도로명주소'].strip():byroad[text_norm(r['kapt도로명주소'])].append(i)
  if r['k-아파트명'].strip():byname[(r['주소(시군구)'].strip(),r['주소(읍면동)'].strip(),name_norm(r['k-아파트명']))].append(i)
 return byroad,byname
def match_key(row):
 return '|'.join(row.get(k,'').strip() for k in ['시군구','번지','단지명','도로명','건축년도'])
def match(row,rows,indexes):
 address=row['시군구'].split();gu=address[1] if len(address)>1 else '';dong=' '.join(address[2:])
 road=' '.join(address[:2])+' '+row['도로명'] if row['도로명'].strip() not in ('','-') else ''
 byroad,byname=indexes
 cands=[i for i in byroad.get(text_norm(road),[]) if rows[i]['주소(시군구)'].strip()==gu] if road else []
 method='road';selected=None;status='unmatched';issues=[]
 same=[i for i in cands if name_norm(rows[i]['k-아파트명'])==name_norm(row['단지명'])]
 if len(same)==1:selected=same[0];status='address_name_supported'
 elif len(cands)==1:selected=cands[0];status='unique_address_review'
 elif cands:status='ambiguous'
 else:
  method='district_dong_name'
  cands=byname.get((gu,dong,name_norm(row['단지명'])),[])
  if len(cands)==1:selected=cands[0];status='name_location_review'
  elif cands:status='ambiguous'
 if selected is not None:
  a=approval_date(rows[selected]);year=row.get('건축년도','').strip()
  if not a:issues.append('approval_date_missing')
  elif year.isdigit() and a.year!=int(year):
   issues.append('approval_build_year_conflict')
   status='year_conflict_review'
  if not row.get('단지명','').strip():issues.append('transaction_name_missing')
 return dict(selected=selected,status=status,method=method if cands else 'none',candidate_count=len(cands),issues=issues,candidate_codes='|'.join(rows[i]['k-아파트코드'] for i in cands))
def snapshot_values(r):
 issues=[];house=nonneg_number(r['k-전체세대수'],positive=True);parking=nonneg_number(r['주차대수'])
 if house is None or house!=house.to_integral_value():house=None;issues.append('households_missing_or_nonpositive')
 if parking is None or parking!=parking.to_integral_value():parking=None;issues.append('parking_missing_or_invalid')
 if parking==0:issues.append('zero_parking_needs_source_confirmation')
 # A reported zero is not converted into an assumed genuine lack of parking.
 ratio=parking/house if house is not None and parking is not None and parking>0 else None
 heat=HEAT.get(r['k-난방방식'].strip(),'');corridor=CORRIDOR.get(r['k-복도유형'].strip(),'')
 if not heat:issues.append('heating_missing_or_unmapped')
 if not corridor:issues.append('corridor_missing_or_unmapped')
 return dict(household_count_snapshot=str(house) if house is not None else '',parking_per_household_snapshot=str(ratio.quantize(decimal.Decimal('0.000001'))) if ratio is not None else '',heating_type_snapshot=heat,corridor_type_snapshot=corridor),issues
def attach(row,result,complex_rows,snapshot_date):
 extra={k:'' for k in ADDED}
 extra.update(complex_match_key=hashlib.sha256(match_key(row).encode()).hexdigest(),complex_match_status=result['status'],complex_match_method=result['method'],complex_match_candidate_count=result['candidate_count'],complex_match_issues='|'.join(result['issues']),complex_history_status='not_available',internal_feature_status='unavailable_history',internal_feature_issues='no_verified_attribute_history')
 selected=result['selected']
 if selected is None:
  extra.update(internal_feature_status='unavailable_match',internal_feature_issues='no_unique_complex_candidate|no_verified_attribute_history')
  return extra
 r=complex_rows[selected];a=approval_date(r)
 extra.update(complex_candidate_kapt_code=r['k-아파트코드'],complex_snapshot_date=snapshot_date,complex_source_modified_at=r['k-수정일자'],complex_approval_date_snapshot=a.isoformat() if a else '',complex_source_file='seoul_complex.csv')
 issues=['no_verified_attribute_history']
 if result['status'] not in ('address_name_supported',):issues.append('complex_identity_review_required')
 try:contract=dt.date.fromisoformat(row['contract_date'])
 except ValueError:contract=None;issues.append('contract_date_invalid')
 if a and contract and contract<a:
  # Could be legitimate pre-completion sales or a wrong match; do not decide here.
  extra['internal_feature_status']='unavailable_preapproval'
  issues.append('contract_before_candidate_approval')
 else:
  values,data_issues=snapshot_values(r);extra.update(values);issues.extend(data_issues)
 extra['internal_feature_issues']='|'.join(issues)
 return extra
def main():
 REPORT.mkdir(parents=True,exist_ok=True)
 market=json.loads((ROOT/'reports/market_features/summary.json').read_text(encoding='utf-8'))
 if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=market['output_sha256']:raise ValueError('Source hash changed')
 with COMPLEX_SOURCE.open(encoding='cp949',newline='') as f:complex_rows=list(csv.DictReader(f))
 codes=[r['k-아파트코드'] for r in complex_rows]
 if len(set(codes))!=len(codes) or any(not c for c in codes):raise ValueError('Non-unique or missing source code')
 downloads=json.loads((ROOT/'reports/complex_download_log.json').read_text(encoding='utf-8'))
 origin=next(r for r in downloads if r['name']=='seoul_complex.csv')
 snapshot_date=dt.datetime.fromisoformat(origin['retrieved_at']).astimezone(dt.timezone(dt.timedelta(hours=9))).date().isoformat()
 indexes=make_indexes(complex_rows);cache={};audit={};statuses=collections.Counter();missing=collections.Counter();snap_n=collections.Counter();reasons=collections.Counter();years=collections.defaultdict(collections.Counter);ids=set();n=0
 with SOURCE.open(encoding='utf-8-sig',newline='') as f,OUTPUT.open('w',encoding='utf-8-sig',newline='') as g:
  reader=csv.DictReader(f)
  if set(reader.fieldnames)&set(ADDED):raise ValueError('Duplicate field names')
  writer=csv.DictWriter(g,fieldnames=reader.fieldnames+ADDED);writer.writeheader()
  for row in reader:
   key=match_key(row)
   if key not in cache:
    result=match(row,complex_rows,indexes);cache[key]=result
    audit[key]=dict(transaction_complex_key=key,transaction_name=row['단지명'],transaction_address=row['시군구']+' '+row['번지'],transaction_road=row['도로명'],transaction_build_year=row['건축년도'],match_status=result['status'],match_method=result['method'],candidate_count=result['candidate_count'],candidate_codes=result['candidate_codes'],selected_kapt_code=complex_rows[result['selected']]['k-아파트코드'] if result['selected'] is not None else '',selected_name=complex_rows[result['selected']]['k-아파트명'] if result['selected'] is not None else '',match_issues='|'.join(result['issues']),transaction_rows=0)
   result=cache[key];extra=attach(row,result,complex_rows,snapshot_date)
   writer.writerow(dict(row,**extra));audit[key]['transaction_rows']+=1;n+=1;ids.add(row['record_id'])
   statuses[result['status']]+=1
   for feature in FEATURES:
    missing[feature]+=extra[feature]==''
    snap_n[feature]+=extra[feature+'_snapshot']!=''
   for issue in extra['internal_feature_issues'].split('|'):reasons[issue]+=1
   y=years[row['contract_date'][:4]];y['rows']+=1;y['candidate_rows']+=bool(extra['complex_candidate_kapt_code']);y['address_name_supported']+=result['status']=='address_name_supported';y['household_snapshot_rows']+=extra['household_count_snapshot']!=''
 if n!=market['output_rows'] or len(ids)!=n:raise ValueError('Row preservation failure')
 with (REPORT/'complex_match_audit.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(next(iter(audit.values()))));w.writeheader();w.writerows(audit.values())
 with (REPORT/'year_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['year','rows','candidate_rows','address_name_supported','household_snapshot_rows'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for year,counts in sorted(years.items()):w.writerow(dict(year=year,**counts))
 source_issues=collections.Counter()
 for r in complex_rows:
  _,issues=snapshot_values(r);source_issues.update(issues)
 summary=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=market['output_sha256'],output=str(OUTPUT.relative_to(ROOT)),output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),output_rows=n,unique_record_ids=len(ids),complex_source=str(COMPLEX_SOURCE.relative_to(ROOT)),complex_source_sha256=hashlib.sha256(COMPLEX_SOURCE.read_bytes()).hexdigest(),complex_source_rows=len(complex_rows),complex_source_url='https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do',complex_snapshot_date=snapshot_date,transaction_complex_keys=len(cache),match_status_transaction_rows=dict(statuses),match_status_complex_keys=dict(collections.Counter(r['status'] for r in cache.values())),candidate_transaction_rows=sum(a['transaction_rows'] for a in audit.values() if a['selected_kapt_code']),feature_names=FEATURES,missing_counts=dict(missing),strict_historical_values_generated=0,snapshot_value_counts=dict(snap_n),history_status='No verified field-specific histories available; unqualified historical feature columns remain blank.',reasons=dict(reasons),source_issues=dict(source_issues),model_run=False)
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
