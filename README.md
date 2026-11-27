# 서울 아파트 시장 국면별 특성 분석

기계학습기초 4조 · 2017–2026년 서울 아파트 실거래 617,592건

**어떤 아파트가 상승기에 서울보다 더 오르고, 하락기에 덜 떨어졌는가?**
단지×면적별 상대 가격 변화를 국면별로 분석한다. 절대 가격이나 미래 시장 방향을 예측하는 연구는 아니다.

## 최신 진행: V3 검증 재설계 (2026-11-27)

기존 V1/V2는 탐색적 기록으로 보존한다. **새 분석은 [V3 검증 규칙](docs/nested_v3.md)**을 기준으로 한다.
원자료에서 기존 시험 동 64개를 먼저 제외하고, 공식 서울 지수 기반 학습 셀을 재생성한 후 학습 전용 EDA와 중첩 법정동 교차검증을 수행한다. 새 외부 시험은 아직 없다. 실행 완료 여부는 [Actions](https://github.com/2026-2nd/26-2-4/actions)에서 확인한다.

학습 전용 EDA는 기존 EDA 담당 브랜치의 계산 모듈을 재사용하며, 새 산출물은 `results/nested_v3/eda_train/`에 저장한다. 과거 전체 자료 EDA와 V1/V2는 최종 모델 성능 근거로 사용하지 않는다.

추가 점검: [현재 단지 정보 제외 비교와 누수 점검 보고서](reports/leakage_audit_v3/audit_report_ko.txt),
[12개 분석표의 비교 수치](reports/leakage_audit_v3/paired_comparison.csv).
같은 표본과 법정동 분할에서 전체 변수/현재값 제외 절차를 비교한다.
현재값 제외 결과도 미래 예측이나 새 독립 외부 검증을 뜻하지 않는다.

## 이전 실험 읽는 순서

| 순서 | 문서 | 내용 |
|---|---|---|
| 1 | [전체 진행 현황 — 완료한 작업과 남은 검토](reports/final/README.md) | 연구 단계 |
| 2 | [EDA — 데이터 품질과 표본 구성](reports/eda/EDA_report_ko.md) | 결측·주차·표본 편향 |
| 3 | [EDA 결과 반영 전 — 기본 모델 비교 결과](reports/final/models/results_v1.md) | v1 동네 외부 시험 결과 |
| 4 | [EDA 결과 반영 후 — 결측치 처리와 특성 공학 비교](reports/final/followup/README.md) | 학습 내부 비교·민감도 |
| 5 | [모델 해석 — 국면별 주요 특성과 SHAP](reports/final/followup/interpretation.md) | 탐색적 해석·유형 후보 |

## 분석 흐름

실거래 → 단지×면적×국면 분석표 → 법정동 분할 → 기본 모델 비교 → EDA 후속 점검 → 특성 해석

- 분석표: 창 방식 27,003행, 기울기 방식 47,412행. [생성 규칙](reports/final/cells/README.md)
- v1: 319개 법정동 중 64개를 시험용으로 고정. 학습 내부 검증에서 12개 조합 모두 CatBoost 선택.
- EDA 후속: 기존 시험 결과를 보존하고 **학습 동네 안에서만** 전처리·특성 대안을 비교한다. 후속 CV는 새 독립 시험 성능이 아니다.
- 결과는 연관 관계다. 현재 단지 정보를 과거에 적용한 가정과 거래된 단지만 남는 편향이 있다.

## 파일 위치

| 위치 | 역할 |
|---|---|
| config/ | 특성·분할·모델·후속 실험 규칙 |
| src/eda/, src/cells/, src/model/ | EDA·분석표·학습·해석 코드 |
| reports/eda/ | 팀 EDA 보고서·그림·표 |
| reports/final/ | 단계별 보고서·재검증 자료 |
| data/final/ | 전처리 v5 원본 |
| tests/, tools/ | 테스트·검증·재현 |

그 밖의 data/와 reports/ 자료는 데이터 생성·출처 대사에 쓰므로 유지한다.
학습 모델과 반복 실행 캐시는 Git 제외 results/에 생긴다.

## 실행과 참고

설치: `python -m pip install -r requirements.txt`

검증: `python -m pytest -q`, `python tools/verify_final.py`

[실행 순서](src/README.md) · [다음 작업](docs/handoff.md) · [연구 방법](docs/methodology.md) ·
[데이터 규격](docs/data.md) · [결정 기록](docs/decisions.md) · [팀 역할](docs/roles/README.md) · [정리 기록](docs/cleanup.md)

원자료는 각 제공기관의 이용 약관을 따른다.
