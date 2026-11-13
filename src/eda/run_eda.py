"""EDA 전체 실행: 표(reports/eda/tables), 그림(reports/eda/figures), 요약(reports/eda/summary.json), 보고서.

    python src/eda/run_eda.py            # 저장소 최상위에서
    python src/eda/run_eda.py --no-figures

원본 데이터는 읽기만 한다. reports/final/과 config/는 건드리지 않는다.
"""
import argparse
import json
import pathlib
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from eda import coverage, load, price, quality, regime  # noqa: E402

ROOT = load.ROOT
OUT = ROOT / 'reports/eda'
PROFILE_COLS = ['거래금액_만원', '㎡당가_만원', '전용면적(㎡)', '층', '건축년도', '건물연식', '연식_개월', '세대수',
                '세대당_주차대수', '최근접_역_거리(m)', '1km내_노선수', '최근접_초등학교_거리(m)', '1km내_학교수']
COMPOSITION_METRICS = ['동남권(강남·서초·송파·강동) 비중(%)', '전용 60㎡ 이하 비중(%)', '신축(5년 이하) 비중(%)', '30년 초과 비중(%)',
                       '1,000세대 이상 비중(%)', '300세대 미만 비중(%)', '상위10 브랜드 단지명 비중(%)', '역 500m 이내 비중(%)']


