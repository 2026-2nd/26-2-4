# 거래·시장 기본 Feature 반영 결과

작업일: 2026-11-02. 명세 v1.2에 따라 지역·시간 통제 3개만 반영했다. 과거 가격·상승률·가격지수와 보조 후보 거래량은 생성하지 않았다.

호실 Feature 파일의 356,087개 거래 레코드를 그대로 유지하고 다음 컬럼을 추가했다. 기존 호실 변수·record_id·원본 필드는 변경하지 않았다.

| 필드 | 정의 | 결측 |
|---|---|---:|
| `district_code` | 거래 원주소의 자치구명을 국토부 공식 5자리 시군구 코드에 연결. 숫자 크기·순서가 없는 범주형 | 0 |
| `contract_month` | 계약일의 월(1~12), 계절 통제 | 0 |
| `contract_time_index` | (계약연도−2020)×12+계약월−1. 2020-01=0, 2026-10=81 | 0 |

검증: 출력 356,087행, 유일 record_id 356,087개, 자치구 25개. 모든 연도별 건수가 호실 Feature 원본과 일치한다. 상태별 건수: {"complete": 356087}. 사유별 건수: {}.

## 날짜·지역 기준과 주의

계약월·추세는 수집일이 아니라 각 행의 계약일에서 계산하고, 원 계약년월·계약일과 일치하는지 검사했다. 공개되지 않은 미래 가격이나 외부 시장정보는 사용하지 않았다.
자치구는 계약자료에 적힌 소재지 자치구명에서 추출했다. [국토부 공식 지역 조회](https://rt.molit.go.kr/pt/xls/xls.do)가 사용하는 `/data/sgg.do` 응답의 25개 코드와 연결했다. 공식 응답·요청조건·수집시점·해시는 `data/raw/region_codes/`에 보관한다. 코드값은 현재 공식 목록으로 표준화한 것이며 2020~2026년의 행정구역 경계·코드 이력 전체를 독립 검증했다고 주장하지 않는다. `district_code_basis`에 이 매핑 근거를 표시했다.
자치구 코드 원문은 범주형 문자열이다. 모델링에서 코드 크기를 연속 수치로 해석하지 않는다. 계약월을 범주 또는 순환 인코딩할지는 Train에서 결정하고 두 인코딩을 중복 입력하지 않는다. 계약연도/원 계약년월/계약일 원문은 감사용으로 보존했으며 월·추세와 함께 자동 모델 입력하지 않는다.
원본 거래가격·원 건축년도 등은 보존 필드이며 모델 기본 입력이 아니다. 명세의 base_feature_names와 실제 생성 상태를 확인해 선택한다. 호실 연식 결측 5건과 층 검토 표시 72건도 그대로 유지했다.

## 파일

- 최신 거래 파일: `data/processed/seoul_sales_2020_2026/seoul_apt_sales_2020_2026_unit_market_features.csv` (UTF-8 BOM).
- 품질 필드: `market_feature_status`, `market_feature_issues`, `district_code_basis`.
- `reports/market_features/summary.json`: 해시·결측·행수·매핑 출처.
- `reports/market_features/district_counts.csv`, `month_counts.csv`: 지역별·계약월별 건수.
- `rows_for_review.csv`: 문제 행만 기록하며 없으면 헤더만 존재.
- 재현: `python src/fetch_district_codes.py` (최초 코드표 확보), `python src/build_market_features.py` (이후 오프라인 재현 가능).

모델 학습·SHAP·공선성 분석은 실행하지 않았다. 다음 미구축 기본 Feature는 교통·교육·단지 내부이며 단지 식별 연결과 과거 이력 확보가 선행되어야 한다.
