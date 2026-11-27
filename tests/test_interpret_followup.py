"""Small end-to-end coverage of the previously unexecuted interpretation path."""
import json
import pathlib
import sys
import numpy as np
import pandas as pd

ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'old/v1'), str(ROOT/'old/v2')]
import followup as f
import interpret_followup as interpretation

def test_interpretation_outputs_and_resume(tmp_path,monkeypatch):
    out=tmp_path/'reports';out.mkdir()
    art=tmp_path/'artifacts';art.mkdir()
    monkeypatch.setattr(f,'OUT',out);monkeypatch.setattr(f,'ART',art)
    cfg={**f.CFG,'bootstrap_replicates':10,'shap_max_rows':24}
    monkeypatch.setattr(f,'CFG',cfg)
    keys=[f'{r}_{m}' for r in ['up1','corr','up2','down','rec','up3'] for m in ['window','slope']]
    rows=[{'table':k,'model':m,'variant':'baseline'} for k in keys for m in ['ridge','catboost']]
    pd.DataFrame(rows).to_csv(out/'cv_choices.csv',index=False)
    (out/'protocol.json').write_text('{}',encoding='utf-8')
    rng=np.random.default_rng(33);names,cats=f.v1.feature_names()
    d=pd.DataFrame({n:rng.normal(size=30) for n in names})
    for c in cats:d[c]=['a','b','c']*10
    for n in names:
        if n.endswith('_missing'):d[n]=0.
    d['cell_id']=[f'c{i}' for i in range(30)]
    d['complex_id']=[f'g{i//2}' for i in range(30)]
    d['y']=2*d['전용면적']+rng.normal(size=30)*.1
    d['weight']=1.
    monkeypatch.setattr(f.v1,'tables',lambda:[(k,None) for k in keys])
    monkeypatch.setattr(f,'train_table',lambda *args:d.copy())
    monkeypatch.setattr(f,'repairs_for',lambda key:pd.Series(dtype=float))
    monkeypatch.setattr(f,'selected_params',lambda key,model:{'alpha':1.} if model=='ridge' else {'iterations':4,'depth':2})
    interpretation.main()
    protocol=json.loads((out/'interpretation_protocol.json').read_text())
    assert protocol['test_used'] is False and protocol['shap_additivity_passed']
    effects=pd.read_csv(out/'numeric_effects.csv')
    assert set(effects.table)==set(keys)
    assert set(effects.sign)<= {'+','-','0','NA'}
    intervals=pd.read_csv(out/'ridge_intervals.csv')
    assert intervals.low.le(intervals.high).all()
    assert intervals.bootstrap_replicates.eq(10).all()
    types=pd.read_csv(out/'type_candidates.csv',keep_default_na=False)
    assert len(types)==24
    before=(out/'shap_importance.csv').read_bytes()
    interpretation.main()
    assert (out/'shap_importance.csv').read_bytes()==before
