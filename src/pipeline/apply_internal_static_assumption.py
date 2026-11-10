"""User-authorized conditional snapshot backfill, explicitly separate from strict history.

No claim of verified historical values. Do not loosen identity matching to increase coverage.
"""
import collections,csv,datetime as dt,hashlib,json,pathlib
from build_internal_features import ROOT,BASE,FEATURES,nonneg_number,approval_date
SOURCE=BASE/'seoul_apt_sales_2020_2026_unit_market_internal_features.csv'
OUTPUT=BASE/'seoul_apt_sales_2020_2026_internal_static_assumption.csv'
REPORT=ROOT/'reports/internal_static_assumption'
POLICY=ROOT/'config/internal_static_assumption_policy.json'
EXTRA=[f'{f}_history_verified' for f in FEATURES]+[f'{f}_basis' for f in FEATURES]+['static_assumption_eligible','static_assumption_exclusion_reason','complex_building_count_snapshot','building_count_history_status','static_assumption_version']
def eligible(row,source,policy):
 reasons=[]
 if row['complex_match_status'] not in policy['eligible_match_status']:reasons.append('identity_not_sufficiently_supported')
 if source is None:reasons.append('complex_source_not_found');return False,reasons
 date=approval_date(source)
 try:contract=dt.date.fromisoformat(row['contract_date'])
 except ValueError:contract=None;reasons.append('contract_date_invalid')
 if not date:reasons.append('approval_date_missing')
 elif contract and date>contract:reasons.append('contract_before_approval')
 if not date or str(date.year)!=row.get('건축년도','').strip():reasons.append('build_year_not_confirmed')
 count=nonneg_number(source['k-전체동수'],positive=True)
 if count is None or count!=count.to_integral_value():reasons.append('snapshot_building_count_missing_or_invalid')
 return not reasons,reasons
def transform(row,source,policy):
 result=dict(row);ok,reasons=eligible(row,source,policy)
 result.update({f'{f}_history_verified':row[f] for f in FEATURES})
 result.update(static_assumption_eligible='true' if ok else 'false',static_assumption_exclusion_reason='|'.join(reasons),complex_building_count_snapshot=source['k-전체동수'] if source else '',building_count_history_status='historical_count_and_individual_building_not_verified',static_assumption_version=policy['version'])
 blocked={(x['kapt_code'],x['feature']) for x in policy['known_change_risk_exclusions']}
 filled=0;rejected=[]
 for feature in FEATURES:
  basis='history_verified' if row[feature]!='' else 'missing'
  if row[feature]=='':
   if not ok:basis='missing_match_or_approval_check'
   elif (row['complex_candidate_kapt_code'],feature) in blocked:
    basis='excluded_known_change_risk';rejected.append(feature+':known_change_risk')
   elif row[feature+'_snapshot']=='':basis='missing_source_value'
   else:
    result[feature]=row[feature+'_snapshot'];basis='assumed_time_invariant';filled+=1
  result[feature+'_basis']=basis
 if filled:
  result['complex_history_status']='assumed_static_not_verified'
  result['internal_feature_status']='assumed_complete' if all(result[f]!='' for f in FEATURES) else 'assumed_partial'
  # Replace the old "no value populated" explanation, retaining source warnings.
  old=[x for x in row['internal_feature_issues'].split('|') if x and x!='no_verified_attribute_history']
  result['internal_feature_issues']='|'.join(old+['static_assumption_not_verified_history','historical_building_count_unverified']+rejected)
 return result
