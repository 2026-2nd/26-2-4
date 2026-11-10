"""Attach date-aligned unit attributes to every non-cancelled disclosed transaction.

No external data or model required. Preserve source fields and invalid rows; mark
missing values and review reasons instead of inventing approvals or attributes.
"""
import collections,csv,datetime as dt,decimal,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/processed/seoul_sales_2020_2026/seoul_apt_sales_2020_2026_all_status.csv'
OUT=ROOT/'data/processed/seoul_sales_2020_2026'
REPORT=ROOT/'reports/unit_features'
ADDED=['record_id','record_fingerprint','source_row','contract_date','exclusive_area_m2','transaction_floor','building_age_years','age_basis','unit_feature_status','unit_feature_issues']
def numeric(raw):
 s=str(raw).strip().replace(',','')
 if s in ('','-'):return None
 try:
  value=decimal.Decimal(s)
  return value if value.is_finite() else None
 except decimal.InvalidOperation:return None
def integer(raw):
 value=numeric(raw)
 return int(value) if value is not None and value==value.to_integral_value() else None
def derive(row):
 issues=[];warnings=[];date=None
 ym=str(row.get('계약년월','')).strip();day=integer(row.get('계약일',''))
 try:
  if not re.fullmatch(r'\d{6}',ym) or day is None:raise ValueError()
  date=dt.date(int(ym[:4]),int(ym[4:]),day)
 except ValueError:issues.append('contract_date_invalid')
 area=numeric(row.get('전용면적(㎡)',''))
 if area is None or area<=0:area=None;issues.append('exclusive_area_invalid_or_missing')
 floor=integer(row.get('층',''))
 if floor is None:issues.append('transaction_floor_invalid_or_missing')
 elif floor<=0:warnings.append('nonpositive_floor_review')
 year=integer(row.get('건축년도',''));age=None
 if year is None or year<=0:issues.append('build_year_invalid_or_missing')
 elif date:
  if year>date.year:issues.append('build_year_after_contract_year')
  else:
   age=date.year-year
   if year<1900:warnings.append('early_build_year_review')
 # Approximation uses only year; do not pretend the approval day is known.
 return dict(contract_date=date.isoformat() if date else '',exclusive_area_m2=str(area) if area is not None else '',transaction_floor=floor if floor is not None else '',building_age_years=age if age is not None else '',age_basis='build_year_approx' if age is not None else 'unknown',unit_feature_status='incomplete' if issues else 'complete_with_review' if warnings else 'complete',unit_feature_issues='|'.join(issues+warnings))
def main():
 REPORT.mkdir(parents=True,exist_ok=True)
 source_summary=json.loads((ROOT/'reports/seoul_sales_2020_2026/collection_summary.json').read_text(encoding='utf-8'))
 if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=source_summary['merged_sha256']:raise ValueError('Source changed since collection')
 manifest=json.loads((ROOT/'reports/seoul_sales_2020_2026/download_manifest.json').read_text(encoding='utf-8'))
 hashes={f"seoul_apt_sales_{m['year']}.csv":m['sha256'] for m in manifest}
 output=OUT/'seoul_apt_sales_2020_2026_unit_features.csv'
 review=REPORT/'rows_for_review.csv'
 statuses=collections.Counter();issues=collections.Counter();byyear=collections.defaultdict(collections.Counter);perfile=collections.Counter()
 ranges={k:[None,None] for k in ['exclusive_area_m2','transaction_floor','building_age_years']}
 missing=collections.Counter();ids=set();input_n=0;cancelled=0;kept=0
 with SOURCE.open(encoding='utf-8-sig',newline='') as f,output.open('w',encoding='utf-8-sig',newline='') as g,review.open('w',encoding='utf-8-sig',newline='') as h:
  reader=csv.DictReader(f);rawfields=reader.fieldnames
  if set(rawfields)&set(ADDED):raise ValueError('Input already contains feature columns')
  writer=csv.DictWriter(g,fieldnames=rawfields+ADDED);writer.writeheader()
  rw=csv.DictWriter(h,fieldnames=['record_id','source_file','source_row','contract_date','unit_feature_status','unit_feature_issues','floor_raw','build_year_raw']);rw.writeheader()
  for row in reader:
   input_n+=1;perfile[row['source_file']]+=1
   if row['해제사유발생일'].strip() not in ('','-'):cancelled+=1;continue
   source_row=perfile[row['source_file']]
   record_id=hashlib.sha256(f"{hashes[row['source_file']]}|{source_row}".encode()).hexdigest()
   if record_id in ids:raise ValueError('record_id collision or repeated source row')
   ids.add(record_id)
   fingerprint=hashlib.sha256(json.dumps({k:row[k] for k in rawfields if k not in ['NO','source_file','retrieved_at']},ensure_ascii=False,sort_keys=True).encode()).hexdigest()
   features=derive(row);writer.writerow(dict(row,record_id=record_id,record_fingerprint=fingerprint,source_row=source_row,**features));kept+=1
   statuses[features['unit_feature_status']]+=1
   year=row['계약년월'][:4];byyear[year]['rows']+=1;byyear[year][features['unit_feature_status']]+=1
   for reason in filter(None,features['unit_feature_issues'].split('|')):issues[reason]+=1
   for key in ranges:
    value=features[key]
    if value=='':missing[key]+=1;continue
    value=float(value);lo,hi=ranges[key];ranges[key]=[value if lo is None else min(lo,value),value if hi is None else max(hi,value)]
   if features['unit_feature_status']!='complete':rw.writerow(dict(record_id=record_id,source_file=row['source_file'],source_row=source_row,contract_date=features['contract_date'],unit_feature_status=features['unit_feature_status'],unit_feature_issues=features['unit_feature_issues'],floor_raw=row['층'],build_year_raw=row['건축년도']))
 if input_n!=source_summary['raw_rows'] or kept!=source_summary['non_cancelled_rows'] or cancelled!=source_summary['cancelled_rows']:raise ValueError('Row reconciliation failed')
 summary=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=source_summary['merged_sha256'],output=str(output.relative_to(ROOT)),output_sha256=hashlib.sha256(output.read_bytes()).hexdigest(),input_rows=input_n,excluded_cancelled=cancelled,output_rows=kept,unique_record_ids=len(ids),statuses=dict(statuses),issues=dict(issues),missing_counts={k:missing[k] for k in ranges},ranges=ranges,by_year={k:dict(v) for k,v in sorted(byyear.items())},feature_names=['exclusive_area_m2','transaction_floor','building_age_years'],age_basis='build_year_approx',approval_date_used=False,relative_floor_included=False,notes=['No row removed for unit-feature issues; missing fields and reasons are retained.','Negative/zero floors retained with review flag, not automatically discarded.','Fingerprint equality is not a duplicate-removal instruction.','These are attributes reported in the latest revised source, not proof of their historical publication time.'])
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 with (REPORT/'year_summary.csv').open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=['year','rows','complete','complete_with_review','incomplete']);w.writeheader()
  for year,counts in sorted(byyear.items()):w.writerow(dict(year=year,**{k:counts[k] for k in ['rows','complete','complete_with_review','incomplete']}))
 print(json.dumps(summary,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
