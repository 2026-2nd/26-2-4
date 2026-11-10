# Phase 1 데이터 사전

연결표 v2 후 최신 파일은 `seoul_apt_sales_2020_2026_internal_static_assumption_crosswalk_v2.csv`이다. 단지 연결·참고값·안정성 가정값을 재계산했고 `crosswalk_version`, `previous_complex_candidate_kapt_code`, `previous_complex_match_status`, `crosswalk_decision`, `crosswalk_evidence`를 추가했다. `<feature>_basis`와 역사값 구분은 유지한다. [연결표 개선 보고서](crosswalk_v2/연결표_개선과_결측감소.md)를 참조한다.

후속 안정성 가정본: `seoul_apt_sales_2020_2026_internal_static_assumption.csv`에서 단지 내부 4개 기본 컬럼 일부를 가정으로 채웠다. `<feature>_basis=assumed_time_invariant`이며 `<feature>_history_verified`에는 원 엄격 값을 보존한다. 과거 총동수·개별 동 일치 이력은 미검증으로 표시한다. [가정 근거·결측 감소](internal_static_assumption/안정성가정_검토와_결측감소.md)와 `config/dataset_registry.json`을 참조한다. 아래 이전 파일 설명은 엄격 이력본에 해당한다.

단지 내부 정리 후 최신 누적 파일은 `seoul_apt_sales_2020_2026_unit_market_internal_features.csv`이다. `household_count`, `parking_per_household`, `heating_type`, `corridor_type`는 계약일 기준 기본 컬럼으로, 이력 미확보 때문에 현재는 모두 결측이다. 현행 참고값은 각 이름 뒤 `_snapshot`을 붙인 별도 컬럼이다. 매칭 등급과 날짜 근거는 [단지 내부 반영 결과](internal_features/단지내부_Feature_반영결과.md)를 참조한다. 현재값을 기본 과거 Feature로 오인하면 안 된다.

최신 누적 거래 테이블은 `seoul_apt_sales_2020_2026_unit_market_features.csv`이다. 호실 변수에 `district_code`(5자리 범주 코드), `contract_month`(1~12), `contract_time_index`(2020-01=0인 연속 월수)를 추가했다. 품질·매핑 근거는 `market_feature_status`, `market_feature_issues`, `district_code_basis`에 있다. 상세는 [거래·시장 Feature 반영 결과](market_features/거래시장_Feature_반영결과.md)를 참조한다.

서울 전체 최신 호실 Feature 파일과 추가 필드(`record_id`, `contract_date`, `exclusive_area_m2`, `transaction_floor`, `building_age_years`, `age_basis`, 품질 상태)는 [호실 Feature 반영 결과](unit_features/호실_Feature_반영결과.md)를 참조한다. 아래 pilot의 `area_m2`·`floor`·`build_year`와 최신 표준 변수명을 구분한다.

이 문서는 기존 pilot 산출물의 필드 기록이다. 서울 전체 거래에 앞으로 결합할 변수의 정의·시점 규칙·결측 처리는 [Feature 명세 v1](FEATURE_SPEC_v1.md)과 `config/feature_spec_v1.json`을 따른다.

2026-11-02: 공원 관련 Feature를 제외했다. 현행 결합 데이터에는 `park_nearest_m`, `park_rows_1km`가 없으며, 주차 관련 `parking`, `parking_per_household`는 유지한다. 기존 `parks_seoul.csv`와 공원 원본은 수집 이력이며 학습 입력이 아니다.

| 필드 | 단위·정의 | 주의 |
|---|---|---|
| complex_id | 주소+정규화 이름 SHA256 앞 20자리 | 공인 ID 아님, 명칭 변경 시 분할 가능 |
| complex_key | 시군구·법정동·본부번+단지명 | 충돌 검토 필요 |
| gu, name, address, road_address | 자치구·원 단지명·지번주소·도로명주소 | 도로명 결합은 공백만 정규화 |
| area_m2 | 전용면적 ㎡ | 건물 연면적 아님 |
| area_bucket_5m2 | floor(area/5)*5 | 하한 포함·상한 제외 |
| date | ISO 계약일 | 신고·공개일 아님 |
| price_man | 거래 총액 만원 | 모델 A Target 후보 |
| unit_price_man_m2 | 만원/㎡ | 레이블 가격수준 산출용 |
| floor, build_year | 거래층·건축연도 | 원본 문자열, 지하층 포함 가능 |
| source_file | 원본 파일명 | 추적용 |
| anchor, endpoint | 2020-12-31, 2023-12-31 | 이번 표본에 고정 |
| window_days | 90일 | 양 끝시점의 후행 창 |
| min_n, n_base, n_future | 각 창 최소 거래수·실제 거래수 | min_n=3은 충분성 증명 아님 |
| p0_man_m2, p1_man_m2 | 각 창 거래 단가의 중위수 | 미래 가격수준은 Feature 사용 금지 |
| return_3y | p1/p0-1, 소수 | 0.1=10%, 예측값 아님 |
| base_median_area, future_median_area | 양 창 전용면적 중위값 ㎡ | 구성 차이 점검용 |
| kapt_code | 서울시 원 단지코드 | 거래코드 aptSeq와 동일 체계로 간주 금지 |
| lat, lon | 현행 서울시 좌표Y/X | 도 단위 배열로 해석, 원천 CRS 추가 검증 |
| households, parking | 현행 세대수·주차대수 | 과거 값으로 소급 금지 |
| parking_per_household | parking/households | households<=0이면 결측 |
| snapshot_only | true | 시점 검증 전 역사적 학습 금지 |
| valid_coordinate | 서울 범위 경위도 검사 | 지리적 정확도 보증 아님 |
| *_nearest_m | Haversine 최근접 직선거리 m | 보행거리·학교배정·공원입구 접근성 아님 |
| *_rows_1km | 반경 1km 원천 행수 | 물리적 시설 중복 제거 전, 1~8호선 한정 |
| match_status | 이름·주소 일치/주소만 유일/복수/불일치 | 주소만 유일해도 정답 매칭 확정 아님 |

학교·공원 CSV는 공식 영문 필드명을 유지했다. 한국어 컬럼 대응은 raw의 `schools_columns.json`, `parks_columns.json`에 있다. 결측 좌표를 0으로 채우지 않는다. 학교 전체 행에는 학교급·운영상태가 섞여 있으므로 정식 교육 Feature에서 구분한다.

후속 모델 입력 추가 요구 필드: `label_available_at`(정답 공개 완료일), `max_feature_available_at`(입력 중 가장 늦은 이용 가능일), `target`, `anchor`. 현재 pilot에는 이력에 근거한 가용일을 생성하지 않았으므로 모델 입력으로 승격하지 않는다.
