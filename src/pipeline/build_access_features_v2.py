"""Point-in-time transport/education access features (straight-line Haversine metres).

Input: crosswalk-v3 CSV (complex_point_lon/lat). Output: new versioned CSV + report.
A facility counts only if open_date <= contract_date < close_date. Missing complex point
-> NULL with reason (never 0). Facility dates/coordinates follow config/access_history/README.md.
"""
import csv,hashlib,json,sys,datetime as dt
import numpy as np
from build_internal_features import ROOT,BASE
csv.field_size_limit(sys.maxsize)
BASE=ROOT/'data/processed/seoul_sales_2017_2026'
SOURCE=BASE/'seoul_apt_sales_2017_2026_internal_static_assumption_crosswalk_v3.csv'
OUTPUT=BASE/'seoul_apt_sales_2017_2026_crosswalk_v3_access_v2.csv'
START='2017-01-01';PROXY_FROM='2016-01-01'
REPORT=ROOT/'reports/access_features_v2'
H=ROOT/'config/access_history'
BEFORE='1900-01-01';NEVER='9999-12-31'
GJ_ON_GYEONGWON={'용산역','이촌역','서빙고역','한남역','옥수역','응봉역','왕십리역'}
NEW=['nearest_operating_station_distance_m','operating_line_count_1km','nearest_operating_station_name','nearest_elementary_school_distance_m','nearest_elementary_school_name','access_point_basis','access_feature_status','access_feature_issues','access_history_version']
def service_line(code,name,station):
 if code in('I4101','I1101'):return 'L1'
 if code=='I4102':return 'GJ' if station in GJ_ON_GYEONGWON else 'L1'
 m={'S1102':'L2','S1121':'L2','S1122':'L2','I1103':'L3','I4106':'L3','I1104':'L4','I4103':'L4','I4104':'L4','S1105':'L5','S1106':'L6','S1107':'L7','S1108':'L8','S4108':'L8','S1109':'L9','I41K2':'GC','I4105':'SB','I28K1':'SB','I11D1':'SBD','I28A1':'AREX','L11SL':'SILLIM','L11UI':'UISINSEOL','L41G1':'GIMPO','I41WS':'SEOHAE','L41U1':'UIJEONGBU','S2801':'IC1','S2802':'IC2','I41K5':'GYEONGGANG','GTXA':'GTXA'}
 if code=='I4108':return 'GC' if name=='경춘선' else 'GJ'
 return m[code]
