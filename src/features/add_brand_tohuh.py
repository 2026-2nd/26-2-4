"""Brand (builder) and land-transaction-permission-zone (토지거래허가구역) features. 2026-11-07.

Brand
- Source: K-apt complex list (data/raw/seoul_complex.csv, 'k-건설사(시공사)').
- Attached only where the K-apt link passed the identity check
  (household_count_basis != 'missing_match_or_approval_check'), same rule as other complex features.
- 시공사_상위10: builder belongs to the top 10 of the 2025 MOLIT construction capability ranking
  (삼성물산, 현대건설, 대우건설, DL이앤씨, GS건설, 현대엔지니어링, 포스코이앤씨, 롯데건설, SK에코플랜트, HDC현대산업개발),
  including former names (대림산업, LG건설, 포스코건설, SK건설, 현대산업개발 ...). Uses the 2025 ranking for all years
  (a 'current large builder' flag, not point-in-time). Ambiguous names ('현대' alone) stay unmapped.
- 단지명_상위10브랜드: complex name contains a top-10 apartment brand (래미안, 힐스테이트, 디에이치, 푸르지오, 써밋,
  e편한세상, 아크로, 자이, 더샵, 롯데캐슬, 르엘, SK뷰, 아이파크). Available for every trade.

토지거래허가구역 (apartments, contract date on/after effective date)
- R1 잠실·삼성·대치·청담 4개 동 전체 아파트: 2020-06-23 ~ 2025-02-12 (bizwatch 2024-06-13; 서울시 2025-02-12 보도자료)
- R1b 해제 제외 재건축 14곳: 2025-02-13 ~ 2025-03-23 (서울시 2025-02-12). Name-matched; '현대1차' not matched (ambiguous).
- R2 압구정아파트지구(24단지): 2021-04-27 ~ (서울시 2021-04-21; heraldk 2026-04-01 연장 2027-04-26).
     Approximated as 압구정동 apartments with 건축년도 <= 1990.
- R3 여의도아파트지구·인근(16단지): same dates. Approximated as 여의도동 apartments with 건축년도 <= 1980 (16 complexes).
- R4 목동택지개발지구(14단지): same dates. 단지명 '목동신시가지1~14'.
- R5 용산 정비창 인근: 2020-05-20 ~ (MTN 2020-05-14). Only apartment matched: 이촌동 '시범(중산1차)'. Continuation by
     re-designation assumed (approximate).
- R6 강남·서초·송파·용산구 전체 아파트: 2025-03-24 ~ 2026-12-31 (newsis 2025-03-19; 2025-09 1년3개월 연장)
- R7 서울 전역 아파트 (10·15 대책): 2025-10-20 ~ (주간경향 2025-10-15)
- 성수전략정비구역: no apartment complex matched in the trade data; not applied.
Outputs
- data/features/brand_tohuh_by_record.csv (record_id, flags)
- data/features/tohuh_regime_start_by_complex.csv (status at the last day of each regime start month)
"""
import pathlib,re
import numpy as np,pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[2]
SRC=ROOT/'data/processed/seoul_sales_2017_2026/seoul_apt_sales_2017_2026_crosswalk_v3_access_v2.csv'
OUT=ROOT/'data/features';OUT.mkdir(parents=True,exist_ok=True)
TOP10=[('삼성물산',r'삼성물산|삼성건설|삼성종합건설'),('현대건설',r'현대건설'),('대우건설',r'대우건설|대우푸르지오|^대우$'),
 ('DL이앤씨',r'DL이앤씨|디엘이앤씨|대림산업|^대림$'),('GS건설',r'GS건설|지에스건설|LG건설|엘지건설|럭키개발'),
 ('현대엔지니어링',r'현대엔지니어링|현대엠코|^엠코'),('포스코이앤씨',r'포스코이앤씨|포스코건설'),('롯데건설',r'롯데건설'),
 ('SK에코플랜트',r'SK에코플랜트|SK건설|에스케이건설|선경건설'),('HDC현대산업개발',r'현대산업개발|HDC|한국도시개발')]
BRAND=r'래미안|힐스테이트|디에이치|푸르지오|써밋|e편한세상|이편한세상|e-편한세상|이-편한세상|아크로|자이(?!언)|더샵|롯데캐슬|르엘|SK뷰|에스케이뷰|아이파크'
def norm(s):return re.sub(r'\(주\)|주식회사|㈜|\s','',s or '').upper().replace('SK','SK')
def top10(name):
 n=norm(name);hit=[g for g,p in TOP10 if re.search(p,n,flags=re.I)]
 return hit[0] if hit else ''
JSDC={('강남구','삼성동'),('강남구','청담동'),('강남구','대치동'),('송파구','잠실동')}
KEEP14={('대치동',r'^개포우성1$|^개포우성2$|^선경[12]차|^한보미도맨션|^쌍용대치|^대치우성아파트|^은마$'),('삼성동',r'^진흥아파트$'),('청담동',r'^진흥아파트$'),
        ('잠실동',r'^주공아파트 5단지$|^우성아파트$|^우성4차$|^아시아선수촌아파트$')}
