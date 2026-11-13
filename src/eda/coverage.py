"""특성 확보율(coverage): 세대수·주차·난방·복도, 역·학교 거리. 국면·자치구·연도·건축 시기별 결측.

여기서 보는 값은 거래 행에 붙어 있는 '계약일 기준' 값이다. 모델 특성은 국면 시작 월 a 기준으로
다시 계산된다(config/features.yaml). 이 모듈은 값이 얼마나 채워져 있는지와 그 한계만 본다.
"""
import numpy as np
import pandas as pd

# 표시 이름 → 열. 단지 내부 특성과 입지 특성
INTERNAL = {'세대수': '세대수', '세대당 주차대수': '세대당_주차대수', '난방방식': '난방방식', '복도유형': '복도유형',
            '시공사(상위10 여부)': '시공사_상위10', '사용승인일': '사용승인일'}
ACCESS = {'최근접 역 거리': '최근접_역_거리(m)', '1km 내 노선 수': '1km내_노선수',
          '최근접 초등학교 거리': '최근접_초등학교_거리(m)', '1km 내 학교 수': '1km내_학교수'}
FEATURES = {**INTERNAL, **ACCESS}
BUILT_BINS = [-np.inf, 1979, 1989, 1999, 2009, 2019, np.inf]
BUILT_LABELS = ['1979년 이전', '1980년대', '1990년대', '2000년대', '2010년대', '2020년 이후']
HH_BINS = [0, 100, 300, 500, 1000, 2000, np.inf]
HH_LABELS = ['100세대 미만', '100~299', '300~499', '500~999', '1,000~1,999', '2,000세대 이상']


def overall(d):
    n = len(d)
    rows = [{'특성': k, '열': c, '값_있음': int(d[c].notna().sum()), '결측건수': int(d[c].isna().sum()),
             '결측률(%)': round(d[c].isna().mean() * 100, 2), '묶음': '단지 내부' if k in INTERNAL else '입지'}
            for k, c in FEATURES.items()]
    return pd.DataFrame(rows)


def missing_by(d, key, order=None, names=None):
    """key별 특성 결측률(%) 표. 행 = key 값, 열 = 특성."""
    miss = pd.DataFrame({k: d[c].isna() for k, c in FEATURES.items()})
    t = miss.groupby(d[key].values, observed=False).mean().mul(100).round(2)
    t.insert(0, '거래건수', d.groupby(key, observed=False).size().reindex(t.index).values)
    if order is not None:
        t = t.reindex(order)
    t = t.rename_axis(key).reset_index()
    if names is not None:
        t.insert(1, '국면', list(names))
    return t


def missing_by_built_period(d):
    """건축 시기별 결측률. 오래된 단지일수록 단지 정보가 비는지 본다."""
    x = d.assign(건축시기=pd.cut(d['건축년도'], BUILT_BINS, labels=BUILT_LABELS))
    return missing_by(x, '건축시기')


def missing_by_household_source(d):
    """세대수 출처(세대수_기준)별 다른 단지 특성의 결측률. K-apt에 없는 단지는 난방·복도·시공사가 구조적으로 빈다."""
    x = d.assign(세대수_출처=d['세대수_기준'].fillna('(세대수 없음)'))
    return missing_by(x, '세대수_출처')


def complex_level_coverage(d):
    """단지(자치구·법정동·번지·단지명) 단위 결측률. 거래 단위 결측률과 다르면 작은 단지에 결측이 몰린 것이다."""
    key = ['자치구', '법정동', '번지', '단지명']
    cid = d.groupby(key, sort=False).ngroup()
    first = d[list(FEATURES.values())].notna().groupby(cid).any()
    n = len(first)
    rows = [{'특성': k, '단지수': n, '값이_한번도_없는_단지': int((~first[c]).sum()),
             '단지_결측률(%)': round((~first[c]).mean() * 100, 2), '거래_결측률(%)': round(d[c].isna().mean() * 100, 2)}
            for k, c in FEATURES.items()]
    return pd.DataFrame(rows)


def category_distribution(d, col):
    t = d[col].fillna('(결측)').value_counts().rename('거래건수').rename_axis(col).reset_index()
    t['비율(%)'] = (t['거래건수'] / len(d) * 100).round(2)
    return t


def category_by_regime(d, regimes, col):
    """국면별 범주 비중(%), 결측 포함."""
    t = pd.crosstab(d['국면ID'], d[col].fillna('(결측)'), normalize='index').mul(100).round(2).reindex(list(regimes['id'])).rename_axis('국면ID')
    t.insert(0, '국면', regimes['name'].values)
    return t.reset_index()


