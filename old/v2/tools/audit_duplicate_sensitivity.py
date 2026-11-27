"""Train-only target sensitivity; identical-condition trades are NOT declared duplicates."""
import pathlib
import sys
import numpy as np
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'old/v1'), str(ROOT/'old/v2')]
sys.path.insert(0,str(ROOT/'src/cells'))
import followup as f
import build_cells as c

def main():
    raw=pd.read_csv(ROOT/f.v1.config('cells')['source'],dtype=str,keep_default_na=False)
    idx=pd.read_csv(ROOT/'data/regime/seoul_index_2017_2026.csv',index_col=0)['main']
    idx.index=[c.month(m) for m in idx.index]
    d=c.prepare(raw,f.v1.config('target'),idx)
    assignments=pd.read_csv(ROOT/'old/v1/models/dong_assignments_v1.csv')
    allowed=set(assignments.loc[assignments.split.eq('train'),'dong_id'])
    d=d[d.exclusion_reason.eq('')&d.dong_id.isin(allowed)]
    keys=['complex_id','전용면적(㎡)','층','계약일','거래금액_만원']
    dedup=d.drop_duplicates(keys)
    records=[];regs=f.v1.config('regime')['regimes'];cfg=f.v1.config('target')
    for i,r in enumerate(regs):
        start,end,period=c.bounds(r,cfg,i,len(regs))
        for method in ['window','slope']:
            key=f'{r["id"]}_{method}'
            original=f.train_table(key,ROOT/f'old/v1/cells/{key}_v1.csv.xz').set_index('cell_id')
            adjusted=c.window_target(dedup,start,end) if method=='window' else c.slope_target(dedup,period,r['L'],cfg)
            adjusted=adjusted[adjusted.target_exclusion.eq('')].reindex(original.index)
            valid=adjusted.y.notna();delta=adjusted.loc[valid,'y']-original.loc[valid,'y']
            records.append({'table':key,'original_train_cells':len(original),'retained_after_hypothetical_dedup':int(valid.sum()),
                'changed_targets':int((delta.abs()>1e-7).sum()),'median_abs_y_change':delta.abs().median(),
                'p95_abs_y_change':delta.abs().quantile(.95),'max_abs_y_change':delta.abs().max(),
                'weighted_rmse_y_change':np.sqrt(np.average(delta**2,weights=original.loc[valid,'weight']))})
    f.save(pd.DataFrame(records),'duplicate_target_sensitivity.csv')
    f.save({'train_eligible_trades':len(d),'hypothetical_removed_trades':len(d)-len(dedup),
        'original_data_changed':False,'test_used':False,'meaning':'same-condition trades may be different real units; sensitivity only'},'duplicate_protocol.json')
    print('Duplicate sensitivity complete',flush=True)

if __name__=='__main__':main()
