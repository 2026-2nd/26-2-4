"""EDA 그림. 계산된 표를 받아 그리기만 한다(그림 안에서 새 통계를 만들지 않는다).

색: 국면 구분(상승·조정·하락·회복) 4색은 색각 이상 구분을 확인한 조합이며, 국면 이름을 축에 항상 함께 적는다.
"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import Patch

SURFACE, INK, INK2, GRID = '#fcfcfb', '#0b0b0b', '#52514e', '#e4e3df'
BLUE, ORANGE = '#2a78d6', '#eb6834'
SIDE_COLOR = {'up': '#2a78d6', 'down': '#e34948', 'recovery': '#1baf7a', 'corr': '#eda100'}
SIDE_LABEL = {'up': '상승기', 'corr': '조정기', 'down': '하락기', 'recovery': '회복기'}
SEQ = LinearSegmentedColormap.from_list('seq_blue', ['#f3f7fd', '#cde2fb', '#86b6ef', '#2a78d6', '#0d366b'])
KOREAN_FONTS = ['Apple SD Gothic Neo', 'AppleGothic', 'Malgun Gothic', 'NanumGothic', 'Noto Sans CJK KR', 'Noto Sans KR']


def setup():
    have = {f.name for f in font_manager.fontManager.ttflist}
    font = next((f for f in KOREAN_FONTS if f in have), None)
    plt.rcParams.update({
        'font.family': [font] if font else plt.rcParams['font.family'], 'axes.unicode_minus': False,
        'figure.facecolor': SURFACE, 'axes.facecolor': SURFACE, 'savefig.facecolor': SURFACE,
        'axes.edgecolor': GRID, 'axes.labelcolor': INK2, 'text.color': INK, 'xtick.color': INK2, 'ytick.color': INK2,
        'axes.spines.top': False, 'axes.spines.right': False, 'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.6,
        'axes.axisbelow': True, 'axes.titlesize': 12, 'axes.titleweight': 'bold', 'axes.titlelocation': 'left',
        'axes.labelsize': 10, 'xtick.labelsize': 9, 'ytick.labelsize': 9, 'legend.frameon': False, 'legend.fontsize': 9,
        'figure.dpi': 110, 'savefig.dpi': 150, 'savefig.bbox': 'tight',
    })
    return font


def regime_color(regimes):
    """국면 id → 색. 조정기는 하락 쪽이지만 구분해 그린다."""
    return {r.id: SIDE_COLOR['corr' if r.id == 'corr' else r.side] for r in regimes.itertuples()}


def _regime_legend(ax, regimes, **kw):
    kinds = []
    for r in regimes.itertuples():
        k = 'corr' if r.id == 'corr' else r.side
        if k not in kinds:
            kinds.append(k)
    ax.legend(handles=[Patch(color=SIDE_COLOR[k], label=SIDE_LABEL[k]) for k in kinds], **kw)


def _note(fig, text, y=-0.02):
    fig.text(0.01, y, text, fontsize=8, color=INK2, ha='left', va='top')


def _save(fig, path):
    fig.savefig(path)
    plt.close(fig)
    return path


def fig_monthly_counts(monthly, regimes, path):
    """월별 거래 건수. 막대 색 = 국면 구분."""
    col = regime_color(regimes)
    x = pd.to_datetime(monthly['계약년월_ym'])
    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.bar(x, monthly['거래건수'], width=25, color=monthly['국면ID'].map(col), linewidth=0)
    top = monthly['거래건수'].max()
    for r in regimes.itertuples():
        m = monthly[monthly['국면ID'] == r.id]
        mid = pd.to_datetime(m['계약년월_ym']).iloc[[0, -1]].mean()
        ax.text(mid, top * 1.06, r.name, ha='center', va='bottom', fontsize=9, color=INK)
        ax.axvline(pd.to_datetime(m['계약년월_ym'].iloc[0]) - pd.Timedelta(days=15), color=GRID, lw=0.8)
    ax.set_ylim(0, top * 1.16)
    ax.set_title('월별 거래 건수와 시장 국면 (2017-01 ~ 2026-10)')
    ax.set_ylabel('거래 건수(건/월)')
    ax.set_xlabel('계약 월')
    ax.yaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
    ax.grid(axis='x', visible=False)
    _regime_legend(ax, regimes, loc='upper left', bbox_to_anchor=(0, -0.16), ncol=4)
    _note(fig, '자료: 국토교통부 실거래(전처리 v5). 국면 경계: config/regime.yaml. 마지막 달은 신고가 덜 끝났을 수 있다.')
    return _save(fig, path)


def fig_missing(missing, path):
    """열별 결측률(결측이 있는 열만)."""
    m = missing[missing['결측건수'] > 0].sort_values('결측률(%)')
    fig, ax = plt.subplots(figsize=(8.5, 0.3 * len(m) + 1.4))
    ax.barh(m['열'], m['결측률(%)'], color=BLUE, height=0.62)
    for y, (v, n) in enumerate(zip(m['결측률(%)'], m['결측건수'])):
        ax.text(v + 0.8, y, f'{v:.2f}% ({n:,}건)', va='center', fontsize=8.5, color=INK2)
    ax.set_xlim(0, max(m['결측률(%)']) * 1.3)
    ax.set_title(f'열별 결측률 — 43열 중 결측이 있는 {len(m)}개 열')
    ax.set_xlabel('결측률(%, 전체 617,592건 대비)')
    ax.grid(axis='y', visible=False)
    return _save(fig, path)


def fig_price_dist(d, path):
    """거래금액과 ㎡당 가격 분포(가로축 로그)."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, c, unit, title in [(axes[0], '거래금액_억원', '억원', '거래금액'), (axes[1], '㎡당가_만원', '만원/㎡', '전용 ㎡당 가격')]:
        x = d[c].dropna()
        bins = np.logspace(np.log10(x.quantile(.0005)), np.log10(x.quantile(.9995)), 70)
        ax.hist(x, bins=bins, color=BLUE, edgecolor=SURFACE, linewidth=0.4)
        ax.set_xscale('log')
        med, q1, q3 = x.median(), x.quantile(.25), x.quantile(.75)
        ax.axvline(med, color=INK, lw=1.2)
        ax.text(med, ax.get_ylim()[1] * 1.01, f'중앙값 {med:,.1f}{unit}', ha='center', va='bottom', fontsize=9)
        ax.set_title(f'{title} 분포', pad=18)
        ax.set_xlabel(f'{title}({unit}, 로그 눈금) · 사분위 범위 {q1:,.1f}~{q3:,.1f}')
        ax.set_ylabel('거래 건수(건)')
        ax.set_xticks([t for t in [0.5, 1, 2, 5, 10, 20, 50, 100, 300, 500, 1000, 2000, 5000] if bins[0] <= t <= bins[-1]])
        ax.minorticks_off()
        ax.xaxis.set_major_formatter(lambda v, _: f'{v:,g}')
        ax.yaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
        ax.grid(axis='x', visible=False)
    _note(fig, '2017~2026년 전체 거래를 합친 명목 가격이다. 시기별 가격 수준 차이가 섞여 있다. 양 끝 0.05%는 그림 범위 밖.')
    return _save(fig, path)


