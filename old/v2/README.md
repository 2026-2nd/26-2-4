# V2 — EDA 후속 비교와 탐색적 해석

V1 이후의 학습 내부 탐색이다. 현재 분석은 [V3](../../README.md)를 기준으로 한다.

| 위치 | 내용 |
|---|---|
| [eda/](eda/EDA_report_ko.md) | 전체 자료 EDA 보고서·표·그림; 후속 비교의 배경 |
| [reports/](reports/README.md) | 전처리·특성 대안 168개 비교 |
| [해석 보고서](reports/interpretation.md) | 계수, SHAP, 유형 후보 |
| [followup.py](followup.py), [interpret_followup.py](interpret_followup.py) | 후속 비교·해석 코드 |
| [config/](config/), [tools/](tools/) | 전용 설정과 도구 |
| [notebooks/](notebooks/) | 기존 EDA 결과 열람 |

V1의 고정 동 분할과 분석표를 `../v1/`에서 읽는다. 새 외부 검증이나 최종 유형 확정을 뜻하지 않는다.
실행은 저장소 최상위에서 `python old/v2/followup.py ...` 형태로 한다.
[과거 캐시와 정확한 재현 안내](../README.md)를 먼저 확인한다.
