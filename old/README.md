# 이전 모델 실험

현재 분석은 [V3](../README.md)다. 이전 탐색 결과와 재현 자료를 이곳에 모았다.

- [v1 — 기본 모델과 기존 시험 결과](v1/README.md)
- [v2 — EDA 후속 비교와 해석](v2/README.md)
- [이전 종합 현황](previous_overview.md)
- [파일 이동표](relocation.json)

분석표·예측·성능 CSV, 압축 데이터, JSON 결과와 그림은 이동 전과 동일한 바이트로 보존했다.
문서 링크, 코드 import, 설정의 경로는 새 위치에 맞췄다. 공통 데이터와 생성 모듈은 루트에 유지한다.

`v1/sha256.json`은 과거 경로를 담은 원래 기록이다. 현재 무결성은
`python tools/verify_final.py`와 `tools/frozen_files.json`으로 확인한다.
과거 프로토콜의 경로·소스 해시는 당시 실행 기록이므로 다시 쓰지 않았다.
코드 경로가 바뀌어 과거 캐시의 소스 지문 검사는 재사용을 거절할 수 있다.
당시 환경·경로까지 정확히 재현하려면 정리 전 커밋
`5cba3abe46701b0b5bfadfd8d58e7b4a70962612`를 별도 checkout한다.
