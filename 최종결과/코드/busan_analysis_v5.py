"""
시나리오 C — 부산 분석 v5 (학력향상지원 실제 예산 데이터 사용)
- 정책 변수: 시도별 학력향상지원 (2013-2024, 결산+예산 통합)
- 종속변수: proxy_risk_score (v4 위험도 합성지수)
- 세종 제외
- 인과 해석 X, 동행성/상관 분석
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
from scipy.optimize import minimize
from linearmodels.panel import PanelOLS
import warnings
warnings.filterwarnings('ignore')

matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

OUT = Path(r'C:/ai_contest2026/out')

# ── 1. 학력향상지원 데이터 통합 ───────────────────────────────
def load_support(path):
    d = pd.read_csv(path, encoding='cp949')
    d.columns = [c.strip() for c in d.columns]
    d['지역구분'] = d['지역구분'].astype(str).str.strip()
    d['항목구분'] = d['항목구분'].astype(str).str.strip()
    d['금액(원)'] = pd.to_numeric(d['금액(원)'], errors='coerce')
    return d

a = load_support(r'C:/ai_contest2026/data/학력향상지원.csv')          # 2013-2021 결산
b = load_support(r'C:/ai_contest2026/data/학력향상지원 (1).csv')       # 2022-2026 예산
sup = pd.concat([a, b], ignore_index=True)
sup = sup.rename(columns={'회계연도': '연도', '지역구분': '시도', '금액(원)': '금액'})

# 학력향상지원 / 세출(결산 or 예산) 분리
def pick(item):
    return sup[sup['항목구분'] == item].pivot_table(
        index=['연도', '시도'], values='금액', aggfunc='first'
    ).reset_index().rename(columns={'금액': item})

hak = pick('학력향상지원')                                 # 17시도 × 2013-2026
sechul_a = pick('세출결산액')                               # 2013-2021
sechul_b = pick('세출예산액')                               # 2022-2026
sechul = pd.concat([sechul_a.rename(columns={'세출결산액': '세출액'}),
                    sechul_b.rename(columns={'세출예산액': '세출액'})],
                   ignore_index=True)

panel = hak.merge(sechul, on=['연도', '시도'], how='left')
panel['학력향상_세출비중'] = panel['학력향상지원'] / panel['세출액'] * 100  # %
panel['학력향상_억원'] = panel['학력향상지원'] / 1e8
panel = panel.sort_values(['시도', '연도']).reset_index(drop=True)

print(f'학력향상지원 패널: {panel.shape[0]} obs ({panel["시도"].nunique()}시도 × {panel["연도"].nunique()}년)')
print(f'연도범위: {panel["연도"].min()}~{panel["연도"].max()}')

# ── 2. v4 dataset과 병합 ──────────────────────────────────────
df = pd.read_csv(r'C:/ai_contest2026/통합_proxy_dataset_v4.csv', encoding='utf-8-sig')
df = df[df['시도'] != '세종'].copy()
df = df.merge(panel[['연도', '시도', '학력향상_억원', '학력향상_세출비중', '세출액']],
              on=['연도', '시도'], how='left')
df['학력향상_학생당_천원'] = (df['학력향상_억원'] * 1e8) / df['총학생수'] / 1000

# 분석은 v4 데이터셋 범위 (2012-2024)와 학력향상지원 가용 연도(2013-2024)의 교집합
df_ana = df[df['연도'].between(2013, 2024)].copy()
print(f'분석 데이터: {df_ana.shape[0]} obs (세종 제외, 2013-2024)')

# 부산 시계열
busan = df_ana[df_ana['시도'] == '부산'].sort_values('연도')
print('\n[부산 학력향상지원 시계열]')
print(busan[['연도', '학력향상_억원', '학력향상_세출비중', '학력향상_학생당_천원',
             'proxy_risk_score']].round(2).to_string(index=False))

# ─────────────────────────────────────────────────────────
# 분석 A: 패널 회귀 (17시도 × 12년 = 192 obs)
# ─────────────────────────────────────────────────────────
print('\n' + '=' * 60)
print('  [A] 패널회귀 — 전 시도, 학력향상_학생당_천원 ↔ 위험도')
print('=' * 60)
ds = df_ana.dropna(subset=['학력향상_학생당_천원']).copy()
ds = ds.set_index(['시도', '연도'])

# 모델 A1: Two-way FE
exog_A1 = ds[['학력향상_학생당_천원']].astype(float)
m_A1 = PanelOLS(dependent=ds['proxy_risk_score'].astype(float),
                exog=exog_A1, entity_effects=True, time_effects=True)
res_A1 = m_A1.fit(cov_type='clustered', cluster_entity=True)
print('\n[A1] 학력향상지원 단독 (시도FE+연도FE)')
print(res_A1.summary.tables[1])

# 모델 A2: + 통제변수
controls = ['학업중단률', '다문화학생_비율', '학급당_학생수', '교원1인당_학생수']
exog_A2 = ds[['학력향상_학생당_천원'] + controls].astype(float)
m_A2 = PanelOLS(dependent=ds['proxy_risk_score'].astype(float),
                exog=exog_A2, entity_effects=True, time_effects=True)
res_A2 = m_A2.fit(cov_type='clustered', cluster_entity=True)
print('\n[A2] 통제변수 포함 (시도FE+연도FE)')
print(res_A2.summary.tables[1])

# 모델 A3: 세출비중 (정책 강도의 다른 측정)
exog_A3 = ds[['학력향상_세출비중'] + controls].astype(float)
m_A3 = PanelOLS(dependent=ds['proxy_risk_score'].astype(float),
                exog=exog_A3, entity_effects=True, time_effects=True)
res_A3 = m_A3.fit(cov_type='clustered', cluster_entity=True)
print('\n[A3] 세출비중 사용')
print(res_A3.summary.tables[1])

beta_A2 = res_A2.params['학력향상_학생당_천원']
pv_A2 = res_A2.pvalues['학력향상_학생당_천원']
beta_A3 = res_A3.params['학력향상_세출비중']
pv_A3 = res_A3.pvalues['학력향상_세출비중']

# ─────────────────────────────────────────────────────────
# 분석 B: 부산 Synthetic Control (위험도 점수)
# ─────────────────────────────────────────────────────────
print('\n' + '=' * 60)
print('  [B] Synthetic Control — 부산')
print('=' * 60)
PRE  = list(range(2013, 2020))
POST = list(range(2020, 2025))
TREAT = '부산'
donors = sorted([s for s in df_ana['시도'].unique() if s != TREAT])
pivot = df_ana.pivot(index='연도', columns='시도', values='proxy_risk_score')
y_pre = pivot.loc[PRE, TREAT].values
X_pre = pivot.loc[PRE, donors].values

covars = ['학업중단률', '다문화학생_비율', '학급당_학생수', 'GRDP_1인당',
          '사교육_참여율', '교원1인당_학생수']
cov_mean = df_ana[df_ana['연도'].isin(PRE)].groupby('시도')[covars].mean()
v_t = cov_mean.loc[TREAT].values
V_d = cov_mean.loc[donors].values.T
V_w = 1.0 / cov_mean.std().replace(0, 1).values

def sc_solve(yp, Xp, vd, Vd_):
    J = Xp.shape[1]
    def loss(w):
        return np.sum((yp - Xp @ w)**2) + 0.5*np.sum(((vd - Vd_ @ w)*V_w)**2)
    r = minimize(loss, np.ones(J)/J, method='SLSQP',
                 bounds=[(0,1)]*J,
                 constraints={'type':'eq','fun': lambda w: w.sum()-1},
                 options={'ftol':1e-10, 'maxiter':1000})
    w = r.x
    w[w<1e-4] = 0
    return w / w.sum()

w_hat = sc_solve(y_pre, X_pre, v_t, V_d)
years_all = pivot.index.tolist()
actual = pivot[TREAT].values
synth  = pivot.loc[:, donors].values @ w_hat
gap = actual - synth

w_df = pd.DataFrame({'시도': donors, '가중치': np.round(w_hat, 3)})
w_df = w_df[w_df['가중치'] > 0].sort_values('가중치', ascending=False)
print('\n[SC 가중치 >0]')
print(w_df.to_string(index=False))
print('\n[실제 vs 합성]')
sc_table = pd.DataFrame({'연도': years_all,
                         '실제부산': np.round(actual,2),
                         '합성부산': np.round(synth,2),
                         '격차': np.round(gap,2)})
print(sc_table.to_string(index=False))

post_idx = np.isin(years_all, POST)
pre_idx  = np.isin(years_all, PRE)
att = gap[post_idx].mean()
pre_rmse = np.sqrt((gap[pre_idx]**2).mean())
post_rmse = np.sqrt((gap[post_idx]**2).mean())
print(f'\n>>> 2020-2024 평균 부산-합성 격차: {att:+.2f}점')
print(f'    Pre-RMSE: {pre_rmse:.2f}, Post-RMSE: {post_rmse:.2f}, 비율: {post_rmse/max(pre_rmse,1e-6):.2f}')

# Placebo
placebo = {TREAT: gap}
all_sd = [TREAT] + donors
for d in donors:
    od = [s for s in all_sd if s != d]
    yp = pivot.loc[PRE, d].values
    Xp = pivot.loc[PRE, od].values
    vd = cov_mean.loc[d].values
    Vd_ = cov_mean.loc[od].values.T
    wd = sc_solve(yp, Xp, vd, Vd_)
    placebo[d] = pivot[d].values - pivot.loc[:, od].values @ wd

def ratio(g):
    pre_ = np.sqrt((g[pre_idx]**2).mean())
    post_ = np.sqrt((g[post_idx]**2).mean())
    return post_ / max(pre_, 1e-6)
ratios = {k: ratio(v) for k, v in placebo.items()}
rank_list = sorted(ratios.items(), key=lambda x: -x[1])
busan_rank = [r[0] for r in rank_list].index(TREAT) + 1
print(f'\n[Placebo] 부산 순위 {busan_rank}/{len(ratios)}, p≈{busan_rank/len(ratios):.2f}')

# ─────────────────────────────────────────────────────────
# 분석 C: 부산 지원강도 시나리오 (회귀계수 기반 외삽)
# ─────────────────────────────────────────────────────────
print('\n' + '=' * 60)
print('  [C] 부산 2024 정책강도 외삽 시나리오')
print('=' * 60)
b24 = df_ana[(df_ana['시도']=='부산') & (df_ana['연도']==2024)].iloc[0]
cur_per = b24['학력향상_학생당_천원']
cur_pct = b24['학력향상_세출비중']
cur_y = b24['proxy_risk_score']
print(f'\n[부산 2024] 학력향상지원 {b24["학력향상_억원"]:.1f}억원 '
      f'(학생당 {cur_per:.2f}천원, 세출의 {cur_pct:.3f}%)')
print(f'           위험도 점수 {cur_y:.2f}')
print('\n[A2 계수 기반 외삽 — 인과 해석 금지]')
for mult in [1.0, 1.5, 2.0, 3.0]:
    delta = beta_A2 * (cur_per * mult - cur_per)
    print(f'  지원 ×{mult:.1f} (학생당 {cur_per*mult:.2f}천원) → 위험도 {cur_y+delta:.2f} (Δ {delta:+.2f})')

# 2026 예산 정보 활용 (이미 데이터 있음)
b26 = panel[(panel['시도']=='부산') & (panel['연도']==2026)]
if len(b26):
    b26 = b26.iloc[0]
    student_2024 = b24['총학생수']
    per_2026 = (b26['학력향상_억원'] * 1e8) / student_2024 / 1000  # 학생수는 2024로 근사
    delta_2026 = beta_A2 * (per_2026 - cur_per)
    print(f'\n[참고: 2026 예산 외삽]')
    print(f'  부산 2026 학력향상지원 예산: {b26["학력향상_억원"]:.1f}억원')
    print(f'  학생당(2024기준) {per_2026:.2f}천원 → 위험도 {cur_y+delta_2026:.2f} (Δ {delta_2026:+.2f})')

# ─────────────────────────────────────────────────────────
# 시각화
# ─────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# (1) 부산 vs 타시도 평균 — 학력향상지원 비교
ax = axes[0, 0]
agg_amt = df_ana.groupby(['연도', df_ana['시도'].eq(TREAT)])['학력향상_학생당_천원'].mean().unstack()
agg_amt.columns = ['타시도평균', '부산']
ax.plot(agg_amt.index, agg_amt['부산'], 'o-', label='부산', color='steelblue', linewidth=2)
ax.plot(agg_amt.index, agg_amt['타시도평균'], 's--', label='타시도 평균', color='gray')
ax.set_title('학력향상지원: 부산 vs 타시도 평균 (학생당 천원)')
ax.set_xlabel('연도'); ax.set_ylabel('학생당 지원액 (천원)')
ax.legend(); ax.grid(alpha=0.3)

# (2) Synthetic Control
ax = axes[0, 1]
ax.plot(years_all, actual, 'o-', label='실제 부산', color='steelblue', linewidth=2)
ax.plot(years_all, synth, 's--', label='합성 부산', color='tomato', linewidth=2)
ax.axvline(2019.5, color='gray', linestyle=':', label='2020 분기점')
ax.set_title(f'Synthetic Control 위험도 (Placebo p≈{busan_rank/len(ratios):.2f})')
ax.set_xlabel('연도'); ax.set_ylabel('proxy_risk_score')
ax.legend(); ax.grid(alpha=0.3)

# (3) 부산 지원액 vs 위험도 (dual axis)
ax = axes[1, 0]
ax2 = ax.twinx()
ax.bar(busan['연도'], busan['학력향상_억원'], color='lightblue', alpha=0.6, label='학력향상지원(억원)')
ax2.plot(busan['연도'], busan['proxy_risk_score'], 'o-', color='crimson',
         linewidth=2, label='위험도 점수')
ax.set_title('부산: 학력향상지원 vs 위험도 (동행성)')
ax.set_xlabel('연도'); ax.set_ylabel('학력향상지원 (억원)')
ax2.set_ylabel('proxy_risk_score', color='crimson')
ax.legend(loc='upper left'); ax2.legend(loc='upper right')
ax.grid(alpha=0.3)

# (4) 시나리오 곡선
ax = axes[1, 1]
mults = np.linspace(0.5, 3.0, 11)
ys = [cur_y + beta_A2*(cur_per*m - cur_per) for m in mults]
ax.plot(mults, ys, 'o-', color='seagreen', linewidth=2)
ax.axhline(cur_y, color='gray', linestyle=':', label='2024 실제')
ax.set_title(f'부산 2024 학력향상지원 강도 시나리오\n(β={beta_A2:+.4f}, p={pv_A2:.3f})')
ax.set_xlabel('지원액 배수 (×현재)'); ax.set_ylabel('외삽 위험도 점수')
ax.legend(); ax.grid(alpha=0.3)

plt.tight_layout()
figp = OUT / 'busan_v5_analysis.png'
plt.savefig(figp, dpi=130, bbox_inches='tight')
print(f'\n그래프 저장: {figp}')

# ── 결과 저장 ──
sc_table.to_csv(OUT / 'busan_sc_v5.csv', index=False, encoding='utf-8-sig')
df_ana.to_csv(r'C:/ai_contest2026/통합_proxy_dataset_v5.csv',
              index=False, encoding='utf-8-sig')
print('데이터셋 저장: 통합_proxy_dataset_v5.csv')

summary = {
    '데이터': f'{df_ana["시도"].nunique()}시도 × {df_ana["연도"].nunique()}년 = {len(df_ana)} obs (세종 제외, 2013-2024)',
    '정책변수': '학력향상지원 (시도별 본예산/결산 raw)',
    'A2_학생당지원_계수': round(float(beta_A2), 5),
    'A2_p값': round(float(pv_A2), 4),
    'A3_세출비중_계수': round(float(beta_A3), 4),
    'A3_p값': round(float(pv_A3), 4),
    'SC_부산_2020_2024_평균격차': round(float(att), 3),
    'SC_Pre_RMSE': round(float(pre_rmse), 3),
    'SC_Post_RMSE': round(float(post_rmse), 3),
    'SC_가중치_상위': w_df.head(5).to_dict(orient='records'),
    'Placebo_순위': f'{busan_rank}/{len(ratios)}',
    'Placebo_p값': round(busan_rank/len(ratios), 3),
    '부산_2024': {
        '학력향상지원_억원': round(float(b24['학력향상_억원']), 2),
        '학생당_천원': round(float(cur_per), 2),
        '세출비중_pct': round(float(cur_pct), 4),
        'proxy_risk_score': round(float(cur_y), 2),
    },
    '주의': '인과해석 금지. 모든 회귀계수는 동시상관. 학력향상지원은 2022+예산, 2021-결산으로 일관성 한계',
}
with open(OUT / 'busan_v5_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f'요약 저장: {OUT / "busan_v5_summary.json"}')
