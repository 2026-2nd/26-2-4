"""자료 품질: 결측, 결측사유, 중복, 값 점검, 이상치, 연도·자치구·국면별 건수."""
import numpy as np
import pandas as pd

# 값이 정해진 범주 열과 허용값(docs/data.md §4)
DOMAINS = {
    '난방방식': {'개별난방', '지역난방', '중앙난방', '기타'},
    '복도유형': {'계단식', '혼합식', '복도식', '기타'},
    '연식_기준': {'사용승인일', '건축년도(7월 준공 가정)', '준공 전 거래', '건축년도(7월 준공 가정) 음수→0'},
    '세대수_기준': {'단지 목록(K-apt)', '건축물대장', '건축물대장(번지 합계)'},
    '좌표기준': {'단지 대표점', '주소 지점(지오코딩)'},
    '평형대': {'10평미만', '10~20평', '20~30평', '30~40평', '40평이상'},
    '시공사_상위10': {0.0, 1.0}, '단지명_상위10브랜드': {0.0, 1.0}, '토지거래허가구역': {0.0, 1.0},
}
# 같은 거래로 보이는지 판단할 때 쓰는 열(거래ID·동 제외: 동은 2022년 이전 미공개)
SAME_TRADE_KEY = ['자치구', '법정동', '번지', '단지명', '전용면적(㎡)', '층', '계약일', '거래금액_만원']
PYEONG_M2 = 3.3058


def missing_table(d, columns):
    """열별 결측 건수·비율(%). columns = 원본 43열."""
    n = len(d)
    miss = d[columns].isna().sum()
    t = pd.DataFrame({'열': columns, '결측건수': miss.values, '결측률(%)': (miss.values / n * 100).round(2)})
    return t.sort_values(['결측건수', '열'], ascending=[False, True], ignore_index=True)


def split_reasons(s):
    """결측사유 Series('[항목] 이유 / [항목] 이유') → (행 번호, 항목, 이유) 긴 표."""
    x = s.dropna().str.split(' / ').explode().str.strip()
    m = x.str.extract(r'^\[(?P<항목>[^\]]+)\]\s*(?P<이유>.*)$')
    m['이유'] = m['이유'].where(m['항목'].notna(), x)   # '[항목]' 형식이 아닌 값도 버리지 않는다
    m['항목'] = m['항목'].fillna('(형식 외)')
    return m


def missing_reason_table(d):
    """결측사유 항목·이유별 거래 건수와 비율."""
    r = split_reasons(d['결측사유'])
    t = r.groupby(['항목', '이유']).size().rename('건수').reset_index()
    t['비율(%)'] = (t['건수'] / len(d) * 100).round(2)
    return t.sort_values('건수', ascending=False, ignore_index=True)


def missing_reason_patterns(d, top=15):
    """결측사유 조합(한 행에 적힌 사유 전체) 상위."""
    t = d['결측사유'].fillna('(사유 없음)').value_counts().head(top).rename('건수').rename_axis('결측사유_조합').reset_index()
    t['비율(%)'] = (t['건수'] / len(d) * 100).round(2)
    return t


def missing_without_reason(d):
    """값이 비었는데 결측사유에 해당 항목이 없는 건수(문서화되지 않은 결측)."""
    reason = d['결측사유'].fillna('')
    checks = {
        '동': ('동', r'\[동\]'),
        '세대수': ('세대수', r'\[단지정보\]|\[건축물대장\]|\[세대수\]'),
        '세대당_주차대수': ('세대당_주차대수', r'\[주차\]|\[단지정보\]|\[건축물대장\]'),
        '난방방식': ('난방방식', r'\[난방·복도·시공사\]|\[단지정보\]|\[난방\]'),
        '위도': ('위도', r'\[좌표\]|주소 소실'),
    }
    rows = []
    for name, (col, pat) in checks.items():
        miss = d[col].isna()
        rows.append({'열': name, '결측건수': int(miss.sum()),
                     '사유_없는_결측': int((miss & ~reason.str.contains(pat)).sum())})
    return pd.DataFrame(rows)


def duplicate_summary(d, columns):
    """완전 중복, 거래ID 중복, '같은 거래로 보이는 행'(ID·동만 다른 행) 수."""
    same = d.duplicated(SAME_TRADE_KEY, keep=False)
    extra = d.duplicated(SAME_TRADE_KEY, keep='first')
    return {
        '전체열_완전중복_행': int(d.duplicated(columns).sum()),
        '거래ID_중복_행': int(d['거래ID'].duplicated().sum()),
        '같은조건_거래_묶음에_속한_행': int(same.sum()),
        '같은조건_거래_중_두번째_이후_행': int(extra.sum()),
        '같은조건_기준열': SAME_TRADE_KEY,
    }