def fig_district(dt, path):
    """자치구별 ㎡당 가격: 중앙값 점 + 사분위 범위."""
    t = dt.sort_values('중앙값')
    fig, ax = plt.subplots(figsize=(8.5, 7.5))
    y = np.arange(len(t))
    ax.hlines(y, t['p25'], t['p75'], color='#86b6ef', lw=5, label='사분위 범위(25~75%)')
    ax.scatter(t['중앙값'], y, color='#104281', s=38, zorder=3, label='중앙값')
    for yi, v in zip(y, t['중앙값']):
        ax.text(t['p75'].iloc[yi] + 25, yi, f'{v:,.0f}', va='center', fontsize=8.5, color=INK2)
    ax.set_yticks(y, [f'{g} ({n:,}건)' for g, n in zip(t['자치구'], t['거래건수'])])
    ax.set_title('자치구별 전용 ㎡당 가격 (2017~2026 전체 거래)')
    ax.set_xlabel('㎡당 가격(만원/㎡) · 숫자는 중앙값')
    ax.xaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
    ax.grid(axis='y', visible=False)
    ax.legend(loc='lower right')
    _note(fig, '전 기간 명목 가격. 구마다 거래가 많았던 시기가 달라 시기 구성 차이가 섞인다.')
    return _save(fig, path)


