"""Readable Korean-column dataset (2020-2026, 356,087 rows) built from crosswalk_v3_access_v1.

- One row per transaction, nothing dropped. Missing values stay empty; the reason is in `결측사유`.
- Source/provenance columns are omitted for readability (they remain in the full working CSV).
- Internal complex values are current snapshots assumed unchanged -> `단지정보_현재값가정`.
- Market statistics (district/complex average price, policy rate) are NOT added (project decision).
"""
import csv,json,sys,collections
import numpy as np
from build_internal_features import ROOT,BASE
from build_access_features_v2 import service_line,hav,read,sha,stations,BEFORE,NEVER,H,PROXY_FROM
csv.field_size_limit(sys.maxsize)
SOURCE=ROOT/'data/processed/seoul_sales_2017_2026/seoul_apt_sales_2017_2026_crosswalk_v3_access_v2.csv'
OUTPUT=ROOT/'data/final/아파트_실거래_전처리_2017_2026.csv'
LINE_KO={'L1':'1호선','L2':'2호선','L3':'3호선','L4':'4호선','L5':'5호선','L6':'6호선','L7':'7호선','L8':'8호선','L9':'9호선','GJ':'경의중앙선','GC':'경춘선','SB':'수인분당선','SBD':'신분당선','AREX':'공항철도','SILLIM':'신림선','UISINSEOL':'우이신설선','GIMPO':'김포골드라인','SEOHAE':'서해선','UIJEONGBU':'의정부경전철','IC1':'인천1호선','IC2':'인천2호선','GYEONGGANG':'경강선','GTXA':'GTX-A'}
HEAT={'individual':'개별난방','district':'지역난방','central':'중앙난방','other':'기타'}
CORR={'staircase':'계단식','corridor':'복도식','mixed':'혼합식','other':'기타'}
FEAT_KO={'household_count':'세대수','parking_per_household':'주차','heating_type':'난방','corridor_type':'복도'}
COLUMNS=['거래ID','자치구','법정동','번지','도로명','단지명','동','층','계약일','계약년월','계약월','계약시점_월순번','건축년도','건물연식','건물연식_구분','사용승인일','연식_개월','연식_기준','전용면적(㎡)','전용면적_평','평형대','거래금액_만원','평당가_만원','위도','경도','최근접_역명','최근접_역_호선','최근접_역_거리(m)','1km내_노선수','최근접_초등학교','최근접_초등학교_거리(m)','1km내_초등학교수','최근접_중학교','최근접_중학교_거리(m)','1km내_중학교수','최근접_고등학교','최근접_고등학교_거리(m)','1km내_고등학교수','세대수','세대당_주차대수','난방방식','복도유형','단지정보_현재값가정','결측사유']
def schools(level):
 rows=[]
 for p in ['schools_page1.json','schools_page2.json']:rows+=json.loads((ROOT/'data/raw'/p).read_text(encoding='utf-8'))
 out=[]
 for r in rows:
  if r['SCHOOL_SE']!=level or not r['LATITUDE']:continue
  lat,lon=float(r['LATITUDE']),float(r['LONGITUDE'])
  if not(37.30<lat<37.80 and 126.60<lon<127.35):continue
  fd=r['FOND_DATE'] or BEFORE
  out.append(dict(name=r['SCHOOL_NM'],lat=lat,lon=lon,open=fd if fd>=PROXY_FROM else BEFORE,close=NEVER))
 f='elementary_school_closures_v2.csv' if level=='초등학교' else 'middle_high_school_closures_v2.csv'
 for r in read(H/f):
  if level=='초등학교' or r['level']==level:out.append(dict(name=r['school_name'],lat=float(r['lat']),lon=float(r['lon']),open=BEFORE,close=r['assumed_close_date']))
 return out
def age_class(a):
 if a=='':return ''
 a=int(a);return '신축(5년이하)' if a<5 else '준신축(5~10년)' if a<10 else '중간(10~20년)' if a<20 else '구축(20년이상)'
def size_class(p):
 return '10평미만' if p<10 else '10~20평' if p<20 else '20~30평' if p<30 else '30~40평' if p<40 else '40평이상'
