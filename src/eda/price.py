"""가격 분석: 거래금액, ㎡당 가격, 면적·층·연식·자치구별 차이.

여기서 가격은 **기술 통계**다. 거래금액·평당가는 y의 재료라 모델 특성이 아니다(config/features.yaml excluded).
연도·국면을 섞은 원시 가격은 시장 수준 변화와 거래 구성 변화를 함께 담는다. 그래서 면적·층·연식 비교는
같은 계약 연도 안에서의 상대 가격(연도 중앙값 대비 %)도 함께 낸다.
"""
import numpy as np
import pandas as pd

AREA_BINS = [0, 40, 60, 85, 102, 135, np.inf]
AREA_LABELS = ['40㎡ 이하', '40~60㎡', '60~85㎡', '85~102㎡', '102~135㎡', '135㎡ 초과']
FLOOR_BINS = [-np.inf, 0, 2, 5, 10, 15, 20, 30, np.inf]
FLOOR_LABELS = ['0층 이하', '1~2층', '3~5층', '6~10층', '11~15층', '16~20층', '21~30층', '31층 이상']
AGE_BINS = [-np.inf, 5, 10, 15, 20, 25, 30, 35, 40, np.inf]
AGE_LABELS = ['5년 이하', '6~10년', '11~15년', '16~20년', '21~25년', '26~30년', '31~35년', '36~40년', '40년 초과']
Q = [.05, .25, .5, .75, .95]
QN = ['p5', 'p25', '중앙값', 'p75', 'p95']


def describe(x):
    """건수·평균·분위수 한 줄."""
    x = x.dropna()
    out = {'건수': int(x.size), '평균': x.mean(), '표준편차': x.std()}
    out.update(dict(zip(QN, x.quantile(Q))))
    out.update({'최솟값': x.min(), '최댓값': x.max(), '왜도': x.skew()})
    return pd.Series(out)


def price_summary(d):
    """거래금액(억원)·㎡당가(만원)·전용면적의 전체 분포."""
    t = pd.DataFrame({'거래금액_억원': describe(d['거래금액_억원']), '㎡당가_만원': describe(d['㎡당가_만원']),
                      '평당가_만원': describe(d['평당가_만원']), '전용면적(㎡)': describe(d['전용면적(㎡)'])}).T
    return t.rename_axis('변수').reset_index()


def price_band_share(d):
    """거래금액 구간별 건수. 9억·15억은 config/features.yaml의 가격대 통제 변수 경계와 같은 값(여기서는 거래 단위 기술 통계)."""
    b = pd.cut(d['거래금액_억원'], [0, 3, 6, 9, 15, 30, np.inf], labels=['3억 이하', '3~6억', '6~9억', '9~15억', '15~30억', '30억 초과'])
    t = b.value_counts(sort=False).rename('거래건수').rename_axis('가격대').reset_index()
    t['비율(%)'] = (t['거래건수'] / len(d) * 100).round(2)
    return t


def by_group(d, key, value='㎡당가_만원', observed=True):
    """그룹별 건수와 가격 분위수."""
    g = d.groupby(key, observed=observed)[value]
    t = g.quantile(Q).unstack()
    t.columns = QN
    t.insert(0, '거래건수', g.size())
    return t.reset_index()


def add_bins(d):
    """면적·층·연식 구간 열을 붙인 사본(필요한 열만)."""
    x = d[['계약연도', '국면', '자치구', '㎡당가_만원', '거래금액_억원', '전용면적(㎡)', '층', '건물연식']].copy()
    x['면적구간'] = pd.cut(x['전용면적(㎡)'], AREA_BINS, labels=AREA_LABELS)
    x['층구간'] = pd.cut(x['층'], FLOOR_BINS, labels=FLOOR_LABELS)
    x['연식구간'] = pd.cut(x['건물연식'], AGE_BINS, labels=AGE_LABELS)
    # 같은 계약 연도·같은 자치구 중앙값 대비 ㎡당가(%). 시기·위치 차이를 걷어낸 상대 수준
    base = x.groupby(['계약연도', '자치구'])['㎡당가_만원'].transform('median')
    x['상대가격(%)'] = (x['㎡당가_만원'] / base - 1) * 100
    return x


def by_bin(x, key):
    """구간별: 건수, ㎡당가 분위수, 거래금액 중앙값, 연도·자치구 중앙값 대비 상대가격 중앙값."""
    t = by_group(x, key, observed=False)
    g = x.groupby(key, observed=False)
    t['거래금액_억원_중앙값'] = g['거래금액_억원'].median().values
    t['상대가격_중앙값(%)'] = g['상대가격(%)'].median().values
    t['상대가격_p25(%)'] = g['상대가격(%)'].quantile(.25).values
    t['상대가격_p75(%)'] = g['상대가격(%)'].quantile(.75).values
    return t


def district_table(d):
    """자치구별 건수, 거래금액·㎡당가 중앙값과 사분위수, 전용면적 중앙값."""
    t = by_group(d, '자치구')
    g = d.groupby('자치구')
    t['거래금액_억원_중앙값'] = g['거래금액_억원'].median().values
    t['전용면적_중앙값'] = g['전용면적(㎡)'].median().values
    t['권역'] = g['권역'].first().values
    return t.sort_values('중앙값', ascending=False, ignore_index=True)


def district_year_median(d):
    """자치구×계약 연도 ㎡당가 중앙값(만원)."""
    return d.pivot_table(index='자치구', columns='계약연도', values='㎡당가_만원', aggfunc='median')


def spearman_with_price(d):
    """ln(㎡당가)와 주요 숫자 열의 Spearman 순위상관. 전체, 그리고 연도·자치구 중앙값을 뺀 뒤.

    연관 관계의 크기만 보여 준다. 인과 해석·특성 선택 근거로 쓰지 않는다.
    """
    cols = ['전용면적(㎡)', '층', '건물연식', '세대수', '세대당_주차대수',
            '최근접_역_거리(m)', '1km내_노선수', '최근접_초등학교_거리(m)', '1km내_학교수']
    lp = np.log(d['㎡당가_만원'])
    rel = lp - lp.groupby([d['계약연도'], d['자치구']]).transform('median')
    rows = []
    for c in cols:
        k = d[c].notna()
        rows.append({'변수': c, '건수': int(k.sum()),
                     '순위상관_전체': d.loc[k, c].corr(lp[k], method='spearman'),
                     '순위상관_연도·자치구_보정': d.loc[k, c].corr(rel[k], method='spearman')})
    return pd.DataFrame(rows)
