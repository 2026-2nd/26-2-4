"""Append only the three agreed location/time controls to unit-feature records.

No price history, price indices, volume proxies, or model fitting are included.
"""
import collections,csv,datetime as dt,hashlib,json,pathlib,re
ROOT=pathlib.Path(__file__).resolve().parents[2]
SOURCE=ROOT/'data/processed/seoul_sales_2020_2026/seoul_apt_sales_2020_2026_unit_features.csv'
OUTPUT=SOURCE.with_name('seoul_apt_sales_2020_2026_unit_market_features.csv')
REPORT=ROOT/'reports/market_features'
CODEBOOK=ROOT/'data/raw/region_codes/molit_seoul_districts.json'
FEATURES=['district_code','contract_month','contract_time_index']
ADDED=FEATURES+['market_feature_status','market_feature_issues','district_code_basis']
def derive(row,mapping):
 issues=[];district='';month='';trend=''
 address=row.get('시군구','').split()
 if len(address)>=2 and address[0]=='서울특별시' and address[1] in mapping:district=mapping[address[1]]
 else:issues.append('district_address_unmapped')
 try:
  raw=row.get('contract_date','')
  if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',raw):raise ValueError()
  date=dt.date.fromisoformat(raw)
  if row.get('계약년월')!=date.strftime('%Y%m') or int(row.get('계약일',''))!=date.day:
   issues.append('contract_date_source_conflict')
  else:month=date.month;trend=(date.year-2020)*12+date.month-1
 except (ValueError,TypeError):issues.append('contract_date_invalid')
 return dict(district_code=district,contract_month=month,contract_time_index=trend,market_feature_status='incomplete' if issues else 'complete',market_feature_issues='|'.join(issues),district_code_basis='source_address_name_to_current_official_code' if district else 'unknown')
