"""Exploratory training-only Ridge intervals and native CatBoost SHAP.

Intervals condition on selected variant/parameters and the reference preprocessing.
They are not post-selection confidence guarantees or causal estimates.
"""
import json
import numpy as np
import pandas as pd
from catboost import Pool
from scipy.stats import spearmanr
from sklearn.linear_model import Ridge
from threadpoolctl import threadpool_limits
import followup as f

def classify(up, down):
    if up=='+' and down=='+':return '전천후형 후보'
    if down=='+' and up in ['0','-']:return '방어형 후보'
    if up=='+' and down=='-':return '공격형 후보'
    if up=='-' and down=='-':return '취약형 후보'
    if up==down=='0':return '효과 미확인'
    return '혼합 또는 판단 유보'

def main():
    fingerprint={'comparison':f.v1.sha(f.OUT/'protocol.json'),'choices':f.v1.sha(f.OUT/'cv_choices.csv'),
                 'source':f.v1.sha(f.pathlib.Path(__file__))}
    manifest=f.ART/'interpretation_manifest.json'
    if manifest.exists() and json.loads(manifest.read_text(encoding='utf-8'))!=fingerprint:
        raise ValueError('Interpretation inputs changed; stale cache refused')
    f.v1.save_json(fingerprint,manifest)
    winners=pd.read_csv(f.OUT/'cv_choices.csv'); coefs=[]; importance=[]; curves=[]; effects=[]
    names,basecats=f.v1.feature_names()
    base=[n for n in names if not n.endswith('_missing') and n not in basecats]
    with threadpool_limits(limits=1):
        for key,path in f.v1.tables():
            cache=f.ART/f'{key}_interpretation.json'
            if cache.exists():
                saved=json.loads(cache.read_text(encoding='utf-8'))
                coefs+=saved['coefs'];importance+=saved['importance'];curves+=saved['curves'];effects+=saved['effects']
                print('Resume interpretation',key,flush=True);continue
            d=f.train_table(key,path); rng=np.random.default_rng(f.CFG['seed'])
            pick={m:winners[(winners.table==key)&(winners.model==m)].iloc[0].variant for m in ['ridge','catboost']}
            xr,cr=f.build_design(d,pick['ridge'],f.repairs_for(key));xc,cc=f.build_design(d,pick['catboost'],f.repairs_for(key))
            pr=f.selected_params(key,'ridge');pc=f.selected_params(key,'catboost')
            ridge=f.fit('ridge',pr,xr,d.y,d.weight,cr)
            cat=f.fit('catboost',pc,xc,d.y,d.weight,cc)
            f.joblib.dump(ridge,f.ART/f'{key}_selected_ridge.joblib',compress=3)
            f.joblib.dump(cat,f.ART/f'{key}_selected_catboost.joblib',compress=3)
            transform=ridge.named_steps['preprocess'];z=transform.transform(xr)
            feature_labels=transform.get_feature_names_out()
            codes,groups=pd.factorize(d.complex_id,sort=True)
            bs=[]
            for _ in range(f.CFG['bootstrap_replicates']):
                multiplicity=np.bincount(rng.integers(0,len(groups),size=len(groups)),minlength=len(groups))
                weights=d.weight.to_numpy()*multiplicity[codes]
                bs.append(Ridge(**pr).fit(z,d.y,sample_weight=weights).coef_)
            lo,hi=np.quantile(bs,[.025,.975],axis=0)
            coef_by={};local_coefs=[]
            for j,label in enumerate(feature_labels):
                label=label.split('__',1)[1]
                record={'table':key,'variant':pick['ridge'],'feature':label,'coefficient':ridge.named_steps['model'].coef_[j],
                        'low':lo[j],'high':hi[j],'bootstrap_replicates':len(bs)}
                coef_by[label]=record;local_coefs.append(record)
            selected=np.sort(rng.choice(len(d),size=min(f.CFG['shap_max_rows'],len(d)),replace=False))
            sx=xc.iloc[selected];sw=d.weight.iloc[selected].to_numpy()
            shap=cat.get_feature_importance(Pool(sx,cat_features=cc),type='ShapValues',thread_count=f.CFG['catboost_threads'])
            if not np.allclose(shap.sum(axis=1),cat.predict(sx),rtol=1e-6,atol=1e-6):raise ValueError('SHAP additivity')
            local_imp=[];local_curves=[];local_effect=[]
            for j,label in enumerate(xc.columns):
                values=shap[:,j]
                rho=np.nan
                if label not in cc:
                    numeric=pd.to_numeric(sx[label],errors='coerce').to_numpy(); valid=np.isfinite(numeric)
                    if valid.sum()>2 and len(np.unique(numeric[valid]))>1:
                        if len(np.unique(values[valid]))>1:
                            rho=float(spearmanr(numeric[valid],values[valid]).statistic)
                        # Quantile dependence summaries expose nonmonotonic patterns.
                        bins=pd.qcut(pd.Series(numeric),q=min(10,len(np.unique(numeric[valid]))),duplicates='drop')
                        for level in bins.dropna().unique():
                            mask=(bins==level).to_numpy()
                            local_curves.append({'table':key,'feature':label,'x_mean':float(np.average(numeric[mask],weights=sw[mask])),
                                'shap_mean':float(np.average(values[mask],weights=sw[mask])),'cells':int(mask.sum())})
                local_imp.append({'table':key,'variant':pick['catboost'],'feature':label,
                    'mean_abs_shap':float(np.average(abs(values),weights=sw)),'feature_shap_spearman':rho,
                    'sample_cells':len(selected)})
                if label in base and label in coef_by:
                    c=coef_by[label];sign='0'
                    if c['low']>0 and np.isfinite(rho) and rho>0:sign='+'
                    if c['high']<0 and np.isfinite(rho) and rho<0:sign='-'
                    local_effect.append({'table':key,'feature':label,'sign':sign,
                        'ridge_variant':pick['ridge'],'catboost_variant':pick['catboost'],
                        'ridge_low':c['low'],'ridge_high':c['high'],'shap_trend':rho})
            # Missing sparse numeric features are explicitly unavailable, not zero effect.
            present={e['feature'] for e in local_effect}
            for label in base:
                if label not in present:local_effect.append({'table':key,'feature':label,'sign':'NA'})
            saved={'coefs':local_coefs,'importance':local_imp,'curves':local_curves,'effects':local_effect}
            f.v1.save_json(json.loads(json.dumps(saved,default=float).replace('NaN','null')),cache)
            coefs+=local_coefs;importance+=local_imp;curves+=local_curves;effects+=local_effect
            print('Interpreted',key,flush=True)
    f.save(pd.DataFrame(coefs),'ridge_intervals.csv');f.save(pd.DataFrame(importance),'shap_importance.csv')
    f.save(pd.DataFrame(curves),'shap_dependence.csv');ef=pd.DataFrame(effects);f.save(ef,'numeric_effects.csv')
    types=[]
    for method in f.CFG['methods']:
        for feature in base:
            signs=ef[ef.feature.eq(feature)].set_index('table')['sign'].to_dict()
            up=[signs[f'{r}_{method}'] for r in ['up1','up2','up3']]
            aggregate='+' if up.count('+')>=2 else '-' if up.count('-')>=2 else 'NA' if 'NA' in up else '0'
            down=signs[f'down_{method}'];corr=signs[f'corr_{method}']
            both=down if down==corr else 'NA'
            types.append({'method':method,'feature':feature,'up_sign':aggregate,'down_sign':down,'corr_sign':corr,
                'without_corr':classify(aggregate,down),'with_corr_agreement':classify(aggregate,both),
                'status':'exploratory_training_only_not_final'})
    f.save(pd.DataFrame(types),'type_candidates.csv')
    f.save({'test_used':False,'shap_additivity_passed':True,'tables':12,'bootstrap_replicates':f.CFG['bootstrap_replicates'],
            'input_sha256':fingerprint,
            'direction':'unweighted Spearman(feature, SHAP) on finite numeric observations; not mean SHAP sign',
            'intervals':'cluster bootstrap conditional on chosen specification and fixed reference preprocessing',
            'categories':'importance only; no ordinal direction or type assigned',
            'limitations':['training-only exploratory interpretation','selection uncertainty excluded','global trend may hide nonlinear effects',
                           'missingness is not causal','zero sign means insufficient agreement, not absence of effect']},'interpretation_protocol.json')

if __name__=='__main__':main()
