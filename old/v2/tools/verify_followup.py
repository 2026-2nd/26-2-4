"""Independently recompute saved OOF scores, selection, group errors and frozen-v1 inputs."""
import json
import pathlib
import sys
import numpy as np
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'old/v1'), str(ROOT/'old/v2')]
import followup as f

def main():
    old=json.loads((ROOT/'old/v1/models/split_manifest_v1.json').read_text(encoding='utf-8'))
    for name,expected in old['input_sha256'].items():
        assert f.v1.sha(ROOT/name)==expected, name
    protocol=json.loads((f.OUT/'protocol.json').read_text(encoding='utf-8'))
    assert not protocol['test_used']
    assert protocol['input_sha256']==f.fingerprint()
    scores=pd.read_csv(f.OUT/'cv_comparison.csv'); choices=pd.read_csv(f.OUT/'cv_choices.csv')
    errors=pd.read_csv(f.OUT/'group_errors.csv');checked=0;group_checked=0
    assert len(scores)==12*len(f.CFG['variants'])*len(f.CFG['models'])
    assert not scores.duplicated(['table','variant','model']).any()
    assert len(choices)==24 and choices.variant.isin(f.CFG['selection_variants']).all()
    assignments=pd.read_csv(ROOT/'old/v1/models/dong_assignments_v1.csv')
    test=set(assignments.loc[assignments.split.eq('test'),'dong_id'])
    for key,path in f.v1.tables():
        d=f.train_table(key,path)
        assert not set(d.dong_id)&test
        for fold in sorted(d.fold.unique()):
            assert not set(d.loc[d.fold.eq(fold),'dong_id'])&set(d.loc[d.fold.ne(fold),'dong_id'])
        for _,r in scores[scores.table.eq(key)].iterrows():
            p=pd.read_csv(f.ART/f'{key}_{r.model}_{r.variant}_oof.csv.xz')
            assert p.cell_id.tolist()==d.cell_id.tolist()
            assert p.dong_id.tolist()==d.dong_id.tolist()
            assert np.allclose(p.y,d.y) and np.allclose(p.weight,d.weight)
            rmse=np.sqrt(np.sum(d.weight*(p.prediction-d.y)**2)/d.weight.sum())
            mae=np.sum(d.weight*abs(p.prediction-d.y))/d.weight.sum()
            assert np.isclose(rmse,r.RMSE,rtol=1e-8) and np.isclose(mae,r.MAE,rtol=1e-8)
            checked+=1
            masks={'all':np.ones(len(d),bool),'heating_missing':d['난방방식'].isna(),
                   'heating_observed':d['난방방식'].notna(),'small_complex':d['세대수'].lt(300),
                   'large_complex':d['세대수'].ge(300),'small_area':d['전용면적'].le(60)}
            subset=errors[(errors.table==key)&(errors.model==r.model)&(errors.variant==r.variant)]
            for _,g in subset.iterrows():
                mask=masks[g.group];residual=p.prediction[mask]-d.y[mask]
                expected=np.sqrt(np.average(residual**2,weights=d.weight[mask]))
                assert int(mask.sum())==g.cells and np.isclose(expected,g.RMSE,rtol=1e-8)
                group_checked+=1
        for model in f.CFG['models']:
            group=scores[(scores.table==key)&(scores.model==model)&scores.variant.isin(f.CFG['selection_variants'])]
            choice=choices[(choices.table==key)&(choices.model==model)].iloc[0]
            assert np.isclose(choice.RMSE,group.RMSE.min())
    interpretation=json.loads((f.OUT/'interpretation_protocol.json').read_text(encoding='utf-8'))
    assert interpretation['test_used'] is False and interpretation['shap_additivity_passed'] is True
    intervals=pd.read_csv(f.OUT/'ridge_intervals.csv')
    assert intervals.low.le(intervals.high).all() and intervals.bootstrap_replicates.eq(1000).all()
    types=pd.read_csv(f.OUT/'type_candidates.csv')
    assert types.status.eq('exploratory_training_only_not_final').all()
    result={'frozen_v1_inputs_unchanged':True,'test_dongs_excluded':True,'group_isolation_passed':True,
            'oof_scores_recomputed':checked,'group_errors_recomputed':group_checked,'selections_verified':len(choices),
            'ridge_intervals_structurally_checked':len(intervals),'shap_additivity_passed':True,
            'new_test_evaluation':False}
    f.save(result,'verification.json');print(json.dumps(result),flush=True)

if __name__=='__main__':main()
