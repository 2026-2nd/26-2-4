"""최종 데이터(v5)와 확정 국면을 읽는다. 원본 파일은 읽기만 한다.

- 빈 문자열은 결측(NaN)으로 읽는다(docs/data.md: "빈 값은 빈 문자열").
- 국면 경계는 config/regime.yaml에서만 가져온다. 여기에 다시 적지 않는다.
- 아래 '파생 열'은 EDA 표·그림용이다. 모델 특성이 아니다(특성 정의는 config/features.yaml).
"""
import pathlib

import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
DATA = ROOT / 'data/final/아파트_실거래_전처리_2017_2026_v5.csv.xz'
REGIME_CFG = ROOT / 'config/regime.yaml'

EXPECTED_ROWS = 617_592   # docs/data.md §1. 실제 파일과 다르면 run_eda가 멈춘다
EXPECTED_COLS = 43

NUMERIC = [
    '층', '계약월', '계약시점_월순번', '건축년도', '건물연식', '연식_개월',
    '전용면적(㎡)', '전용면적_평', '거래금액_만원', '평당가_만원', '위도', '경도',
    '최근접_역_거리(m)', '1km내_노선수', '최근접_초등학교_거리(m)', '1km내_학교수',
    '세대수', '세대당_주차대수', '시공사_상위10', '단지명_상위10브랜드', '토지거래허가구역',
]
# EDA에서 덧붙이는 열(원본 43열에는 없음)
DERIVED = ['계약일_dt', '계약연도', '계약년월_ym', '국면ID', '국면', '㎡당가_만원', '거래금액_억원', '권역']

# 서울 5개 생활권. src/regime/build_index_2017_2026.py의 ZONE과 같은 구분
ZONE = {
    '종로구': '도심권', '중구': '도심권', '용산구': '도심권',
    '성동구': '동북권', '광진구': '동북권', '동대문구': '동북권', '중랑구': '동북권',
    '성북구': '동북권', '강북구': '동북권', '도봉구': '동북권', '노원구': '동북권',
    '은평구': '서북권', '서대문구': '서북권', '마포구': '서북권',
    '양천구': '서남권', '강서구': '서남권', '구로구': '서남권', '금천구': '서남권',
    '영등포구': '서남권', '동작구': '서남권', '관악구': '서남권',
    '서초구': '동남권', '강남구': '동남권', '송파구': '동남권', '강동구': '동남권',
}
ZONES = ['도심권', '동북권', '서북권', '서남권', '동남권']


def load_regimes(path=REGIME_CFG):
    """config/regime.yaml의 확정 국면 → DataFrame(id, name, start, end, side, L, official_change_pct). 순서 유지."""
    cfg = yaml.safe_load(pathlib.Path(path).read_text(encoding='utf-8'))
    r = pd.DataFrame(cfg['regimes'])
    r['start'] = r['start'].astype(str)
    r['end'] = r['end'].where(r['end'].notna(), None)
    return r[['id', 'name', 'start', 'end', 'side', 'L', 'official_change_pct']]


def assign_regime(ym, regimes):
    """계약 월('YYYY-MM' 문자열 Series) → 국면 id Series. 끝이 없는(진행 중) 국면은 자료 끝까지."""
    out = pd.Series(pd.NA, index=ym.index, dtype='object')
    for r in regimes.itertuples():
        k = ym >= r.start
        if r.end is not None:
            k &= ym <= str(r.end)
        out[k] = r.id
    return out


def read_raw(path=DATA):
    """원본 그대로(모두 문자열, 빈 값은 '')."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, encoding='utf-8-sig')


def prepare(raw, regimes=None):
    """문자열 원본 → 분석용 표. 숫자 열 변환, 빈 값 → NaN, 파생 열 추가.

    숫자로 바꿀 수 없던 비어 있지 않은 값의 수는 d.attrs['숫자변환_실패']에 남긴다.
    """
    regimes = load_regimes() if regimes is None else regimes
    d = raw.replace('', pd.NA)
    fail = {}
    for c in NUMERIC:
        v = pd.to_numeric(d[c], errors='coerce')
        fail[c] = int((d[c].notna() & v.isna()).sum())
        d[c] = v.astype('float64')
    d['계약일_dt'] = pd.to_datetime(d['계약일'], format='%Y-%m-%d', errors='coerce')
    fail['계약일'] = int(d['계약일_dt'].isna().sum())
    d['계약연도'] = d['계약일_dt'].dt.year
    d['계약년월_ym'] = d['계약일_dt'].dt.strftime('%Y-%m')
    d['국면ID'] = assign_regime(d['계약년월_ym'], regimes)
    d['국면'] = d['국면ID'].map(dict(zip(regimes['id'], regimes['name'])))
    d['㎡당가_만원'] = d['거래금액_만원'] / d['전용면적(㎡)']
    d['거래금액_억원'] = d['거래금액_만원'] / 10_000
    d['권역'] = d['자치구'].map(ZONE)
    d.attrs['숫자변환_실패'] = fail
    return d


def load(path=DATA):
    """(분석용 표, 국면 표). 행·열 수가 문서와 다르면 멈춘다."""
    raw = read_raw(path)
    if raw.shape != (EXPECTED_ROWS, EXPECTED_COLS):
        raise ValueError(f'데이터 크기가 문서와 다르다: {raw.shape} != ({EXPECTED_ROWS}, {EXPECTED_COLS})')
    regimes = load_regimes()
    d = prepare(raw, regimes)
    d.attrs['원본_열'] = list(raw.columns)
    return d, regimes
