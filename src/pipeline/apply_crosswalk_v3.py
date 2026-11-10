"""Apply crosswalk v3 to the v2 active CSV and write a new versioned CSV.

* v2 CSV is not modified. Rows whose combo keeps its v2 decision are copied unchanged
  (only new columns appended); this is verified field by field.
* Rows whose combo got a v3 link are rebuilt with the same attach()/transform() code
  that v2 used, starting from their strict-history values (the *_history_verified columns).
* Identity rules may receive static-assumption values only if the unchanged policy checks
  pass (approval year == build year, approval <= contract, building count present).
* Location-only links never fill internal values. They (and v2 unique_address_review rows,
  whose only evidence is an exact road-address match) only supply a complex reference point.
"""
import collections,csv,hashlib,json,sys
from build_internal_features import ROOT,BASE,FEATURES,attach
from apply_internal_static_assumption import EXTRA,transform
from improve_complex_crosswalk import ACCEPTED
from improve_complex_crosswalk_v3 import IDENTITY_RULES,LOCATION_ONLY_RULES
csv.field_size_limit(sys.maxsize)
SOURCE=BASE/'seoul_apt_sales_2020_2026_internal_static_assumption_crosswalk_v2.csv'
SOURCE_SHA='89ba7820946d7bad9ec5cf330b24edb4619503db049b47fee8330ecc10d63694'
OUTPUT=BASE/'seoul_apt_sales_2020_2026_internal_static_assumption_crosswalk_v3.csv'
REPORT=ROOT/'reports/crosswalk_v3'
V2_ADDED=EXTRA+['crosswalk_version','previous_complex_candidate_kapt_code','previous_complex_match_status','crosswalk_decision','crosswalk_evidence']
NEW=['crosswalk_v3_decision','crosswalk_v3_rule','complex_link_scope','complex_point_lon','complex_point_lat','complex_point_basis']
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def main():
 if sha(SOURCE)!=SOURCE_SHA:raise ValueError('v2 active CSV changed')
 with (REPORT/'crosswalk_v3.csv').open(encoding='utf-8-sig',newline='') as f:cw={r['complex_match_key']:r for r in csv.DictReader(f)}
 with (ROOT/'data/raw/seoul_complex.csv').open(encoding='cp949',newline='') as f:sources=list(csv.DictReader(f))
 index={r['k-아파트코드']:i for i,r in enumerate(sources)}
 strict_meta=json.loads((ROOT/'reports/internal_features/summary.json').read_text(encoding='utf-8'))
 policy=json.loads((ROOT/'config/internal_static_assumption_policy_v2.json').read_text(encoding='utf-8'))
 policy.update(version='3.0_crosswalk_v3',eligible_match_status=sorted(ACCEPTED|IDENTITY_RULES))
 (ROOT/'config/internal_static_assumption_policy_v3.json').write_text(json.dumps(policy,ensure_ascii=False,indent=2),encoding='utf-8')
 before=collections.Counter();after=collections.Counter();basis={f:collections.Counter() for f in FEATURES}
 status=collections.Counter();scope=collections.Counter();point=collections.Counter();changed_values=collections.Counter()
 n=0;ids=set();rebuilt=0;unchanged_ok=0;complete_before=0;complete_after=0;elig=0
 with SOURCE.open(encoding='utf-8-sig',newline='') as f,OUTPUT.open('w',encoding='utf-8-sig',newline='') as g:
  reader=csv.DictReader(f);fields=reader.fieldnames
  strict_fields=[c for c in fields if c not in V2_ADDED]
  w=csv.DictWriter(g,fieldnames=fields+NEW);w.writeheader()
  for row in reader:
   r=cw[row['complex_match_key']];dec=r['v3_decision']
   for ft in FEATURES:before[ft]+=row[ft]!=''
   complete_before+=all(row[ft]!='' for ft in FEATURES)
   if dec.startswith('v3_rule') or dec=='v3_location_only':
    original={c:row[c] for c in strict_fields}
    for ft in FEATURES:original[ft]=row[ft+'_history_verified']
    # The original snapshot attach() of v1 is re-run for the v3 candidate.
    i=index[r['v3_kapt_code']]
    result=dict(selected=i,status=r['v3_match_status'],method=r['v3_match_status'],candidate_count=1,issues=[] if dec.startswith('v3_rule') else ['location_only_scope_not_identity'])
    new=dict(original,**attach(original,result,sources,strict_meta['complex_snapshot_date']))
    if r['v3_match_status'] in IDENTITY_RULES:
     new['internal_feature_issues']='|'.join(x for x in new['internal_feature_issues'].split('|') if x!='complex_identity_review_required')
    out=transform(new,sources[i],policy)
    out.update(crosswalk_version='3.0',previous_complex_candidate_kapt_code=row['complex_candidate_kapt_code'],previous_complex_match_status=row['complex_match_status'],crosswalk_decision=row['crosswalk_decision'],crosswalk_evidence=row['crosswalk_evidence'])
    rebuilt+=1
    for c in fields:
     if c in FEATURES and row[c]!=out[c] and row[c]!='':changed_values[c]+=1
   else:
    out=dict(row);unchanged_ok+=1
   sc='identity' if out['complex_match_status'] in (ACCEPTED|IDENTITY_RULES) else ('location_only' if out['complex_match_status'] in LOCATION_ONLY_RULES else ('location_only' if out['complex_match_status']=='unique_address_review' and out['complex_candidate_kapt_code'] else 'none'))
   pb='';lon='';lat=''
   if sc!='none':
    s=sources[index[out['complex_candidate_kapt_code']]]
    if s['좌표X'].strip() and s['좌표Y'].strip():
     lon,lat=s['좌표X'].strip(),s['좌표Y'].strip()
     pb={'identity':'kapt_snapshot_point_identity_link','location_only':'kapt_snapshot_point_location_only_link'}[sc]
    else:pb='kapt_point_missing'
   else:pb='no_complex_link'
   out.update(crosswalk_v3_decision=dec,crosswalk_v3_rule=r['v3_rule'],complex_link_scope=sc,complex_point_lon=lon,complex_point_lat=lat,complex_point_basis=pb)
   w.writerow(out);n+=1;ids.add(out['record_id'])
   for ft in FEATURES:after[ft]+=out[ft]!='';basis[ft][out[ft+'_basis']]+=1
   complete_after+=all(out[ft]!='' for ft in FEATURES);elig+=out['static_assumption_eligible']=='true'
   status[out['complex_match_status']]+=1;scope[sc]+=1;point[pb]+=1
 if n!=356087 or len(ids)!=n:raise ValueError('Row preservation failure')
 if any(changed_values.values()):raise ValueError(f'Previously filled values changed: {changed_values}')
 comparison=[dict(feature=ft,v2_filled=before[ft],v3_filled=after[ft],additional_filled=after[ft]-before[ft],v2_missing_rate=round((n-before[ft])/n,6),v3_missing_rate=round((n-after[ft])/n,6),missing_reduction_percentage_points=round(100*(after[ft]-before[ft])/n,4)) for ft in FEATURES]
 with (REPORT/'missing_comparison_v3.csv').open('w',encoding='utf-8-sig',newline='') as f:
  wr=csv.DictWriter(f,fieldnames=list(comparison[0]));wr.writeheader();wr.writerows(comparison)
 summary=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=SOURCE_SHA,output=str(OUTPUT.relative_to(ROOT)),output_sha256=sha(OUTPUT),output_rows=n,unique_record_ids=len(ids),columns=len(fields)+len(NEW),rows_rebuilt_from_v3_links=rebuilt,rows_copied_unchanged=unchanged_ok,previously_filled_values_changed=0,eligible_rows=elig,rows_with_all_four_values_v2=complete_before,rows_with_all_four_values_v3=complete_after,missing_comparison=comparison,basis_counts={k:dict(v) for k,v in basis.items()},match_status_rows=dict(status),link_scope_rows=dict(scope),complex_point_rows=dict(point),policy_file='config/internal_static_assumption_policy_v3.json',historical_verification_completed=False,manual_match_accuracy_evaluation_completed=False,model_run=False)
 (REPORT/'application_summary_v3.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=1))
if __name__=='__main__':main()