D=lambda s:pd.Timestamp(s)
def tohuh(gu,dong,name,by,date):
 """returns rule code ('' if none) for one trade (vectorised over a DataFrame below)"""
 pass
def flag(df,date):
 code=pd.Series('',index=df.index)
 gd=list(zip(df.gu,df.dong))
 in_jsdc=pd.Series([x in JSDC for x in gd],index=df.index)
 keep=pd.Series(False,index=df.index)
 for dn,pat in KEEP14:keep|=(df.dong==dn)&df.name.str.match(pat)
 by=pd.to_numeric(df.by,errors='coerce')
 rules=[('R7',date>=D('2025-10-20')),
  ('R6',df.gu.isin(['강남구','서초구','송파구','용산구'])&(date>=D('2025-03-24'))),
  ('R1',in_jsdc&(date>=D('2020-06-23'))&(date<=D('2025-02-12'))),
  ('R1b',in_jsdc&keep&(date>=D('2025-02-13'))&(date<=D('2025-03-23'))),
  ('R2',(df.gu=='강남구')&(df.dong=='압구정동')&(by<=1990)&(date>=D('2021-04-27'))),
  ('R3',(df.gu=='영등포구')&(df.dong=='여의도동')&(by<=1980)&(date>=D('2021-04-27'))),
  ('R4',df.name.str.match(r'^목동신시가지\d+$')&(date>=D('2021-04-27'))),
  ('R5',(df.gu=='용산구')&(df.dong=='이촌동')&(df.name=='시범(중산1차)')&(date>=D('2020-05-20')))]
 for c,m in reversed(rules):code=code.mask(m.fillna(False),c)
 return code
def main():
 cols=['record_id','시군구','번지','단지명','건축년도','contract_date','complex_candidate_kapt_code','household_count_basis']
 d=pd.read_csv(SRC,dtype=str,keep_default_na=False,encoding='utf-8-sig',usecols=cols)
 sp=d.시군구.str.split();d['gu']=sp.str[1];d['dong']=sp.str[2];d['name']=d.단지명;d['by']=d.건축년도
 k=pd.read_csv(ROOT/'data/raw/seoul_complex.csv',dtype=str,encoding='cp949')
 k['g']=k['k-건설사(시공사)'].fillna('').map(top10);k['bn']=k['k-건설사(시공사)'].fillna('').map(norm)
 kk=k.set_index('k-아파트코드')
 ok=(d.complex_candidate_kapt_code!='')&(d.household_count_basis!='missing_match_or_approval_check')
 code=d.complex_candidate_kapt_code.where(ok)
 out=pd.DataFrame({'record_id':d.record_id,'거래ID':d.record_id.str[:16]})
 out['시공사']=code.map(kk['bn']).fillna('')
 out['시공사_상위10그룹']=code.map(kk['g']).fillna('')
 out['시공사_상위10']=np.where(code.notna()&(out.시공사!=''),(out.시공사_상위10그룹!='').astype(int).astype(str),'')
 out['단지명_상위10브랜드']=d.단지명.str.contains(BRAND,regex=True).astype(int)
 date=pd.to_datetime(d.contract_date)
 out['토허_근거']=flag(d,date);out['토지거래허가구역']=(out.토허_근거!='').astype(int)
 out.to_csv(OUT/'brand_tohuh_by_record.csv',index=False,encoding='utf-8-sig')
 # regime-start status (last day of boundary month a) per complex
 comp=d.drop_duplicates(['시군구','번지','단지명'])[['시군구','번지','단지명','gu','dong','name','by']].reset_index(drop=True)
 rows=[]
 for reg,a in [('상승기①','2017-01'),('조정기','2018-10'),('상승기②','2019-04'),('하락기','2021-10'),('회복기','2023-01'),('상승기③','2024-07')]:
  dt=pd.Period(a,'M').end_time.normalize();c=flag(comp,pd.Series(dt,index=comp.index))
  rows.append(comp[['시군구','번지','단지명']].assign(국면=reg,기준일=str(dt.date()),토허_근거=c,토지거래허가구역=(c!='').astype(int)))
 rs=pd.concat(rows);rs.to_csv(OUT/'tohuh_regime_start_by_complex.csv',index=False,encoding='utf-8-sig')
 # report
 print('rows',len(out))
 print('시공사 attached',(out.시공사!='').mean().round(4),' 상위10 among attached',(out.시공사_상위10=='1').sum()/(out.시공사_상위10!='').sum())
 print(out.시공사_상위10그룹.value_counts().to_string())
 print('단지명 브랜드',out.단지명_상위10브랜드.mean().round(4))
 print(pd.crosstab(out.시공사_상위10,out.단지명_상위10브랜드).to_string())
 un=out[(out.시공사!='')&(out.시공사_상위10=='0')].시공사.value_counts().head(25);print('unmapped top builders\n',un.to_string())
 print(out.토허_근거.value_counts().to_string())
 print(rs.groupby('국면').토지거래허가구역.sum().to_string())
 print(rs[rs.토지거래허가구역==1].groupby(['국면','토허_근거']).size().to_string())
if __name__=='__main__':main()
