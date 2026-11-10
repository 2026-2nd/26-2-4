"""Pre-registered market-regime rule (fixed 2026-11-03, before 2017-2019 data are added).

Input: a monthly Seoul apartment price index (official R-ONE preferred; our real-time FE index as cross-check).
Rule (Bry-Boschan style, simplified):
 1. Smooth: 3-month centred moving average (endpoints use available months).
 2. Candidate peak/trough: smoothed value is the max/min within +-6 months.
 3. Alternate peaks and troughs (keep the higher peak / lower trough when two of the same kind are adjacent).
 4. Minimum phase length 6 months; minimum full cycle 15 months (else drop the weaker pair).
 5. Amplitude of a peak->trough phase (raw index):  >=10% -> '하락기', 3~10% -> '조정기', <3% -> merged into surrounding 상승.
 6. After a trough: '회복기' lasts until the index recovers 50% of the preceding peak->trough loss; afterwards '상승기'.
 7. Cell-change windows: peak window = peak month +-3 months, trough window = trough month +-3 months.
"""
import json,sys
import numpy as np,pandas as pd
def turning_points(s:pd.Series,win=6,min_phase=6,min_cycle=15):
 sm=s.rolling(3,center=True,min_periods=1).mean();v=sm.values;n=len(v);tp=[]
 for i in range(n):
  lo,hi=max(0,i-win),min(n,i+win+1)
  if i in(0,n-1):continue
  if v[i]==v[lo:hi].max():tp.append((i,'P'))
  elif v[i]==v[lo:hi].min():tp.append((i,'T'))
 out=[]
 for i,k in tp:
  if out and out[-1][1]==k:
   j=out[-1][0]
   if (k=='P' and v[i]>v[j]) or (k=='T' and v[i]<v[j]):out[-1]=(i,k)
  else:out.append((i,k))
 changed=True
 while changed:
  changed=False
  for a in range(len(out)-1):
   if out[a+1][0]-out[a][0]<min_phase:
    del out[a:a+2];changed=True;break
  for a in range(len(out)-2):
   if out[a+2][0]-out[a][0]<min_cycle and out[a][1]==out[a+2][1]:
    del out[a+1:a+3];changed=True;break
 return out,sm
def label(s:pd.Series):
 tp,sm=turning_points(s);lab=pd.Series('상승기',index=s.index);phases=[]
 for (i,k),(j,k2) in zip(tp,tp[1:]):
  if k=='P' and k2=='T':
   amp=s.iloc[j]/s.iloc[i]-1
   name='하락기' if amp<=-0.10 else ('조정기' if amp<=-0.03 else None)
   if name:
    lab.iloc[i+1:j+1]=name;loss=s.iloc[i]-s.iloc[j];target=s.iloc[j]+0.5*loss
    after=np.where(s.iloc[j+1:].values>=target)[0];end=j+1+after[0] if len(after) else len(s)
    lab.iloc[j+1:end]='회복기';phases.append(dict(peak=str(s.index[i]),trough=str(s.index[j]),amplitude=round(float(amp),4),type=name,recovery_end=str(s.index[end-1]) if end<=len(s) else None))
 return lab,tp,phases
if __name__=='__main__':
 V=np.load(sys.argv[1]);s=pd.Series(np.exp(V[-1,-1,:]),index=pd.period_range('2020-01',periods=V.shape[2],freq='M'))
 lab,tp,ph=label(s)
 print(json.dumps(dict(turning_points=[(str(s.index[i]),k,round(float(s.iloc[i]),3)) for i,k in tp],phases=ph),ensure_ascii=False,indent=1))
 runs=(lab!=lab.shift()).cumsum();print(lab.groupby(runs).agg(lambda x:f'{x.index[0]}~{x.index[-1]} {x.iloc[0]}').to_string(index=False))
