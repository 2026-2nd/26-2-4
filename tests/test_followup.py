import pathlib
import sys
import numpy as np
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'old/v1'), str(ROOT/'old/v2')]
import followup as f

def fixture():
    names,cats=f.v1.feature_names()
    d=pd.DataFrame({n:[1.,2.,3.,4.] for n in names})
    for c in cats:d[c]=['a','b',None,'a']
    d['cell_id']=['a','b','c','d'];d['세대당_주차대수']=[0.,1.,4.,np.nan]
    return d

def test_unknown_day_retains_valid_month_only():
    r=f.repaired_month(pd.Series(['1970-03-00','2000-12-17','2000-13-00','garbage']))
    assert str(r[0].date())=='1970-03-01'
    assert r[1].day==17 and r.iloc[2:].isna().all()

def test_quality_does_not_mutate_baseline_and_refreshes_flag():
    d=fixture(); original=d.copy(deep=True)
    baseline,_=f.build_design(d,'baseline')
    quality,_=f.build_design(d,'quality',pd.Series({'a':120.}))
    pd.testing.assert_frame_equal(d,original)
    assert baseline.loc[0,'세대당_주차대수']==0
    assert np.isnan(quality.loc[0,'세대당_주차대수'])
    assert quality.loc[0,'세대당_주차대수_missing']==1
    assert quality.loc[0,'연식_개월_a']==120 and quality.loc[0,'재건축연한']==0

def test_sparse_removal_and_cap_are_separate_variants():
    d=fixture(); x,cats=f.build_design(d,'without_sparse')
    assert not set(f.SPARSE)&set(x) and '난방방식' not in cats
    capped,_=f.build_design(d,'parking_cap')
    assert capped.loc[2,'세대당_주차대수']==3
    quality,_=f.build_design(d,'quality')
    assert quality.loc[2,'세대당_주차대수']==4

def test_imputation_uses_fit_subset_and_unknown_category_is_safe():
    d=fixture();x,cats=f.build_design(d,'quality');p=f.prep(x,cats)
    p.fit(x.iloc[:2]); median=p.named_transformers_['numeric'].named_steps['impute'].statistics_
    numeric=[n for n in x if n not in cats]
    assert median[numeric.index('세대당_주차대수')]==1.
    assert np.isfinite(p.transform(x.iloc[2:])).all()

def test_train_loader_removes_test_rows(monkeypatch):
    monkeypatch.setattr(f.v1,'load_table',lambda *args:pd.DataFrame({'split':['train','test'],'cell_id':['train_id','secret_test']}))
    loaded=f.train_table('unused',None)
    assert loaded.cell_id.tolist()==['train_id']

def test_type_candidates_do_not_turn_missing_evidence_into_direction():
    from interpret_followup import classify
    assert classify('NA','+')=='혼합 또는 판단 유보'
    assert classify('0','0')=='효과 미확인'
    assert classify('+','-')=='공격형 후보'