def main():
 REPORT.mkdir(parents=True,exist_ok=True)
 old=json.loads((ROOT/'reports/internal_features/summary.json').read_text(encoding='utf-8'))
 if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=old['output_sha256']:raise ValueError('Strict source changed')
 policy=json.loads(POLICY.read_text(encoding='utf-8'))
 with (ROOT/'data/raw/seoul_complex.csv').open(encoding='cp949',newline='') as f:sources={r['k-아파트코드']:r for r in csv.DictReader(f)}
 before=collections.Counter();after=collections.Counter();basis_counts={f:collections.Counter() for f in FEATURES};exclusions=collections.Counter();byyear=collections.defaultdict(collections.Counter);byg=collections.defaultdict(collections.Counter);audit={};ids=set();n=0;eligible_n=0;complete=0;anyfill=0
 with SOURCE.open(encoding='utf-8-sig',newline='') as f,OUTPUT.open('w',encoding='utf-8-sig',newline='') as g:
  reader=csv.DictReader(f)
  if set(reader.fieldnames)&set(EXTRA):raise ValueError('Repeated enrichment')
  w=csv.DictWriter(g,fieldnames=reader.fieldnames+EXTRA);w.writeheader()
  for row in reader:
   source=sources.get(row['complex_candidate_kapt_code']);out=transform(row,source,policy);w.writerow(out)
   n+=1;ids.add(row['record_id']);eligible_n+=out['static_assumption_eligible']=='true'
   complete+=all(out[x]!='' for x in FEATURES);filled_here=any(out[x+'_basis']=='assumed_time_invariant' for x in FEATURES);anyfill+=filled_here
   year=row['contract_date'][:4];gu=row['district_code'];byyear[year]['rows']+=1;byg[gu]['rows']+=1
   for feature in FEATURES:
    before[feature]+=row[feature]=='';after[feature]+=out[feature]=='';basis_counts[feature][out[feature+'_basis']]+=1
    byyear[year][feature+'_filled']+=out[feature]!='';byg[gu][feature+'_filled']+=out[feature]!=''
   if out['static_assumption_exclusion_reason']:exclusions.update(out['static_assumption_exclusion_reason'].split('|'))
   key=row['complex_match_key']
   if key not in audit:audit[key]=dict(complex_match_key=key,transaction_name=row['단지명'],candidate_kapt_code=row['complex_candidate_kapt_code'],match_status=row['complex_match_status'],building_count_snapshot=out['complex_building_count_snapshot'],transaction_rows=0,rows_with_any_assumed_value=0)
   audit[key]['transaction_rows']+=1;audit[key]['rows_with_any_assumed_value']+=filled_here
 if n!=old['output_rows'] or len(ids)!=n:raise ValueError('Row preservation failed')
 comparison=[dict(feature=f,before_missing=before[f],before_missing_rate=before[f]/n,after_missing=after[f],after_missing_rate=after[f]/n,missing_reduction=before[f]-after[f],missing_reduction_percentage_points=100*(before[f]-after[f])/n,verified_history_values=n-before[f],assumed_values=basis_counts[f]['assumed_time_invariant']) for f in FEATURES]
 for file,rows in [('missing_comparison',comparison),('complex_assumption_audit',list(audit.values()))]:
  with (REPORT/f'{file}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 for file,data in [('year_summary',byyear),('district_summary',byg)]:
  with (REPORT/f'{file}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   fields=['group','rows']+[x+'_filled' for x in FEATURES];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for group,counts in sorted(data.items()):w.writerow(dict(group=group,**counts))
 summary=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=old['output_sha256'],output=str(OUTPUT.relative_to(ROOT)),output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),output_rows=n,unique_record_ids=len(ids),eligible_rows=eligible_n,rows_with_any_assumed_value=anyfill,rows_with_all_four_values=complete,feature_names=FEATURES,missing_comparison=comparison,basis_counts={k:dict(v) for k,v in basis_counts.items()},eligibility_exclusions=dict(exclusions),verified_history_values_generated=0,historical_building_count_verified=False,policy_file=str(POLICY.relative_to(ROOT)),policy_sha256=hashlib.sha256(POLICY.read_bytes()).hexdigest(),notes=['Exploratory static-assumption dataset, not strict point-in-time verification.','No missing-value reduction is claimed as an increase in historically verified observations.','Known risk search is illustrative, not exhaustive.','Same current building count does not prove no heating/parking changes.','Identity criteria were not relaxed to improve coverage.'],model_run=False)
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
