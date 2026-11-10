"""Pilot (2026-11-04): is 'resilience' just location?

For a regime (peak -> trough), each cell (complex x rounded m2) gets
  y = [median time-adjusted log price/m2 in end window] - [same in start window]
with each trade adjusted to the boundary month by the in-house Seoul FE index, so y is the cell's
change relative to Seoul. Windows = boundary month +-3.
Then: variance decomposition (gu / dong / within-dong), and out-of-sample checks with GroupKFold by legal dong.
"""
import json,pathlib,sys
import numpy as np,pandas as pd
from sklearn.linear_model import RidgeCV
from sklearn.model_selection import GroupKFold
ROOT=pathlib.Path(__file__).resolve().parents[2]
SRC=ROOT/'data/processed/seoul_sales_2017_2026/seoul_apt_sales_2017_2026_crosswalk_v3_access_v2.csv'
REG={'하락기':('2021-10','2023-01'),'상승기②':('2019-04','2021-10'),'회복기':('2023-01','2024-07')}
MINN=int(sys.argv[1]) if len(sys.argv)>1 else 1
cols=['시군구','번지','단지명','건축년도','거래금액(만원)','contract_date','exclusive_area_m2','transaction_floor','household_count','parking_per_household','nearest_operating_station_distance_m','operating_line_count_1km','nearest_elementary_school_distance_m','complex_point_lat']
d=pd.read_csv(SRC,dtype=str,keep_default_na=False,encoding='utf-8-sig',usecols=cols)
idx=pd.read_csv(ROOT/'data/regime/seoul_index_2017_2026.csv',index_col=0)['main'];LI=np.log(idx)
d['m']=pd.to_datetime(d.contract_date).dt.strftime('%Y-%m')
d['area']=d.exclusive_area_m2.astype(float);d['lup']=np.log(d['거래금액(만원)'].str.replace(',','').astype(float)/d.area)
d['gu']=d.시군구.str.split().str[1];d['dong']=d.시군구
d['cell']=d.시군구+'|'+d.번지+'|'+d.단지명+'#'+np.round(d.area).astype(int).astype(str)
for c,s in [('floor','transaction_floor'),('build','건축년도'),('hh','household_count'),('park','parking_per_household'),('st','nearest_operating_station_distance_m'),('lines','operating_line_count_1km'),('sch','nearest_elementary_school_distance_m')]:
 d[c]=pd.to_numeric(d[s],errors='coerce')
per=pd.PeriodIndex(d.m,freq='M')
def cell_y(a,b):
 pa,pb=pd.Period(a,'M'),pd.Period(b,'M')
 def agg(c):
  w=d[(per>=c-3)&(per<=c+3)].copy();w['adj']=w.lup-w.m.map(LI)+LI[str(c)]
  return w.groupby('cell').agg(v=('adj','median'),n=('adj','size'),floor=('floor','median'))
 s,e=agg(pa),agg(pb);j=s.join(e,lsuffix='_s',rsuffix='_e',how='inner')
 j['y']=(j.v_e-j.v_s-(LI[str(pb)]-LI[str(pa)]))*100
 st=d.drop_duplicates('cell').set_index('cell')[['gu','dong','area','build','hh','park','st','lines','sch']]
 j=j.join(st);j['age']=pa.year-j.build
 return j[(j.n_s>=MINN)&(j.n_e>=MINN)]
def r2(y,yh,w):return 1-np.sum(w*(y-yh)**2)/np.sum(w*(y-np.average(y,weights=w))**2)
out={}
for name,(a,b) in REG.items():
 j=cell_y(a,b);j=j[j.y.abs()<60]  # drop extreme (likely mismatched cells)
 w=np.minimum(j.n_s,j.n_e).astype(float);y=j.y.values
 # variance decomposition (weighted, in-sample)
 gu_m=j.groupby('gu').apply(lambda g:np.average(g.y,weights=np.minimum(g.n_s,g.n_e))) ;yg=j.gu.map(gu_m).values
 dong_m=j.groupby('dong').apply(lambda g:np.average(g.y,weights=np.minimum(g.n_s,g.n_e)));yd=j.dong.map(dong_m).values
 res={'cells':len(j),'mean_y':round(float(np.average(y,weights=w)),2),'sd_y':round(float(np.sqrt(np.cov(y,aweights=w))),2),
      'R2_gu_in':round(r2(y,yg,w),3),'R2_dong_in':round(r2(y,yd,w),3)}
 # within-dong: features after removing dong means (complete-case)
 F=['area','floor_s','age','hh','park','st','lines','sch']
 k=j.dropna(subset=['age','hh','park','st','sch']).copy();k=k[k.age>=0]
 k['l_area']=np.log(k.area);k['l_hh']=np.log(k.hh.clip(lower=1));k['l_st']=np.log(k.st.clip(lower=50));k['age30']=(k.age>=30).astype(float)
 X=['l_area','floor_s','age','age30','l_hh','park','l_st','lines','sch']
 kw=np.minimum(k.n_s,k.n_e).astype(float)
 ky=k.y-k.groupby('dong').y.transform('mean');kX=k[X]-k.groupby('dong')[X].transform('mean')
 kXs=(kX-kX.mean())/kX.std()
 beta,*_=np.linalg.lstsq(kXs.values*np.sqrt(kw.values)[:,None],ky.values*np.sqrt(kw.values),rcond=None)
 res['within_dong_cells']=len(k);res['R2_features_within_dong_in']=round(r2(ky.values,kXs.values@beta,kw.values),3)
 res['within_dong_std_coef(%p per 1sd)']={x:round(float(b_),2) for x,b_ in zip(X,beta)}
 # out-of-sample by held-out dongs: gu-only vs gu+features (Ridge), complete-case sample
 G=pd.get_dummies(k.gu).astype(float);Z=pd.concat([G,(k[X]-k[X].mean())/k[X].std()],axis=1)
 gkf=GroupKFold(5);pred_g=np.zeros(len(k));pred_f=np.zeros(len(k));pred_0=np.zeros(len(k))
 for tr,te in gkf.split(Z,k.y,k.dong):
  m1=RidgeCV(alphas=np.logspace(-2,3,12)).fit(G.iloc[tr],k.y.iloc[tr],sample_weight=kw.iloc[tr]);pred_g[te]=m1.predict(G.iloc[te])
  m2=RidgeCV(alphas=np.logspace(-2,3,12)).fit(Z.iloc[tr],k.y.iloc[tr],sample_weight=kw.iloc[tr]);pred_f[te]=m2.predict(Z.iloc[te])
  pred_0[te]=np.average(k.y.iloc[tr],weights=kw.iloc[tr])
 res['oos_R2_gu_only']=round(r2(k.y.values,pred_g,kw.values),3);res['oos_R2_gu_plus_features']=round(r2(k.y.values,pred_f,kw.values),3)
 from scipy.stats import spearmanr
 res['oos_spearman_gu_only']=round(spearmanr(pred_g,k.y).correlation,3);res['oos_spearman_gu_plus_features']=round(spearmanr(pred_f,k.y).correlation,3)
 # split-half reliability for cells with >=2 trades in each window (noise ceiling)
 out[name]=res
print(json.dumps(out,ensure_ascii=False,indent=1))
(ROOT/f'data/regime/pilot_location_vs_features_min{MINN}.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
