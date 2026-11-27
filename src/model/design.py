"""V3 feature construction and fold-fitted preprocessing; no V2 experiment settings."""
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
import common as v1
SPARSE = ['난방방식', '복도유형', '시공사_상위10']
LOGS = ['세대수', '최근접_역_거리', '최근접_초등학교_거리']
CONTROLS = ['토지거래허가구역_a', '가격대', '직전국면_y', '회전율']

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
