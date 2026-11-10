"""Attach Kakao geocoded address points to trades without a complex point, then rebuild access features
and the Korean dataset (v3). 2026-11-08.

- Match key: (시군구, 번지, 단지명) of the geocoding target list.
- Geocoded rows: complex_point_basis = 'kakao_address_point' (address point, not the complex centroid).
- 37 addresses not found (358 trades): kept, complex_point empty, basis = 'address_lost_presumed'
  (presumably lost through redevelopment or lot split/merge). They are excluded from modelling samples.
Outputs
- data/processed/.../seoul_apt_sales_2017_2026_internal_static_assumption_crosswalk_v3_geo.csv
- data/processed/.../seoul_apt_sales_2017_2026_crosswalk_v3_geo_access_v3.csv (access features recomputed)
- data/final/아파트_실거래_전처리_2017_2026_v3.csv (Korean dataset + 좌표기준 + brand/토허 columns)
"""
import csv,sys,json,collections,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src'/'pipeline'))
csv.field_size_limit(sys.maxsize)
BASE=ROOT/'data/processed/seoul_sales_2017_2026'
SRC=BASE/'seoul_apt_sales_2017_2026_internal_static_assumption_crosswalk_v3.csv'
GEO_SRC=BASE/'seoul_apt_sales_2017_2026_internal_static_assumption_crosswalk_v3_geo.csv'
ACC=BASE/'seoul_apt_sales_2017_2026_crosswalk_v3_geo_access_v3.csv'
KO=ROOT/'data/final/아파트_실거래_전처리_2017_2026_v3.csv'
G=ROOT/'data/geocoding/kakao_geocode_results.csv'
def step1():
 g={};lost=set()
 for r in csv.DictReader(G.open(encoding='utf-8-sig')):
  k=(r['시군구'],r['번지'],r['단지명'])
  if r['상태']=='성공':g[k]=(r['위도'],r['경도'])
  else:lost.add(k)
 c=collections.Counter()
 with SRC.open(encoding='utf-8-sig',newline='') as f,GEO_SRC.open('w',encoding='utf-8-sig',newline='') as h:
  rd=csv.DictReader(f);w=csv.DictWriter(h,fieldnames=rd.fieldnames);w.writeheader()
  for r in rd:
   if not r['complex_point_lat']:
    k=(r['시군구'],r['번지'],r['단지명'])
    if k in g:r['complex_point_lat'],r['complex_point_lon']=g[k];r['complex_point_basis']='kakao_address_point';c['geocoded']+=1
    elif k in lost:r['complex_point_basis']='address_lost_presumed';c['lost']+=1
    else:c['still_missing_other']+=1
   else:c['had_point']+=1
   w.writerow(r)
 print('step1',dict(c));return c
def step2():
 import build_access_features_v2 as A
 A.SOURCE=GEO_SRC;A.OUTPUT=ACC;A.REPORT=ROOT/'reports/access_features_v3_geo';A.main()
def step3():
 import build_korean_dataset_v2 as K
 K.SOURCE=ACC;K.OUTPUT=KO.with_name('_tmp_ko_v3.csv');K.main()
def step4():
 import pandas as pd,hashlib
 d=pd.read_csv(KO.with_name('_tmp_ko_v3.csv'),dtype=str,keep_default_na=False,encoding='utf-8-sig')
 a=pd.read_csv(ACC,dtype=str,keep_default_na=False,encoding='utf-8-sig',usecols=['record_id','complex_point_basis'])
 a['거래ID']=a.record_id.str[:16];a=a.set_index('거래ID').complex_point_basis
 basis=d.거래ID.map(a)
 d.insert(d.columns.get_loc('경도')+1,'좌표기준',basis.map({'kakao_address_point':'주소 지점(지오코딩)','address_lost_presumed':''}).fillna('단지 대표점').where(d.위도!='',''))
 lost=basis=='address_lost_presumed'
 d.loc[lost,'결측사유']=d.loc[lost,'결측사유'].str.replace('[입지] 단지 위치를 찾지 못해 위도·경도·역·학교 거리 계산 불가','[입지] 주소 소실 추정(재건축·번지 변경 등)으로 좌표를 찾지 못해 역·학교 거리 계산 불가',regex=False)
 b=pd.read_csv(ROOT/'data/features/brand_tohuh_by_record.csv',dtype=str,keep_default_na=False,encoding='utf-8-sig').set_index('거래ID')
 for c in ['시공사','시공사_상위10','단지명_상위10브랜드','토지거래허가구역']:d[c]=d.거래ID.map(b[c])
 d.to_csv(KO,index=False,encoding='utf-8-sig');KO.with_name('_tmp_ko_v3.csv').unlink()
 print('step4',d.shape,hashlib.sha256(KO.read_bytes()).hexdigest())
 print(d.좌표기준.value_counts().to_string())
 for c in ['위도','최근접_역_거리(m)','최근접_초등학교_거리(m)','세대수','시공사']:print(c,'missing',round((d[c]=='').mean()*100,2),'%')
if __name__=='__main__':
 step1();step2();step3();step4()
