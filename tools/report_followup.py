"""Readable stage reports generated from completed follow-up outputs."""
import pathlib
import sys
import json
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/model'))
import followup as f
LABELS={'baseline':'기존 처리 재비교','quality':'주차 0 결측·승인월 보완','parking_cap':'품질 처리 + 주차 상한 3',
        'without_sparse':'품질 처리 + 난방·복도·시공사 제외','log_numeric':'품질 처리 + 규모·거리 로그 변환',
        'extended':'품질 처리 + 통제변수 4개','equal_weight':'품질 처리 + 학습 가중치 동일'}
REG={'up1':'상승기①','corr':'조정기','up2':'상승기②','down':'하락기','rec':'회복기','up3':'상승기③'}
def main():
    scores=pd.read_csv(f.OUT/'cv_comparison.csv');choices=pd.read_csv(f.OUT/'cv_choices.csv')
    quality=pd.read_csv(f.OUT/'quality_audit.csv');dup=pd.read_csv(f.OUT/'duplicate_target_sensitivity.csv')
    best=choices.loc[choices.groupby('table').RMSE.idxmin()]
    cat_wins=int(best.model.eq('catboost').sum())
    lines=['# EDA 결과 반영 후 — 결측치 처리와 특성 공학 비교','',
        '2026-11-16 · v2 탐색 실험. 기존 v1 결과와 시험 동네는 변경하지 않았다.', '',
        f'**모델 판단:** 두 모델을 비교한 {len(best)}개 표 중 CatBoost의 선택 사양이 {cat_wins}개에서 더 낮은 CV 오차를 보였다. '+
        ('기존 주모델 CatBoost를 유지하고 Ridge는 효과 방향을 대조하는 보조 모델로 사용하는 판단을 뒷받침한다.' if cat_wins==len(best) else '국면별 비교표를 보고 모델별 차이를 판단해야 한다.')+
        ' 수치형·범주형 특성과 결측을 함께 다룰 수 있다는 장점도 있다. 다만 이번 결과는 학습 내부 탐색이며 새 시험 성능을 입증하지 않는다.', '',
        '## 무엇을 비교했나','',
        '학습 동네만 사용해 12개 국면×방식에서 아래 7개 사양과 Ridge·CatBoost를 비교했다. 총 168개 비교, 각 5-fold로 840회 적합했다.',
        'v1에서 선택한 모델 설정·CatBoost 최종 반복 수를 고정해 모든 사양에 동일하게 적용했다. 랜덤포레스트의 v1 결과는 보존했으며 이번 사양 탐색에서는 재학습하지 않았다.',
        '기존 처리도 동일한 고정 반복 수로 다시 비교했으므로 v1의 fold별 조기 종료 CV 점수와 직접 같지 않다.', '',
        '| 사양 | 처리 |','|---|---|']
    lines += [f'| {k} | {v} |' for k,v in LABELS.items()]
    lines += ['', '품질 처리에서 주차 0은 오류 확정이 아니라 결측 가정의 민감도다. 승인일의 일자가 00이면 유효한 연·월을 살린다. 대상은 기존 v1 학습 셀로 고정했다.',
        '로그 변환은 세대수·역 거리·초등학교 거리에 log1p를 적용한다. 확장 변수는 토지거래허가구역·과거 가격대·직전 국면 y·회전율이다.',
        '동일 가중치 사양은 학습 가중치만 바꾸고 평가에는 기존 가중치를 사용한다. 민감도 전용이며 선택 대상에서는 제외했다.', '',
        '## 국면별 학습 내부 결과','', '![CatBoost 창 방식의 학습 내부 비교](figures/cv_comparison.png)', '',
        '아래는 주 분석인 창 방식이다. 오차는 가중 RMSE이며 작을수록 좋다. 각 모델에서 사양을 따로 선택했다.', '',
        '| 국면 | 모델 | 기존 처리 RMSE | 선택 사양 | 선택 RMSE |','|---|---|---:|---|---:|']
    for _,r in choices[choices.table.str.endswith('_window')].sort_values(['table','model']).iterrows():
        baseline=scores[(scores.table==r.table)&(scores.model==r.model)&(scores.variant=='baseline')].iloc[0].RMSE
        lines.append(f'| {REG[r.table.split("_")[0]]} | {r.model} | {baseline:.3f} | {LABELS[r.variant]} | {r.RMSE:.3f} |')
    counts=choices.groupby(['model','variant']).size()
    family=choices.loc[choices.groupby('table').RMSE.idxmin(),'model'].value_counts()
    lines += ['', '선택 횟수(창·기울기 12개 표): '+ '; '.join(f'{m} {LABELS[v]} {n}개' for (m,v),n in counts.items())+'.', '',
        '후속 비교의 두 모델 중 표별 최저 CV 오차: '+', '.join(f'{m} {n}개' for m,n in family.items())+'. 랜덤포레스트를 포함한 새 최종 모델 선정을 뜻하지는 않는다.', '',
        '**이 숫자는 독립 시험 성능이 아니다.** EDA가 전체 자료를 보았고, v1 설정과 동일한 학습 fold를 재사용했다. 사양 선택까지 한 CV 최저값은 낙관적일 수 있다. 새 효과·성능의 확증에는 새 외부 검증이 필요하다.', '',
        '## 데이터 품질과 표본 편향','',
        f'- 원자료 주차 0값 4,550건, 3 초과 3,869건, 승인일 형식 오류 17건을 재확인했다. 월 보완은 학습 셀×표 {int(quality.approval_repaired_cells.sum())}행에 영향을 줬다.',
        '- 결측은 모델별로 처리한다. CatBoost 숫자 NaN·범주 결측 토큰, Ridge는 학습 fold 중앙값·원핫·표준화. 모든 사양에서 사용한 특성의 결측 표시를 유지한다.',
        '- 난방·복도·시공사 결측은 K-apt 연결 및 소규모 단지와 겹친다. 이 변수군 제외 실험과 결측/관측 집단별 OOF 오차를 별도로 저장했다.',
        '- 국면별 적격 학습 거래와 남은 학습 셀의 면적·세대수·소형 비중을 비교했다. 서로 집계 단위가 다르며, 표본 구성 진단용이지 선택 편향 보정은 아니다.',
        f'- 동일 조건 거래를 가상으로 중복 제거했을 때 목표값 변화의 가중 RMS는 {dup.weighted_rmse_y_change.min():.3f}~{dup.weighted_rmse_y_change.max():.3f}였다. 일부 셀은 최대 {dup.max_abs_y_change.max():.2f}까지 변해 개별 셀 민감도가 남는다. 실제 거래인지 구분할 수 없어 원본은 삭제하지 않았다.', '',
        '## 파일과 재현','',
        '- [전체 비교](cv_comparison.csv), [모델별 선택](cv_choices.csv), [집단별 오차](group_errors.csv)',
        '- [품질 점검](quality_audit.csv), [표본 구성](cohort_composition.csv), [중복 가정 민감도](duplicate_target_sensitivity.csv)',
        '- [모델 해석 — 국면별 주요 특성과 SHAP](interpretation.md)',
        '- 설정: `config/followup.yaml`. 실행 순서: 아래 명령을 저장소 루트에서 실행한다.', '',
        '```bash','python src/model/followup.py audit','python src/model/followup.py compare',
        'python tools/audit_duplicate_sensitivity.py','python src/model/interpret_followup.py',
        'python tools/verify_followup.py','python tools/plot_followup.py','python tools/report_followup.py','```','',
        '학습 모델·행별 OOF·재시작 캐시는 Git 제외 `results/followup_v2/`에 저장된다. 입력·코드 해시가 달라지면 기존 캐시 재사용을 거부한다.', '',
        '## 남은 검토','',
        '주차 출처 확인, 창 폭 변경, 2020년 이후 표본, 좌표 출처별 분석, 다음 국면 예측과 새로운 외부 검증은 아직 하지 않았다. 이번 작업은 EDA 지적 사항에 대한 학습 내부 비교와 탐색적 해석이다.']
    (f.OUT/'README.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    imp=pd.read_csv(f.OUT/'shap_importance.csv');types=pd.read_csv(f.OUT/'type_candidates.csv')
    lines=['# 모델 해석 — 국면별 주요 특성과 SHAP','',
        'EDA 후속 비교에서 모델별로 선택한 사양을 학습 동네 전체에 적합하고 해석했다. 기존 v1 시험은 다시 열지 않았다. **아래는 탐색 결과이며 최종 인과효과나 확정 유형이 아니다.**', '',
        '목표값은 서울 전체 대비 상대 로그가격 변화다. 아래 유형은 아파트를 분류한 결과가 아니라, 수치 특성이 커질 때의 상대 변화 방향을 묶은 후보다. 하락기의 +는 서울 대비 덜 하락하는 방향을 뜻하며 절대가격 상승을 뜻하지 않는다.', '',
        '## 해석 방법','',
        '- Ridge: 학습 단지 단위 1,000회 부트스트랩. 선택된 사양·규제강도·기준 전처리를 고정한 조건부 구간이다. 모델/특성 선택의 불확실성은 포함하지 않는다.',
        '- CatBoost: 표마다 학습 셀 최대 1,000개를 고정 시드로 추출해 내장 SHAP를 계산했다. SHAP 합과 예측값의 일치도 확인했다.',
        '- 중요도는 가중 평균 |SHAP|다. 평균 SHAP 자체의 부호로 방향을 정하지 않는다.',
        '- 수치 특성 방향은 특성값과 SHAP의 Spearman 부호로 요약한다. Ridge 구간이 0을 제외하고 방향도 같을 때만 +/− 후보로 표시한다. 전반적 방향은 비선형 관계를 숨길 수 있어 의존도 표도 함께 봐야 한다.',
        '- 범주형은 중요도만 제시한다. 결측 표시와 자치구를 방어형·공격형 특성으로 판정하지 않는다. 제외된 특성은 NA이며, 0은 효과 없음의 증명이 아니라 일치한 증거 부족이다.',
        '- Ridge와 CatBoost가 서로 다른 사양을 선택할 수 있어 부호 비교도 사양에 조건부다. 규모·거리 로그 변환 사양의 Ridge 계수는 변환된 값의 1표준편차 기준이다.', '',
        '## 창 방식에서 중요한 특성','', '![국면별 주요 특성](figures/shap_importance.png)', '',
        '| 국면 | 평균 절대 SHAP 상위 5개 |','|---|---|']
    for key,g in imp[imp.table.str.endswith('_window')].groupby('table'):
        top=g.nlargest(5,'mean_abs_shap')
        lines.append(f'| {REG[key.split("_")[0]]} | '+', '.join(f'{r.feature} ({r.mean_abs_shap:.2f})' for _,r in top.iterrows())+' |')
    lines+=['', '## 특성 유형 후보','',
        '상승기 3개 중 2개 이상 방향이 같을 때 상승 방향으로 묶었다. 하락기만 적용한 경우와 하락기·조정기 방향이 모두 같은 경우를 나누어 저장했다. 회복기는 방향표에는 있으나 유형 판정에는 쓰지 않는다.', '',
        '| 특성 | 창 방식 후보 | 기울기 방식 후보 |','|---|---|---|']
    pivot=types.pivot(index='feature',columns='method',values='without_corr')
    for feature,row in pivot.iterrows():lines.append(f'| {feature} | {row.get("window", "NA")} | {row.get("slope", "NA")} |')
    lines+=['', '유형이 방식·조정기 포함 여부에 따라 달라지면 안정적인 유형으로 확정하지 않는다. 현재값 가정·변수 상관·거래 선택 편향도 남는다.', '',
        '## 상세 자료','',
        '- [Ridge 계수 구간](ridge_intervals.csv)',
        '- [SHAP 중요도와 전반적 방향](shap_importance.csv)',
        '- [SHAP 분위구간별 의존도](shap_dependence.csv)',
        '- [국면별 수치 특성 방향](numeric_effects.csv)',
        '- [조정기 포함·제외 유형 후보](type_candidates.csv)',
        '- [해석 프로토콜과 한계](interpretation_protocol.json)']
    (f.OUT/'interpretation.md').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
    verified=json.loads((f.OUT/'verification.json').read_text(encoding='utf-8'))
    if verified['oof_scores_recomputed']!=len(scores) or len(scores)!=168:
        raise ValueError('Full validated comparison required before marking completion')
    f.save({'status':'complete_train_only_followup','completed_comparisons':len(scores),
            'planned_comparisons':168,'completed_fits':len(scores)*5,
            'comparisons_by_table':scores.groupby('table').size().to_dict(),
            'all_completed_oof_scores_recomputed':True,'frozen_v1_inputs_unchanged':True,
            'test_evaluated':False,'interpretation_executed':True,
            'interpretation_status':'exploratory_not_causal_or_independent_validation',
            'verification':'verification.json','cache_location':'results/followup_v2 (local only, gitignored)'},'status.json')
    print('Reports generated')
if __name__=='__main__':main()
