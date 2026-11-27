# V3 실행 코드

모든 명령은 저장소 최상위에서 실행한다. [현재 결과](../README.md) · [검증 규칙](../docs/nested_v3.md)

| 파일 | 역할 |
|---|---|
| [model/nested_v3.py](model/nested_v3.py) | 학습 전용 데이터 생성, 중첩 CV, 재적합, 예측 검증 |
| [model/common.py](model/common.py) | 설정·특성 목록·가중 성능 지표·저장 함수 |
| [model/design.py](model/design.py) | 특성 구성·학습 fold 전처리 |
| [eda/](eda/) | 학습 자료에 재사용하는 EDA 모듈 |
| [cells/build_cells.py](cells/build_cells.py) | 셀 목표·시점 특성·통제변수 계산 |
| [../tools/run_v3_audit.py](../tools/run_v3_audit.py) | 전체 변수/현재값 제외 구성의 짝지은 비교 |

```bash
python -m pytest -q
python tools/verify_final.py
python src/model/nested_v3.py build --output results/leakage_audit_v3
python tools/run_v3_audit.py --output results/leakage_audit_v3 --workers 4
```

개별 분석표 실행:

```bash
python src/model/nested_v3.py evaluate --table down_window --output results/leakage_audit_v3
python src/model/nested_v3.py evaluate --table down_window --feature-policy without_snapshot --output results/leakage_audit_v3
```

같은 출력 경로에 완료 결과가 있으면 덮어쓰지 않는다. 변경 후에는 새 출력 경로에서 build부터 시작한다.
V3는 `old/`의 실험 모듈을 import하지 않는다. 고정 동 분할은 `data/splits/`에서 읽는다.

`pipeline/`, `geo/`, `features/`, `dataset/`, `buildreg/`, `regime/`는 공통 원자료 생성 기반이다.
이 모듈의 버전 이름을 모델 실험 버전과 혼동하지 않는다.
V1/V2 실행·결과는 [old 안내](../old/README.md)에서 확인한다.
