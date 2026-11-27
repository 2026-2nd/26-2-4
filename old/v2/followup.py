"""EDA follow-up on frozen TRAIN dongs only. Never reopens the held-out test.

python old/v2/followup.py audit
python old/v2/followup.py compare
python old/v2/followup.py interpret
"""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import sys
from concurrent.futures import ThreadPoolExecutor
import joblib
import numpy as np
import pandas as pd
import yaml
from catboost import CatBoostRegressor, Pool
from scipy.stats import spearmanr
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]/'old/v1'))
import train as v1
ROOT = pathlib.Path(__file__).resolve().parents[2]
CFG = yaml.safe_load((ROOT/'old/v2/config/followup.yaml').read_text(encoding='utf-8'))
OUT = ROOT/CFG['output']
ART = ROOT/CFG['artifacts']
SPARSE = ['난방방식', '복도유형', '시공사_상위10']
LOGS = ['세대수', '최근접_역_거리', '최근접_초등학교_거리']
CONTROLS = ['토지거래허가구역_a', '가격대', '직전국면_y', '회전율']

def save(d, name):
    OUT.mkdir(parents=True, exist_ok=True)
    if isinstance(d, pd.DataFrame): v1.save_csv(d, OUT/name)
    else: v1.save_json(d, OUT/name)

def train_table(key, path):
    d = v1.load_table(key, path)
    d = d.loc[d['split'].eq('train')].reset_index(drop=True)
    if not len(d) or not d['split'].eq('train').all(): raise ValueError('Train only')
    return d

def repaired_month(s):
    """Retain a valid YYYY-MM when only the approval day is unknown (00)."""
    s = s.astype('string')
    parsed = pd.to_datetime(s, errors='coerce')
    repair = parsed.isna() & s.str.fullmatch(r'\d{4}-(0[1-9]|1[0-2])-00', na=False)
    parsed.loc[repair] = pd.to_datetime(s.loc[repair].str[:7]+'-01', errors='raise')
    return parsed

def build_design(d, variant, repairs=None):
    x = v1.design(d)
    cats = list(v1.feature_names()[1])
    if variant != 'baseline':
        parking = '세대당_주차대수'
        x.loc[x[parking].eq(0), parking] = np.nan
        x[parking+'_missing'] = x[parking].isna().astype(int)
        if repairs is not None:
            values = d.cell_id.map(repairs)
            use = values.notna()
            x.loc[use, '연식_개월_a'] = values[use].to_numpy()
            x.loc[use, '재건축연한'] = (values[use] >= 360).astype(int).to_numpy()
        if variant == 'parking_cap': x[parking] = x[parking].clip(upper=3)
        if variant == 'without_sparse':
            x = x.drop(columns=SPARSE+[c+'_missing' for c in SPARSE])
            cats = [c for c in cats if c not in SPARSE]
        if variant == 'log_numeric':
            for c in LOGS: x[c] = np.log1p(x[c].clip(lower=0))
        if variant == 'extended':
            for c in CONTROLS:
                x[c+'_missing'] = d[c].isna().astype(int)
                x[c] = d[c].fillna('__MISSING__').astype(str) if c == '가격대' else d[c]
            cats.append('가격대')
    return x, cats

def prep(x, cats):
    nums = [c for c in x if c not in cats]
    return ColumnTransformer([
        ('numeric', Pipeline([('impute', SimpleImputer(strategy='median', keep_empty_features=True)),
                              ('scale', StandardScaler())]), nums),
        ('category', OneHotEncoder(handle_unknown='ignore', sparse_output=False), cats)])

def selected_params(key, model):
    return json.loads((ROOT/f'old/v1/models/selections/{key}_{model}_v1.json').read_text(encoding='utf-8'))['params']

def fit(model_id, params, x, y, w, cats):
    if model_id == 'catboost':
        model = CatBoostRegressor(**params, random_seed=v1.config('models')['seed'],
            thread_count=CFG['catboost_threads'], loss_function='RMSE', verbose=False, allow_writing_files=False)
        model.fit(Pool(x, y, weight=w, cat_features=cats))
    else:
        model = Pipeline([('preprocess', prep(x, cats)), ('model', Ridge(**params))])
        model.fit(x, y, model__sample_weight=w)
    return model