def internal_reason(r):
 st=r['complex_match_status'];scope=r['complex_link_scope'];ex=r['static_assumption_exclusion_reason']
 if not r['complex_candidate_kapt_code'] or st=='unmatched':return '단지정보 없음(단지 목록에서 이 단지를 찾지 못함)'
 if scope=='location_only' and st!='unique_address_review':return '단지정보 불확실(여러 단지를 묶어 관리하는 단지라 이 단지 값이 따로 없음)'
 if st in('ambiguous','unique_address_review','name_location_review','year_conflict_review'):return '단지정보 불확실(같은 단지인지 확정하지 못함)'
 if 'contract_before_approval' in ex:return '준공 전 거래(분양권·입주권 등)라 단지값 미적용'
 if 'build_year_not_confirmed' in ex:return '건축년도와 단지 준공연도가 달라 단지값 미적용'
 if 'snapshot_building_count' in ex:return '단지 동수 정보가 없어 단지값 미적용'
 return '단지값 미적용'
def main():
 OUTPUT.parent.mkdir(parents=True,exist_ok=True)
 st=stations();Sl=np.array([s['lat'] for s in st]);So=np.array([s['lon'] for s in st]);Sop=np.array([s['open'] for s in st]);Scl=np.array([s['close'] for s in st]);lines=np.array([s['line'] for s in st])
 SS=hav(Sl,So,Sl,So);BN=np.array([s['name'].removesuffix('역').split('(')[0] for s in st])
 sch={lv:schools(lv) for lv in('초등학교','중학교','고등학교')}
 arr={lv:dict(lat=np.array([x['lat'] for x in v]),lon=np.array([x['lon'] for x in v]),op=np.array([x['open'] for x in v]),cl=np.array([x['close'] for x in v])) for lv,v in sch.items()}
 with SOURCE.open(encoding='utf-8-sig',newline='') as f:pts=sorted({(r['complex_point_lat'],r['complex_point_lon']) for r in csv.DictReader(f) if r['complex_point_lat']})
 rows=csv.DictReader(SOURCE.open(encoding='utf-8-sig',newline=''));pidx={p:i for i,p in enumerate(pts)}
 plat=np.array([float(a) for a,_ in pts]);plon=np.array([float(b) for _,b in pts])
 Dst=hav(plat,plon,Sl,So);Dsc={lv:hav(plat,plon,a['lat'],a['lon']) for lv,a in arr.items()}
 cache={};reasons=collections.Counter();miss=collections.Counter();n=0
 with OUTPUT.open('w',encoding='utf-8-sig',newline='') as g:
  w=csv.DictWriter(g,fieldnames=COLUMNS);w.writeheader()
  for r in rows:
   addr=r['시군구'].split();o={c:'' for c in COLUMNS};why=[]
   area=float(r['exclusive_area_m2']);pyeong=area/3.305785;price=int(r['거래금액(만원)'].replace(',','').strip())
   o.update({'거래ID':r['record_id'][:16],'자치구':addr[1],'법정동':' '.join(addr[2:]),'번지':r['번지'],'도로명':r['도로명'] if r['도로명'].strip() not in('','-') else '','단지명':r['단지명'],'동':r['동'] if r['동'].strip() not in('','-') else '','층':r['transaction_floor'],'계약일':r['contract_date'],'계약년월':r['계약년월'],'계약월':r['contract_month'],'계약시점_월순번':str(int(r['contract_time_index'])+36),'건축년도':r['건축년도'],'건물연식':r['building_age_years'],'건물연식_구분':age_class(r['building_age_years']),'전용면적(㎡)':r['exclusive_area_m2'],'전용면적_평':f'{pyeong:.2f}','평형대':size_class(pyeong),'거래금액_만원':str(price),'평당가_만원':f'{price/pyeong:.0f}'})
   if r['building_age_years']=='':why.append('[연식] 건축년도가 계약연도보다 늦게 기록됨')
   ap=r['complex_approval_date_snapshot'];cdt=r['contract_date'];by=r['건축년도'].strip()
   if ap and r['complex_link_scope']=='identity' and ap[:4]==by:
    o['사용승인일']=ap
    if cdt<ap:o['연식_기준']='준공 전 거래';why.append('[연식_개월] 사용승인일 이전 계약(분양권·입주권 등)')
    else:o['연식_개월']=str((int(cdt[:4])-int(ap[:4]))*12+int(cdt[5:7])-int(ap[5:7]));o['연식_기준']='사용승인일'
   elif by.isdigit() and int(by)<=int(cdt[:4]):
    mm=(int(cdt[:4])-int(by))*12+int(cdt[5:7])-7
    o['연식_개월']=str(max(mm,0));o['연식_기준']='건축년도(7월 준공 가정)'+(' 음수→0' if mm<0 else '')
   else:why.append('[연식_개월] 건축년도 이상으로 계산 불가')
   if o['도로명']=='':why.append('[도로명] 원자료에 도로명 없음')
   if o['동']=='':why.append('[동] 원자료에 동 미공개')
   key=(r['complex_point_lat'],r['complex_point_lon'])
   if key[0]:
    i=pidx[key];d=r['contract_date'];ck=(i,d)
    if ck not in cache:
     ms=(Sop<=d)&(d<Scl);ds=Dst[i];j=int(np.argmin(np.where(ms,ds,np.inf)))
     same=ms&(SS[j]<=150)&(BN==BN[j])
     lk=sorted({LINE_KO[x] for x in lines[same]},key=list(LINE_KO.values()).index)
     c={'최근접_역명':st[j]['name'].removesuffix('역').split('(GTX-A)')[0],'최근접_역_호선':', '.join(lk),'최근접_역_거리(m)':f'{ds[j]:.0f}','1km내_노선수':str(len(set(lines[ms&(ds<=1000)])))}
     for lv,pre in(('초등학교','초등학교'),('중학교','중학교'),('고등학교','고등학교')):
      a=arr[lv];m=(a['op']<=d)&(d<a['cl']);dd=Dsc[lv][i];k=int(np.argmin(np.where(m,dd,np.inf)))
      c[f'최근접_{pre}']=sch[lv][k]['name'];c[f'최근접_{pre}_거리(m)']=f'{dd[k]:.0f}';c[f'1km내_{pre}수']=str(int((m&(dd<=1000)).sum()))
     cache[ck]=c
    o.update(cache[ck]);o['위도']=key[0];o['경도']=key[1]
   else:why.append('[입지] 단지 위치를 찾지 못해 위도·경도·역·학교 거리 계산 불가')
   o['세대수']=r['household_count'].split('.')[0] if r['household_count'] else ''
   o['세대당_주차대수']=f"{float(r['parking_per_household']):.2f}" if r['parking_per_household'] else ''
   o['난방방식']=HEAT.get(r['heating_type'],'');o['복도유형']=CORR.get(r['corridor_type'],'')
   filled=[f for f in FEAT_KO if r[f]!='']
   o['단지정보_현재값가정']='예' if filled else ''
   empty=[f for f in FEAT_KO if r[f]=='']
   if empty:
    if len(empty)==4:why.append('[단지정보] '+internal_reason(r))
    else:
     for f in empty:
      b=r[f+'_basis']
      why.append(f'[{FEAT_KO[f]}] '+('기간 중 변경 이력이 의심되어 제외' if b=='excluded_known_change_risk' else '원자료에 값이 없거나 0으로 기재'))
   o['결측사유']=' / '.join(why)
   for x in why:reasons[x.split('] ')[0]+'] '+x.split('] ')[1]]+=1
   for c in COLUMNS:
    if c not in('결측사유','단지정보_현재값가정') and o[c]=='':miss[c]+=1
   w.writerow(o);n+=1
 assert n==617592
 summary=dict(output=str(OUTPUT.relative_to(ROOT)),rows=n,columns=len(COLUMNS),sha256=sha(OUTPUT),missing_by_column={c:miss[c] for c in COLUMNS if miss[c]},missing_rate={c:round(miss[c]/n,4) for c in COLUMNS if miss[c]},reason_rows=dict(reasons.most_common()))
 (ROOT/'reports/korean_dataset_summary_2017_2026.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=1))
if __name__=='__main__':main()
