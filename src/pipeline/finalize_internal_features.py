"""Export normalized source snapshot and truthful partial-completion handoff."""
import csv,json,pathlib
from build_internal_features import ROOT,REPORT,BASE,COMPLEX_SOURCE,FEATURES,snapshot_values,approval_date
def main():
 s=json.loads((REPORT/'summary.json').read_text(encoding='utf-8'))
 with COMPLEX_SOURCE.open(encoding='cp949',newline='') as f:rows=list(csv.DictReader(f))
 dest=BASE/'complex_internal_snapshot_2026_11_01.csv'
 with dest.open('w',encoding='utf-8-sig',newline='') as f:
  fields=['kapt_code','complex_name','road_address','source_snapshot_date','source_modified_at','approval_date']+[x+'_snapshot' for x in FEATURES]+['parking_total_raw','households_raw','heating_raw','corridor_raw','source_issues']
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
  for r in rows:
   values,issues=snapshot_values(r);a=approval_date(r)
   w.writerow(dict(kapt_code=r['k-아파트코드'],complex_name=r['k-아파트명'],road_address=r['kapt도로명주소'],source_snapshot_date=s['complex_snapshot_date'],source_modified_at=r['k-수정일자'],approval_date=a.isoformat() if a else '',**values,parking_total_raw=r['주차대수'],households_raw=r['k-전체세대수'],heating_raw=r['k-난방방식'],corridor_raw=r['k-복도유형'],source_issues='|'.join(issues)))
 text=['# 단지 내부 변수 정리·결합 결과','',
 '작업일: 2026-11-02. **단지 후보 연결과 현행 스냅샷 정리는 완료했으나, 계약일 기준 단지 Feature의 유효값 반영은 미완료다.** 과거 변경 이력이 확보되지 않아 기본 Feature 4개는 결측으로 유지했다. 현재값을 과거에 소급하지 않았다.','',
 '## 대상 및 출처','',
 '[서울 열린데이터광장 — 서울시 공동주택 아파트 정보 OA-15818](https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do)의 2,894개 단지 CSV를 사용했다. 수집일은 2026-11-01(한국시간)이다. 수정일·등록일·단지승인일은 개별 속성의 적용 시작일이 아니므로 과거 이력으로 사용하지 않았다. 사용승인일은 건물 존재 시점과 매칭 점검의 근거일 뿐 세대수·주차·난방·복도의 모든 과거 값이 같다는 근거가 아니다.',
 '[한국부동산원의 K-apt 소개](https://www.reb.or.kr/reb/cm/cntnts/cntntsView.do?cntntsId=1204)는 단지 기본정보와 시설 유지관리 이력 공개를 구분한다. 유지관리 이력이 있다는 안내만으로 네 속성의 연도별 전 값이 다운로드 가능하다고 판단하지 않았다. 이번 조사에서는 검증된 속성별 과거 이력을 확보하지 못했으며 자료가 존재하지 않는다고 단정하지 않는다.','',
 '## 매칭 결과','',
 f"입력·출력 거래는 모두 {s['output_rows']:,}행이고 record_id도 {s['unique_record_ids']:,}개다. 거래 주소·이름·건축연도 조합은 {s['transaction_complex_keys']:,}개다. 이 수는 공인 단지 수가 아니다.",'',
 '| 상태 | 거래행 | 의미 |','|---|---:|---|']
 meanings={'address_name_supported':'도로명주소·정규화 이름 일치, 사용승인연도 충돌 없음. 수동 정답 검증 완료를 뜻하지 않음','unique_address_review':'주소만 유일하게 일치. 명칭 검토 필요','name_location_review':'같은 자치구·법정동 안 이름으로 유일 후보. 주소 검토 필요','year_conflict_review':'후보 사용승인연도와 거래 건축연도 불일치','ambiguous':'복수 후보로 미해결','unmatched':'후보 없음'}
 for key,count in s['match_status_transaction_rows'].items():text.append(f'| `{key}` | {count:,} | {meanings[key]} |')
 text += ['',f"총 연결 후보 {s['candidate_transaction_rows']:,}행({s['candidate_transaction_rows']/s['output_rows']:.1%}). 후보 연결률은 매칭 정확도가 아니다. 숫자·차수·동을 지우지 않고 공백·문장부호·말미 '아파트' 표기만 정규화했다. 유사도만으로 임의 연결하지 않았고 애매한 후보를 강제 선택하지 않았다.",'',
 '## 변수와 현재값','',
 '| 계약일 기준 기본 Feature | 별도로 보관한 현재값 | 현재값이 있는 거래행 |','|---|---|---:|']
 for feature in FEATURES:text.append(f"| `{feature}` — 현재 전부 결측 | `{feature}_snapshot` | {s['snapshot_value_counts'][feature]:,} |")
 text += ['',
 '- `household_count`: 총세대수. 현행 원천 0·빈값 등은 양의 세대수로 간주하지 않았다.',
 '- `parking_per_household`: 같은 스냅샷의 총주차대수/총세대수, 소수점 6자리. 원천 주차 0은 실제 0인지 불명확하여 비율도 결측 처리하고 검토 사유를 남겼다. 총주차대수는 모델 기본 Feature로 추가하지 않았다.',
 '- `heating_type`: 개별난방=individual, 지역난방=district, 중앙난방=central, 기타=other.',
 '- `corridor_type`: 계단식=staircase, 복도식=corridor, 혼합식=mixed, 기타=other.',
 '- 원천 난방·복도 문자열과 주차·세대수는 정리된 단지 스냅샷 테이블에 보존했다. 기타는 결측과 구분한다.',
 f"- 원천자료의 양수 세대수 미확인 {s['source_issues'].get('households_missing_or_nonpositive',0)}개 단지, 주차 0 표기 {s['source_issues'].get('zero_parking_needs_source_confirmation',0)}개 단지. 원천 단지 기준 건수와 거래에 반복된 행수는 구분한다.",
 f"- 계약일이 후보 사용승인일보다 빠른 거래 {s['reasons'].get('contract_before_candidate_approval',0):,}건은 해당 현재값조차 채우지 않고 검토 표시했다. 선준공 거래 성격이나 매칭 오류 등을 근거 확인 전 단정하지 않는다.",
 '- `_snapshot` 값은 정체성이 미확정인 연결 후보도 포함한다. `complex_match_status`와 함께 검토해야 하며 기본 학습 입력으로 쓰지 않는다.','',
 '## 추가 컬럼','',
 '| 컬럼 | 의미 |','|---|---|',
 '| `complex_match_key` | 원 거래 단지 조합 비교키. 공인 단지 ID 아님 |',
 '| `complex_candidate_kapt_code` | 유일 후보의 원천 단지코드. 확정 연결 코드와 구분 |',
 '| `complex_match_status`, `complex_match_method`, `complex_match_candidate_count`, `complex_match_issues` | 매칭 등급·경로·후보 수·연도 충돌 등 |',
 '| `complex_snapshot_date` | 현재값을 관측한 수집 날짜. 속성 적용 시작일 아님 |',
 '| `complex_source_modified_at` | 원천 전체 레코드 수정일. 개별 속성 변경 이력 아님 |',
 '| `complex_approval_date_snapshot` | 현재 원천의 사용승인일. 거래 연식 값을 덮어쓰지 않음 |',
 '| `complex_source_file` | 단지 원본 추적용 파일명 |',
 '| `complex_history_status` | 현재는 모두 not_available. 단지 속성별 검증된 이력 없음 |',
 '| `internal_feature_status`, `internal_feature_issues` | 연결 실패·이력 없음·준공 이전·원천 이상값 등의 사유 |','',
 '## 파일과 검증','',
 '- 최신 누적 CSV: `data/processed/seoul_sales_2020_2026/seoul_apt_sales_2020_2026_unit_market_internal_features.csv`.',
 '- 단지별 정리된 현행값: 같은 폴더 `complex_internal_snapshot_2026_11_01.csv` (2,894행).',
 '- `reports/internal_features/complex_match_audit.csv`: 거래 단지 조합별 후보코드·선택 이유·거래행수.',
 '- `reports/internal_features/year_summary.csv`, `summary.json`: 연도별·매칭등급별 건수 및 파일 해시.',
 '- 재현: `python src/build_internal_features.py`, `python src/finalize_internal_features.py`.',
 '현재값 과거 소급 금지, 복수 후보 강제 선택 금지, 타 자치구 동일명 연결 금지, 세대수 0에서 비율 계산 금지, 준공 이전 속성 연결 보류의 인공 fixture 검사 5개가 통과했다. 실제 입출력 거래행수와 고유 record_id도 확인했다. 별도로 기존 컬럼과 record_id의 행별 보존을 검사한다.','',
 '## 남은 작업','',
 '먼저 매칭 검토 대상의 주소·명칭·준공연도 충돌을 해결하고, 단지코드·속성별 값·valid_from/to·근거자료를 갖춘 과거 이력표를 확보해야 한다. 과거 스냅샷·사용승인 도서·변경 신고·공사 이력 등이 후보이지만 이력이 확인되지 않은 기간을 무변경으로 가정하지 않는다. 그 이후에만 기본 Feature 4개를 날짜별로 채운다. 현재값을 일정하다고 가정한 보조 분석은 사용자와 별도 범위를 정한 뒤 명시적으로 분리해야 한다. 모델 학습은 하지 않았다.']
 (REPORT/'단지내부_Feature_반영결과.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
 print(json.dumps(dict(normalized_snapshot_rows=len(rows),strict_historical_values=s['strict_historical_values_generated'],candidate_transactions=s['candidate_transaction_rows'])))
if __name__=='__main__':main()