def audit():
    OUT.mkdir(parents=True, exist_ok=True)
    # Input is read for data-quality auditing; target analysis below is train-only.
    raw = pd.read_csv(ROOT/v1.config('cells')['source'], dtype=str, keep_default_na=False)
    sys.path.insert(0, str(ROOT/'src/cells'))
    import build_cells as cells
    idx = pd.read_csv(ROOT/'data/regime/seoul_index_2017_2026.csv', index_col=0)['main']
    idx.index = [cells.month(m) for m in idx.index]
    d = cells.prepare(raw, v1.config('target'), idx)
    assignments = pd.read_csv(ROOT/'old/v1/models/dong_assignments_v1.csv')
    train_dongs = set(assignments.loc[assignments.split.eq('train'), 'dong_id'])
    clean = d.loc[d.exclusion_reason.eq('') & d.dong_id.isin(train_dongs)].copy()
    static, _ = cells.static_features(clean, v1.config('features'))
    orig = pd.to_datetime(static['사용승인일'], errors='coerce')
    repaired = repaired_month(static['사용승인일'])
    fixed = static.loc[orig.isna() & repaired.notna()].copy()
    fixed['approval_month'] = repaired.loc[fixed.index].dt.to_period('M').astype(str)
    save(fixed.reset_index()[['complex_id', '사용승인일', '건축년도', 'approval_month']], 'approval_repairs.csv')
    quality, composition, repairs = [], [], []
    for key, path in v1.tables():
        t = train_table(key, path)
        r = next(r for r in v1.config('regime')['regimes'] if r['id'] == key.rsplit('_',1)[0])
        am = pd.to_datetime(t.complex_id.map(fixed.approval_month), errors='coerce')
        newage = (pd.Period(r['a'],'M').year-am.dt.year)*12 + pd.Period(r['a'],'M').month-am.dt.month
        if (newage.dropna()<0).any(): raise ValueError('Repair changes eligibility; requires separate cohort protocol')
        for i in t.index[newage.notna()]: repairs.append({'table':key,'cell_id':t.at[i,'cell_id'],'old_age':t.at[i,'연식_개월_a'],'new_age':newage[i]})
        quality.append({'table':key,'train_cells':len(t),'parking_zero':int(t['세대당_주차대수'].eq(0).sum()),
            'parking_gt3':int(t['세대당_주차대수'].gt(3).sum()),'approval_repaired_cells':int(newage.notna().sum()),
            'heating_missing_share':float(t['난방방식'].isna().mean())})
        period = cells.bounds(r,v1.config('target'),v1.config('regime')['regimes'].index(r),6)[2]
        transactions = clean.loc[clean.m.between(*period)]
        for population, g in [('eligible_train_trades',transactions),('retained_train_cells',t)]:
            area = g['전용면적(㎡)'] if population.endswith('trades') else g['전용면적']
            households = pd.to_numeric(g['세대수'], errors='coerce')
            composition.append({'table':key,'population':population,'rows':len(g),'complexes':g.complex_id.nunique(),
                'area_median':area.median(),'small_area_share':area.le(60).mean(),
                'households_median':households.median(),'small_complex_share_among_known':households.dropna().lt(300).mean()})
    save(pd.DataFrame(repairs,columns=['table','cell_id','old_age','new_age']),'cell_age_repairs.csv')
    save(pd.DataFrame(quality),'quality_audit.csv'); save(pd.DataFrame(composition),'cohort_composition.csv')
    # Source diagnostics retain ambiguity rather than declaring zero parking erroneous.
    parking=pd.to_numeric(raw['세대당_주차대수'],errors='coerce')
    save({'source_rows':len(raw),'parking_zero_source_rows':int(parking.eq(0).sum()),
          'parking_gt3_source_rows':int(parking.gt(3).sum()),
          'invalid_nonempty_approval_rows':int((raw['사용승인일'].ne('')&pd.to_datetime(raw['사용승인일'],errors='coerce').isna()).sum()),
          'policy':'Zero parking is an unverified missing-value sensitivity, not a certified source correction.',
          'experiment_population':'frozen train dongs only; retained v1 cells and targets unchanged'},'audit.json')
    print('Audit complete',flush=True)

def repairs_for(key):
    t=pd.read_csv(OUT/'cell_age_repairs.csv'); return t[t.table.eq(key)].set_index('cell_id').new_age

