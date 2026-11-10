"""저장소 규칙: 설정 파일이 읽히는지, 키·대용량 파일이 커밋되지 않는지, 유형 규칙이 완전한지."""
import pathlib, re, subprocess, unittest
import yaml
ROOT = pathlib.Path(__file__).resolve().parents[1]


def tracked():
    try:
        out = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, capture_output=True, check=True).stdout
        files = [ROOT / p for p in out.decode('utf-8').split('\0') if p]
        if files:
            return files
    except Exception:
        pass
    return [p for p in ROOT.rglob('*') if p.is_file() and '.git' not in p.parts]


class RepoRules(unittest.TestCase):
    def test_configs_load(self):
        for f in sorted((ROOT / 'config').glob('*.yaml')):
            self.assertIsInstance(yaml.safe_load(f.read_text(encoding='utf-8')), dict, f.name)

    def test_no_file_over_50mb(self):
        big = [str(p.relative_to(ROOT)) for p in tracked() if p.exists() and p.stat().st_size > 50 * 2**20]
        self.assertEqual(big, [])

    def test_no_api_keys_in_code(self):
        pat = re.compile(r'(KakaoAK\s+[0-9a-f]{20,}|serviceKey=[A-Za-z0-9%+/=]{40,})')
        hits = [str(p.relative_to(ROOT)) for p in tracked()
                if p.suffix in {'.py', '.md', '.yaml', '.json', '.txt', '.ipynb'} and p.exists()
                and pat.search(p.read_text(encoding='utf-8', errors='ignore'))]
        self.assertEqual(hits, [])

    def test_type_rule_covers_all_types(self):
        t = yaml.safe_load((ROOT / 'config/types.yaml').read_text(encoding='utf-8'))
        self.assertEqual(set(t['types']), {'전천후형', '방어형', '공격형', '취약형', '국면무관'})
        self.assertEqual(t['aggregate']['up_effect']['min_agree'], 2)

    def test_split_is_by_dong(self):
        s = yaml.safe_load((ROOT / 'config/split.yaml').read_text(encoding='utf-8'))
        self.assertEqual(s['group'], ['자치구', '법정동'])
        self.assertAlmostEqual(s['test_share'], 0.2)


if __name__ == '__main__':
    unittest.main()
