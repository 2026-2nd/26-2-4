"""Shared V3 configuration, features and weighted evaluation (no legacy experiment runner)."""
import hashlib
import json
import pathlib
from functools import lru_cache
import numpy as np
import pandas as pd
import yaml
from scipy.stats import rankdata
ROOT = pathlib.Path(__file__).resolve().parents[2]

@lru_cache(maxsize=None)
def config(name):
    return yaml.safe_load((ROOT / 'config' / f"{'v3' if name == 'training' else name}.yaml").read_text(encoding='utf-8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save_json(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8', newline='\n')


def save_csv(data, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(path, index=False, encoding='utf-8-sig', lineterminator='\n', float_format='%.12g')


def feature_names():
    base = [s for group in config('features')['base'].values() for s in group]
    cats = [s['name'] for s in base if s.get('type') == 'category']
    names = [s['name'] for s in base]
    return names + [n+'_missing' for n in names], cats


def design(d):
    names, cats = feature_names()
    x = d[names].copy()
    for c in cats:
        x[c] = x[c].fillna(config('training')['category_missing']).astype(str)
    return x


def baseline(d, x):
    means = d.groupby('자치구').apply(lambda g: np.average(g.y, weights=g.weight), include_groups=False)
    fallback = np.average(d.y, weights=d.weight)
    return x['자치구'].map(means).fillna(fallback).to_numpy()


def metric_values(y, prediction, w):
    y, prediction, w = map(lambda a: np.asarray(a, float), [y, prediction, w])
    residual = prediction-y
    ry, rp = rankdata(y), rankdata(prediction)
    ry -= np.average(ry, weights=w); rp -= np.average(rp, weights=w)
    den = np.sqrt(np.sum(w*ry**2)*np.sum(w*rp**2))
    correlation = float(np.sum(w*ry*rp)/den) if den > 0 else np.nan
    # Ties at a cutoff contribute equally, avoiding arbitrary apartment-ID ordering.
    tail_n = len(y)*config('training')['tail_share']
    _, inverse, count = np.unique(prediction, return_inverse=True, return_counts=True)
    before = np.cumsum(count)-count
    low_fraction = np.clip((tail_n-before)/count, 0, 1)[inverse]
    after = len(y)-np.cumsum(count)
    high_fraction = np.clip((tail_n-after)/count, 0, 1)[inverse]
    gap = np.average(y, weights=w*high_fraction)-np.average(y, weights=w*low_fraction)
    return {'RMSE': float(np.sqrt(np.average(residual**2, weights=w))),
            'MAE': float(np.average(abs(residual), weights=w)), 'Spearman': correlation,
            'top_bottom_20pct_gap': float(gap)}