def household_bins(d):
    b = pd.cut(d['세대수'], HH_BINS, labels=HH_LABELS, right=False)
    t = b.value_counts(sort=False).rename('거래건수').rename_axis('세대수_구간').reset_index()
    t['비율(%)'] = (t['거래건수'] / d['세대수'].notna().sum() * 100).round(2)
    return t


def distance_bands(d):
    """역·초등학교 직선거리 구간별 거래 비중(값이 있는 거래 기준)."""
    bins = [0, 250, 500, 750, 1000, 1500, np.inf]
    labels = ['250m 이하', '250~500m', '500~750m', '750m~1km', '1~1.5km', '1.5km 초과']
    out = {}
    for name, c in [('최근접 역', '최근접_역_거리(m)'), ('최근접 초등학교', '최근접_초등학교_거리(m)')]:
        b = pd.cut(d[c], bins, labels=labels, include_lowest=True)
        out[f'{name}_거래건수'] = b.value_counts(sort=False)
        out[f'{name}_비율(%)'] = (b.value_counts(sort=False) / d[c].notna().sum() * 100).round(2)
    return pd.DataFrame(out).rename_axis('직선거리').reset_index()


def access_by_regime(d, regimes):
    """국면별 입지 값 중앙값. 계약일 기준 값이라 새 역 개통·학교 신설이 반영된다(같은 단지도 시점마다 다를 수 있음)."""
    t = d.groupby('국면ID').agg(**{
        '역 거리 중앙값(m)': ('최근접_역_거리(m)', 'median'), '역 500m 이내(%)': ('최근접_역_거리(m)', lambda s: (s.dropna() <= 500).mean() * 100),
        '1km 내 노선 수 평균': ('1km내_노선수', 'mean'), '초등학교 거리 중앙값(m)': ('최근접_초등학교_거리(m)', 'median'),
        '1km 내 학교 수 중앙값': ('1km내_학교수', 'median')}).round(2).reindex(list(regimes['id'])).rename_axis('국면ID')
    t.insert(0, '국면', regimes['name'].values)
    return t.reset_index()


def access_changes_within_complex(d):
    """같은 단지 안에서 계약 시점에 따라 입지 값이 달라진 단지 수(시점 반영 여부 확인)."""
    key = ['자치구', '법정동', '번지', '단지명']
    k = d['위도'].notna()
    g = d[k].groupby(key, sort=False)
    rows = []
    for name, c in ACCESS.items():
        nun = g[c].nunique()
        rows.append({'특성': name, '좌표_있는_단지수': int(len(nun)), '값이_시점에_따라_바뀐_단지': int((nun > 1).sum()),
                     '비율(%)': round((nun > 1).mean() * 100, 2)})
    return pd.DataFrame(rows)


def static_assumption(d, regimes):
    """단지 내부값이 '현재값을 과거에 적용'한 가정인 거래의 비중(단지정보_현재값가정 = '예'), 국면별."""
    flag = d['단지정보_현재값가정'].eq('예')
    t = pd.DataFrame({'거래건수': d.groupby('국면ID').size(), '현재값가정_표시': flag.groupby(d['국면ID']).sum()}).reindex(list(regimes['id'])).rename_axis('국면ID')
    t['비율(%)'] = (t['현재값가정_표시'] / t['거래건수'] * 100).round(2)
    t.insert(0, '국면', regimes['name'].values)
    return t.reset_index()


def coord_basis(d, regimes):
    """좌표기준(단지 대표점 / 지오코딩 주소 지점) 국면별 비중. 거리 값의 정밀도가 다르다."""
    t = pd.crosstab(d['국면ID'], d['좌표기준'].fillna('(좌표 없음)'), normalize='index').mul(100).round(2).reindex(list(regimes['id'])).rename_axis('국면ID')
    t.insert(0, '국면', regimes['name'].values)
    return t.reset_index()


def parking_extremes(d):
    p = d['세대당_주차대수']
    return {'값_있음': int(p.notna().sum()), '중앙값': float(p.median()), '0.5대_미만': int((p < 0.5).sum()),
            '1대_미만': int((p < 1).sum()), '3대_초과': int((p > 3).sum()), '최댓값': float(p.max())}


def size_by_household_source(d):
    """세대수 출처별 단지 규모(거래 기준 세대수 분위수). K-apt 등록 단지와 미등록 단지의 크기 차이."""
    g = d.groupby(d['세대수_기준'].fillna('(세대수 없음)'))['세대수']
    t = pd.DataFrame({'거래건수': g.size(), '세대수_p25': g.quantile(.25), '세대수_중앙값': g.median(), '세대수_p75': g.quantile(.75)})
    return t.rename_axis('세대수_출처').reset_index()
