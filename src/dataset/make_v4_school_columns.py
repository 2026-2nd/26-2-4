"""v3 → v4: 학교 열 정리 (2026-11-09 결정, docs/decisions.md).

- 뺀 열: 최근접 초·중·고 이름, 최근접 중·고 거리, 1km 내 초·중·고 수
- 남긴 열: 최근접_초등학교_거리(m)
- 추가 열: 1km내_학교수 = 1km 내 초·중·고 수의 합 (좌표가 없으면 빈 값), 최근접_초등학교_거리(m) 바로 뒤
- 결측사유 등 나머지 열은 그대로
"""
import hashlib, pathlib
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
V3 = ROOT / 'data/final/아파트_실거래_전처리_2017_2026_v3.csv'
V4 = ROOT / 'data/final/아파트_실거래_전처리_2017_2026_v4.csv'
COUNTS = ['1km내_초등학교수', '1km내_중학교수', '1km내_고등학교수']
DROP = ['최근접_초등학교', '최근접_중학교', '최근접_중학교_거리(m)', '최근접_고등학교', '최근접_고등학교_거리(m)'] + COUNTS


def main():
    d = pd.read_csv(V3, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    has = d[COUNTS].ne('').all(axis=1)
    total = d.loc[has, COUNTS].astype(int).sum(axis=1).astype(str)
    d['1km내_학교수'] = ''
    d.loc[has, '1km내_학교수'] = total
    cols = [c for c in d.columns if c not in DROP and c != '1km내_학교수']
    cols.insert(cols.index('최근접_초등학교_거리(m)') + 1, '1km내_학교수')
    d[cols].to_csv(V4, index=False, encoding='utf-8-sig')
    print(d[cols].shape, hashlib.sha256(V4.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