def fig_price_vs(area, floor, age, path):
    """면적·층·연식 구간별 상대 가격(같은 계약 연도·자치구 중앙값 대비 %)."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.4), sharey=True, gridspec_kw={'width_ratios': [6, 8, 9]})
    for ax, t, key, title, xl in [(axes[0], area, '면적구간', '전용면적', '전용면적 구간'),
                                  (axes[1], floor[floor['거래건수'] > 0], '층구간', '층', '층 구간'),
                                  (axes[2], age, '연식구간', '건물 연식', '계약연도 - 건축년도(년)')]:
        x = np.arange(len(t))
        ax.vlines(x, t['상대가격_p25(%)'], t['상대가격_p75(%)'], color='#86b6ef', lw=5)
        ax.plot(x, t['상대가격_중앙값(%)'], color='#104281', lw=2, marker='o', ms=6)
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_xticks(x, [f'{a}\n{n / 1000:,.0f}천 건' if n >= 1000 else f'{a}\n{n:,}건' for a, n in zip(t[key].astype(str), t['거래건수'])],
                      fontsize=7.5, rotation=35, ha='right', rotation_mode='anchor')
        ax.set_title(title)
        ax.set_xlabel(xl)
        ax.grid(axis='x', visible=False)
    axes[0].set_ylabel('㎡당 가격의 상대 수준(%)\n같은 계약 연도·자치구 중앙값 = 0')
    axes[0].legend(handles=[plt.Line2D([], [], color='#104281', lw=2, marker='o', label='중앙값'),
                            plt.Line2D([], [], color='#86b6ef', lw=5, label='사분위 범위')], loc='lower left')
    _note(fig, '기술 통계다. 면적·층·연식은 서로, 그리고 재건축 기대·입지와 겹치므로 각 특성의 고유 효과가 아니다.', y=-0.13)
    return _save(fig, path)


def fig_regime_counts(rc, regimes, path):
    """국면별 거래 건수와 월평균 거래 건수."""
    col = [regime_color(regimes)[i] for i in rc['국면ID']]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, c, title, unit in [(axes[0], '거래건수', '국면별 거래 건수', '건'), (axes[1], '월평균_거래건수', '국면별 월평균 거래 건수', '건/월')]:
        ax.bar(rc['국면'], rc[c], color=col, width=0.62)
        for i, v in enumerate(rc[c]):
            extra = f'\n({rc["비율(%)"].iloc[i]:.1f}%)' if c == '거래건수' else f'\n({rc["자료_개월수"].iloc[i]}개월)'
            ax.text(i, v, f'{v:,.0f}{extra}', ha='center', va='bottom', fontsize=8.5, color=INK)
        ax.set_ylim(0, rc[c].max() * 1.2)
        ax.set_title(title)
        ax.set_ylabel(f'거래 건수({unit})')
        ax.yaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
        ax.grid(axis='x', visible=False)
    _regime_legend(axes[1], regimes, loc='upper right', ncol=2)
    _note(fig, '국면 길이가 달라 총 건수만으로 비교할 수 없다. 오른쪽은 자료에 있는 달 수로 나눈 값이다.')
    return _save(fig, path)


def fig_regime_price(dist, regimes, path):
    """국면별 ㎡당 가격·전용면적 분포(5·25·50·75·95 분위)."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    col = regime_color(regimes)
    for ax, var, title, unit in [(axes[0], '㎡당가_만원', '국면별 ㎡당 가격 분포', '만원/㎡'), (axes[1], '전용면적(㎡)', '국면별 전용면적 분포', '㎡')]:
        t = dist[dist['변수'] == var].reset_index(drop=True)
        x = np.arange(len(t))
        c = [col[i] for i in t['국면ID']]
        ax.vlines(x, t['p5'], t['p95'], color=c, lw=1.4)
        ax.bar(x, t['p75'] - t['p25'], bottom=t['p25'], width=0.5, color=c, alpha=0.55, linewidth=0)
        ax.hlines(t['중앙값'], x - 0.25, x + 0.25, color=INK, lw=1.8)
        for i, v in enumerate(t['중앙값']):
            ax.text(i + 0.3, v, f'{v:,.0f}', va='center', fontsize=8.5, color=INK)
        ax.set_xticks(x, t['국면'])
        ax.set_xlim(-0.6, len(t) - 0.2)
        ax.set_title(title)
        ax.set_ylabel(f'{unit} · 상자 25~75%, 선 5~95%, 숫자 중앙값')
        ax.yaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
        ax.grid(axis='x', visible=False)
    _regime_legend(axes[0], regimes, loc='upper left', ncol=2)
    _note(fig, '거래된 집의 원시 분포다. 국면마다 거래된 집의 구성이 달라 가격지수로 읽으면 안 된다(국면 판정은 반복매매 방식 지수 기준).')
    return _save(fig, path)