def same_trade_by_year(d):
    """같은 조건(단지·면적·층·계약일·금액)이 겹치는 행을 연도별로."""
    extra = d.duplicated(SAME_TRADE_KEY, keep='first')
    t = pd.DataFrame({'거래건수': d.groupby('계약연도').size(), '같은조건_두번째_이후': extra.groupby(d['계약연도']).sum()})
    t['비율(%)'] = (t['같은조건_두번째_이후'] / t['거래건수'] * 100).round(2)
    return t.reset_index()


def validity_checks(d):
    """값·열 사이 일관성 점검. 한 줄 = 규칙 하나, '위반건수'가 0이 아니면 내용을 봐야 한다."""
    y = d['계약일_dt']
    rows = []

    def add(rule, mask, note=''):
        rows.append({'점검': rule, '위반건수': int(mask.sum()), '비고': note})

    for c, n in d.attrs.get('숫자변환_실패', {}).items():
        if n:
            add(f'{c}: 숫자·날짜로 읽을 수 없는 값', pd.Series([True] * n))
    add('숫자·날짜 변환 실패(전체 열 합)', pd.Series([True] * sum(d.attrs.get('숫자변환_실패', {}).values())))
    add('계약일이 2017-01-01 ~ 2026-10-31 밖', (y < '2017-01-01') | (y > '2026-10-31'))
    add('계약년월 ≠ 계약일의 연월', d['계약년월'] != y.dt.strftime('%Y%m'))
    add('계약월 ≠ 계약일의 월', d['계약월'] != y.dt.month)
    add('국면이 배정되지 않은 거래', d['국면ID'].isna())
    add('거래금액_만원 ≤ 0', d['거래금액_만원'] <= 0)
    add('전용면적(㎡) ≤ 0', d['전용면적(㎡)'] <= 0)
    add('층 ≤ 0', d['층'] <= 0, '지하·반지하 표기일 수 있음(오류로 단정하지 않음)')
    add('층이 정수가 아님', d['층'].notna() & (d['층'] % 1 != 0))
    add('전용면적_평 ≠ ㎡ ÷ 3.3058 (오차 0.02평 초과)', (d['전용면적_평'] - d['전용면적(㎡)'] / PYEONG_M2).abs() > 0.02)
    add('평당가_만원 ≠ 거래금액 ÷ 전용면적_평 (오차 1% 초과)',
        ((d['평당가_만원'] - d['거래금액_만원'] / d['전용면적_평']).abs() / d['평당가_만원']) > 0.01)
    add('건물연식 ≠ 계약연도 − 건축년도', d['건물연식'].notna() & (d['건물연식'] != d['계약연도'] - d['건축년도']))
    add('건물연식 < 0', d['건물연식'] < 0)
    add('건축년도 > 계약연도', d['건축년도'] > d['계약연도'], '준공 전 거래(분양권·입주권) 가능')
    add('연식_개월 < 0', d['연식_개월'] < 0)
    add("연식_기준 = '준공 전 거래'", d['연식_기준'] == '준공 전 거래', 'config/target.yaml의 제외 대상')
    ap = pd.to_datetime(d['사용승인일'], format='%Y-%m-%d', errors='coerce')
    add('사용승인일이 날짜 형식(YYYY-MM-DD)이 아님', d['사용승인일'].notna() & ap.isna(), "일(日)이 '00'으로 적힌 값")
    add('사용승인일이 계약일보다 뒤', ap > y, "'준공 전 거래' + 같은 달 안에서 승인일이 며칠 늦은 거래")
    add('사용승인 연도와 건축년도 차이 2년 이상', (ap.dt.year - d['건축년도']).abs() > 1)
    add('위도·경도가 서울 범위(37.40~37.72, 126.75~127.20) 밖',
        d['위도'].notna() & ~(d['위도'].between(37.40, 37.72) & d['경도'].between(126.75, 127.20)))
    add('좌표 없음', d['위도'].isna(), "결측사유 '주소 소실 추정'. 모델 표본 제외 대상")
    add('좌표는 있는데 역 거리 없음', d['위도'].notna() & d['최근접_역_거리(m)'].isna())
    add('최근접_역_거리(m) < 0', d['최근접_역_거리(m)'] < 0)
    add('최근접_초등학교_거리(m) < 0', d['최근접_초등학교_거리(m)'] < 0)
    add('세대수 ≤ 0', d['세대수'] <= 0)
    add('세대당_주차대수 < 0', d['세대당_주차대수'] < 0)
    add('세대당_주차대수 = 0', d['세대당_주차대수'] == 0, '값은 있으나 0. 결측사유에 주차 항목 없음 → 사실상 미기재로 보임')
    add('세대당_주차대수 = 0인데 결측사유에 [주차]가 있음', (d['세대당_주차대수'] == 0) & d['결측사유'].fillna('').str.contains('주차'))
    add('세대당_주차대수 > 3', d['세대당_주차대수'] > 3, '주상복합 등 비주거 주차 포함 추정(docs/data.md §6)')
    add("세대수_기준 = '건축물대장(번지 합계)'", d['세대수_기준'] == '건축물대장(번지 합계)', '번지 전체 세대수')
    for c, ok in DOMAINS.items():
        add(f'{c}: 허용값 밖', d[c].notna() & ~d[c].isin(ok))
    add('자치구가 서울 25개 구가 아님', d['권역'].isna())
    return pd.DataFrame(rows)


