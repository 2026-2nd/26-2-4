"""Complex-cluster bootstrap of the main FE index and the fixed regime rule (B reps, seed 20261103)."""
import json,pathlib,sys
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src/regime'))
from turning_points import label
SRC=ROOT/'data/processed/seoul_sales_2017_2026/seoul_apt_sales_2017_2026_crosswalk_v3_access_v2.csv'
B=int(sys.argv[1]) if len(sys.argv)>1 else 200
d=pd.read_csv(SRC,dtype=str,keep_default_na=False,encoding='utf-8-sig',usecols=['시군구','번지','단지명','거래금액(만원)','contract_date','exclusive_area_m2'])
date=pd.to_datetime(d.contract_date);m=((date.dt.year-2017)*12+date.dt.month-1).values;M=m.max()+1
idx=pd.period_range('2017-01',periods=M,freq='M')
area=d.exclusive_area_m2.astype(float).values;y=np.log(d['거래금액(만원)'].str.replace(',','').astype(float).values/area)
cx=pd.Series(d.시군구+'|'+d.번지+'|'+d.단지명).astype('category').cat.codes.values
cell=pd.Series(cx.astype(str)+'#'+pd.Series(np.round(area).astype(int)).astype(str)).astype('category').cat.codes.values
_,cinv=np.unique(cell,return_inverse=True);NC=cinv.max()+1;NX=cx.max()+1
def fe(w,iters=60):
 cw=np.bincount(cinv,w,minlength=NC);mw=np.bincount(m,w,minlength=M);mf=np.zeros(M)
 for _ in range(iters):
  cf=np.bincount(cinv,w*(y-mf[m]),minlength=NC)/np.maximum(cw,1e-12)
  mf=np.bincount(m,w*(y-cf[cinv]),minlength=M)/np.maximum(mw,1e-12);mf=mf-mf[0]
 return mf
rng=np.random.default_rng(20261103);out=[]
for b in range(B):
 w=np.bincount(rng.integers(0,NX,NX),minlength=NX)[cx].astype(float)
 s=pd.Series(np.exp(fe(w)),index=idx);lab,tp,ph=label(s)
 out.append(dict(phases=ph,turning=[(str(idx[i]),k) for i,k in tp],
  dip=float(s['2019-04']/s['2018-10']-1),bust=float(s['2023-01']/s['2021-09']-1)))
 if b%20==0:print(b,flush=True)
(ROOT/'data/regime/bootstrap_regime.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')
