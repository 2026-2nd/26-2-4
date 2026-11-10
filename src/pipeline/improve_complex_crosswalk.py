"""Evidence-based crosswalk revision; no transaction prices and no fuzzy-only matches."""
import collections,csv,hashlib,json,pathlib,re
from build_internal_features import ROOT,make_indexes,approval_date,text_norm
REPORT=ROOT/'reports/crosswalk_v2'
SOURCE=ROOT/'reports/internal_features/complex_match_audit.csv'
GENERIC={'현대','삼성','한신','한양','동아','우성','두산','대림','벽산','주공','래미안','롯데캐슬','아이파크','이편한세상','푸르지오','자이','아파트','임대'}
ACCEPTED={'address_name_supported','road_year_parcel_supported','road_year_name_alias_supported','parcel_year_name_supported'}
def parcel(value):
 value=str(value).strip()
 m=re.match(r'^(산)?\s*(\d+)(?:\s*-\s*(\d+))?(?=번지|\s|$)',value)
 if not m:return None
 return (bool(m[1]),int(m[2]),int(m[3] or 0))
def canonical_name(value):
 s=text_norm(value)
 s=s.replace('ipark','아이파크').replace('e-편한세상','이편한세상').replace('e편한세상','이편한세상')
 s=re.sub(r'\(고층\)|\(저층\)','',s)
 s=re.sub(r'[^a-z0-9가-힣]','',s).replace('아파트','')
 return s
def phases(value):
 s=text_norm(value);s=re.sub(r'\(고층\)|\(저층\)','',s);found=set()
 for m in re.finditer(r'(\d+(?:[,·]\d+)+)(?:단지|차)',s):found.update(int(v) for v in re.split('[,·]',m[1]))
 found.update(int(v) for v in re.findall(r'(\d+)(?:단지|차)',s))
 # A trailing phase number is only recognized in the original spelling, not a parcel in parentheses.
 m=re.search(r'[가-힣a-z](\d{1,2})$',s)
 if m:found.add(int(m[1]))
 return found
def scope_issues(txname,srcname):
 reasons=[];a=phases(txname);b=phases(srcname)
 if a and b and a!=b:reasons.append('phase_or_complex_scope_conflict')
 elif bool(a)!=bool(b):reasons.append('phase_scope_not_aligned')
 if re.search(r'\d+동(?:\s*[~～\-]\s*\d+동)?',txname):reasons.append('transaction_building_subset_name')
 if bool('임대' in txname)!=bool('임대' in srcname):reasons.append('rental_scope_mismatch')
 if len(a)>1 or len(b)>1:reasons.append('combined_complex_scope_review')
 for builder in re.findall(r'\((동아|삼성|한진|한화|대림|두산|현대|롯데)\)',txname):
  if builder not in srcname:reasons.append('builder_subcomplex_scope_review')
 return reasons
def name_evidence(txname,srcname,gu,dong):
 a=canonical_name(txname);b=canonical_name(srcname)
 if not a or not b:return ''
 if a==b:return 'canonical_brand_spelling_equal'
 # Geographic prefixes differ across portals; never remove phase numbers or merge common brands alone.
 prefixes=sorted({gu.removesuffix('구'),dong,dong.removesuffix('동'),re.sub(r'\d+가$','',dong)},key=len,reverse=True)
 def strip_geo(s):
  for prefix in prefixes:
   if len(prefix)>=2 and s.startswith(prefix) and len(s)>len(prefix):s=s[len(prefix):]
  return s
 aa=strip_geo(a);bb=strip_geo(b)
 if aa==bb and aa not in GENERIC and len(aa)>=3:return 'geographic_prefix_equal'
 shorter,longer=sorted([aa,bb],key=len)
 if len(shorter)>=3 and shorter not in GENERIC and shorter in longer:return 'distinctive_name_containment'
 return ''
def evaluate(tx,source):
 address=tx['시군구'].split();gu=address[1] if len(address)>1 else '';dong=' '.join(address[2:])
 year=approval_date(source);txyear=tx.get('건축년도','').strip()
 reasons=[]
 if source['주소(시군구)'].strip()!=gu:reasons.append('district_conflict')
 if not year or str(year.year)!=txyear:reasons.append('approval_year_conflict_or_missing')
 reasons.extend(scope_issues(tx['단지명'],source['k-아파트명']))
 txroad=' '.join(address[:2])+' '+tx['도로명'] if tx['도로명'].strip() not in ('','-') else ''
 road=bool(txroad) and text_norm(txroad)==text_norm(source['kapt도로명주소'])
 dong_equal=bool(dong) and dong==source['주소(읍면동)'].strip()
 a=parcel(tx['번지']);b=parcel(source['나머지주소'])
 same_parcel=dong_equal and a is not None and b is not None and a==b
 parcel_conflict=dong_equal and a is not None and b is not None and a!=b
 if parcel_conflict:reasons.append('explicit_parcel_conflict')
 names=name_evidence(tx['단지명'],source['k-아파트명'],gu,dong)
 method=''
 if not reasons:
  if road and same_parcel:method='road_year_parcel_supported'
  elif road and names and dong_equal:method='road_year_name_alias_supported'
  elif same_parcel and names:method='parcel_year_name_supported'
 return dict(method=method,road_equal=road,legal_dong_equal=dong_equal,parcel_equal=same_parcel,name_evidence=names,blocking_reasons='|'.join(reasons),source_parcel_text=source['나머지주소'])