def numeric_profile(d, cols):
    """숫자 열의 분위수 요약."""
    q = [0, .001, .01, .05, .25, .5, .75, .95, .99, .999, 1]
    names = ['최솟값', 'p0.1', 'p1', 'p5', 'p25', '중앙값', 'p75', 'p95', 'p99', 'p99.9', '최댓값']
    t = d[cols].quantile(q).T
    t.columns = names
    t.insert(0, '평균', d[cols].mean())
    t.insert(0, '건수', d[cols].count())
    return t.rename_axis('열').reset_index()


def iqr_outliers(d, cols, k=1.5):
    """Tukey 기준(Q1 − k·IQR, Q3 + k·IQR) 밖 건수. 지우자는 뜻이 아니라 분포의 꼬리를 보는 용도."""
    rows = []
    for c in cols:
        x = d[c].dropna()
        q1, q3 = x.quantile([.25, .75])
        lo, hi = q1 - k * (q3 - q1), q3 + k * (q3 - q1)
        rows.append({'열': c, '하한': lo, '상한': hi, '하한_미만': int((x < lo).sum()), '상한_초과': int((x > hi).sum()),
                     '이상치_비율(%)': round(((x < lo) | (x > hi)).mean() * 100, 2)})
    return pd.DataFrame(rows)


def local_price_outliers(d, z=3.0, min_n=30):
    """같은 자치구·같은 계약 월 안에서 ln(㎡당가)가 중앙값에서 크게 벗어난 거래.

    시기와 위치의 가격 차이를 걷어낸 뒤의 이상치다. 척도는 MAD 기반 robust z.
    """
    lp = np.log(d['㎡당가_만원'])
    g = [d['자치구'], d['계약년월_ym']]
    med = lp.groupby(g).transform('median')
    mad = (lp - med).abs().groupby(g).transform('median') * 1.4826
    n = lp.groupby(g).transform('size')
    rz = (lp - med) / mad
    ok = n >= min_n
    return {'기준': f'자치구×계약월(거래 {min_n}건 이상) 안 ln(㎡당가)의 robust z, |z| > {z}',
            '판정가능_거래': int(ok.sum()), '낮은쪽': int((ok & (rz < -z)).sum()), '높은쪽': int((ok & (rz > z)).sum()),
            '비율(%)': round(float((ok & (rz.abs() > z)).sum() / ok.sum() * 100), 2)}


def counts_by(d, key):
    t = d.groupby(key, sort=True).size().rename('거래건수').reset_index()
    t['비율(%)'] = (t['거래건수'] / len(d) * 100).round(2)
    return t


def counts_district_year(d):
    return d.pivot_table(index='자치구', columns='계약연도', values='거래ID', aggfunc='count', fill_value=0)


def monthly_counts(d):
    t = d.groupby(['계약년월_ym', '국면ID', '국면']).size().rename('거래건수').reset_index()
    return t.sort_values('계약년월_ym', ignore_index=True)


def zero_parking_complexes(d):
    """세대당 주차대수가 0으로 적힌 단지 목록(값이 있는 것으로 집계되지만 실제로는 미기재로 보이는 경우)."""
    z = d[d['세대당_주차대수'] == 0]
    t = z.groupby(['자치구', '법정동', '번지', '단지명']).agg(거래건수=('거래ID', 'size'), 세대수=('세대수', 'first'),
                                                    세대수_기준=('세대수_기준', 'first'), 건축년도=('건축년도', 'first'))
    return t.sort_values('거래건수', ascending=False).reset_index()


def same_trade_profile(d):
    """같은 조건 거래 묶음의 성격: 묶음 크기, 소형 비중, 동(棟)이 공개된 묶음에서 동이 같은지."""
    dd = d[d.duplicated(SAME_TRADE_KEY, keep=False)]
    g = dd.groupby(SAME_TRADE_KEY).size()
    h = dd[dd['동'].notna()].groupby(SAME_TRADE_KEY)['동'].nunique()
    return {'묶음_수': int(len(g)), '묶음_최대_크기': int(g.max()), '2건_묶음': int((g == 2).sum()),
            '전용40㎡이하_비율(%)_묶음내': round(float((dd['전용면적(㎡)'] <= 40).mean() * 100), 2),
            '전용40㎡이하_비율(%)_전체': round(float((d['전용면적(㎡)'] <= 40).mean() * 100), 2),
            '동_공개된_묶음': int(len(h)), '동이_모두_같은_묶음': int((h == 1).sum()), '동이_다른_묶음': int((h > 1).sum())}
