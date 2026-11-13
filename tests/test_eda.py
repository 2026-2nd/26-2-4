"""EDA 검증: (1) 함수 단위 규칙, (2) 실제 파일의 크기·건수, (3) 저장된 reports/eda 숫자가 재계산과 같은지.

실제 파일(18MB xz)을 한 번 읽는다(약 10초). EDA는 config·원본 데이터를 바꾸지 않는다는 것도 확인한다.
"""
import json
import pathlib
import sys
import unittest

import numpy as np
import pandas as pd
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from eda import coverage, load, price, quality, regime  # noqa: E402

EDA = ROOT / 'reports/eda'
_CACHE = {}


def data():
    if 'd' not in _CACHE:
        _CACHE['d'], _CACHE['r'] = load.load()
    return _CACHE['d'], _CACHE['r']


def table(name):
    return pd.read_csv(EDA / 'tables' / f'{name}.csv', encoding='utf-8-sig')


def summary():
    return json.loads((EDA / 'summary.json').read_text(encoding='utf-8'))


class Units(unittest.TestCase):
    """작은 가짜 자료로 규칙만 확인한다."""

    def setUp(self):
        self.reg = load.load_regimes()

    def test_regimes_come_from_config(self):
        cfg = yaml.safe_load((ROOT / 'config/regime.yaml').read_text(encoding='utf-8'))['regimes']
        self.assertEqual(list(self.reg['id']), [r['id'] for r in cfg])
        self.assertEqual(list(self.reg['name']), [r['name'] for r in cfg])
        self.assertEqual(list(self.reg['start']), [str(r['start']) for r in cfg])

    def test_regime_boundaries(self):
        ym = pd.Series(['2017-01', '2018-10', '2018-11', '2019-04', '2019-05', '2021-10', '2021-11',
                        '2023-01', '2023-02', '2024-07', '2024-08', '2026-10', '2016-12'])
        got = list(load.assign_regime(ym, self.reg))
        self.assertEqual(got[:12], ['up1', 'up1', 'corr', 'corr', 'up2', 'up2', 'down', 'down', 'rec', 'rec', 'up3', 'up3'])
        self.assertTrue(pd.isna(got[12]))   # 자료 기간 밖은 배정하지 않는다

    def test_regimes_do_not_overlap_or_leave_gaps(self):
        months = pd.Series(pd.period_range('2017-01', '2026-10', freq='M').astype(str))
        lab = load.assign_regime(months, self.reg)
        self.assertFalse(lab.isna().any())
        runs = (lab != lab.shift()).cumsum().nunique()
        self.assertEqual(runs, len(self.reg))   # 국면마다 연속 구간 하나

    def test_split_reasons(self):
        s = pd.Series(['[동] 원자료에 동 미공개 / [주차] 건축물대장에 주차대수 미기재', None, '[동] 원자료에 동 미공개', '형식 없는 사유'])
        r = quality.split_reasons(s)
        self.assertEqual(r['항목'].value_counts().to_dict(), {'동': 2, '주차': 1, '(형식 외)': 1})
        self.assertEqual(r.loc[r['항목'] == '(형식 외)', '이유'].iloc[0], '형식 없는 사유')

    def test_prepare_keeps_rows_and_marks_empty_as_missing(self):
        raw = load.read_raw().head(300)
        d = load.prepare(raw, self.reg)
        self.assertEqual(len(d), 300)
        self.assertEqual(list(d.columns[:43]), list(raw.columns))
        self.assertEqual(int(d['동'].isna().sum()), int((raw['동'] == '').sum()))
        self.assertTrue(np.allclose(d['㎡당가_만원'], raw['거래금액_만원'].astype(float) / raw['전용면적(㎡)'].astype(float)))

    def test_iqr_outliers(self):
        d = pd.DataFrame({'x': [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]})
        t = quality.iqr_outliers(d, ['x']).iloc[0]
        self.assertEqual((t['하한_미만'], t['상한_초과']), (0, 1))

    def test_ks_distance(self):
        reg = self.reg.head(2)
        d = pd.DataFrame({'국면ID': ['up1'] * 4 + ['corr'] * 4, 'v': [1, 2, 3, 4, 1, 2, 3, 4]})
        self.assertEqual(regime.ks_between_regimes(d, reg, 'v').iloc[0, 2], 0)
        d['v'] = [1, 2, 3, 4, 11, 12, 13, 14]
        self.assertEqual(regime.ks_between_regimes(d, reg, 'v').iloc[0, 2], 1)


class RealData(unittest.TestCase):
    """실제 파일에서 다시 센다."""

    def test_shape_matches_docs(self):
        d, _ = data()
        self.assertEqual(len(d), 617_592)
        self.assertEqual(len(d.attrs['원본_열']), 43)
        self.assertEqual(len(d.columns), 43 + len(load.DERIVED))

    def test_no_duplicates_and_every_trade_has_regime(self):
        d, r = data()
        self.assertEqual(int(d['거래ID'].duplicated().sum()), 0)
        self.assertEqual(int(d['국면ID'].isna().sum()), 0)
        self.assertEqual(int(d.groupby('국면ID').size().sum()), len(d))
        self.assertEqual(set(d['국면ID']), set(r['id']))

    def test_numeric_columns_parse(self):
        d, _ = data()
        self.assertEqual(sum(d.attrs['숫자변환_실패'].values()), 0)

    def test_documented_missing_counts(self):
        """docs/data.md §5의 결측 건수."""
        d, _ = data()
        for col, n in {'위도': 358, '세대수': 6795, '세대당_주차대수': 75555, '동': 424259}.items():
            self.assertEqual(int(d[col].isna().sum()), n, col)

    def test_original_file_untouched(self):
        """EDA는 원본·config를 바꾸지 않는다(reports/final/sha256.json과 같은 해시)."""
        import hashlib
        saved = json.loads((ROOT / 'reports/final/sha256.json').read_text(encoding='utf-8'))
        for rel in [load.DATA.relative_to(ROOT).as_posix(), 'config/regime.yaml', 'config/target.yaml', 'config/features.yaml']:
            self.assertEqual(hashlib.sha256((ROOT / rel).read_bytes()).hexdigest(), saved[rel], rel)


