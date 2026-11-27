import pathlib
import sys
import numpy as np
import pandas as pd
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/model'))
import nested_v3 as n

def sample():
    names,cats=n.v1.feature_names()
    d=pd.DataFrame({k:[1.,2.,3.,4.] for k in names})
    for k in cats:d[k]=['a','b','a','b']
    for k in n.f.CONTROLS:d[k]=[1.,2.,3.,4.]
    d['가격대']=['a','b','a','b']
    d['세대당_주차대수']=[1.,2.,0.,4.]
    d['세대당_주차대수_missing']=0
    d['dong_id']=['a','a','b','b']
    d['y']=[1.,2.,3.,4.]
    d['weight']=1.
    return d

def test_holdout_excluded():
    train,excluded=n.eligible_groups()
    assert len(train)==255 and len(excluded)==64 and not train&excluded

def test_quality_decision_never_uses_validation():
    d=sample()
    for variant in ('quality','extended'):
        x,z,cats,flag=n.fit_design(d.iloc[:2],d.iloc[2:],variant)
        assert not flag and z['세대당_주차대수'].iloc[0]==0
        x,z,cats,flag=n.fit_design(d.iloc[2:],d.iloc[:2],variant)
        assert flag and np.isnan(x['세대당_주차대수'].iloc[0])

def test_group_overlap_rejected():
    d=sample()
    with pytest.raises(ValueError,match='Group overlap'):
        n.fit_predict(d.iloc[:2],d.iloc[1:3],'ridge',{'alpha':1},'baseline')

def test_fixed_grid_and_tie_order():
    assert len(list(n.candidates()))==18
    s=pd.DataFrame([dict(family='ridge',variant='baseline',grid_index=0,RMSE=1.),
                    dict(family='catboost',variant='extended',grid_index=1,RMSE=1.)])
    assert n.choose(s)==('ridge','baseline',0)


def test_full_eda_rejects_held_out_dongs(tmp_path):
    raw=pd.DataFrame({'자치구':['A','A'],'법정동':['train','test']})
    with pytest.raises(ValueError,match='non-training'):
        n.run_train_eda(raw,{'A|train'},{'A|test'},tmp_path)
