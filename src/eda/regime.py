"""국면별 EDA: 거래 건수, 분포 비교, 표본 불균형과 거래 구성(선택 편향).

국면 경계는 config/regime.yaml의 확정값을 그대로 읽는다(load.load_regimes). 여기서 다시 판정하지 않는다.
국면은 기간 전체의 지수를 본 뒤 정한 사후(ex-post) 구분이다. 국면별 통계는 과거를 설명하는 용도이며
"국면 안에서 미리 알 수 있던 정보"가 아니다.
"""
import numpy as np
import pandas as pd

Q = [.05, .25, .5, .75, .95]
QN = ['p5', 'p25', '중앙값', 'p75', 'p95']
GANGNAM3 = ['강남구', '서초구', '송파구']
CELL_KEY = ['자치구', '법정동', '번지', '단지명']   # config/target.yaml cell.key (읽기만 함)


def _order(t, regimes, col='국면ID'):
    return t.set_index(col).reindex(list(regimes['id'])).rename_axis('국면ID').reset_index()


def regime_counts(d, regimes):
    """국면별 거래 건수, 자료에 있는 달 수, 월평균 건수, 불균형 지표."""
    g = d.groupby('국면ID')
    t = pd.DataFrame({'거래건수': g.size(), '자료_개월수': g['계약년월_ym'].nunique(),
                      '첫_계약월': g['계약년월_ym'].min(), '끝_계약월': g['계약년월_ym'].max()})
    t = _order(t.reset_index(), regimes)
    t.insert(1, '국면', regimes['name'].values)
    t['구분'] = regimes['side'].values
    t['비율(%)'] = (t['거래건수'] / len(d) * 100).round(2)
    t['월평균_거래건수'] = (t['거래건수'] / t['자료_개월수']).round(0)
    t['최다국면_대비'] = (t['거래건수'] / t['거래건수'].max()).round(3)
    return t


def side_counts(rc):
    """상승·하락(조정 포함)·회복 묶음별 건수."""
    t = rc.groupby('구분', sort=False)[['거래건수', '자료_개월수']].sum().reset_index()
    t['비율(%)'] = (t['거래건수'] / t['거래건수'].sum() * 100).round(2)
    t['월평균_거래건수'] = (t['거래건수'] / t['자료_개월수']).round(0)
    return t


def regime_distribution(d, regimes, cols):
    """국면별 분위수(긴 표). 원시 수준 비교이며 가격지수가 아니다."""
    out = []
    for c in cols:
        g = d.groupby('국면ID')[c]
        t = g.quantile(Q).unstack()
        t.columns = QN
        t.insert(0, '평균', g.mean())
        t.insert(0, '건수', g.count())
        t = _order(t.reset_index(), regimes)
        t.insert(1, '국면', regimes['name'].values)
        t.insert(0, '변수', c)
        out.append(t)
    return pd.concat(out, ignore_index=True)


