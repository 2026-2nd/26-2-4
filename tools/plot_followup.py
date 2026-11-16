"""Two compact figures for the stage reports (train-only exploratory results)."""
import pathlib
import sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
ROOT=pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/model'))
import followup as f

def main():
    fonts={x.name for x in font_manager.fontManager.ttflist}
    plt.rcParams['font.family']=next((n for n in ['Malgun Gothic','NanumGothic','Noto Sans CJK KR'] if n in fonts),'DejaVu Sans')
    plt.rcParams['axes.unicode_minus']=False
    plt.rcParams['font.size']=10
    out=f.OUT/'figures';out.mkdir(exist_ok=True)
    keys=['up1_window','corr_window','up2_window','down_window','rec_window','up3_window']
    labels=['상승기①','조정기','상승기②','하락기','회복기','상승기③']
    scores=pd.read_csv(f.OUT/'cv_comparison.csv');choices=pd.read_csv(f.OUT/'cv_choices.csv')
    fig,ax=plt.subplots(figsize=(9,4.8));xx=np.arange(6)
    base=scores[(scores.model=='catboost')&(scores.variant=='baseline')].set_index('table').loc[keys,'RMSE']
    chosen=choices[choices.model=='catboost'].set_index('table').loc[keys,'RMSE']
    ax.bar(xx-.18,base,.36,label='기존 처리 재비교',color='#a9b8c7')
    ax.bar(xx+.18,chosen,.36,label='후속 선택 사양',color='#34658c')
    ax.set_xticks(xx,labels);ax.set_ylabel('학습 내부 가중 RMSE');ax.legend(frameon=False)
    ax.set_title('EDA 결과 반영 전후 사양 비교 — CatBoost 창 방식',pad=18)
    ax.spines[['top','right']].set_visible(False)
    fig.text(.5,.02,'같은 고정 설정으로 재비교한 탐색적 CV입니다. 독립 시험 성능이 아닙니다.',ha='center',fontsize=9)
    fig.tight_layout(rect=[0,.06,1,1]);fig.savefig(out/'cv_comparison.png',dpi=160);plt.close(fig)
    imp=pd.read_csv(f.OUT/'shap_importance.csv')
    fig,axes=plt.subplots(2,3,figsize=(14,8))
    for ax,key,label in zip(axes.flat,keys,labels):
        top=imp[imp.table.eq(key)].nlargest(6,'mean_abs_shap').iloc[::-1]
        ax.barh(top.feature,top.mean_abs_shap,color='#34658c');ax.set_title(label)
        ax.tick_params(axis='y',labelsize=9);ax.spines[['top','right']].set_visible(False)
        ax.set_xlabel('가중 평균 |SHAP|')
    fig.suptitle('모델 해석 — 국면별 주요 특성',fontsize=17)
    fig.text(.5,.02,'학습 표본에서 계산한 탐색적 중요도입니다. 효과의 방향이나 인과관계를 뜻하지 않습니다.',ha='center',fontsize=10)
    fig.tight_layout(rect=[0,.05,1,.95]);fig.savefig(out/'shap_importance.png',dpi=160);plt.close(fig)
    print('Figures generated')

if __name__=='__main__':main()
