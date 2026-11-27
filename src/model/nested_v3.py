"""V3: train-only EDA and nested group CV; never evaluate the exposed V1 holdout."""
from __future__ import annotations
import argparse
import copy
import json
import pathlib
import sys

import numpy as np
import pandas as pd
from catboost import CatBoostRegressor, Pool
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold
from threadpoolctl import threadpool_limits

import train as v1
import followup as f

ROOT = v1.ROOT
OUT = ROOT / 'results' / 'nested_v3'
SEED = 20261127
OUTER, INNER = 5, 3
# Fixed before evaluation; do not reuse V1 winners or tune on outer predictions.
VARIANTS = ('baseline', 'quality', 'extended')
GRID = {
    'ridge': [{'alpha': a} for a in (1., 100.)],
    'random_forest': [
        {'n_estimators': 150, 'max_depth': d, 'min_samples_leaf': l, 'max_features': .6}
        for d, l in ((8, 10), (None, 20))],
    'catboost': [
        {'depth': d, 'iterations': 300, 'learning_rate': .05, 'l2_leaf_reg': 5}
        for d in (4, 6)],
}
FAMILIES = tuple(GRID)


def eligible_groups():
    a = pd.read_csv(ROOT/'reports/final/models/dong_assignments_v1.csv')
    assert a.dong_id.is_unique
    train = set(a.loc[a.split.eq('train'), 'dong_id'])
    excluded = set(a.loc[a.split.eq('test'), 'dong_id'])
    assert len(train) == 255 and len(excluded) == 64 and not train & excluded
    return train, excluded


def profile(d, stage, table):
    """Only call with a fitting partition. No evaluation data passed here."""
    names, cats = v1.feature_names()
    features = [n for n in names if not n.endswith('_missing')] + f.CONTROLS
    rows = []
    for name in features:
        s = d[name]
        numeric = pd.to_numeric(s, errors='coerce') if name not in cats + ['가격대'] else None
        record = dict(stage=stage, table=table, feature=name, rows=len(d),
                      dongs=d.dong_id.nunique(), missing=int(s.isna().sum()),
                      distinct=int(s.nunique()))
        if numeric is not None:
            for q, label in [(0.01,'p01'),(.25,'q1'),(.5,'median'),(.75,'q3'),(.99,'p99')]:
                record[label] = numeric.quantile(q)
            record['zero'] = int(numeric.eq(0).sum())
            record['above3'] = int(numeric.gt(3).sum()) if name == '세대당_주차대수' else np.nan
        rows.append(record)
    return rows


def fit_design(train, other, variant):
    """Decide quality operations from fitting rows, then apply identical rules."""
    parking = '세대당_주차대수'
    zero_as_missing = variant != 'baseline' and bool(train[parking].eq(0).any())
    actual = variant if variant != 'quality' or zero_as_missing else 'baseline'
    x, cats = f.build_design(train, actual)
    z, zcats = f.build_design(other, actual)
    # Extended features remain even if train contains no zero. In this case undo
    # the zero transformation on BOTH partitions; no peeking at other statistics.
    if actual == 'extended' and not zero_as_missing:
        for frame, source in [(x, train), (z, other)]:
            frame[parking] = source[parking]
            frame[parking+'_missing'] = source[parking+'_missing']
    if list(x.columns) != list(z.columns) or cats != zcats:
        raise ValueError('Feature schema differs')
    return x, z, cats, zero_as_missing


def fit_predict(train, validation, family, params, variant):
    if set(train.dong_id) & set(validation.dong_id):
        raise ValueError('Group overlap')
    x, z, cats, quality = fit_design(train, validation, variant)
    if family == 'catboost':
        model = CatBoostRegressor(**params, random_seed=SEED, thread_count=2,
                                  loss_function='RMSE', verbose=False,
                                  allow_writing_files=False)
        model.fit(Pool(x, train.y, weight=train.weight, cat_features=cats))
        p = model.predict(z)
    else:
        prep = f.prep(x, cats)
        xt, xv = prep.fit_transform(x), prep.transform(z)
        model = Ridge(**params) if family == 'ridge' else RandomForestRegressor(
            **params, random_state=SEED, n_jobs=2)
        model.fit(xt, train.y, sample_weight=train.weight)
        p = model.predict(xv)
    if not np.isfinite(p).all():
        raise ValueError('Non-finite predictions')
    return np.asarray(p), quality