def _py(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if np.isnan(o) else float(o)
    if isinstance(o, (pd.Timestamp,)):
        return o.strftime('%Y-%m-%d')
    raise TypeError(type(o))


def compute(d, regimes):
    """모든 표와 요약 숫자를 계산한다. 반환: (표 dict, 요약 dict)."""
    cols = d.attrs['원본_열']
    T, S = {}, {}

    # 1. 품질
    T['01_결측_열별'] = quality.missing_table(d, cols)
    T['01_결측사유_항목별'] = quality.missing_reason_table(d)
    T['01_결측사유_조합_상위'] = quality.missing_reason_patterns(d)
    T['01_결측_사유없는건수'] = quality.missing_without_reason(d)
    T['01_중복_연도별'] = quality.same_trade_by_year(d)
    T['01_값점검'] = quality.validity_checks(d)
    T['01_분위수_요약'] = quality.numeric_profile(d, PROFILE_COLS)
    T['01_이상치_IQR'] = quality.iqr_outliers(d, PROFILE_COLS)
    T['01_주차0_단지'] = quality.zero_parking_complexes(d)
    T['01_건수_연도별'] = quality.counts_by(d, '계약연도')
    T['01_건수_자치구별'] = quality.counts_by(d, '자치구').sort_values('거래건수', ascending=False, ignore_index=True)
    T['01_건수_자치구x연도'] = quality.counts_district_year(d).reset_index()
    T['01_건수_월별'] = quality.monthly_counts(d)

    # 2. 가격
    x = price.add_bins(d)
    T['02_가격_요약'] = price.price_summary(d)
    T['02_가격대_비중'] = price.price_band_share(d)
    T['02_가격_면적구간별'] = price.by_bin(x, '면적구간')
    T['02_가격_층구간별'] = price.by_bin(x, '층구간')
    T['02_가격_연식구간별'] = price.by_bin(x, '연식구간')
    T['02_가격_자치구별'] = price.district_table(d)
    T['02_가격_자치구x연도_중앙값'] = price.district_year_median(d).round(0).reset_index()
    T['02_가격_연도별'] = price.by_group(d, '계약연도')
    T['02_가격_순위상관'] = price.spearman_with_price(d).round(3)

    # 3. 국면
    rc = regime.regime_counts(d, regimes)
    T['03_국면_건수'] = rc
    T['03_국면_구분별_건수'] = regime.side_counts(rc)
    T['03_국면_분포'] = regime.regime_distribution(
        d, regimes, ['㎡당가_만원', '거래금액_억원', '전용면적(㎡)', '층', '건물연식', '세대수', '최근접_역_거리(m)'])
    T['03_국면_거래구성'] = regime.regime_composition(d, regimes)
    T['03_국면_권역비중'] = regime.regime_share(d, regimes, '권역', load.ZONES)
    T['03_국면_평형대비중'] = regime.regime_share(d, regimes, '평형대', ['10평미만', '10~20평', '20~30평', '30~40평', '40평이상'])
    T['03_국면_자치구비중_변화'] = regime.district_share_shift(d, regimes)
    T['03_국면_자치구_월평균거래'] = regime.turnover_by_district(d, regimes)
    by_n, per, cmp, cs = regime.complex_presence(d, regimes)
    T['03_단지_거래된국면수'] = by_n
    T['03_국면_거래단지수'] = per
    T['03_단지_전국면거래_비교'] = cmp
    T['03_국면_모델제외대상'] = regime.model_exclusion_counts(d, regimes)
    T['03_국면_KS_㎡당가'] = regime.ks_between_regimes(d, regimes, '㎡당가_만원')
    T['03_국면_KS_전용면적'] = regime.ks_between_regimes(d, regimes, '전용면적(㎡)')

    # 4. 특성 확보율
    T['04_특성_결측_전체'] = coverage.overall(d)
    T['04_특성_결측_국면별'] = coverage.missing_by(d, '국면ID', order=list(regimes['id']), names=regimes['name'])
    T['04_특성_결측_자치구별'] = coverage.missing_by(d, '자치구')
    T['04_특성_결측_연도별'] = coverage.missing_by(d, '계약연도')
    T['04_특성_결측_건축시기별'] = coverage.missing_by_built_period(d)
    T['04_특성_결측_세대수출처별'] = coverage.missing_by_household_source(d)
    T['04_세대수_출처별_규모'] = coverage.size_by_household_source(d)
    T['04_특성_결측_단지단위'] = coverage.complex_level_coverage(d)
    for c in ['난방방식', '복도유형', '세대수_기준', '연식_기준', '좌표기준', '건물연식_구분', '평형대']:
        T[f'04_분포_{c}'] = coverage.category_distribution(d, c)
    T['04_난방방식_국면별'] = coverage.category_by_regime(d, regimes, '난방방식')
    T['04_복도유형_국면별'] = coverage.category_by_regime(d, regimes, '복도유형')
    T['04_세대수_구간'] = coverage.household_bins(d)
    T['04_거리_구간'] = coverage.distance_bands(d)
    T['04_입지_국면별'] = coverage.access_by_regime(d, regimes)
    T['04_입지_단지내_시점변화'] = coverage.access_changes_within_complex(d)
    T['04_현재값가정_국면별'] = coverage.static_assumption(d, regimes)
    T['04_좌표기준_국면별'] = coverage.coord_basis(d, regimes)

    # 요약(보고서·테스트가 읽는 숫자)
    S['데이터'] = {'파일': load.DATA.relative_to(ROOT).as_posix(), '행': len(d), '열': len(cols),
                 '첫_계약일': d['계약일_dt'].min(), '끝_계약일': d['계약일_dt'].max(),
                 '자치구_수': d['자치구'].nunique(), '법정동_수': d.groupby(['자치구', '법정동']).ngroups,
                 '단지_수': cs['전체_단지수'], '계약월_수': d['계약년월_ym'].nunique()}
    S['중복'] = quality.duplicate_summary(d, cols)
    S['같은조건_거래'] = quality.same_trade_profile(d)
    S['주차0'] = {'거래건수': int((d['세대당_주차대수'] == 0).sum()), '단지수': len(T['01_주차0_단지'])}
    S['숫자변환_실패'] = d.attrs['숫자변환_실패']
    S['가격_지역내_이상치'] = quality.local_price_outliers(d)
    S['주차'] = coverage.parking_extremes(d)
    S['결측사유_없음_건수'] = int(d['결측사유'].isna().sum())
    S['국면_건수'] = dict(zip(rc['국면ID'], rc['거래건수']))
    S['국면_개월수'] = dict(zip(rc['국면ID'], rc['자료_개월수']))
    S['국면_불균형_최대÷최소'] = round(float(rc['거래건수'].max() / rc['거래건수'].min()), 2)
    S['국면_월평균_최대÷최소'] = round(float(rc['월평균_거래건수'].max() / rc['월평균_거래건수'].min()), 2)
    S['단지'] = cs
    S['가격'] = {'거래금액_억원_중앙값': float(d['거래금액_억원'].median()), '㎡당가_만원_중앙값': float(d['㎡당가_만원'].median()),
               '전용면적_중앙값': float(d['전용면적(㎡)'].median())}
    return T, S


def write_tables(T, S, out=OUT):
    (out / 'tables').mkdir(parents=True, exist_ok=True)
    for name, t in T.items():
        t.to_csv(out / 'tables' / f'{name}.csv', index=False, encoding='utf-8-sig', float_format='%.6g')
    (out / 'summary.json').write_text(json.dumps(S, ensure_ascii=False, indent=1, default=_py) + '\n', encoding='utf-8')


def make_figures(d, regimes, T, out=OUT):
    from eda import plots
    fig = out / 'figures'
    fig.mkdir(parents=True, exist_ok=True)
    plots.setup()
    internal = list(coverage.INTERNAL)
    return [
        plots.fig_monthly_counts(T['01_건수_월별'], regimes, fig / '01_월별_거래건수_국면.png'),
        plots.fig_missing(T['01_결측_열별'], fig / '02_열별_결측률.png'),
        plots.fig_price_dist(d, fig / '03_가격_분포.png'),
        plots.fig_district(T['02_가격_자치구별'], fig / '04_자치구별_㎡당가.png'),
        plots.fig_price_vs(T['02_가격_면적구간별'], T['02_가격_층구간별'], T['02_가격_연식구간별'], fig / '05_가격_면적_층_연식.png'),
        plots.fig_regime_counts(T['03_국면_건수'], regimes, fig / '06_국면별_거래건수.png'),
        plots.fig_regime_price(T['03_국면_분포'], regimes, fig / '07_국면별_가격_면적_분포.png'),
        plots.fig_composition(T['03_국면_거래구성'], regimes, fig / '08_국면별_거래구성.png', COMPOSITION_METRICS),
        plots.fig_coverage_regime(T['04_특성_결측_국면별'], T['04_특성_결측_연도별'], list(coverage.FEATURES), fig / '09_특성_결측률_국면_연도.png'),
        plots.fig_coverage_district(T['04_특성_결측_자치구별'], internal, fig / '10_특성_결측률_자치구.png'),
        plots.fig_access(d, fig / '11_역_학교_거리_분포.png'),
    ]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--no-figures', action='store_true')
    a = ap.parse_args()
    d, regimes = load.load()
    print(f'읽음: {len(d):,}행 × {len(d.attrs["원본_열"])}열')
    T, S = compute(d, regimes)
    write_tables(T, S)
    print(f'표 {len(T)}개 → {(OUT / "tables").relative_to(ROOT)}')
    if not a.no_figures:
        figs = make_figures(d, regimes, T)
        print(f'그림 {len(figs)}개 → {(OUT / "figures").relative_to(ROOT)}')
    from eda import report
    p = report.write(OUT)
    print(f'보고서 → {p.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