class SavedOutputs(unittest.TestCase):
    """reports/eda에 저장된 숫자 = 지금 다시 계산한 숫자."""

    def test_summary_matches_data(self):
        d, _ = data()
        S = summary()
        self.assertEqual((S['데이터']['행'], S['데이터']['열']), (len(d), 43))
        self.assertEqual(S['국면_건수'], d.groupby('국면ID').size().to_dict())
        self.assertEqual(S['중복'], quality.duplicate_summary(d, d.attrs['원본_열']))
        self.assertEqual(S['주차0']['거래건수'], int((d['세대당_주차대수'] == 0).sum()))
        self.assertAlmostEqual(S['가격']['거래금액_억원_중앙값'], float(d['거래금액_억원'].median()))
        self.assertAlmostEqual(S['가격']['㎡당가_만원_중앙값'], float(d['㎡당가_만원'].median()))

    def test_regime_table(self):
        d, r = data()
        t = table('03_국면_건수')
        self.assertEqual(int(t['거래건수'].sum()), len(d))
        pd.testing.assert_frame_equal(t[['국면ID', '거래건수', '자료_개월수']],
                                      regime.regime_counts(d, r)[['국면ID', '거래건수', '자료_개월수']], check_dtype=False)

    def test_missing_table(self):
        d, _ = data()
        t = table('01_결측_열별').set_index('열')['결측건수']
        self.assertEqual(len(t), 43)
        for c in d.attrs['원본_열']:
            self.assertEqual(int(t[c]), int(d[c].isna().sum()), c)

    def test_every_missing_value_has_a_reason(self):
        self.assertEqual(int(table('01_결측_사유없는건수')['사유_없는_결측'].sum()), 0)

    def test_coverage_by_regime(self):
        d, r = data()
        t = table('04_특성_결측_국면별').set_index('국면ID')
        for rid in r['id']:
            k = d['국면ID'] == rid
            self.assertAlmostEqual(t.loc[rid, '난방방식'], round(d.loc[k, '난방방식'].isna().mean() * 100, 2), places=2)
            self.assertAlmostEqual(t.loc[rid, '세대수'], round(d.loc[k, '세대수'].isna().mean() * 100, 2), places=2)
            self.assertEqual(int(t.loc[rid, '거래건수']), int(k.sum()))

    def test_district_price_table(self):
        d, _ = data()
        t = table('02_가격_자치구별').set_index('자치구')
        self.assertEqual(len(t), 25)
        self.assertEqual(int(t['거래건수'].sum()), len(d))
        g = d.groupby('자치구')['㎡당가_만원'].median()
        self.assertTrue(np.allclose(t['중앙값'].reindex(g.index), g, rtol=1e-5))

    def test_composition_shares_are_percentages(self):
        t = table('03_국면_거래구성')
        share = t[[c for c in t.columns if c.endswith('비중(%)')]]
        self.assertTrue(((share >= 0) & (share <= 100)).all().all())
        self.assertEqual(list(t['국면ID']), list(load.load_regimes()['id']) + ['all'])

    def test_bins_cover_all_trades(self):
        d, _ = data()
        for name in ['02_가격_면적구간별', '02_가격_층구간별']:
            self.assertEqual(int(table(name)['거래건수'].sum()), len(d), name)
        self.assertEqual(int(table('02_가격_연식구간별')['거래건수'].sum()), int(d['건물연식'].notna().sum()))

    def test_figures_and_report_exist(self):
        figs = sorted((EDA / 'figures').glob('*.png'))
        self.assertTrue(6 <= len(figs), len(figs))
        for f in figs:
            self.assertGreater(f.stat().st_size, 10_000, f.name)
            self.assertLess(f.stat().st_size, 2 * 2**20, f.name)
        text = (EDA / 'EDA_report_ko.md').read_text(encoding='utf-8')
        self.assertIn('617,592', text)
        self.assertNotIn('nan', text.lower().replace('nanum', ''))
        for f in figs:
            self.assertIn(f'figures/{f.name}', text, f.name)

    def test_eda_does_not_build_model_inputs(self):
        """EDA 코드는 y·셀 표·분할을 만들지 않는다(모델링 담당 범위)."""
        for f in (ROOT / 'src/eda').glob('*.py'):
            s = f.read_text(encoding='utf-8')
            for word in ['sklearn', 'catboost', 'GroupKFold', 'seoul_index_2017_2026']:
                self.assertNotIn(word, s, f'{f.name}: {word}')


if __name__ == '__main__':
    unittest.main()