def build():
    """Split raw rows FIRST, then construct labels/features without excluded dongs."""
    sys.path.insert(0, str(ROOT/'src/cells'))
    import build_cells as c
    train, excluded = eligible_groups()
    cfg, target, feat = [copy.deepcopy(v1.config(n)) for n in ('cells','target','features')]
    regimes = v1.config('regime')['regimes']
    official_path = ROOT/'data/external/rone_apt_trade_index_seoul_raw.csv'
    official = pd.read_csv(official_path, dtype={'ym':str})
    index = pd.Series(official['서울'].to_numpy(float),
                      index=pd.PeriodIndex(pd.to_datetime(official.ym,format='%Y%m'),freq='M').asi8)
    index = index.dropna()
    cutoff = int(index.index.max())
    raw = pd.read_csv(ROOT/cfg['source'], dtype=str, keep_default_na=False)
    group = raw['자치구']+'|'+raw['법정동']
    raw = raw.loc[group.isin(train)].copy()
    assert not set(raw['자치구']+'|'+raw['법정동']) & excluded
    months = pd.to_datetime(raw['계약일'], errors='raise').dt.to_period('M').astype('int64')
    raw = raw.loc[months.le(cutoff)].copy()
    # Raw EDA after the split, prior to model construction; deterministic counts.
    OUT.mkdir(parents=True, exist_ok=True)
    eda = []
    for col in raw:
        s = raw[col]
        eda.append(dict(feature=col, rows=len(s), missing=int(s.eq('').sum()), distinct=s.nunique()))
    v1.save_csv(pd.DataFrame(eda), OUT/'train_raw_eda.csv')
    v1.save_csv(raw.groupby(['자치구','법정동']).size().rename('transactions').reset_index(),
                OUT/'train_raw_groups.csv')
    quality = pd.to_numeric(raw['세대당_주차대수'],errors='coerce')
    v1.save_json(dict(train_transactions=len(raw), train_dongs=len(train), excluded_dongs=len(excluded),
                      parking_zero=int(quality.eq(0).sum()), parking_gt3=int(quality.gt(3).sum()),
                      official_index_last_month=str(pd.Period(ordinal=cutoff,freq='M')),
                      official_index_sha256=v1.sha(official_path),
                      raw_source_sha256=v1.sha(ROOT/cfg['source'])), OUT/'build_manifest.json')
    d = c.prepare(raw, target, index)
    clean = d[d.exclusion_reason.eq('')].copy()
    static, _ = c.static_features(clean, feat)
    tohuh = pd.read_csv(ROOT/feat['controls'][0]['source'],dtype=str,keep_default_na=False)
    previous = None
    base_names = [s['name'] for group in feat['base'].values() for s in group]
    summary = []
    for i,r in enumerate(regimes):
        start,end,period = c.bounds(r,target,i,len(regimes))
        end = (end[0],min(end[1],cutoff))
        period = (period[0],min(period[1],cutoff))
        features = c.features_at(clean,static,r,cfg,feat)
        features = features.join(c.controls(clean,features,r,previous,target,cfg,start,tohuh))
        # Fixed observation start, not a statistic estimated from validation data.
        if start[0]-cfg['controls']['turnover_months'] < c.month('2017-01'):
            features['회전율'] = np.nan
        for method in ('window','slope'):
            candidate = (c.window_target(clean,start,end) if method=='window'
                         else c.slope_target(clean,period,r['L'],target))
            valid = candidate.loc[candidate.target_exclusion.eq('')].join(features)
            valid = valid.loc[valid.cell_exclusion.eq('')].copy()
            # Slope's within-period median floor uses later transactions. Use
            # only floor from the start window for BOTH target definitions.
            floor = clean.loc[clean.m.between(*start)].groupby('cell_id')['층'].median()
            valid['층'] = floor.reindex(valid.index)
            for name in base_names:
                valid[name+'_missing'] = valid[name].isna().astype(int)
            assert valid.index.is_unique and np.isfinite(valid[['y','weight']]).all().all()
            assert valid.weight.gt(0).all() and set(valid.dong_id)<=train
            key = r['id']+'_'+method
            v1.save_csv(valid.sort_index().reset_index(), OUT/'tables'/f'{key}.csv.xz')
            summary.append(dict(table=key,cells=len(valid),dongs=valid.dong_id.nunique(),
                                complexes=valid.complex_id.nunique()))
        previous = (start,end)
    v1.save_csv(pd.DataFrame(summary),OUT/'train_tables.csv')


def candidates():
    for family in FAMILIES:
        for variant in VARIANTS:
            for i,params in enumerate(GRID[family]):
                yield family,variant,i,params