def cv_task(key,d,variant,model_id):
    x,cats=build_design(d,variant,repairs_for(key)); params=selected_params(key,model_id)
    prediction=np.empty(len(d)); weights=np.ones(len(d)) if variant=='equal_weight' else d.weight.to_numpy()
    for fold in sorted(d.fold.unique()):
        tr=np.flatnonzero(d.fold.ne(fold)); va=np.flatnonzero(d.fold.eq(fold))
        if set(d.iloc[tr].dong_id)&set(d.iloc[va].dong_id): raise ValueError('Group overlap')
        model=fit(model_id,params,x.iloc[tr],d.y.iloc[tr],weights[tr],cats)
        prediction[va]=model.predict(x.iloc[va])
    # All variants are evaluated using original weights, even equal-weight training.
    metrics=v1.metric_values(d.y,prediction,d.weight)
    pred=d[['cell_id','complex_id','dong_id','fold','y','weight']].copy(); pred['prediction']=prediction
    v1.save_csv(pred,ART/f'{key}_{model_id}_{variant}_oof.csv.xz')
    record={'table':key,'model':model_id,'variant':variant,'train_cells':len(d),**metrics}
    v1.save_json(record,ART/f'{key}_{model_id}_{variant}.json')
    print('CV',key,model_id,variant,round(metrics['RMSE'],4),flush=True)
    return record

def fingerprint():
    paths=[ROOT/'old/v2/config/followup.yaml',pathlib.Path(__file__),ROOT/'old/v1/train.py',OUT/'cell_age_repairs.csv']
    paths += [p for _,p in v1.tables()]
    paths += list((ROOT/'old/v1/models/selections').glob('*.json'))
    paths += [ROOT/'old/v1/models/cell_splits_v1.csv.xz']
    return {p.relative_to(ROOT).as_posix():v1.sha(p) for p in paths}

def compare():
    ART.mkdir(parents=True,exist_ok=True)
    manifest={'input_sha256':fingerprint(),'test_used':False,'interpretation':'exploratory train CV, not unbiased generalization estimate; v1 params were selected on these folds'}
    cache=ART/'manifest.json'
    if cache.exists() and json.loads(cache.read_text(encoding='utf-8'))!=manifest: raise ValueError('Inputs changed; no stale resume')
    v1.save_json(manifest,cache); records=[]
    with threadpool_limits(limits=1),ThreadPoolExecutor(max_workers=CFG['workers']) as pool:
        for key,path in v1.tables():
            d=train_table(key,path); pending=[]
            for variant in CFG['variants']:
                for model in CFG['models']:
                    cached=ART/f'{key}_{model}_{variant}.json'
                    if cached.exists(): records.append(json.loads(cached.read_text(encoding='utf-8')))
                    else: pending.append(pool.submit(cv_task,key,d,variant,model))
            records.extend(task.result() for task in pending)
            save(pd.DataFrame(records),'cv_comparison.csv')
    scores=pd.DataFrame(records).sort_values(['table','model','RMSE','variant'])
    eligible=scores[scores.variant.isin(CFG['selection_variants'])]
    winners=eligible.groupby(['table','model'],sort=False).head(1)
    save(winners,'cv_choices.csv'); save(manifest,'protocol.json')
    # Stratify honest out-of-fold residuals, never held-out test residuals.
    groups=[]
    for key,path in v1.tables():
        d=train_table(key,path)
        subsets={'all':np.ones(len(d),bool),'heating_missing':d['난방방식'].isna(),
            'heating_observed':d['난방방식'].notna(),'small_complex':d['세대수'].lt(300),
            'large_complex':d['세대수'].ge(300),'small_area':d['전용면적'].le(60)}
        for model in CFG['models']:
            chosen=winners[(winners.table==key)&(winners.model==model)].iloc[0].variant
            for variant in sorted(set(['baseline',chosen])):
                pred=pd.read_csv(ART/f'{key}_{model}_{variant}_oof.csv.xz').set_index('cell_id').reindex(d.cell_id).prediction.to_numpy()
                for label,mask in subsets.items():
                    if not np.any(mask): continue
                    groups.append({'table':key,'model':model,'variant':variant,'group':label,'cells':int(np.sum(mask)),
                        **v1.metric_values(d.y[mask],pred[mask],d.weight[mask])})
    save(pd.DataFrame(groups),'group_errors.csv')
    print('Comparison complete',flush=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['audit','compare']);args=ap.parse_args()
    {'audit':audit,'compare':compare}[args.phase]()
