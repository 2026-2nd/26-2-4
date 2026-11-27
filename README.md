# 서울 아파트 시장 국면별 특성 분석 — V3

기계학습기초 4조 · **어떤 아파트가 상승기에 서울보다 더 오르고, 하락기에 덜 떨어졌는가?**

현재 분석은 **학습 전용 EDA와 중첩 법정동 교차검증(V3)**이다.
미래 시장 방향 예측이나 인과효과 추정이 아닌 사후 국면 분석이다.

## V3 읽는 순서

| 순서 | 문서 | 내용 |
|---|---|---|
| 1 | [V3 방법과 검증 규칙](docs/nested_v3.md) | 자료 분리, 목표 정의, 모델 선택, 한계 |
| 2 | [누수 점검 결과](reports/leakage_audit_v3/audit_report_ko.txt) | 수정 내용과 현재 단지 정보 제외 실험 |
| 3 | [12개 분석표의 비교 수치](reports/leakage_audit_v3/paired_comparison.csv) | 오차 차이, 구간, 예측 순위 상관 |
| 4 | [실행 코드와 순서](src/README.md) | 데이터 생성 → 학습·평가 → 비교 |
| 5 | [남은 작업](docs/handoff.md) | 특성 해석과 새로운 외부 검증 |

## 확인된 상태

- 기존 시험용 64개 동을 제외하고, 255개 학습 동의 원자료 480,007건을 사용한다.
- 12개 분석표 × 전체 변수/현재값 제외 구성의 **24개 평가와 집계가 완료**됐다.
- 현재값 제외 시 RMSE는 0.47~13.88% 증가했고, 예측 순위 상관은 0.818~0.908이다.
- 이는 현재 단지 정보에 대한 예측 의존성 결과이며, 차이 전체가 누수라는 증거는 아니다.
- **새 독립 외부 검증은 아직 없다.** 과거 탐색과 현재값 소급 적용의 한계가 남는다.

[검증된 비교 실행과 아티팩트](https://github.com/2026-2nd/26-2-4/actions/runs/45923897103)

## 실행

저장소 최상위에서 실행한다.

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python tools/verify_final.py
python src/model/nested_v3.py build --output results/leakage_audit_v3
python tools/run_v3_audit.py --output results/leakage_audit_v3 --workers 4
```

코드·설정·입력이 바뀌면 새 출력 디렉터리를 사용한다. 기존 결과를 덮어쓰지 않는다.

## 저장소 구조

| 위치 | 역할 |
|---|---|
| [src/model/](src/model/) | V3 실행과 공통 전처리·평가 함수 |
| [src/eda/](src/eda/), [src/cells/](src/cells/) | 재사용하는 EDA·셀 생성 모듈 |
| [config/](config/) | 공통 데이터 규칙 및 V3 평가 규칙 |
| [data/splits/](data/splits/) | V3 고정 동 분할과 출처 |
| [reports/leakage_audit_v3/](reports/leakage_audit_v3/) | 검증된 V3 비교 결과 |
| [old/v1/](old/v1/README.md) | V1 분석표·모델·시험 결과·전용 코드 |
| [old/v2/](old/v2/README.md) | V2 전체 자료 EDA·후속 비교·해석·전용 코드 |
| [tests/](tests/), [tools/](tools/) | 회귀 테스트, 무결성 검증, V3 비교 실행 |

`data/`와 `src/pipeline/` 등의 데이터 생성 코드는 공통 기반이다. 그 안의 v1/v2/v3 표기는
데이터 처리 버전으로, 모델 실험 V1/V2/V3와 다르다. 바이너리와 실행 캐시는 Git 제외 `results/`에 저장한다.

이전 실험은 [old 안내](old/README.md)에서 읽는다. 과거 전체 자료 EDA와 V1/V2 성능은
현재 V3의 최종 성능 근거로 사용하지 않는다.

[데이터 규격](docs/data.md) · [결정 기록](docs/decisions.md) · [팀 역할](docs/roles/README.md)
