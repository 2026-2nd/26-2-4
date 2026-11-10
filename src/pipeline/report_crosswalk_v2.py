"""Write measured crosswalk/enrichment comparison and point the registry to v2."""
import collections,csv,json
from improve_complex_crosswalk import ROOT,REPORT
def main():
 rules=json.loads((REPORT/'summary.json').read_text(encoding='utf-8'));s=json.loads((REPORT/'application_summary.json').read_text(encoding='utf-8'))
 with (REPORT/'crosswalk_v2.csv').open(encoding='utf-8-sig',newline='') as f:cross=list(csv.DictReader(f))
 retained={r['complex_match_key']:r for r in cross if r['decision']=='retained_previous_supported'}
 warnings=[]
 with (REPORT/'candidate_evidence.csv').open(encoding='utf-8-sig',newline='') as f:
  for r in csv.DictReader(f):
   if r['complex_match_key'] in retained and r['candidate_kapt_code']==retained[r['complex_match_key']]['new_kapt_code'] and r['blocking_reasons']:warnings.append(r)
 with (REPORT/'retained_mapping_warnings.csv').open('w',encoding='utf-8-sig',newline='') as f:
  fields=list(warnings[0]) if warnings else ['complex_match_key','blocking_reasons'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(warnings)
 with (ROOT/'data/raw/seoul_complex.csv').open(encoding='cp949',newline='') as f:names={r['k-아파트코드']:r['k-아파트명'] for r in csv.DictReader(f)}
 labels={'household_count':'총세대수','parking_per_household':'세대당 주차대수','heating_type':'난방방식','corridor_type':'복도유형'}
 accepted_before=rules['status_before']['address_name_supported'];accepted_after=sum(s['match_status_transaction_rows'].get(k,0) for k in rules['accepted_statuses'])
 text=['# 단지 연결표 개선 v2 및 결측 감소 결과','',
 '작업일: 2026-11-02. 기존 파일은 보존하고 개선 연결표·후보별 근거·재결합한 거래 CSV를 별도 생성했다. 거래가격·매수자·매도자·미래 가격은 매칭에 사용하지 않았다.','',
 '## 무엇을 개선했나','',
 '기존의 단지명 완전 일치 중심 규칙에서 주소·준공·지번과 설명 가능한 이름 차이를 결합한 증거 규칙으로 확장했다. 지역명 접두어, 공백·기호, 말미 아파트, IPARK/아이파크·e편한세상/이편한세상 등의 표기 차이를 처리한다. 원문과 사용 규칙은 연결표에 보존하며 의미 없는 공통 브랜드 일치만으로 연결하지 않는다.',
 '자동 연결은 (1) 같은 도로명주소+사용승인연도+법정동/지번 일치, (2) 같은 도로명주소+사용승인연도+법정동+설명 가능한 이름 관계, (3) 같은 법정동/지번+사용승인연도+이름 관계 중 하나를 만족하고 유일한 후보가 남는 경우다. 이름 유사도 점수만으로 선택하지 않는다. 현재 서울시 단지자료는 법정동주소의 부정확성 안내가 있으므로 [원천 페이지](https://data.seoul.go.kr/dataList/OA-15818/S/1/datasetView.do)의 법정동·나머지주소는 보조 근거로만 사용하며 단독으로 확정하지 않는다.',
 '단지 차수·단지번호가 다르거나 한 자료가 여러 단지를 합쳐 관리하는 경우, 임대 구분 충돌, 개별 동 범위를 가리키는 이름, 명시적 지번 충돌은 새 자동 연결에서 보류했다. 일부 기존 등급에서 새 부가정보의 충돌이 발견된 경우에는 원 연결을 임의 변경하지 않고 검토표를 별도로 남겼다.','',
 '## 연결 성과','',
 f"거래 전체 {s['output_rows']:,}행, 거래 단지 조합 {rules['transaction_complex_keys']:,}개에 대해 처리했다. 조합 수는 공인 단지 수가 아니다.",'',
 '| 항목 | 이전 | 개선 후 |','|---|---:|---:|',
 f"| 근거 규칙을 통과한 거래행 | {accepted_before:,} ({accepted_before/s['output_rows']:.2%}) | {accepted_after:,} ({accepted_after/s['output_rows']:.2%}) |",
 f"| 안정성 가정 적용 대상 거래 | 104,911 | {s['eligible_rows']:,} |",
 f"| 단지 변수 4개가 모두 채워진 거래 | 93,960 | {s['rows_with_all_four_values']:,} |",'',
 f"새 규칙으로 거래 {rules['new_rule_supported_transaction_rows']:,}행, 거래 단지 조합 {rules['new_rule_supported_keys']:,}개를 추가 연결했다. 이 가운데 일부는 기존 복수/잘못 선택된 잠정 후보를 새 근거로 구분했으며 후보 코드가 달라진 거래는 {s['changed_candidate_code_rows']:,}행이다. 기존에 채웠던 값은 유지되는지 별도 대조한다. 연결 근거 통과율은 수작업 정답 대비 매칭 정확도가 아니다.",'',
 '### 대표적인 이름 차이 처리','',
 '| 거래자료 이름 | 단지자료 이름 | 거래행 | 규칙 |','|---|---|---:|---|']
 for r in sorted([r for r in cross if r['decision']=='new_rule_supported'],key=lambda r:int(r['transaction_rows']),reverse=True)[:12]:text.append(f"| {r['transaction_name']} | {names[r['new_kapt_code']]} | {int(r['transaction_rows']):,} | {r['new_match_status']} |")
 text += ['','## 실제 결측 감소','',
 '| 변수 | 이전 값 있음 | 개선 후 값 있음 | 추가로 채운 거래 | 이전 결측률 | 개선 후 결측률 |','|---|---:|---:|---:|---:|---:|']
 for r in s['missing_comparison']:text.append(f"| {labels[r['feature']]} | {r['previous_filled']:,} | {r['new_filled']:,} | {r['additional_filled']:,} | {r['previous_missing_rate']:.2%} | {r['new_missing_rate']:.2%} |")
 text += ['',
 '분모는 전체 356,087개 거래로 고정했다. 각 변수의 채운 건수는 겹치므로 합산하지 않는다. 주차대수 0 의미 미확인·세대수 0·원천값 누락은 계속 결측으로 두고, 난방/주차 변경 단서 제외도 유지했다. 기존 안정성 가정과 동일하게 채운 값은 assumed_time_invariant이며, 새로 과거 이력을 확보하거나 역사적으로 검증한 값이 아니다.','',
 '## 남은 문제와 검토 목록','',
 f"개선 후 보류 상태별 거래행: {json.dumps({k:v for k,v in s['match_status_transaction_rows'].items() if k not in rules['accepted_statuses']},ensure_ascii=False)}.",
 f"기존 address_name_supported 조합 중 추가 보조정보 경고가 있는 조합 {len(warnings)}개·거래 {sum(int(r['transaction_rows']) for r in warnings):,}행은 `retained_mapping_warnings.csv`에 있다. 대부분 지번 표기의 충돌이며 원자료의 예전 지번·복수 필지·오류 중 원인 확인이 필요하다. 주소·이름 일치 근거를 바로 폐기하지도, 현재 보조 지번이 항상 맞다고 단정하지도 않았다.",
 '새 규칙은 원천의 여러 항목을 교차 대조한 자동 근거 연결이며 사람의 전수 확인·독립 정답 표본을 통한 정확도 평가를 완료한 것은 아니다. 그룹 단위와 임대/분양 혼합, 명칭 변경, 주소 변경은 잔여 위험이다. 남은 결측을 전부 평균이나 가장 비슷한 이름으로 채우지 않았다.','',
 '## 산출물·재현','',
 '- 개선 연결표: `reports/crosswalk_v2/crosswalk_v2.csv`. 이전/새 코드·이전/새 등급·판정·명칭 근거·거래행수.',
 '- 후보별 세부 근거: `candidate_evidence.csv`. 도로명·법정동·지번·이름 일치 여부와 차수/임대/범위 충돌.',
 '- 실제 적용 건수: `crosswalk_application_counts.csv`. 조합별 변수 확보 수.',
 '- 최신 누적 CSV: `data/processed/seoul_sales_2020_2026/seoul_apt_sales_2020_2026_internal_static_assumption_crosswalk_v2.csv`.',
 '- CSV 추가 필드: `crosswalk_version`, `previous_complex_candidate_kapt_code`, `previous_complex_match_status`, `crosswalk_decision`, `crosswalk_evidence`. 이전의 `<feature>_basis`와 역사값 구분도 유지.',
 '- `missing_comparison_v2.csv`, `year_summary.csv`, `district_summary.csv`, `application_summary.json`: 전후 결측과 해시.',
 '- 정책: `config/internal_static_assumption_policy_v2.json`, 최신 파일 구분: `config/dataset_registry.json`.',
 '- 재현 순서: `python src/improve_complex_crosswalk.py`, `python src/apply_crosswalk_v2.py`, `python src/report_crosswalk_v2.py`.',
 '차수·통합 단지·임대·다른 지번·일반 브랜드·동번호 혼동 등을 막는 인공 fixture 검사 8개가 통과했다. 실제 출력은 거래행수·ID·기존 호실/지역시간 값·이전 가정값 보존을 별도 검사한다. 모델 학습·성능평가·SHAP는 실행하지 않았다.']
 (REPORT/'연결표_개선과_결측감소.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
 registry={'active_variant':'internal_static_assumption_crosswalk_v2','active_csv':s['output'],'active_sha256':s['output_sha256'],'crosswalk_csv':s['crosswalk_file'],'crosswalk_sha256':s['crosswalk_sha256'],'strict_history_csv':s['source'],'strict_history_sha256':s['source_sha256'],'previous_static_csv':s['previous_static_file'],'previous_static_sha256':s['previous_static_sha256'],'warning':'Evidence-rule matching is not independently validated accuracy. Internal values remain static assumptions, not verified historical observations.'}
 (ROOT/'config/dataset_registry.json').write_text(json.dumps(registry,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'accepted_before':accepted_before,'accepted_after':accepted_after,'additional_supported_rows':rules['new_rule_supported_transaction_rows'],'retained_warning_keys':len(warnings)}))
if __name__=='__main__':main()
