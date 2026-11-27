"""Paired, prespecified full / without-snapshot nested CV; never select on outer scores."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import pathlib
import subprocess
import sys

import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]


def summarize(output):
    rows = []
    for path in sorted((output/'evaluation').glob('*/outer_predictions.csv.xz')):
        key = path.parent.name
        other = output/'evaluation_without_snapshot'/key
        a, b = pd.read_csv(path), pd.read_csv(other/path.name)
        for c in ['cell_id', 'dong_id', 'outer_fold', 'y', 'weight']:
            pd.testing.assert_series_equal(a[c], b[c])
        w, y = a.weight.to_numpy(), a.y.to_numpy()
        ea = w*(a.inner_selected.to_numpy()-y)**2
        eb = w*(b.inner_selected.to_numpy()-y)**2
        grouped = pd.DataFrame({'dong':a.dong_id, 'w':w, 'a':ea, 'b':eb}).groupby('dong').sum()
        rng = np.random.default_rng(20261127)
        draws = rng.integers(0, len(grouped), size=(1000, len(grouped)))
        sums = grouped[['w','a','b']].to_numpy()[draws].sum(axis=1)
        delta = np.sqrt(sums[:,2]/sums[:,0])-np.sqrt(sums[:,1]/sums[:,0])
        full, reduced = np.sqrt(ea.sum()/w.sum()), np.sqrt(eb.sum()/w.sum())
        rows.append(dict(table=key,cells=len(a),dongs=len(grouped),
            full_RMSE=full,without_snapshot_RMSE=reduced,delta_RMSE=reduced-full,
            delta_ci_low=np.quantile(delta,.025),delta_ci_high=np.quantile(delta,.975),
            prediction_rank_correlation=a.inner_selected.corr(b.inner_selected,method='spearman')))
    if len(rows) != 12:
        raise ValueError(f'Expected 12 paired tables, found {len(rows)}')
    pd.DataFrame(rows).to_csv(output/'paired_comparison.csv',index=False,encoding='utf-8-sig')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=pathlib.Path,default=ROOT/'results/leakage_audit_v3')
    p.add_argument('--workers',type=int,default=4)
    p.add_argument('--summarize-only',action='store_true')
    args = p.parse_args()
    output = args.output.resolve()
    if args.summarize_only:
        summarize(output)
        return
    tables = sorted((output/'tables').glob('*.csv.xz'))
    if len(tables) != 12:
        p.error('Build 12 input tables with nested_v3.py build --output first')
    sources = [ROOT/'src/model/nested_v3.py',ROOT/'src/model/design.py',
               ROOT/'src/model/common.py',ROOT/'src/cells/build_cells.py',pathlib.Path(__file__)]
    sources += sorted((ROOT/'config').glob('*.yaml')) + tables
    manifest = dict(protocol='paired_snapshot_ablation_v1', policies=['full','without_snapshot'],
        selection='inner CV only; compare inner_selected outer predictions',
        intervals='1000 paired dong bootstrap resamples of saved OOF errors; conditional on fits, not selection uncertainty',
        independent_external_test=False,
        hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})
    manifest_path = output/'audit_protocol.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text(encoding='utf-8')) != manifest:
        raise ValueError('Inputs or code changed; choose a new output directory')
    manifest_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    logs = output/'logs'
    logs.mkdir(exist_ok=True)
    def run(task):
        key, policy = task
        folder = output/('evaluation' if policy=='full' else 'evaluation_without_snapshot')/key
        if (folder/'verification.json').exists():
            return f'{key} {policy}: existing verified result'
        with (logs/f'{key}_{policy}.log').open('w',encoding='utf-8') as log:
            subprocess.run([sys.executable,str(ROOT/'src/model/nested_v3.py'),'evaluate',
                '--table',key,'--feature-policy',policy,'--output',str(output)],
                cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
        return f'{key} {policy}: completed'
    tasks = [(p.name.removesuffix('.csv.xz'),policy) for p in tables for policy in ('full','without_snapshot')]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for future in as_completed([pool.submit(run,t) for t in tasks]):
            print(future.result(),flush=True)
    summarize(output)


if __name__ == '__main__':
    main()
