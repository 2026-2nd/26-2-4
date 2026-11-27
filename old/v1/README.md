# V1 — 기본 모델과 기존 시험 결과

이전 탐색 실험이다. 현재 분석은 [V3](../../README.md)를 기준으로 한다.

| 위치 | 내용 |
|---|---|
| [cells/](cells/README.md) | 셀 분석표와 생성 검증 |
| [models/](models/README.md) | 동 분할, 모델 선택, OOF·시험 예측 |
| [기본 모델 결과](models/results_v1.md) | 기존 시험 결과 |
| [train.py](train.py) | V1 학습·평가 코드 |
| [config/](config/), [tools/](tools/) | 전용 설정·보고서·재적합·검증 도구 |

공통 특성·셀·국면 규칙과 원자료는 루트 `config/`, `data/`에 있다.
실행은 저장소 최상위에서 `python old/v1/train.py ...` 형태로 한다.
[과거 캐시와 정확한 재현 안내](../README.md)를 먼저 확인한다.