def main():
 REPORT.mkdir(parents=True,exist_ok=True)
 unit_summary=json.loads((ROOT/'reports/unit_features/summary.json').read_text(encoding='utf-8'))
 if hashlib.sha256(SOURCE.read_bytes()).hexdigest()!=unit_summary['output_sha256']:raise ValueError('Unit-feature source changed')
 entries=json.loads(CODEBOOK.read_text(encoding='utf-8'));mapping={str(r['signguNm']):str(r['signguCode']) for r in entries}
 if len(mapping)!=25 or len(set(mapping.values()))!=25 or not all(re.fullmatch(r'11\d{3}',x) for x in mapping.values()):raise ValueError('Invalid district mapping')
 code_meta=json.loads(CODEBOOK.with_suffix('.meta.json').read_text(encoding='utf-8'))
 if hashlib.sha256(CODEBOOK.read_bytes()).hexdigest()!=code_meta['sha256']:raise ValueError('Codebook hash mismatch')
 ids=set();year_counts=collections.Counter();district_counts=collections.Counter();month_counts=collections.Counter();issues=collections.Counter();status=collections.Counter();missing=collections.Counter();n=0
 bounds={k:[None,None] for k in ['contract_month','contract_time_index']}
 with SOURCE.open(encoding='utf-8-sig',newline='') as f,OUTPUT.open('w',encoding='utf-8-sig',newline='') as g,(REPORT/'rows_for_review.csv').open('w',encoding='utf-8-sig',newline='') as h:
  reader=csv.DictReader(f)
  if set(reader.fieldnames)&set(ADDED):raise ValueError('Input already contains market features')
  writer=csv.DictWriter(g,fieldnames=reader.fieldnames+ADDED);writer.writeheader()
  audit=csv.DictWriter(h,fieldnames=['record_id','contract_date','시군구','market_feature_issues']);audit.writeheader()
  for row in reader:
   n+=1
   if row['record_id'] in ids:raise ValueError('Duplicate record ID')
   ids.add(row['record_id']);derived=derive(row,mapping);writer.writerow(dict(row,**derived))
   status[derived['market_feature_status']]+=1
   year_counts[row['contract_date'][:4]]+=1;district_counts[derived['district_code']]+=1;month_counts[row['contract_date'][:7]]+=1
   for feature in FEATURES:
    value=derived[feature]
    if value=='':missing[feature]+=1
    elif feature in bounds:
     lo,hi=bounds[feature];bounds[feature]=[value if lo is None else min(lo,value),value if hi is None else max(hi,value)]
   if derived['market_feature_issues']:
    for reason in derived['market_feature_issues'].split('|'):issues[reason]+=1
    audit.writerow(dict(record_id=row['record_id'],contract_date=row['contract_date'],시군구=row['시군구'],market_feature_issues=derived['market_feature_issues']))
 if n!=unit_summary['output_rows']:raise ValueError('Row count changed')
 if dict(year_counts)!={year:counts['rows'] for year,counts in unit_summary['by_year'].items()}:raise ValueError('Year counts changed')
 summary=dict(source=str(SOURCE.relative_to(ROOT)),source_sha256=unit_summary['output_sha256'],output=str(OUTPUT.relative_to(ROOT)),output_sha256=hashlib.sha256(OUTPUT.read_bytes()).hexdigest(),output_rows=n,unique_record_ids=len(ids),feature_names=FEATURES,missing_counts={k:missing[k] for k in FEATURES},statuses=dict(status),issues=dict(issues),ranges=bounds,district_count=len(district_counts)-('' in district_counts),by_year=dict(sorted(year_counts.items())),codebook=str(CODEBOOK.relative_to(ROOT)),codebook_sha256=code_meta['sha256'],codebook_source=code_meta['url'],codebook_retrieved_at=code_meta['retrieved_at'],district_mapping_basis='Original transaction district name mapped to current official MOLIT code list. Historical code/boundary versions not independently verified.',excluded=['past_prices','price_growth','price_indices','trade_counts','relative_floor'],model_run=False)
 (REPORT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
 with (REPORT/'district_counts.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=['district_code','district_name','transaction_rows']);writer.writeheader()
  for name,code in sorted(mapping.items(),key=lambda x:x[1]):writer.writerow(dict(district_code=code,district_name=name,transaction_rows=district_counts[code]))
 with (REPORT/'month_counts.csv').open('w',encoding='utf-8-sig',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=['contract_month','transaction_rows']);writer.writeheader()
  for month,count in sorted(month_counts.items()):writer.writerow(dict(contract_month=month,transaction_rows=count))
 text=['# 거래·시장 기본 Feature 반영 결과','', '작업일: 2026-11-02. 명세 v1.2에 따라 지역·시간 통제 3개만 반영했다. 과거 가격·상승률·가격지수와 보조 후보 거래량은 생성하지 않았다.','',
 f'호실 Feature 파일의 {n:,}개 거래 레코드를 그대로 유지하고 다음 컬럼을 추가했다. 기존 호실 변수·record_id·원본 필드는 변경하지 않았다.','',
 '| 필드 | 정의 | 결측 |','|---|---|---:|',
 f"| `district_code` | 거래 원주소의 자치구명을 국토부 공식 5자리 시군구 코드에 연결. 숫자 크기·순서가 없는 범주형 | {missing['district_code']:,} |",
 f"| `contract_month` | 계약일의 월(1~12), 계절 통제 | {missing['contract_month']:,} |",
 f"| `contract_time_index` | (계약연도−2020)×12+계약월−1. 2020-01=0, 2026-10=81 | {missing['contract_time_index']:,} |",'',
 f"검증: 출력 {n:,}행, 유일 record_id {len(ids):,}개, 자치구 {summary['district_count']}개. 모든 연도별 건수가 호실 Feature 원본과 일치한다. 상태별 건수: {json.dumps(dict(status),ensure_ascii=False)}. 사유별 건수: {json.dumps(dict(issues),ensure_ascii=False)}.",'',
 '## 날짜·지역 기준과 주의','',
 '계약월·추세는 수집일이 아니라 각 행의 계약일에서 계산하고, 원 계약년월·계약일과 일치하는지 검사했다. 공개되지 않은 미래 가격이나 외부 시장정보는 사용하지 않았다.',
 '자치구는 계약자료에 적힌 소재지 자치구명에서 추출했다. [국토부 공식 지역 조회](https://rt.molit.go.kr/pt/xls/xls.do)가 사용하는 `/data/sgg.do` 응답의 25개 코드와 연결했다. 공식 응답·요청조건·수집시점·해시는 `data/raw/region_codes/`에 보관한다. 코드값은 현재 공식 목록으로 표준화한 것이며 2020~2026년의 행정구역 경계·코드 이력 전체를 독립 검증했다고 주장하지 않는다. `district_code_basis`에 이 매핑 근거를 표시했다.',
 '자치구 코드 원문은 범주형 문자열이다. 모델링에서 코드 크기를 연속 수치로 해석하지 않는다. 계약월을 범주 또는 순환 인코딩할지는 Train에서 결정하고 두 인코딩을 중복 입력하지 않는다. 계약연도/원 계약년월/계약일 원문은 감사용으로 보존했으며 월·추세와 함께 자동 모델 입력하지 않는다.',
 '원본 거래가격·원 건축년도 등은 보존 필드이며 모델 기본 입력이 아니다. 명세의 base_feature_names와 실제 생성 상태를 확인해 선택한다. 호실 연식 결측 5건과 층 검토 표시 72건도 그대로 유지했다.','',
 '## 파일','',
 '- 최신 거래 파일: `data/processed/seoul_sales_2020_2026/seoul_apt_sales_2020_2026_unit_market_features.csv` (UTF-8 BOM).',
 '- 품질 필드: `market_feature_status`, `market_feature_issues`, `district_code_basis`.',
 '- `reports/market_features/summary.json`: 해시·결측·행수·매핑 출처.',
 '- `reports/market_features/district_counts.csv`, `month_counts.csv`: 지역별·계약월별 건수.',
 '- `rows_for_review.csv`: 문제 행만 기록하며 없으면 헤더만 존재.',
 '- 재현: `python src/fetch_district_codes.py` (최초 코드표 확보), `python src/build_market_features.py` (이후 오프라인 재현 가능).','',
 '모델 학습·SHAP·공선성 분석은 실행하지 않았다. 다음 미구축 기본 Feature는 교통·교육·단지 내부이며 단지 식별 연결과 과거 이력 확보가 선행되어야 한다.']
 (REPORT/'거래시장_Feature_반영결과.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
 print(json.dumps(summary,ensure_ascii=True,indent=2))
if __name__=='__main__':main()
