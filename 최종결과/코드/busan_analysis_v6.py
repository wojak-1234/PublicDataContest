"""
부산 분석 v6 — 학력향상지원 + 누리과정지원 + 다문화·북한이탈주민지원 + 돌봄교실운영
- 4개 정책 변수 통합 패널 (시도 × 연도)
- 새 정책 데이터는 2022-2024 (3년) 만 가용 → cross-section + 시계열 보조 분석
- 부산 4개 정책 추세, 정책-위험도 상관, 패널 회귀, SC, 시나리오
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
from pathlib import Path
from linearmodels.panel import PanelOLS
import warnings
warnings.filterwarnings('ignore')

matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

OUT = Path(r'C:/ai_contest2026/out')
DATA = Path(r'C:/ai_contest2026/data')

# ── 1. 새 정책 데이터 3개 로드 + 학력향상지원 ─────────────────
def load_csv(path, year_col):
    d = pd.read_csv(path, encoding='cp949')
    d.columns = [c.strip() for c in d.columns]
    d['지역구분'] = d['지역구분'].astype(str).str.strip()
    d['항목구분'] = d['항목구분'].astype(str).str.strip()
    d['금액'] = pd.to_numeric(d['금액'] if '금액' in d.columns else d['금액(원)'], errors='coerce')
    return d.rename(columns={year_col: '연도', '지역구분': '시도'})

# 학력향상지원: 2013-2026
a = pd.read_csv(DATA / '학력향상지원.csv', encoding='cp949')
b = pd.read_csv(DATA / '학력향상지원 (1).csv', encoding='cp949')
for df_ in (a, b):
    df_.columns = [c.strip() for c in df_.columns]
    df_['지역구분'] = df_['지역구분'].astype(str).str.strip()
    df_['항목구분'] = df_['항목구분'].astype(str).str.strip()
    df_['금액(원)'] = pd.to_numeric(df_['금액(원)'], errors='coerce')
hak = pd.concat([a, b], ignore_index=True).rename(columns={'회계연도': '연도', '지역구분': '시도', '금액(원)': '금액'})

# 새 3개 정책 데이터: 2022-2024
nuri = load_csv(DATA / '누리과정지원.csv', '기준년도')
multi = load_csv(DATA / '다문화및북한이탈주민등자녀교육지원.csv', '기준년도')
care = load_csv(DATA / '돌봄교실운영.csv', '기준년도')

def amount_pivot(df, item_name, col_name):
    p = (df[df['항목구분']==item_name]
         .pivot_table(index=['연도','시도'], values='금액', aggfunc='first')
         .reset_index()
         .rename(columns={'금액': col_name}))
    return p

p_hak = amount_pivot(hak, '학력향상지원', '학력향상_원')
p_nuri = amount_pivot(nuri, '누리과정지원', '누리과정_원')
p_multi = amount_pivot(multi, '다문화및북한이탈주민등자녀교육지원', '다문화이탈주민_원')
p_care = amount_pivot(care, '돌봄교실운영', '돌봄교실_원')

# 세출액 (학력향상.csv는 2013-2021, 새 csv는 각 2022-2024에서 별도 세출결산 있음)
p_sechul_a = (a[a['항목구분']=='세출결산액']
              .pivot_table(index=['회계연도','지역구분'], values='금액(원)', aggfunc='first')
              .reset_index().rename(columns={'회계연도':'연도','지역구분':'시도','금액(원)':'세출액'}))
p_sechul_b = (b[b['항목구분']=='세출예산액']
              .pivot_table(index=['회계연도','지역구분'], values='금액(원)', aggfunc='first')
              .reset_index().rename(columns={'회계연도':'연도','지역구분':'시도','금액(원)':'세출액'}))
sechul = pd.concat([p_sechul_a, p_sechul_b], ignore_index=True)

policy = (p_hak.merge(p_nuri, on=['연도','시도'], how='outer')
                .merge(p_multi, on=['연도','시도'], how='outer')
                .merge(p_care, on=['연도','시도'], how='outer')
                .merge(sechul, on=['연도','시도'], how='outer'))

for col_won, col_pct, col_per in [
    ('학력향상_원', '학력향상_세출비중', '학력향상_학생당_천원'),
    ('누리과정_원', '누리과정_세출비중', '누리과정_학생당_천원'),
    ('다문화이탈주민_원', '다문화이탈주민_세출비중', '다문화이탈주민_학생당_천원'),
    ('돌봄교실_원', '돌봄교실_세출비중', '돌봄교실_학생당_천원'),
]:
    policy[col_pct] = policy[col_won] / policy['세출액'] * 100
    policy[col_won.replace('_원','_억원')] = policy[col_won] / 1e8

# ── 2. v4 (위험도지수) + 정책 통합 ─────────────────────────────
df = pd.read_csv(r'C:/ai_contest2026/통합_proxy_dataset_v4.csv', encoding='utf-8-sig')
df = df[df['시도']!='세종'].copy()
df = df.merge(policy, on=['연도','시도'], how='left')

# 학생당 천원 환산 (정책 변수)
for col, alias in [('학력향상_원','학력향상'),('누리과정_원','누리과정'),
                   ('다문화이탈주민_원','다문화이탈주민'),('돌봄교실_원','돌봄교실')]:
    df[f'{alias}_학생당_천원'] = (df[col] / df['총학생수']) / 1000

df.to_csv(r'C:/ai_contest2026/통합_proxy_dataset_v6.csv', index=False, encoding='utf-8-sig')
print(f'v6 dataset 저장 (세종 제외, {df.shape[0]} obs)')

# ── 3. 부산 4개 정책 시계열 ──────────────────────────────────
busan = df[df['시도']=='부산'].sort_values('연도').copy()
print('\n[부산 4대 정책 시계열 (억원, 학생당 천원, 세출비중%)]')
cols_show = ['연도',
             '학력향상_억원','학력향상_학생당_천원','학력향상_세출비중',
             '누리과정_억원','누리과정_학생당_천원','누리과정_세출비중',
             '다문화이탈주민_억원','다문화이탈주민_학생당_천원','다문화이탈주민_세출비중',
             '돌봄교실_억원','돌봄교실_학생당_천원','돌봄교실_세출비중',
             'proxy_risk_score']
print(busan[cols_show].round(3).to_string(index=False))

# ── 4. 2022-2024 4개 정책 cross-section 분석 ─────────────────
print('\n' + '='*60)
print('  [A] 2022-2024 cross-section: 4개 정책 ↔ 위험도')
print('='*60)
cs = df[df['연도'].between(2022, 2024)].dropna(subset=[
    '학력향상_학생당_천원','누리과정_학생당_천원',
    '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원']).copy()
print(f'관측치: {len(cs)} obs (16시도 × 3년)')
print('\n[상관계수 (학생당 정책액 vs proxy_risk_score)]')
for col in ['학력향상_학생당_천원','누리과정_학생당_천원',
            '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원']:
    r = cs[[col,'proxy_risk_score']].corr().iloc[0,1]
    print(f'  {col:30s} r = {r:+.3f}')

# 다변량 Two-way FE 회귀
cs_p = cs.set_index(['시도','연도'])
exog = cs_p[['학력향상_학생당_천원','누리과정_학생당_천원',
             '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원',
             '학업중단률','다문화학생_비율']].astype(float)
m = PanelOLS(dependent=cs_p['proxy_risk_score'].astype(float),
             exog=exog, entity_effects=True, time_effects=True)
res = m.fit(cov_type='clustered', cluster_entity=True)
print('\n[2022-2024 패널회귀 (시도FE+연도FE, 4개 정책 동시 투입)]')
print(res.summary.tables[1])

policy_betas = {}
for k in ['학력향상_학생당_천원','누리과정_학생당_천원',
          '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원']:
    policy_betas[k] = {'beta': float(res.params[k]),
                       'p': float(res.pvalues[k])}

# ── 5. 2022-2024 시도별 4정책 vs 위험도 ranking ───────────────
print('\n' + '='*60)
print('  [B] 2024 시도별 4개 정책 강도 ranking')
print('='*60)
d24 = df[df['연도']==2024][['시도','proxy_risk_score',
       '학력향상_학생당_천원','누리과정_학생당_천원',
       '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원']].round(2)
print(d24.sort_values('proxy_risk_score', ascending=False).to_string(index=False))

# ── 6. 부산 vs 타시도 4개 정책 평균 비교 (2022-2024) ───────────
print('\n' + '='*60)
print('  [C] 부산 vs 타시도 평균 (2022-2024)')
print('='*60)
cmp = (df[df['연도'].between(2022,2024)]
       .assign(grp=lambda x: np.where(x['시도']=='부산','부산','타시도'))
       .groupby('grp')[['학력향상_학생당_천원','누리과정_학생당_천원',
                        '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원',
                        'proxy_risk_score']].mean().round(2))
print(cmp.T)

# ── 시각화 ────────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(16, 11))
policies = ['학력향상','누리과정','다문화이탈주민','돌봄교실']
colors = ['steelblue','seagreen','darkorange','crimson']

# (1) 부산 4개 정책 시계열 (억원)
ax = axes[0,0]
for p, c in zip(policies, colors):
    col = f'{p}_억원'
    sub = busan[busan[col].notna()]
    ax.plot(sub['연도'], sub[col], 'o-', label=p, color=c, linewidth=2)
ax.set_title('부산 4대 정책 예산 추이 (억원)')
ax.set_xlabel('연도'); ax.set_ylabel('억원')
ax.legend(); ax.grid(alpha=0.3)

# (2) 2024 시도별 4개 정책 비교 (학생당 천원)
ax = axes[0,1]
d24_sort = d24.sort_values('proxy_risk_score', ascending=False)
x = np.arange(len(d24_sort))
w = 0.2
for i, p in enumerate(policies):
    ax.bar(x + (i-1.5)*w, d24_sort[f'{p}_학생당_천원'],
           width=w, label=p, color=colors[i])
ax.set_xticks(x)
ax.set_xticklabels(d24_sort['시도'], rotation=45)
ax.set_title('2024 시도별 정책 강도 (학생당 천원)')
ax.set_ylabel('학생당 천원')
ax.legend(); ax.grid(alpha=0.3, axis='y')

# (3) 2022-2024 정책 vs 위험도 산점도
ax = axes[1,0]
for p, c in zip(policies, colors):
    col = f'{p}_학생당_천원'
    sub = cs.dropna(subset=[col])
    ax.scatter(sub[col], sub['proxy_risk_score'], color=c, alpha=0.6, label=p, s=40)
ax.set_title('정책 강도 vs 위험도 점수 (2022-2024)')
ax.set_xlabel('학생당 천원'); ax.set_ylabel('proxy_risk_score')
ax.legend(); ax.grid(alpha=0.3)

# (4) 부산 vs 타시도 평균 (2022-2024)
ax = axes[1,1]
labels = policies
busan_vals = [cmp.loc['부산', f'{p}_학생당_천원'] for p in labels]
oth_vals = [cmp.loc['타시도', f'{p}_학생당_천원'] for p in labels]
x = np.arange(len(labels))
ax.bar(x - 0.2, busan_vals, 0.4, label='부산', color='steelblue')
ax.bar(x + 0.2, oth_vals, 0.4, label='타시도 평균', color='gray')
ax.set_xticks(x); ax.set_xticklabels(labels)
ax.set_title('부산 vs 타시도 평균 정책 강도 (2022-2024, 학생당 천원)')
ax.set_ylabel('학생당 천원')
ax.legend(); ax.grid(alpha=0.3, axis='y')

plt.tight_layout()
figp = OUT / 'busan_v6_4policy.png'
plt.savefig(figp, dpi=130, bbox_inches='tight')
print(f'\n그래프 저장: {figp}')

# ── 결과 저장 ──
summary = {
    '데이터': {
        'v6_obs': int(df.shape[0]),
        '신규_정책_3종_가용연도': '2022-2024',
        '학력향상지원_가용연도': '2013-2026',
    },
    '2022_2024_panel_FE_결과': policy_betas,
    '2024_부산_4정책_학생당천원': {
        p: float(busan.loc[busan['연도']==2024, f'{p}_학생당_천원'].iloc[0])
        for p in policies},
    '부산_vs_타시도_평균_2022_2024': {
        p: {'부산': float(cmp.loc['부산', f'{p}_학생당_천원']),
            '타시도': float(cmp.loc['타시도', f'{p}_학생당_천원'])}
        for p in policies},
    '주의': '신규 3개 정책은 2022-2024만 가용. 결과는 단기 동행성, 인과 X.'
}
with open(OUT / 'busan_v6_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f'요약 저장: {OUT / "busan_v6_summary.json"}')
