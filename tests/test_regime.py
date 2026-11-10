"""국면 판정 규칙이 저장된 지수에서 config/regime.yaml의 확정 국면을 다시 만드는지 확인한다."""
import json, pathlib, sys, unittest
import pandas as pd, yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src' / 'regime'))
from turning_points import label

CFG = yaml.safe_load((ROOT / 'config/regime.yaml').read_text(encoding='utf-8'))


def runs(lab):
    r = (lab != lab.shift()).cumsum()
    return [(g.iloc[0], str(g.index[0]), str(g.index[-1])) for _, g in lab.groupby(r)]


class Regime(unittest.TestCase):
    def test_official_index_gives_2021_decline(self):
        d = pd.read_csv(ROOT / 'data/external/rone_apt_trade_index_seoul_raw.csv', dtype={'ym': str})
        s = pd.Series(d['서울'].values, index=pd.PeriodIndex(pd.to_datetime(d.ym, format='%Y%m'), freq='M'))['2017-01':]
        r = runs(label(s)[0])
        self.assertIn(('하락기', '2021-11', '2023-01'), r)
        self.assertIn(('회복기', '2023-02', '2024-07'), r)

    def test_own_index_gives_2018_correction(self):
        own = pd.read_csv(ROOT / 'data/regime/seoul_index_2017_2026.csv', index_col=0)
        s = pd.Series(own['main'].values, index=pd.PeriodIndex(own.index, freq='M'))
        self.assertIn(('조정기', '2018-11', '2019-04'), runs(label(s)[0]))

    def test_config_matches_saved_final_regimes(self):
        final = json.loads((ROOT / 'data/regime/official_comparison.json').read_text(encoding='utf-8'))['final']
        cfg = CFG['regimes']
        self.assertEqual(len(final), len(cfg))
        for f, c in zip(final, cfg):
            self.assertEqual(f['start'], c['start'])
            self.assertEqual(f['end'], c['end'] or '진행 중')
            self.assertAlmostEqual(f['rone_trade'][0], c['official_change_pct'])
            self.assertEqual(f['rone_trade'][1], c['b'])

    def test_regimes_are_contiguous_and_lengths_match(self):
        cfg = CFG['regimes']
        for prev, cur in zip(cfg, cfg[1:]):
            self.assertEqual(pd.Period(prev['end'], 'M') + 1, pd.Period(cur['start'], 'M'))
            self.assertEqual(prev['b'], cur['a'])
        for c in cfg:
            self.assertEqual((pd.Period(c['b'], 'M') - pd.Period(c['a'], 'M')).n, c['L'])


if __name__ == '__main__':
    unittest.main()