def refine(tx,source_rows,indexes,old):
 # Preserve previous accepted records; no unsupported silent reassignment.
 byroad,_=indexes;address=tx['시군구'].split();gu=address[1] if len(address)>1 else '';dong=' '.join(address[2:])
 road=' '.join(address[:2])+' '+tx['도로명'] if tx['도로명'].strip() not in ('','-') else ''
 candidates=set(byroad.get(text_norm(road),[])) if road else set()
 p=parcel(tx['번지'])
 if p is not None:
  for i,s in enumerate(source_rows):
   if s['주소(시군구)'].strip()==gu and s['주소(읍면동)'].strip()==dong and parcel(s['나머지주소'])==p:candidates.add(i)
 if old['selected_kapt_code']:
  candidates.update(i for i,s in enumerate(source_rows) if s['k-아파트코드']==old['selected_kapt_code'])
 evidence=[(i,evaluate(tx,source_rows[i])) for i in sorted(candidates)]
 accepted=[(i,e) for i,e in evidence if e['method']]
 if old['match_status']=='address_name_supported':
  return dict(code=old['selected_kapt_code'],status=old['match_status'],decision='retained_previous_supported',evidence='previous_address_name_rule',candidates=evidence,changed=False)
 if len(accepted)==1:
  i,e=accepted[0];return dict(code=source_rows[i]['k-아파트코드'],status=e['method'],decision='new_rule_supported',evidence=e['name_evidence'] or 'road_parcel_year_agreement',candidates=evidence,changed=True)
 return dict(code=old['selected_kapt_code'],status=old['match_status'],decision='unresolved_multiple_supported' if len(accepted)>1 else 'unresolved_insufficient_evidence',evidence='',candidates=evidence,changed=False)
def main():
 REPORT.mkdir(parents=True,exist_ok=True)
 with (ROOT/'data/raw/seoul_complex.csv').open(encoding='cp949',newline='') as f:sources=list(csv.DictReader(f))
 indexes=make_indexes(sources)
 with SOURCE.open(encoding='utf-8-sig',newline='') as f:audits=list(csv.DictReader(f))
 rows=[];evidence=[];decisions=collections.Counter();status_before=collections.Counter();status_after=collections.Counter();changes=0
 for old in audits:
  parts=old['transaction_complex_key'].split('|')
  if len(parts)!=5:raise ValueError('Unexpected original transaction complex key')
  tx=dict(zip(['시군구','번지','단지명','도로명','건축년도'],parts))
  result=refine(tx,sources,indexes,old);weight=int(old['transaction_rows']);decisions[result['decision']]+=weight;status_before[old['match_status']]+=weight;status_after[result['status']]+=weight
  changes+=weight if result['changed'] else 0
  rows.append(dict(complex_match_key=hashlib.sha256(old['transaction_complex_key'].encode()).hexdigest(),transaction_complex_key=old['transaction_complex_key'],transaction_name=tx['단지명'],transaction_address=tx['시군구']+' '+tx['번지'],transaction_road=tx['도로명'],transaction_build_year=tx['건축년도'],old_kapt_code=old['selected_kapt_code'],new_kapt_code=result['code'],old_match_status=old['match_status'],new_match_status=result['status'],decision=result['decision'],name_evidence=result['evidence'],transaction_rows=weight))
  for i,e in result['candidates']:evidence.append(dict(complex_match_key=rows[-1]['complex_match_key'],transaction_name=tx['단지명'],candidate_kapt_code=sources[i]['k-아파트코드'],candidate_name=sources[i]['k-아파트명'],transaction_rows=weight,**e))
 for name,data in [('crosswalk_v2',rows),('candidate_evidence',evidence)]:
  with (REPORT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 summary=dict(transaction_complex_keys=len(rows),transaction_rows=sum(r['transaction_rows'] for r in rows),new_rule_supported_transaction_rows=changes,new_rule_supported_keys=sum(r['decision']=='new_rule_supported' for r in rows),status_before=dict(status_before),status_after=dict(status_after),decisions=dict(decisions),accepted_statuses=sorted(ACCEPTED),manual_validation_completed=False,notes=['No transaction prices used.','Current source legal-dong/parcel is corroborating evidence, not standalone authoritative cadastral validation.','Phase/subcomplex/rental conflicts remain review items.','Existing address_name_supported mappings are retained; possible new conflicts are exposed in candidate_evidence.'])
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
