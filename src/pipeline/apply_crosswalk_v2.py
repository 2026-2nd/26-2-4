"""Refresh internal snapshots from the revised crosswalk, then apply the same static policy.

Prior strict and static datasets remain unchanged. Price is never used in matching.
"""
import collections,csv,hashlib,json
from build_internal_features import ROOT,BASE,FEATURES,attach
from apply_internal_static_assumption import EXTRA,transform
from improve_complex_crosswalk import ACCEPTED
SOURCE=BASE/'seoul_apt_sales_2020_2026_unit_market_internal_features.csv'
OUTPUT=BASE/'seoul_apt_sales_2020_2026_internal_static_assumption_crosswalk_v2.csv'
REPORT=ROOT/'reports/crosswalk_v2'
ADDED=EXTRA+['crosswalk_version','previous_complex_candidate_kapt_code','previous_complex_match_status','crosswalk_decision','crosswalk_evidence']
def main():
 strict=json.loads((ROOT/'reports/internal_features/summary.json').read_text(encoding='utf-8'))
 previous=json.loads((ROOT/'reports/internal_static_assumption/summary.json').read_text(encoding='utf-8'))
 if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=strict['output_sha256']:raise ValueError('Strict input changed')
 with (REPORT/'crosswalk_v2.csv').open(encoding='utf-8-sig',newline='') as f:crosswalk={r['complex_match_key']:r for r in csv.DictReader(f)}
 with (ROOT/'data/raw/seoul_complex.csv').open(encoding='cp949',newline='') as f:sources=list(csv.DictReader(f))
 index={r['k-아파트코드']:i for i,r in enumerate(sources)}
 policy=json.loads((ROOT/'config/internal_static_assumption_policy.json').read_text(encoding='utf-8'))
 policy.update(version='2.0_crosswalk_v2',eligible_match_status=sorted(ACCEPTED))
 (ROOT/'config/internal_static_assumption_policy_v2.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2),encoding='utf-8')
 previous_counts={r['feature']:r['assumed_values'] for r in previous['missing_comparison']}
 count=collections.Counter();basis={f:collections.Counter() for f in FEATURES};rows_by_status=collections.Counter();year=collections.defaultdict(collections.Counter);gu=collections.defaultdict(collections.Counter);ids=set();n=0;elig=0;anyfilled=0;complete=0;changed_codes=0;changed_status=0;group_stats=collections.defaultdict(collections.Counter)
 with SOURCE.open(encoding='utf-8-sig',newline='') as f,OUTPUT.open('w',encoding='utf-8-sig',newline='') as g:
  reader=csv.DictReader(f);writer=csv.DictWriter(g,fieldnames=reader.fieldnames+ADDED);writer.writeheader()
  for original in reader:
   rule=crosswalk[original['complex_match_key']];code=rule['new_kapt_code'];i=index.get(code)
   issues=original['complex_match_issues'].split('|') if original['complex_match_issues'] else []
   if rule['decision']=='new_rule_supported':issues=[]
   result=dict(selected=i,status=rule['new_match_status'],method=rule['new_match_status'] if rule['decision']=='new_rule_supported' else original['complex_match_method'],candidate_count=1 if rule['decision']=='new_rule_supported' else original['complex_match_candidate_count'],issues=issues)
   row=dict(original,**attach(original,result,sources,strict['complex_snapshot_date']))
   if rule['new_match_status'] in ACCEPTED:
    row['internal_feature_issues']='|'.join(x for x in row['internal_feature_issues'].split('|') if x!='complex_identity_review_required')
   out=transform(row,sources[i] if i is not None else None,policy)
   out.update(crosswalk_version='2.0',previous_complex_candidate_kapt_code=original['complex_candidate_kapt_code'],previous_complex_match_status=original['complex_match_status'],crosswalk_decision=rule['decision'],crosswalk_evidence=rule['name_evidence'])
   writer.writerow(out);n+=1;ids.add(original['record_id'])
   rows_by_status[out['complex_match_status']]+=1;elig+=out['static_assumption_eligible']=='true'
   anyfilled+=any(out[f]!='' for f in FEATURES);complete+=all(out[f]!='' for f in FEATURES)
   changed_codes+=out['complex_candidate_kapt_code']!=original['complex_candidate_kapt_code'];changed_status+=out['complex_match_status']!=original['complex_match_status']
   for grouping in [year[original['contract_date'][:4]],gu[original['district_code']]]:
    grouping['rows']+=1
    for feature in FEATURES:grouping[feature+'_filled']+=out[feature]!=''
   group_stats[original['complex_match_key']]['rows']+=1
   for feature in FEATURES:
    count[feature]+=out[feature]!='';basis[feature][out[feature+'_basis']]+=1
    group_stats[original['complex_match_key']][feature+'_filled']+=out[feature]!=''
 if n!=strict['output_rows'] or len(ids)!=n:raise ValueError('Row reconciliation failed')
 comparison=[dict(feature=f,previous_filled=previous_counts[f],new_filled=count[f],additional_filled=count[f]-previous_counts[f],previous_missing=n-previous_counts[f],new_missing=n-count[f],previous_missing_rate=(n-previous_counts[f])/n,new_missing_rate=(n-count[f])/n,missing_reduction_percentage_points=100*(count[f]-previous_counts[f])/n) for f in FEATURES]
 if any(r['additional_filled']<0 for r in comparison):raise ValueError('Unexpected decline; investigate before publishing')
 for file,data,fields in [('missing_comparison_v2',comparison,list(comparison[0]))]:
  with (REPORT/f'{file}.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(data)
 for file,data in [('year_summary',year),('district_summary',gu)]:
  with (REPORT/f'{file}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   fields=['group','rows']+[x+'_filled' for x in FEATURES];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
   for group,counts in sorted(data.items()):w.writerow(dict(group=group,**counts))
 with (REPORT/'crosswalk_application_counts.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['complex_match_key','transaction_name','kapt_code','match_status','decision','rows']+[x+'_filled' for x in FEATURES];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for key,counts in group_stats.items():
   r=crosswalk[key];w.writerow(dict(complex_match_key=key,transaction_name=r['transaction_name'],kapt_code=r['new_kapt_code'],match_status=r['new_match_status'],decision=r['decision'],**counts))
 summary=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=strict['output_sha256'],previous_static_file=previous['output'],previous_static_sha256=previous['output_sha256'],output=str(OUTPUT.relative_to(ROOT)),output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),crosswalk_file=str((REPORT/'crosswalk_v2.csv').relative_to(ROOT)),crosswalk_sha256=hashlib.sha256((REPORT/'crosswalk_v2.csv').read_bytes()).hexdigest(),output_rows=n,unique_record_ids=len(ids),eligible_rows=elig,rows_with_any_assumed_value=anyfilled,rows_with_all_four_values=complete,changed_candidate_code_rows=changed_codes,changed_match_status_rows=changed_status,match_status_transaction_rows=dict(rows_by_status),feature_names=FEATURES,missing_comparison=comparison,basis_counts={f:dict(c) for f,c in basis.items()},historical_verification_completed=False,manual_match_accuracy_evaluation_completed=False,model_run=False)
 (REPORT/'application_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