def fig_composition(comp, regimes, path, metrics):
    """국면별 거래 구성 지표(작은 그림 여러 개). 점선 = 전체 기간 값."""
    t = comp[comp['국면ID'] != 'all']
    allrow = comp[comp['국면ID'] == 'all'].iloc[0]
    col = [regime_color(regimes)[i] for i in t['국면ID']]
    fig, axes = plt.subplots(2, 4, figsize=(14, 6), sharex=True)
    for ax, m in zip(axes.ravel(), metrics):
        ax.bar(t['국면'], t[m], color=col, width=0.62)
        ax.axhline(allrow[m], color=INK, lw=1, ls=(0, (4, 3)))
        for i, v in enumerate(t[m]):
            ax.text(i, v, f'{v:.1f}', ha='center', va='bottom', fontsize=8, color=INK)
        ax.set_ylim(0, max(t[m].max(), allrow[m]) * 1.22)
        ax.set_title(m.replace(' 비중(%)', ''), fontsize=10)
        ax.set_ylabel('거래 비중(%)', fontsize=8.5)
        ax.tick_params(axis='x', labelsize=7.5, rotation=30)
        ax.grid(axis='x', visible=False)
    handles = [Patch(color=SIDE_COLOR[k], label=SIDE_LABEL[k]) for k in ['up', 'corr', 'down', 'recovery']]
    handles.append(plt.Line2D([], [], color=INK, lw=1, ls=(0, (4, 3)), label='전체 기간'))
    fig.legend(handles=handles, loc='upper right', ncol=5, bbox_to_anchor=(0.99, 1.0))
    fig.suptitle('국면별로 거래된 집의 구성 (거래 건수 기준 비중)', x=0.01, ha='left', fontsize=12, fontweight='bold')
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    _note(fig, '국면마다 막대 높이가 다르면 그 국면에 거래된 집의 구성이 다르다는 뜻이다(표본 선택). 세대수·연식·역 거리는 값이 있는 거래 기준.')
    return _save(fig, path)


