"""
v7 보강 분석
- 목적 ② : 서울/경기/부산 각각 SC + DiD + 패널회귀 일괄 실행, 3개 사례 비교
- 목적 ③ : Lag(t-1, t-2) + 누적 5년 지원 + 부산학력개발원(2022) Event Study
            + 서울 β를 부산에 이식한 counterfactual 시뮬레이션
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

# ── 데이터 ────────────────────────────────────────────────────
df = pd.read_csv(r'C:/ai_contest2026/통합_proxy_dataset_v6.csv', encoding='utf-8-sig')
df = df[df['시도'] != '세종'].copy().sort_values(['시도', '연도']).reset_index(drop=True)
df_ana = df[df['연도'].between(2013, 2024)].copy()

print(f'분석 데이터: {df_ana.shape[0]} obs (16시도 × 2013-2024)')

PRE  = list(range(2013, 2020))
POST = list(range(2020, 2025))

# ─────────────────────────────────────────────────────────────
# [목적 ②] 서울·경기·부산 각각 SC + DiD + 패널회귀
# ─────────────────────────────────────────────────────────────
covars = ['학업중단률', '다문화학생_비율', '학급당_학생수', 'GRDP_1인당',
          '사교육_참여율', '교원1인당_학생수']
cov_mean = df_ana[df_ana['연도'].isin(PRE)].groupby('시도')[covars].mean()
V_w = 1.0 / cov_mean.std().replace(0, 1).values

def sc_solve(yp, Xp, vt, Vd):
    J = Xp.shape[1]
    def loss(w):
        return np.sum((yp - Xp@w)**2) + 0.5*np.sum(((vt - Vd@w)*V_w)**2)
    r = minimize(loss, np.ones(J)/J, method='SLSQP',
                 bounds=[(0,1)]*J,
                 constraints={'type':'eq','fun': lambda w: w.sum()-1},
                 options={'ftol':1e-10, 'maxiter':1000})
    w = r.x
    w[w<1e-4] = 0
    return w / w.sum()

def analyze_city(target, df_ana):
    donors = sorted([s for s in df_ana['시도'].unique() if s != target])
    pivot = df_ana.pivot(index='연도', columns='시도', values='proxy_risk_score')
    y_pre = pivot.loc[PRE, target].values
    X_pre = pivot.loc[PRE, donors].values
    v_t = cov_mean.loc[target].values
    V_d = cov_mean.loc[donors].values.T
    w_hat = sc_solve(y_pre, X_pre, v_t, V_d)

    years_all = pivot.index.tolist()
    actual = pivot[target].values
    synth = pivot.loc[:, donors].values @ w_hat
    gap = actual - synth
    post_idx = np.isin(years_all, POST)
    pre_idx = np.isin(years_all, PRE)
    att = gap[post_idx].mean()
    pre_rmse = np.sqrt((gap[pre_idx]**2).mean())
    post_rmse = np.sqrt((gap[post_idx]**2).mean())

    # placebo
    all_sd = [target] + donors
    placebo = {target: gap}
    for d in donors:
        od = [s for s in all_sd if s != d]
        yp = pivot.loc[PRE, d].values
        Xp = pivot.loc[PRE, od].values
        vd = cov_mean.loc[d].values
        Vd_ = cov_mean.loc[od].values.T
        wd = sc_solve(yp, Xp, vd, Vd_)
        placebo[d] = pivot[d].values - pivot.loc[:, od].values @ wd
    def ratio(g):
        a = np.sqrt((g[pre_idx]**2).mean())
        b = np.sqrt((g[post_idx]**2).mean())
        return b / max(a, 1e-6)
    ratios = {k: ratio(v) for k, v in placebo.items()}
    rank = sorted(ratios.items(), key=lambda x: -x[1])
    pos = [r[0] for r in rank].index(target) + 1

    # DiD
    dpanel = df_ana.copy()
    dpanel['treated'] = (dpanel['시도'] == target).astype(int)
    dpanel['post'] = (dpanel['연도'] >= 2020).astype(int)
    dpanel['did'] = dpanel['treated'] * dpanel['post']
    dpanel = dpanel.set_index(['시도', '연도'])
    exog = dpanel[['did', '학업중단률', '다문화학생_비율', '학급당_학생수', '교원1인당_학생수']].astype(float)
    m = PanelOLS(dpanel['proxy_risk_score'].astype(float),
                 exog=exog, entity_effects=True, time_effects=True)
    rd = m.fit(cov_type='clustered', cluster_entity=True)

    return {
        'target': target,
        'sc_weights': dict(zip(donors, w_hat)),
        'sc_actual': actual, 'sc_synth': synth, 'years': years_all,
        'sc_att': att, 'sc_pre_rmse': pre_rmse, 'sc_post_rmse': post_rmse,
        'placebo_rank': pos, 'placebo_n': len(ratios),
        'did_coef': rd.params['did'], 'did_pval': rd.pvalues['did'],
        'did_se': rd.std_errors['did'],
    }

cases = {}
for tgt in ['서울', '경기', '부산']:
    print('\n' + '='*60)
    print(f'  [{tgt}] SC + DiD')
    print('='*60)
    cases[tgt] = analyze_city(tgt, df_ana)
    r = cases[tgt]
    print(f'  SC 합성 가중치 (>0.05):')
    top = sorted({k:v for k,v in r['sc_weights'].items() if v>0.05}.items(),
                 key=lambda x:-x[1])
    for s, w in top:
        print(f'    {s}: {w:.3f}')
    print(f'  SC ATT (2020-2024): {r["sc_att"]:+.2f}점')
    print(f'  Pre-RMSE: {r["sc_pre_rmse"]:.2f}, Post-RMSE: {r["sc_post_rmse"]:.2f}')
    print(f'  Placebo 순위: {r["placebo_rank"]}/{r["placebo_n"]}, p≈{r["placebo_rank"]/r["placebo_n"]:.2f}')
    print(f'  DiD 계수: {r["did_coef"]:+.3f} (SE={r["did_se"]:.3f}, p={r["did_pval"]:.3f})')

# 3개 사례 비교표
print('\n' + '='*60)
print('  [3사례 비교]')
print('='*60)
cmp = pd.DataFrame({
    '시도': list(cases.keys()),
    'SC_ATT': [cases[k]['sc_att'] for k in cases],
    'SC_Pre_RMSE': [cases[k]['sc_pre_rmse'] for k in cases],
    'SC_Post_RMSE': [cases[k]['sc_post_rmse'] for k in cases],
    'Placebo_p': [cases[k]['placebo_rank']/cases[k]['placebo_n'] for k in cases],
    'DiD_coef': [cases[k]['did_coef'] for k in cases],
    'DiD_p': [cases[k]['did_pval'] for k in cases],
})
print(cmp.round(3).to_string(index=False))

# ─────────────────────────────────────────────────────────────
# [목적 ③-A] Lag + 누적 5년 패널회귀
# ─────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('  [Lag/누적] 학력향상지원의 지연·누적효과')
print('='*60)

dlag = df_ana.copy().sort_values(['시도', '연도'])
dlag['학력향상_lag1'] = dlag.groupby('시도')['학력향상_학생당_천원'].shift(1)
dlag['학력향상_lag2'] = dlag.groupby('시도')['학력향상_학생당_천원'].shift(2)
dlag['학력향상_5년누적'] = (dlag.groupby('시도')['학력향상_학생당_천원']
                          .rolling(5, min_periods=3).sum()
                          .reset_index(level=0, drop=True))

dlag_p = dlag.dropna(subset=['학력향상_lag1','학력향상_lag2','학력향상_5년누적']).copy()
dlag_p = dlag_p.set_index(['시도','연도'])
controls = ['학업중단률', '다문화학생_비율', '학급당_학생수', '교원1인당_학생수']

print(f'\nLag obs: {len(dlag_p)} ({dlag_p.index.get_level_values(0).nunique()}시도)')

# 모델 L1: t, t-1, t-2 동시
exog = dlag_p[['학력향상_학생당_천원','학력향상_lag1','학력향상_lag2'] + controls].astype(float)
m_L1 = PanelOLS(dlag_p['proxy_risk_score'].astype(float),
                exog=exog, entity_effects=True, time_effects=True)
res_L1 = m_L1.fit(cov_type='clustered', cluster_entity=True)
print('\n[L1] 동기 + 1년·2년 지연 동시 투입')
print(res_L1.summary.tables[1])

# 모델 L2: 5년 누적
exog2 = dlag_p[['학력향상_5년누적'] + controls].astype(float)
m_L2 = PanelOLS(dlag_p['proxy_risk_score'].astype(float),
                exog=exog2, entity_effects=True, time_effects=True)
res_L2 = m_L2.fit(cov_type='clustered', cluster_entity=True)
print('\n[L2] 5년 누적 지원')
print(res_L2.summary.tables[1])

# ─────────────────────────────────────────────────────────────
# [목적 ③-B] 부산학력개발원 설립(2022) Event Study
# ─────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('  [Event Study] 부산학력개발원 설립(2022) — 부산 위험도 구조변화')
print('='*60)

# 부산 SC 격차에서 2022 전·후 평균 비교
busan_case = cases['부산']
gap_b = busan_case['sc_actual'] - busan_case['sc_synth']
years = np.array(busan_case['years'])
pre_2022 = gap_b[(years >= 2020) & (years <= 2021)]   # 2020-2021
post_2022 = gap_b[(years >= 2022) & (years <= 2024)]  # 2022-2024
print(f'  2020-2021 평균 격차 (학개원 설립 전): {pre_2022.mean():+.2f}')
print(f'  2022-2024 평균 격차 (학개원 설립 후): {post_2022.mean():+.2f}')
print(f'  구조변화 추정치: {post_2022.mean() - pre_2022.mean():+.2f}점')

# 회귀형 ITS (interrupted time series) on 부산 only
busan_only = df_ana[df_ana['시도']=='부산'].sort_values('연도').copy()
busan_only['t'] = busan_only['연도'] - 2013
busan_only['post2022'] = (busan_only['연도'] >= 2022).astype(int)
busan_only['t_post'] = busan_only['t'] * busan_only['post2022']
X_its = busan_only[['t', 'post2022', 't_post']].astype(float)
X_its = pd.concat([pd.Series(1.0, index=X_its.index, name='const'), X_its], axis=1)
y = busan_only['proxy_risk_score'].astype(float).values
# OLS
b = np.linalg.lstsq(X_its.values, y, rcond=None)[0]
print(f'\n  ITS 회귀: const={b[0]:.2f}, t={b[1]:+.3f}, post2022={b[2]:+.2f}, t_post={b[3]:+.3f}')
print('   → post2022 음수면 즉각 수준 변화 감소, t_post 음수면 추세 변화 감소')

# ─────────────────────────────────────────────────────────────
# [목적 ③-C] 서울 β를 부산에 이식한 counterfactual
# ─────────────────────────────────────────────────────────────
print('\n' + '='*60)
print('  [Counterfactual] 서울 정책강도 β를 부산에 적용')
print('='*60)

# 시도별 within 회귀: proxy_risk_score ~ 학력향상_학생당_천원 + 통제변수
def within_beta(city):
    sub = df_ana[df_ana['시도']==city].sort_values('연도').copy()
    X = sub[['학력향상_학생당_천원','학업중단률','다문화학생_비율',
             '학급당_학생수','교원1인당_학생수']].astype(float).values
    y = sub['proxy_risk_score'].astype(float).values
    X1 = np.column_stack([np.ones(len(X)), X])
    b = np.linalg.lstsq(X1, y, rcond=None)[0]
    return b[1]   # 학력향상 계수

beta_seoul = within_beta('서울')
beta_gyeonggi = within_beta('경기')
beta_busan = within_beta('부산')
print(f'  Within 부산 β: {beta_busan:+.4f}')
print(f'  Within 서울 β: {beta_seoul:+.4f}')
print(f'  Within 경기 β: {beta_gyeonggi:+.4f}')

# 부산 2024 시나리오: 부산이 서울/경기 수준 지원이었다면?
seoul_24 = df_ana[(df_ana['시도']=='서울') & (df_ana['연도']==2024)].iloc[0]
gyeonggi_24 = df_ana[(df_ana['시도']=='경기') & (df_ana['연도']==2024)].iloc[0]
busan_24 = df_ana[(df_ana['시도']=='부산') & (df_ana['연도']==2024)].iloc[0]

print(f'\n[2024 실제] 부산 학력향상지원 학생당 {busan_24["학력향상_학생당_천원"]:.1f}천원, 위험도 {busan_24["proxy_risk_score"]:.2f}')
print(f'          서울 {seoul_24["학력향상_학생당_천원"]:.1f}천원, 위험도 {seoul_24["proxy_risk_score"]:.2f}')
print(f'          경기 {gyeonggi_24["학력향상_학생당_천원"]:.1f}천원, 위험도 {gyeonggi_24["proxy_risk_score"]:.2f}')

# 시나리오 1: 부산의 β로 서울 수준 지원 강도였다면
scenarios = []
for name, beta, src_per in [
    ('부산β × 서울지원수준', beta_busan, seoul_24['학력향상_학생당_천원']),
    ('서울β × 서울지원수준', beta_seoul, seoul_24['학력향상_학생당_천원']),
    ('부산β × 경기지원수준', beta_busan, gyeonggi_24['학력향상_학생당_천원']),
    ('경기β × 경기지원수준', beta_gyeonggi, gyeonggi_24['학력향상_학생당_천원']),
    ('서울β × 현재부산지원', beta_seoul, busan_24['학력향상_학생당_천원']),
]:
    delta = beta * (src_per - busan_24['학력향상_학생당_천원'])
    new_y = busan_24['proxy_risk_score'] + delta
    scenarios.append({
        '시나리오': name,
        'β': round(float(beta), 4),
        '지원수준_천원': round(float(src_per), 2),
        '예상위험도': round(float(new_y), 2),
        'Δ': round(float(delta), 2),
    })
print('\n[counterfactual]')
print(pd.DataFrame(scenarios).to_string(index=False))

# ─────────────────────────────────────────────────────────────
# 시각화
# ─────────────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# (1) 3사례 SC 비교
ax = axes[0,0]
colors = {'서울':'steelblue','경기':'seagreen','부산':'crimson'}
for k, r in cases.items():
    ax.plot(r['years'], r['sc_actual'], 'o-', color=colors[k], label=f'{k} 실제', linewidth=2)
    ax.plot(r['years'], r['sc_synth'], '--', color=colors[k], alpha=0.6, label=f'{k} 합성')
ax.axvline(2019.5, color='gray', linestyle=':')
ax.set_title('3개 시도 Synthetic Control 비교')
ax.set_xlabel('연도'); ax.set_ylabel('proxy_risk_score')
ax.legend(fontsize=8); ax.grid(alpha=0.3)

# (2) DiD/SC 결과 막대
ax = axes[0,1]
labels = list(cases.keys())
sc_vals = [cases[k]['sc_att'] for k in labels]
did_vals = [cases[k]['did_coef'] for k in labels]
x = np.arange(len(labels))
ax.bar(x-0.2, sc_vals, 0.4, label='SC ATT', color='steelblue')
ax.bar(x+0.2, did_vals, 0.4, label='DiD 계수', color='tomato')
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.axhline(0, color='black', linewidth=0.6)
ax.set_title('3사례 정책효과 비교 (음수=위험도 둔화)')
ax.set_ylabel('점수 변화'); ax.legend(); ax.grid(alpha=0.3, axis='y')

# (3) Lag 효과 시각화
ax = axes[1,0]
keys = ['학력향상_학생당_천원','학력향상_lag1','학력향상_lag2']
vals = [res_L1.params[k] for k in keys]
ses = [res_L1.std_errors[k] for k in keys]
ax.errorbar(['t','t-1','t-2'], vals, yerr=[1.96*s for s in ses],
            fmt='o', color='steelblue', capsize=5, markersize=10)
ax.axhline(0, color='black', linewidth=0.6)
ax.set_title(f'Lag 효과 (95% CI), 5년누적 β={res_L2.params["학력향상_5년누적"]:+.4f}')
ax.set_ylabel('계수'); ax.grid(alpha=0.3)

# (4) Counterfactual
ax = axes[1,1]
df_sc = pd.DataFrame(scenarios)
y_pos = np.arange(len(df_sc))
ax.barh(y_pos, df_sc['예상위험도'], color='seagreen', alpha=0.7)
ax.set_yticks(y_pos); ax.set_yticklabels(df_sc['시나리오'], fontsize=9)
ax.axvline(busan_24['proxy_risk_score'], color='red', linestyle=':',
           label=f'부산 2024 실제 {busan_24["proxy_risk_score"]:.1f}')
ax.set_title('부산 counterfactual 시나리오')
ax.set_xlabel('예상 위험도 점수')
ax.legend(); ax.grid(alpha=0.3, axis='x')

plt.tight_layout()
figp = OUT / 'v7_seoul_gyeonggi_busan.png'
plt.savefig(figp, dpi=130, bbox_inches='tight')
print(f'\n그래프 저장: {figp}')

# ── 저장 ──
summary = {
    '목적②_3사례': {
        k: {
            'SC_ATT': round(float(r['sc_att']),3),
            'SC_pre_RMSE': round(float(r['sc_pre_rmse']),3),
            'SC_post_RMSE': round(float(r['sc_post_rmse']),3),
            'Placebo_p': round(r['placebo_rank']/r['placebo_n'],3),
            'DiD_coef': round(float(r['did_coef']),3),
            'DiD_p': round(float(r['did_pval']),3),
            'SC_top_donors': sorted({s:round(float(w),3) for s,w in r['sc_weights'].items() if w>0.05}.items(), key=lambda x:-x[1])
        } for k, r in cases.items()
    },
    '목적③_A_Lag': {
        't': round(float(res_L1.params['학력향상_학생당_천원']),5),
        't-1': round(float(res_L1.params['학력향상_lag1']),5),
        't-2': round(float(res_L1.params['학력향상_lag2']),5),
        't_pval': round(float(res_L1.pvalues['학력향상_학생당_천원']),4),
        't-1_pval': round(float(res_L1.pvalues['학력향상_lag1']),4),
        't-2_pval': round(float(res_L1.pvalues['학력향상_lag2']),4),
        '5년누적_β': round(float(res_L2.params['학력향상_5년누적']),5),
        '5년누적_p': round(float(res_L2.pvalues['학력향상_5년누적']),4),
    },
    '목적③_B_부산학개원2022': {
        '2020_2021_평균격차': round(float(pre_2022.mean()),3),
        '2022_2024_평균격차': round(float(post_2022.mean()),3),
        '구조변화_추정': round(float(post_2022.mean() - pre_2022.mean()),3),
        'ITS_const': round(float(b[0]),3),
        'ITS_trend': round(float(b[1]),3),
        'ITS_post2022_step': round(float(b[2]),3),
        'ITS_post2022_slope_change': round(float(b[3]),3),
    },
    '목적③_C_counterfactual': scenarios,
    '주의': '동행성 분석. 인과해석 금지. 위험도 지수는 환경변수 합성.'
}
with open(OUT / 'v7_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
cmp.to_csv(OUT / 'v7_3city_comparison.csv', index=False, encoding='utf-8-sig')
print(f'요약 저장: {OUT / "v7_summary.json"}')
print(f'비교표 저장: {OUT / "v7_3city_comparison.csv"}')
