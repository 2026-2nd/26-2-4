"""Seoul apartment monthly price indices 2017-01..2026-10 from MOLIT transactions, and regime labels.

Main index  : log(price/m2) = cell FE (complex x rounded m2) + month FE, full sample (ex-post, for regime dating).
Alternatives: (B) median log price/m2 per month (raw, composition-sensitive)
              (C) cell FE with coarse cells (legal dong x area band x build-year band)
              (D) main spec estimated on 2020-01.. only (consistency with the earlier 2020-2026 run)
              (E) main spec excluding trades marked 직거래
              (R) main spec per Seoul living zone (5 권역)
Regime rule : src/regime/turning_points.py (fixed 2026-11-03, before 2017-2019 data were added). Not modified here.
"""
import json,pathlib,sys
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/regime'))
from turning_points import label
SRC=ROOT/'data/processed/seoul_sales_2017_2026/seoul_apt_sales_2017_2026_crosswalk_v3_access_v2.csv'
OUT=ROOT/'data/regime';OUT.mkdir(parents=True,exist_ok=True)
ZONE={'종로구':'도심권','중구':'도심권','용산구':'도심권',
 '성동구':'동북권','광진구':'동북권','동대문구':'동북권','중랑구':'동북권','성북구':'동북권','강북구':'동북권','도봉구':'동북권','노원구':'동북권',
 '은평구':'서북권','서대문구':'서북권','마포구':'서북권',
 '양천구':'서남권','강서구':'서남권','구로구':'서남권','금천구':'서남권','영등포구':'서남권','동작구':'서남권','관악구':'서남권',
 '서초구':'동남권','강남구':'동남권','송파구':'동남권','강동구':'동남권'}
def fe(cell,month,y,M,iters=60):
 cu,cinv=np.unique(cell,return_inverse=True);cnt=np.bincount(month,minlength=M);mf=np.zeros(M)
 for _ in range(iters):
  cf=np.bincount(cinv,y-mf[month])/np.bincount(cinv)
  mf=np.where(cnt>0,np.bincount(month,y-cf[cinv],minlength=M)/np.maximum(cnt,1),np.nan)
  mf=pd.Series(mf).interpolate(limit_direction='both').values;mf=mf-mf[0]
 return mf,cnt
def runs(lab):
 r=(lab!=lab.shift()).cumsum()
 return [dict(phase=g.iloc[0],start=str(g.index[0]),end=str(g.index[-1]),months=len(g)) for _,g in lab.groupby(r)]
def regime(logidx,idx):
 s=pd.Series(np.exp(logidx),index=idx);lab,tp,ph=label(s)
 return dict(turning_points=[(str(s.index[i]),k,round(float(s.iloc[i]),4)) for i,k in tp],phases=ph,runs=runs(lab)),lab
def main():
 cols=['시군구','번지','단지명','건축년도','거래금액(만원)','거래유형','contract_date','exclusive_area_m2']
 d=pd.read_csv(SRC,dtype=str,keep_default_na=False,encoding='utf-8-sig',usecols=cols)
 date=pd.to_datetime(d.contract_date);per=date.dt.to_period('M')
 idx=pd.period_range('2017-01',per.max(),freq='M');M=len(idx);m=((date.dt.year-2017)*12+date.dt.month-1).values
 area=d.exclusive_area_m2.astype(float).values;price=d['거래금액(만원)'].str.replace(',','').astype(float).values
 y=np.log(price/area);gu=d.시군구.str.split().str[1].values;dong=d.시군구.str.split().str[2].values
 zone=pd.Series(gu).map(ZONE).values;assert not pd.isna(zone).any()
 cell=pd.Series(d.시군구+'|'+d.번지+'|'+d.단지명+'#'+pd.Series(np.round(area).astype(int)).astype(str)).astype('category').cat.codes.values
 by=pd.to_numeric(d.건축년도,errors='coerce').fillna(0).values
 coarse=pd.Series(pd.Series(gu)+'|'+pd.Series(dong)+'|'+pd.Series(np.digitize(area,[40,60,85,102,135])).astype(str)+'|'+pd.Series((by//5).astype(int)).astype(str)).astype('category').cat.codes.values
 res={};L={}
 L['main'],cnt=fe(cell,m,y,M)
 med=pd.Series(y).groupby(m).median().reindex(range(M)).values;L['median']=med-med[0]
 L['coarse'],_=fe(coarse,m,y,M)
 k20=m>=36;f20,_=fe(cell[k20],m[k20]-36,y[k20],M-36);L['from2020']=np.r_[np.full(36,np.nan),f20]
 nd=(d.거래유형!='직거래').values;L['no_direct'],_=fe(cell[nd],m[nd],y[nd],M)
 for z in ['도심권','동북권','서북권','서남권','동남권']:
  k=zone==z;L[z],_=fe(cell[k],m[k],y[k],M)
 tab=pd.DataFrame({k:np.exp(v)*100 for k,v in L.items()},index=idx.astype(str));tab['거래건수']=cnt
 tab.round(3).to_csv(OUT/'seoul_index_2017_2026.csv',encoding='utf-8-sig')
 labs={}
 for k,v in L.items():
  if k=='from2020':r,lab=regime(v[36:],idx[36:])
  else:r,lab=regime(v,idx)
  res[k]=r;labs[k]=lab
 pd.DataFrame({k:v.reindex(idx) for k,v in labs.items()}).to_csv(OUT/'regime_labels_2017_2026.csv',encoding='utf-8-sig')
 res['meta']=dict(rows=int(len(d)),months=M,first=str(idx[0]),last=str(idx[-1]),cells=int(cell.max()+1),direct_marked=int((~nd).sum()),source=str(SRC.relative_to(ROOT)))
 (OUT/'regime_results_2017_2026.json').write_text(json.dumps(res,ensure_ascii=False,indent=1),encoding='utf-8')
 for k in L:print(k,[(r['phase'],r['start'],r['end']) for r in res[k]['runs']])
 print(json.dumps({k:res[k]['phases'] for k in ['main','coarse','median','from2020','no_direct']},ensure_ascii=False))
if __name__=='__main__':main()
