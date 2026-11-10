"""Crosswalk v3: review of combos left unresolved by v2. No prices, no similarity scores.

v2 decisions are never changed. Only `unresolved_*` combos are re-evaluated with
additional, explicitly named rules that need agreement of several independent fields
(legal dong, completion year, complex/phase number, road address). Every new link keeps
its rule name; location-only links are not eligible for the internal static assumption.
"""
import collections,csv,hashlib,json,re
from build_internal_features import ROOT,approval_date,text_norm
from improve_complex_crosswalk import GENERIC,canonical_name,parcel,phases
REPORT=ROOT/'reports/crosswalk_v3'
V2=ROOT/'reports/crosswalk_v2/crosswalk_v2.csv'
# Accepted for identity (internal static assumption may apply if its own policy passes).
IDENTITY_RULES={'road_year_geo_prefix_supported','road_year_phase_name_supported','dong_year_phase_name_supported','road_name_year_off_by_one_supported'}
# Location only: the source record covers a wider management scope than the transaction name.
LOCATION_ONLY_RULES={'road_year_subcomplex_scope_location_only','parcel_year_subcomplex_scope_location_only'}
PHASE_TOKEN=re.compile(r'제?\d+(?:[,·\-]\d+)*(?:단지|차)|\d+$')
def base_name(name,gu,dong):
 s=canonical_name(name)
 s=PHASE_TOKEN.sub('',s)
 s=re.sub(r'(임대|분양)$','',s)
 prefixes=sorted({gu,gu.removesuffix('구'),dong,dong.removesuffix('동'),re.sub(r'\d+가$','',dong),re.sub(r'\d+가$','',dong).removesuffix('동')},key=len,reverse=True)
 changed=True
 while changed:
  changed=False
  for p in prefixes:
   if len(p)>=2 and s.startswith(p) and len(s)>len(p):s=s[len(p):];changed=True
 return s
def generic_only(base):
 s=base
 for g in sorted(GENERIC,key=len,reverse=True):s=s.replace(g,'')
 return len(s)<2
def blockers(tx_name,src_name,tx_parcel,src_parcel,dong_equal):
 r=[]
 if bool('임대' in tx_name)!=bool('임대' in src_name):r.append('rental_scope_mismatch')
 if re.search(r'\d+동',tx_name):r.append('transaction_building_subset_name')
 if re.search(r'\((동아|삼성|한진|한화|대림|두산|현대|롯데)\)',tx_name):r.append('builder_subcomplex_scope_review')
 if dong_equal and tx_parcel is not None and src_parcel is not None and tx_parcel!=src_parcel:r.append('explicit_parcel_conflict')
 if len(phases(tx_name))>1 or len(phases(src_name))>1:r.append('combined_complex_scope_review')
 return r
def evaluate(tx,src,road_candidates):
 address=tx['시군구'].split();gu=address[1] if len(address)>1 else '';dong=' '.join(address[2:])
 if src['주소(시군구)'].strip()!=gu:return None
 dong_equal=dong==src['주소(읍면동)'].strip()
 txroad=' '.join(address[:2])+' '+tx['도로명'] if tx['도로명'].strip() not in ('','-') else ''
 road=bool(txroad) and text_norm(txroad)==text_norm(src['kapt도로명주소'])
 a=parcel(tx['번지']);b=parcel(src['나머지주소'] or '')
 same_parcel=dong_equal and a is not None and b is not None and a==b
 year=approval_date(src);txyear=int(tx['건축년도']) if tx['건축년도'].strip().isdigit() else None
 ydiff=None if (year is None or txyear is None) else year.year-txyear
 pa=phases(tx['단지명']);pb=phases(src['k-아파트명'])
 ba=base_name(tx['단지명'],gu,dong);bb=base_name(src['k-아파트명'],gu,dong)
 block=blockers(tx['단지명'],src['k-아파트명'],a,b,dong_equal)
 contain=bool(ba) and bool(bb) and (ba in bb or bb in ba) and min(len(ba),len(bb))>=2
 method=''
 if not block and dong_equal:
  if ydiff==0 and road and road_candidates==1 and pa==pb and ba==bb and ba:
   method='road_year_geo_prefix_supported'
  elif ydiff==0 and road and pa and pa==pb and (contain or not ba or not bb):
   method='road_year_phase_name_supported'
  elif ydiff==0 and not road and ba==bb and len(ba)>=2 and ((pa and pa==pb) or (not pa and not pb and not generic_only(ba) and len(ba)>=3)):
   method='dong_year_phase_name_supported'
  elif ydiff in (-1,1) and road and pa==pb and (ba==bb or same_parcel) and ba:
   method='road_name_year_off_by_one_supported'
  elif ydiff==0 and road and pa and not pb and contain:
   method='road_year_subcomplex_scope_location_only'
  elif ydiff==0 and same_parcel and pa and not pb and contain:
   method='parcel_year_subcomplex_scope_location_only'
 return dict(method=method,road_equal=road,legal_dong_equal=dong_equal,parcel_equal=same_parcel,year_diff='' if ydiff is None else ydiff,tx_phases=','.join(map(str,sorted(pa))),src_phases=','.join(map(str,sorted(pb))),tx_base=ba,src_base=bb,blocking_reasons='|'.join(block))
