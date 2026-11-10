"""Compare the in-house transaction index with official Seoul apartment indices and fix final regimes.

Inputs (data/external/, collected 2026-11-04 from R-ONE 부동산통계정보시스템, 한국부동산원):
  rone_apt_trade_index_seoul_raw.csv  : 공동주택 실거래가격지수(아파트) 지역별 매매지수, 월간, A_2024_00178, 2015-01..2026-08
  rone_apt_survey_index_seoul_raw.csv : 전국주택가격동향조사 매매가격지수(아파트), 월간, A_2024_00045, 2015-01..2026-09
  (both published with base 2026-06 = 100; values as displayed, 1 or 2 decimals)
Rule: src/regime/turning_points.py (unchanged).
Output: data/regime/official_comparison.json
"""
import json,pathlib,sys
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'src/regime'))
from turning_points import label
EXT=ROOT/'data/external'
def load(p):
 d=pd.read_csv(p,dtype={'ym':str});d.index=pd.PeriodIndex(pd.to_datetime(d.ym,format='%Y%m'),freq='M');return d.drop(columns='ym')
def runs(lab):
 r=(lab!=lab.shift()).cumsum();return [dict(phase=g.iloc[0],start=str(g.index[0]),end=str(g.index[-1])) for _,g in lab.groupby(r)]
def main():
 own=pd.read_csv(ROOT/'data/regime/seoul_index_2017_2026.csv',index_col=0);own.index=pd.PeriodIndex(own.index,freq='M')
 tr=load(EXT/'rone_apt_trade_index_seoul_raw.csv');sv=load(EXT/'rone_apt_survey_index_seoul_raw.csv')
 out={'seoul':{},'zones':{},'corr':{}}
 for k,s in [('own',own['main']),('rone_trade',tr['서울']),('rone_survey',sv['서울'])]:
  s=s['2017-01':];lab,tp,ph=label(s);out['seoul'][k]=dict(last=str(s.index[-1]),runs=runs(lab),phases=ph)
 j=pd.concat([np.log(own['main']).diff(),np.log(tr['서울']).diff(),np.log(sv['서울']).diff()],axis=1,keys=['own','trade','survey'])['2017-02':].dropna()
 out['corr']=dict(months=len(j),matrix=j.corr().round(3).to_dict(),own_vs_survey_lag1=round(j.own.corr(j.survey.shift(-1)),3))
 for z in ['도심권','동북권','서북권','서남권','동남권']:
  zz={}
  for k,s in [('own',own[z]),('rone_trade',tr[z]),('rone_survey',sv[z])]:
   s=s['2017-01':];lab,tp,ph=label(s);zz[k]=ph
  zz['corr_own_trade']=round(np.log(own[z]).diff().corr(np.log(tr[z]).diff()),3);out['zones'][z]=zz
 # final regimes: official transaction index boundaries; 2019-05~06 recovery merged into the following upturn
 final=[('상승기①','2017-01','2018-10'),('조정기','2018-11','2019-04'),('상승기②','2019-05','2021-10'),('하락기','2021-11','2023-01'),('회복기','2023-02','2024-07'),('상승기③','2024-08',None)]
 rows=[]
 for name,a,b in final:
  pa=pd.Period(a,'M')-1 if a!='2017-01' else pd.Period(a,'M')
  def chg(s,b=b):
   e=pd.Period(b,'M') if b else s.dropna().index[-1]
   return round(float(s[e]/s[pa]-1)*100,1),str(e)
  rows.append(dict(regime=name,start=a,end=b or '진행 중',rone_trade=chg(tr['서울']),own=chg(own['main'])))
 out['final']=rows
 (ROOT/'data/regime/official_comparison.json').write_text(json.dumps(out,ensure_ascii=False,indent=1),encoding='utf-8')
 for r in rows:print(r)
 print(out['corr'])
if __name__=='__main__':main()