def regime_composition(d, regimes):
    """국면별로 '거래된 집'의 구성. 국면 사이에 이 값이 달라지면 원시 가격 비교에 구성 효과가 섞인다."""
    x = pd.DataFrame({
        '국면ID': d['국면ID'],
        '동남권(강남·서초·송파·강동) 비중(%)': d['권역'].eq('동남권'),
        '강남3구 비중(%)': d['자치구'].isin(GANGNAM3),
        '전용 60㎡ 이하 비중(%)': d['전용면적(㎡)'] <= 60,
        '전용 85㎡ 초과 비중(%)': d['전용면적(㎡)'] > 85,
        '신축(5년 이하) 비중(%)': (d['건물연식'] <= 5).where(d['건물연식'].notna()),
        '30년 초과 비중(%)': (d['건물연식'] > 30).where(d['건물연식'].notna()),
        '1,000세대 이상 비중(%)': (d['세대수'] >= 1000).where(d['세대수'].notna()),
        '300세대 미만 비중(%)': (d['세대수'] < 300).where(d['세대수'].notna()),
        '상위10 브랜드 단지명 비중(%)': d['단지명_상위10브랜드'].eq(1),
        '토지거래허가구역 거래 비중(%)': d['토지거래허가구역'].eq(1),
        '역 500m 이내 비중(%)': (d['최근접_역_거리(m)'] <= 500).where(d['최근접_역_거리(m)'].notna()),
        '5층 이하 비중(%)': d['층'] <= 5,
    })
    t = (x.groupby('국면ID').mean(numeric_only=False).astype(float) * 100).round(2)
    med = d.groupby('국면ID').agg(**{'전용면적 중앙값(㎡)': ('전용면적(㎡)', 'median'), '건물연식 중앙값(년)': ('건물연식', 'median'),
                                    '세대수 중앙값': ('세대수', 'median'), '층 중앙값': ('층', 'median')})
    t = _order(t.join(med).reset_index(), regimes)
    t.insert(1, '국면', regimes['name'].values)
    overall = (x.drop(columns='국면ID').mean().astype(float) * 100).round(2)
    row = {'국면ID': 'all', '국면': '전체', **overall.to_dict(), '전용면적 중앙값(㎡)': d['전용면적(㎡)'].median(),
           '건물연식 중앙값(년)': d['건물연식'].median(), '세대수 중앙값': d['세대수'].median(), '층 중앙값': d['층'].median()}
    return pd.concat([t, pd.DataFrame([row])], ignore_index=True)


def regime_share(d, regimes, key, order=None):
    """국면별 key(권역·평형대 등) 거래 비중(%). 행 = 국면."""
    t = pd.crosstab(d['국면ID'], d[key], normalize='index').mul(100).round(2).reindex(list(regimes['id'])).rename_axis('국면ID')
    if order:
        t = t[order]
    t.insert(0, '국면', regimes['name'].values)
    return t.reset_index()


def district_share_shift(d, regimes):
    """자치구별 국면 내 거래 비중(%)과 전체 비중 대비 차이(%p). 어느 구의 거래가 어느 국면에 더/덜 잡혔는지."""
    share = pd.crosstab(d['자치구'], d['국면ID'], normalize='columns').mul(100)[list(regimes['id'])]
    share.columns = list(regimes['name'])
    share.insert(0, '전체', d['자치구'].value_counts(normalize=True).mul(100).reindex(share.index))
    diff = share[list(regimes['name'])].sub(share['전체'], axis=0)
    diff.columns = [f'{c}−전체(%p)' for c in diff.columns]
    return share.join(diff).round(2).reset_index()


def turnover_by_district(d, regimes):
    """자치구×국면 월평균 거래 건수와, 그 구의 전체 기간 월평균 대비 배율."""
    months = d.groupby('국면ID')['계약년월_ym'].nunique()
    cnt = pd.crosstab(d['자치구'], d['국면ID'])[list(regimes['id'])]
    per = cnt.div(months.reindex(cnt.columns), axis=1)
    base = cnt.sum(axis=1) / d['계약년월_ym'].nunique()
    ratio = per.div(base, axis=0)
    per.columns = [f'{n}_월평균' for n in regimes['name']]
    ratio.columns = [f'{n}_전체대비' for n in regimes['name']]
    return per.round(1).join(ratio.round(3)).reset_index()