def search(train, stage, table, eda):
    splits = list(GroupKFold(INNER).split(train,groups=train.dong_id))
    for i,(a,b) in enumerate(splits):
        assert not set(train.iloc[a].dong_id)&set(train.iloc[b].dong_id)
        eda.extend(profile(train.iloc[a],f'{stage}_inner{i}_fit',table))
    scores = []
    for family,variant,idx,params in candidates():
        p = np.full(len(train),np.nan)
        for a,b in splits:
            p[b],_ = fit_predict(train.iloc[a],train.iloc[b],family,params,variant)
        assert np.isfinite(p).all()
        score = np.sqrt(np.average((p-train.y.to_numpy())**2,weights=train.weight))
        scores.append(dict(family=family,variant=variant,grid_index=idx,RMSE=float(score)))
    # Stable candidate order breaks ties. Select separately by family and overall.
    return pd.DataFrame(scores)


def choose(scores, family=None):
    s = scores if family is None else scores.loc[scores.family.eq(family)]
    r = s.loc[s.RMSE.idxmin()]
    return r.family,r.variant,int(r.grid_index)


def evaluate(key):
    train_groups,excluded = eligible_groups()
    d = pd.read_csv(OUT/'tables'/f'{key}.csv.xz').sort_values('cell_id').reset_index(drop=True)
    assert d.cell_id.is_unique and set(d.dong_id)<=train_groups and not set(d.dong_id)&excluded
    models = ('b0','b1',*FAMILIES,'inner_selected')
    predictions = {m:np.full(len(d),np.nan) for m in models}
    folds = np.full(len(d),-1)
    eda, all_scores, choices = [], [], []
    for fold,(a,b) in enumerate(GroupKFold(OUTER).split(d,groups=d.dong_id)):
        tr,va=d.iloc[a],d.iloc[b]
        assert not set(tr.dong_id)&set(va.dong_id)
        folds[b]=fold
        stage=f'outer{fold}'
        eda.extend(profile(tr,stage+'_fit',key))
        scores=search(tr,stage,key,eda)
        all_scores.append(scores.assign(stage=stage))
        predictions['b0'][b]=0
        predictions['b1'][b]=v1.baseline(tr,va)
        for family in FAMILIES:
            fam,variant,i=choose(scores,family)
            p,quality=fit_predict(tr,va,fam,GRID[fam][i],variant)
            predictions[fam][b]=p
            choices.append(dict(stage=stage,model=fam,variant=variant,grid_index=i,
                                zero_as_missing=quality))
        winner,variant,i=choose(scores)
        predictions['inner_selected'][b]=predictions[winner][b]
        choices.append(dict(stage=stage,model='inner_selected',family=winner,
                            variant=variant,grid_index=i))
        print(key,stage,winner,variant,flush=True)
    assert (folds>=0).all()
    for p in predictions.values():
        assert np.isfinite(p).all()
    # Final choice on all 255 eligible dongs' rows (never the 64 held-out dongs).
    # This choice is not evaluated by another test in V3.
    eda.extend(profile(d,'final_fit',key))
    final=search(d,'final',key,eda)
    all_scores.append(final.assign(stage='final'))
    family,variant,i=choose(final)
    folder=OUT/'evaluation'/key
    folder.mkdir(parents=True,exist_ok=False)
    v1.save_csv(pd.DataFrame(eda),folder/'train_fold_eda.csv')
    v1.save_csv(pd.concat(all_scores,ignore_index=True),folder/'inner_scores.csv')
    v1.save_csv(pd.DataFrame(choices),folder/'outer_choices.csv')
    frame=d[['cell_id','complex_id','dong_id','y','weight']].copy()
    frame['outer_fold']=folds
    for m,p in predictions.items(): frame[m]=p
    v1.save_csv(frame,folder/'outer_predictions.csv.xz')
    metrics=[dict(table=key,model=m,cells=len(d),**v1.metric_values(d.y,p,d.weight))
             for m,p in predictions.items()]
    v1.save_csv(pd.DataFrame(metrics),folder/'metrics.csv')
    v1.save_json(dict(table=key,family=family,variant=variant,params=GRID[family][i],
                      train_cells=len(d),outer_folds=OUTER,inner_folds=INNER,
                      independently_unseen_test=False,
                      note='Final selection only; no fresh holdout available.'),folder/'final_choice.json')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['build','evaluate'])
    p.add_argument('--table')
    a=p.parse_args()
    with threadpool_limits(limits=1):
        if a.stage=='build': build()
        else:
            if not a.table: p.error('--table required')
            evaluate(a.table)

if __name__=='__main__':
    main()