def hav(lat1,lon1,lat2,lon2):
 r=6371008.8;p1=np.radians(lat1)[:,None];p2=np.radians(lat2)[None,:]
 dl=np.radians(lon2)[None,:]-np.radians(lon1)[:,None]
 a=np.sin((p2-p1)/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
 return 2*r*np.arcsin(np.sqrt(a))
def read(p,enc='utf-8-sig'):
 with open(p,encoding=enc,newline='') as f:return list(csv.DictReader(f))
def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def stations():
 base=read(ROOT/'data/raw/kric_stations_bbox_20260630.csv')
 ev={(r['station_no'],r['line_code']):r for r in read(H/'rail_open_events_v2.csv')}
 seen=set();out=[]
 for r in base:
  k=(r['station_no'],r['line_code'],r['station_name'])
  if k in seen:continue
  seen.add(k);e=ev.get((r['station_no'],r['line_code']))
  out.append(dict(name=r['station_name'],line=service_line(r['line_code'],r['line_name'],r['station_name']),lat=float(r['lat']),lon=float(r['lon']),open=e['open_date'] if e else BEFORE,close=NEVER,basis='event_open_date' if e else 'assumed_open_before_2017'))
 used={(r['station_no'],r['line_code']) for r in base}
 missing=[k for k in ev if k not in used]
 if missing:raise ValueError(f'events without station rows: {missing}')
 coords={(r['station_no'],r['line_code']):r for r in base}
 for r in read(H/'rail_added_platforms_v1.csv'):
  c=coords[(r['coordinate_from_station_no'],r['coordinate_from_line_code'])]
  out.append(dict(name=r['station_name'],line='GTXA',lat=float(c['lat']),lon=float(c['lon']),open=r['open_date'],close=NEVER,basis='added_platform_proxy_coordinate'))
 return out
def schools():
 rows=[]
 for p in ['schools_page1.json','schools_page2.json']:rows+=json.loads((ROOT/'data/raw'/p).read_text(encoding='utf-8'))
 out=[]
 for r in rows:
  if r['SCHOOL_SE']!='초등학교' or not r['LATITUDE']:continue
  lat,lon=float(r['LATITUDE']),float(r['LONGITUDE'])
  if not(37.30<lat<37.80 and 126.60<lon<127.35):continue
  fd=r['FOND_DATE'] or BEFORE
  out.append(dict(name=r['SCHOOL_NM'],lat=lat,lon=lon,open=fd if fd>=PROXY_FROM else BEFORE,close=NEVER,basis='fond_date_as_open_proxy' if fd>=PROXY_FROM else 'operating_in_2026_snapshot_assumed_open'))
 for r in read(H/'elementary_school_closures_v2.csv'):
  out.append(dict(name=r['school_name'],lat=float(r['lat']),lon=float(r['lon']),open=BEFORE,close=r['assumed_close_date'],basis='closed_year_assumed_mar01'))
 return out
def periods(fac):
 b=sorted({f['open'] for f in fac}|{f['close'] for f in fac})
 return b
def main():
 REPORT.mkdir(parents=True,exist_ok=True)
 st=stations();sc=schools()
 S=dict(lat=np.array([s['lat'] for s in st]),lon=np.array([s['lon'] for s in st]),open=np.array([s['open'] for s in st]),close=np.array([s['close'] for s in st]))
 C=dict(lat=np.array([s['lat'] for s in sc]),lon=np.array([s['lon'] for s in sc]),open=np.array([s['open'] for s in sc]),close=np.array([s['close'] for s in sc]))
 lines=np.array([s['line'] for s in st])
 with SOURCE.open(encoding='utf-8-sig',newline='') as f:
  reader=csv.DictReader(f);fields=reader.fieldnames
  pts=sorted({(r['complex_point_lat'],r['complex_point_lon']) for r in reader if r['complex_point_lat']})
 pidx={p:i for i,p in enumerate(pts)}
 plat=np.array([float(a) for a,_ in pts]);plon=np.array([float(b) for _,b in pts])
 Dst=hav(plat,plon,S['lat'],S['lon']);Dsc=hav(plat,plon,C['lat'],C['lon'])
 cache={};counts={'rows':0,'with_point':0}
 recent_station={s['name'] for s in st if s['open']>=START}
 boundary_close={s['close'][:4] for s in sc if s['close']!=NEVER}
 with OUTPUT.open('w',encoding='utf-8-sig',newline='') as g:
  w=csv.DictWriter(g,fieldnames=fields+NEW);w.writeheader()
  import collections
  status=collections.Counter();iss=collections.Counter();dist=[];sdist=[];lc=collections.Counter();by_year=collections.defaultdict(collections.Counter);ids=set()
  for r in csv.DictReader(SOURCE.open(encoding='utf-8-sig',newline='')):
   counts['rows']+=1;d=r['contract_date'];out={k:'' for k in NEW};out['access_history_version']='access_v2_2026-11-03'
   key=(r['complex_point_lat'],r['complex_point_lon'])
   if not key[0]:
    out.update(access_point_basis=r['complex_point_basis'],access_feature_status='unavailable_no_complex_point',access_feature_issues='no_complex_link_or_point')
   else:
    counts['with_point']+=1;i=pidx[key]
    ck=(i,d)
    if ck not in cache:
     ms=(S['open']<=d)&(d<S['close']);ds=Dst[i]
     j=int(np.argmin(np.where(ms,ds,np.inf)))
     nl=len(set(lines[ms&(ds<=1000)]))
     mc=(C['open']<=d)&(d<C['close']);dc=Dsc[i];k=int(np.argmin(np.where(mc,dc,np.inf)))
     issues=[]
     if st[j]['basis']=='added_platform_proxy_coordinate':issues.append('nearest_station_proxy_coordinate')
     if any(s['basis']=='added_platform_proxy_coordinate' and ms[n] and ds[n]<=1000 for n,s in enumerate(st)):issues.append('gtx_proxy_platform_within_1km')
     if sc[k]['basis']=='fond_date_as_open_proxy':issues.append('nearest_school_open_date_proxy')
     if d[:4] in boundary_close and d[5:7] in('01','02') and any(s['basis']=='closed_year_assumed_mar01' and s['close'][:4]==d[:4] and dc[n]<=3000 for n,s in enumerate(sc)):issues.append('closure_year_jan_feb_ambiguous')
     cache[ck]=dict(nearest_operating_station_distance_m=f'{ds[j]:.1f}',operating_line_count_1km=str(nl),nearest_operating_station_name=st[j]['name'],nearest_elementary_school_distance_m=f'{dc[k]:.1f}',nearest_elementary_school_name=sc[k]['name'],issues=issues)
    c=cache[ck]
    out.update({k:v for k,v in c.items() if k!='issues'})
    scope=r['complex_link_scope']
    issues=['straight_line_haversine_not_walking','kapt_snapshot_point_not_historical']+(['location_only_complex_link'] if scope=='location_only' else [])+c['issues']
    out.update(access_point_basis=r['complex_point_basis'],access_feature_status='computed',access_feature_issues='|'.join(issues))
   w.writerow(dict(r,**out));x=out;ids.add(r['record_id'])
   status[x['access_feature_status']]+=1;iss.update(i for i in x['access_feature_issues'].split('|') if i)
   if x['nearest_operating_station_distance_m']:dist.append(float(x['nearest_operating_station_distance_m']));sdist.append(float(x['nearest_elementary_school_distance_m']));lc[x['operating_line_count_1km']]+=1
   y=by_year[r['contract_date'][:4]];y['rows']+=1;y['computed']+=x['access_feature_status']=='computed'
 assert len(ids)==counts['rows']
 dist=np.array(dist);sdist=np.array(sdist);res=range(counts['rows'])
 q=lambda a:{p:round(float(np.percentile(a,p)),1) for p in (0,5,25,50,75,95,100)}
 summary=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=sha(SOURCE),output=str(OUTPUT.relative_to(ROOT)),output_sha256=sha(OUTPUT),rows=len(res),unique_record_ids=len(ids),columns=len(fields)+len(NEW),station_platform_rows=len(st),station_rows_with_post2017_open_event=sum(s['basis']!='assumed_open_before_2017' for s in st),elementary_school_points=len(sc),status_rows=dict(status),issue_rows=dict(iss),
  missing_rate_station_distance=round(1-len(dist)/len(res),6),missing_rate_school_distance=round(1-len(sdist)/len(res),6),station_distance_percentiles_m=q(dist),school_distance_percentiles_m=q(sdist),line_count_1km_rows=dict(sorted(lc.items(),key=lambda kv:int(kv[0]))),by_year={k:dict(v) for k,v in sorted(by_year.items())},
  notes=['Straight-line Haversine metres between K-apt snapshot complex point and station/school point; not walking distance.','Stations without an event row are assumed open before 2017-01-01 (KRIC has no opening dates; 2017-2025 openings from rail_open_events_v2).','Elementary schools: FOND_DATE>=2016 used as open-date proxy; closed schools from 폐교알리미 with closure assumed March 1 of closure year.','Rows without complex point are NULL, not 0.'],model_run=False)
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=False,indent=1))
if __name__=='__main__':main()