def _heat(ax, vals, rows, cols, fmt='{:.1f}', vmax=None):
    im = ax.imshow(vals, cmap=SEQ, vmin=0, vmax=vmax or np.nanmax(vals), aspect='auto')
    ax.set_xticks(range(len(cols)), cols)
    ax.set_yticks(range(len(rows)), rows)
    ax.grid(False)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-.5, len(cols)), minor=True)
    ax.set_yticks(np.arange(-.5, len(rows)), minor=True)
    ax.grid(which='minor', color=SURFACE, linewidth=2)
    ax.tick_params(which='minor', length=0)
    lim = (vmax or np.nanmax(vals)) * 0.55
    for i in range(vals.shape[0]):
        for j in range(vals.shape[1]):
            ax.text(j, i, fmt.format(vals[i, j]), ha='center', va='center', fontsize=8.5,
                    color='white' if vals[i, j] > lim else INK)
    return im


def fig_coverage_regime(by_regime, by_year, feats, path):
    """특성 결측률 — 국면별, 계약 연도별."""
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw={'width_ratios': [6, 10]})
    vmax = max(by_regime[feats].values.max(), by_year[feats].values.max())
    _heat(axes[0], by_regime[feats].values.T, feats, list(by_regime['국면']), vmax=vmax)
    axes[0].set_title('국면별 특성 결측률(%)')
    im = _heat(axes[1], by_year[feats].values.T, feats, [str(int(v)) for v in by_year['계약연도']], vmax=vmax)
    axes[1].set_yticklabels([])
    axes[1].set_title('계약 연도별 특성 결측률(%)')
    cb = fig.colorbar(im, ax=axes, fraction=0.025, pad=0.02)
    cb.set_label('결측률(%)')
    cb.outline.set_visible(False)
    _note(fig, '칸의 숫자 = 그 국면(연도) 거래 중 값이 빈 비율(%). 입지 4개 특성은 좌표가 없는 358건에서만 빈다.')
    return _save(fig, path)


def fig_coverage_district(by_district, feats, path):
    """자치구별 단지 내부 특성 결측률."""
    t = by_district.sort_values(feats[2], ascending=False)
    fig, ax = plt.subplots(figsize=(8, 8.2))
    im = _heat(ax, t[feats].values, [f'{g} ({n:,}건)' for g, n in zip(t['자치구'], t['거래건수'])], feats)
    ax.xaxis.tick_top()
    ax.set_title('자치구별 단지 내부 특성 결측률(%)', pad=28)
    cb = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.02)
    cb.set_label('결측률(%)')
    cb.outline.set_visible(False)
    _note(fig, f'{feats[2]} 결측률이 높은 구부터 정렬. 난방·복도·시공사는 K-apt 단지 목록에 없는 단지에서 함께 빈다.', y=0.07)
    return _save(fig, path)


def fig_access(d, path):
    """최근접 역·초등학교 직선거리 분포."""
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, c, title in [(axes[0], '최근접_역_거리(m)', '최근접 역까지 직선거리'), (axes[1], '최근접_초등학교_거리(m)', '최근접 초등학교까지 직선거리')]:
        x = d[c].dropna()
        hi = float(np.ceil(x.quantile(.995) / 100) * 100)
        ax.hist(x.clip(upper=hi), bins=np.arange(0, hi + 50, 50), color=BLUE, edgecolor=SURFACE, linewidth=0.4)
        med = x.median()
        ax.axvline(med, color=INK, lw=1.2)
        ax.text(med, ax.get_ylim()[1] * 1.01, f'중앙값 {med:,.0f}m', ha='center', va='bottom', fontsize=9)
        ax.set_title(title, pad=18)
        ax.set_xlabel(f'직선거리(m, 50m 구간) · 500m 이내 {(x <= 500).mean() * 100:.1f}%')
        ax.set_ylabel('거래 건수(건)')
        ax.yaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
        ax.xaxis.set_major_formatter(lambda v, _: f'{v:,.0f}')
        ax.grid(axis='x', visible=False)
    _note(fig, '계약일에 운영 중이던 역·학교 기준 직선거리(도보 거리 아님). 좌표가 없는 358건 제외. 상위 0.5%는 마지막 구간에 합쳤다.')
    return _save(fig, path)