def main():
 REPORT.mkdir(parents=True,exist_ok=True)
 with (ROOT/'data/raw/seoul_complex.csv').open(encoding='cp949',newline='') as f:sources=list(csv.DictReader(f))
 byroad=collections.Counter(text_norm(s['kapt도로명주소']) for s in sources if s['kapt도로명주소'].strip())
 bydong=collections.defaultdict(list)
 for i,s in enumerate(sources):bydong[(s['주소(시군구)'].strip(),s['주소(읍면동)'].strip())].append(i)
 bygu=collections.defaultdict(list)
 for i,s in enumerate(sources):bygu[s['주소(시군구)'].strip()].append(i)
 with V2.open(encoding='utf-8-sig',newline='') as f:v2=list(csv.DictReader(f))
 out=[];evidence=[];counts=collections.Counter()
 for r in v2:
  row=dict(r,v3_kapt_code=r['new_kapt_code'],v3_match_status=r['new_match_status'],v3_decision='v2_retained' if not r['decision'].startswith('unresolved') else r['decision'],v3_rule='',v3_scope='identity' if r['new_match_status'] in ('address_name_supported','road_year_parcel_supported','road_year_name_alias_supported','parcel_year_name_supported') else '')
  if r['decision'].startswith('unresolved'):
   parts=r['transaction_complex_key'].split('|');tx=dict(zip(['시군구','번지','단지명','도로명','건축년도'],parts))
   address=tx['시군구'].split();gu=address[1] if len(address)>1 else ''
   txroad=' '.join(address[:2])+' '+tx['도로명'] if tx['도로명'].strip() not in ('','-') else ''
   nroad=byroad.get(text_norm(txroad),0) if txroad else 0
   results=[(i,evaluate(tx,sources[i],nroad)) for i in bygu.get(gu,[])]
   results=[(i,e) for i,e in results if e is not None]
   # Keep evidence only for plausible candidates (same road, parcel, dong+base or any method).
   for i,e in results:
    if e['method'] or e['road_equal'] or e['parcel_equal'] or (e['legal_dong_equal'] and e['tx_base'] and e['tx_base']==e['src_base']):
     evidence.append(dict(complex_match_key=r['complex_match_key'],transaction_name=tx['단지명'],transaction_build_year=tx['건축년도'],candidate_kapt_code=sources[i]['k-아파트코드'],candidate_name=sources[i]['k-아파트명'],candidate_road=sources[i]['kapt도로명주소'],candidate_approval=sources[i]['k-사용검사일-사용승인일'][:10],transaction_rows=r['transaction_rows'],**e))
   ident=[(i,e) for i,e in results if e['method'] in IDENTITY_RULES]
   loc=[(i,e) for i,e in results if e['method'] in LOCATION_ONLY_RULES]
   if len(ident)==1 and not loc:
    i,e=ident[0];row.update(v3_kapt_code=sources[i]['k-아파트코드'],v3_match_status=e['method'],v3_decision='v3_rule_supported',v3_rule=e['method'],v3_scope='identity')
   elif not ident and len(loc)==1:
    i,e=loc[0];row.update(v3_kapt_code=sources[i]['k-아파트코드'],v3_match_status=e['method'],v3_decision='v3_location_only',v3_rule=e['method'],v3_scope='location_only')
   elif len(ident)+len(loc)>1:
    row.update(v3_decision='v3_unresolved_multiple_rule_candidates',v3_rule='|'.join(sorted({e['method'] for _,e in ident+loc})))
   if row['v3_decision'].startswith('v3_rule') or row['v3_decision']=='v3_location_only':
    if row['v3_kapt_code']!=r['new_kapt_code'] and r['new_kapt_code']:row['v3_decision']+='_changed_candidate'
  counts[(row['v3_decision'],row['v3_match_status'])]+=int(r['transaction_rows'])
  out.append(row)
 for name,data in [('crosswalk_v3',out),('candidate_evidence_v3',evidence)]:
  with (REPORT/f'{name}.csv').open('w',encoding='utf-8-sig',newline='') as f:
   w=csv.DictWriter(f,fieldnames=list(data[0]));w.writeheader();w.writerows(data)
 changed=[r for r in out if r['v3_decision'].startswith('v3_rule') or r['v3_decision'].startswith('v3_location')]
 with (REPORT/'v3_changes.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=['complex_match_key','transaction_name','transaction_address','transaction_road','transaction_build_year','transaction_rows','new_kapt_code','new_match_status','v3_kapt_code','v3_match_status','v3_decision','v3_scope']
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
  for r in sorted(changed,key=lambda r:-int(r['transaction_rows'])):w.writerow(r)
 summary=dict(input=str(V2.relative_to(ROOT)),input_sha256=hashlib.sha256(V2.read_bytes()).hexdigest(),combos=len(out),transaction_rows=sum(int(r['transaction_rows']) for r in out),
  by_decision={d:dict(combos=sum(1 for r in out if r['v3_decision']==d),rows=sum(int(r['transaction_rows']) for r in out if r['v3_decision']==d)) for d in sorted({r['v3_decision'] for r in out})},
  by_v3_status={s:dict(combos=sum(1 for r in out if r['v3_match_status']==s),rows=sum(int(r['transaction_rows']) for r in out if r['v3_match_status']==s)) for s in sorted({r['v3_match_status'] for r in out})},
  identity_rules=sorted(IDENTITY_RULES),location_only_rules=sorted(LOCATION_ONLY_RULES),v2_decisions_changed=0,prices_used=False,manual_validation_completed=False)
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=1))
if __name__=='__main__':main()