def complex_presence(d, regimes):
    """단지(자치구·법정동·번지·단지명)가 몇 개 국면에서 거래됐는가, 국면별 거래 단지 수.

    모든 국면에 등장하는 단지만 남기면 표본이 어떻게 줄어드는지 보여 준다(선택 편향의 크기).
    """
    cid = d.groupby(CELL_KEY, sort=False).ngroup()
    pres = pd.crosstab(cid, d['국면ID'])[list(regimes['id'])] > 0
    n_reg = pres.sum(axis=1)
    trades = cid.map(cid.value_counts())
    n_reg_row = cid.map(n_reg)
    by_n = pd.DataFrame({'단지수': n_reg.value_counts().sort_index(),
                         '거래건수': n_reg_row.value_counts().sort_index()}).rename_axis('거래된_국면수').reset_index()
    by_n['단지_비율(%)'] = (by_n['단지수'] / by_n['단지수'].sum() * 100).round(2)
    by_n['거래_비율(%)'] = (by_n['거래건수'] / len(d) * 100).round(2)
    per = pd.DataFrame({'국면ID': regimes['id'], '국면': regimes['name'].values,
                        '거래된_단지수': pres.sum().reindex(list(regimes['id'])).rename_axis('국면ID').values})
    per['전체_단지_대비(%)'] = (per['거래된_단지수'] / len(pres) * 100).round(2)
    g = d.groupby('국면ID')
    per['단지당_거래건수_중앙값'] = [cid[d['국면ID'] == r].value_counts().median() for r in regimes['id']]
    per['거래 1건뿐인 단지 비율(%)'] = [round((cid[d['국면ID'] == r].value_counts() == 1).mean() * 100, 2) for r in regimes['id']]
    # 모든 국면에서 거래된 단지와 그렇지 않은 단지의 차이(전체 기간 거래 기준)
    all_reg = n_reg_row == len(regimes)
    cmp = pd.DataFrame({
        '구분': ['모든 국면에서 거래된 단지', '일부 국면에서만 거래된 단지'],
        '단지수': [int((n_reg == len(regimes)).sum()), int((n_reg < len(regimes)).sum())],
        '거래건수': [int(all_reg.sum()), int((~all_reg).sum())],
        '세대수_중앙값': [d.loc[all_reg, '세대수'].median(), d.loc[~all_reg, '세대수'].median()],
        '건축년도_중앙값': [d.loc[all_reg, '건축년도'].median(), d.loc[~all_reg, '건축년도'].median()],
        '㎡당가_중앙값(만원)': [d.loc[all_reg, '㎡당가_만원'].median(), d.loc[~all_reg, '㎡당가_만원'].median()],
        '세대수_결측률(%)': [d.loc[all_reg, '세대수'].isna().mean() * 100, d.loc[~all_reg, '세대수'].isna().mean() * 100],
        '난방방식_결측률(%)': [d.loc[all_reg, '난방방식'].isna().mean() * 100, d.loc[~all_reg, '난방방식'].isna().mean() * 100],
    }).round(2)
    return by_n, per, cmp, {'전체_단지수': int(len(pres)), '단지당_전체_거래건수_중앙값': float(trades.groupby(cid).first().median())}


def model_exclusion_counts(d, regimes):
    """config/target.yaml exclude_trades에 해당하는 거래가 국면별로 몇 건인지(표본에서 빠질 거래의 분포).

    셀×국면 표와 y는 여기서 만들지 않는다(모델링 담당 범위).
    """
    x = pd.DataFrame({'국면ID': d['국면ID'], '좌표 없음': d['위도'].isna(), '준공 전 거래': d['연식_기준'].eq('준공 전 거래')})
    x['둘 중 하나'] = x['좌표 없음'] | x['준공 전 거래']
    t = _order(x.groupby('국면ID').sum().reset_index(), regimes)
    t.insert(1, '국면', regimes['name'].values)
    tot = {'국면ID': 'all', '국면': '전체', **x.drop(columns='국면ID').sum().to_dict()}
    return pd.concat([t, pd.DataFrame([tot])], ignore_index=True)


def ks_between_regimes(d, regimes, col):
    """국면 쌍별 Kolmogorov–Smirnov 거리(두 분포의 누적분포 최대 차이, 0~1). 표본이 커서 p값은 내지 않는다."""
    ids = list(regimes['id'])
    xs = {r: np.sort(d.loc[d['국면ID'] == r, col].dropna().values) for r in ids}
    m = pd.DataFrame(0.0, index=regimes['name'].values, columns=regimes['name'].values)
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            if i < j:
                grid = np.concatenate([xs[a], xs[b]])
                ks = np.abs(np.searchsorted(xs[a], grid, side='right') / xs[a].size
                            - np.searchsorted(xs[b], grid, side='right') / xs[b].size).max()
                m.iloc[i, j] = m.iloc[j, i] = ks
    return m.round(3).rename_axis('국면').reset_index()
