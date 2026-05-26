"""
학교급별 정책 Lag 분석
- 종속변수: 학교급별 위험도 점수 (중/고)
- 정책: 학력향상지원 (t/t-1/t-2/5년누적) + 누리/다문화/돌봄 (3년)
- 학교급별로 정책 효과 차이 검증
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
import numpy as np
import pandas as pd
from pathlib import Path
from linearmodels.panel import PanelOLS
import matplotlib.pyplot as plt
import matplotlib
import warnings; warnings.filterwarnings('ignore')

matplotlib.rcParams['font.family'] = 'Malgun Gothic'
matplotlib.rcParams['axes.unicode_minus'] = False

OUT = Path(r'C:/ai_contest2026/out')

# ── 데이터 로드 ──
df = pd.read_csv(r'C:/ai_contest2026/통합_proxy_dataset_v8_학교급.csv', encoding='utf-8-sig')
df = df[df['학제'].isin(['중','고'])].copy()
df = df[df['연도'].between(2013, 2024)].copy()
print(f'분석 데이터: {len(df)} obs (16시도 × 2학교급 × 12년)')

# ── 학력향상 Lag 변수 ──
df = df.sort_values(['시도','학제','연도'])
df['학력향상_lag1'] = df.groupby(['시도','학제'])['학력향상_학생당_천원'].shift(1)
df['학력향상_lag2'] = df.groupby(['시도','학제'])['학력향상_학생당_천원'].shift(2)
df['학력향상_5년누적'] = (df.groupby(['시도','학제'])['학력향상_학생당_천원']
                          .rolling(5, min_periods=3).sum()
                          .reset_index(level=[0,1], drop=True))

controls = ['학업중단률_급','다문화_비율_급','학급당_학생수_급','교원1인당_학생수']

# ── 학교급별 학력향상 Lag 패널회귀 ──
print('\n' + '='*60)
print('  [학력향상지원] 학교급별 Lag 분석')
print('='*60)
results_grade = {}
for grade in ['중','고']:
    sub = df[df['학제']==grade].dropna(subset=['학력향상_lag1','학력향상_lag2']).copy()
    sub = sub.set_index(['시도','연도'])
    exog = sub[['학력향상_학생당_천원','학력향상_lag1','학력향상_lag2']+controls].astype(float)
    m = PanelOLS(sub['위험도_점수'].astype(float),
                 exog=exog, entity_effects=True, time_effects=True)
    res = m.fit(cov_type='clustered', cluster_entity=True)
    results_grade[grade] = res
    print(f'\n[{grade}학교] obs={len(sub)}')
    print(res.summary.tables[1])

# ── 4정책 동시 투입 패널회귀 (학교급별) ──
print('\n' + '='*60)
print('  [4정책 동시] 2022-2024 학교급별 패널회귀')
print('='*60)
cs_results = {}
for grade in ['중','고']:
    sub = df[(df['학제']==grade) & df['연도'].between(2022,2024)].dropna(
        subset=['학력향상_학생당_천원','누리과정_학생당_천원',
                '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원']).copy()
    sub = sub.set_index(['시도','연도'])
    exog = sub[['학력향상_학생당_천원','누리과정_학생당_천원',
                '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원']+controls].astype(float)
    m = PanelOLS(sub['위험도_점수'].astype(float),
                 exog=exog, entity_effects=True, time_effects=True)
    res = m.fit(cov_type='clustered', cluster_entity=True)
    cs_results[grade] = res
    print(f'\n[{grade}학교, 2022-2024] obs={len(sub)}')
    print(res.summary.tables[1])

# ── 누리·다문화·돌봄 정책의 학교급별 1년 Lag (가능한 한) ──
# 2023-2024 obs만 lag 가능 (16시도 × 2년 × 2학교급 = 64)
print('\n' + '='*60)
print('  [신규 3정책 Lag1] 누리·다문화·돌봄 1년 지연')
print('='*60)
df['누리_lag1'] = df.groupby(['시도','학제'])['누리과정_학생당_천원'].shift(1)
df['다문화이탈주민_lag1'] = df.groupby(['시도','학제'])['다문화이탈주민_학생당_천원'].shift(1)
df['돌봄_lag1'] = df.groupby(['시도','학제'])['돌봄교실_학생당_천원'].shift(1)

lag3_results = {}
for grade in ['중','고']:
    sub = df[(df['학제']==grade) & df['연도'].isin([2023,2024])].dropna(
        subset=['누리_lag1','다문화이탈주민_lag1','돌봄_lag1']).copy()
    sub = sub.set_index(['시도','연도'])
    exog = sub[['누리_lag1','다문화이탈주민_lag1','돌봄_lag1']+controls].astype(float)
    # 시간FE 사용 못함 (T=2)
    m = PanelOLS(sub['위험도_점수'].astype(float),
                 exog=exog, entity_effects=True, time_effects=False)
    res = m.fit(cov_type='clustered', cluster_entity=True)
    lag3_results[grade] = res
    print(f'\n[{grade}학교 2023-2024] obs={len(sub)}')
    print(res.summary.tables[1])

# ── 학력향상 5년 누적 학교급별 ──
print('\n' + '='*60)
print('  [학력향상 5년 누적] 학교급별')
print('='*60)
cum_results = {}
for grade in ['중','고']:
    sub = df[df['학제']==grade].dropna(subset=['학력향상_5년누적']).copy()
    sub = sub.set_index(['시도','연도'])
    exog = sub[['학력향상_5년누적']+controls].astype(float)
    m = PanelOLS(sub['위험도_점수'].astype(float),
                 exog=exog, entity_effects=True, time_effects=True)
    res = m.fit(cov_type='clustered', cluster_entity=True)
    cum_results[grade] = res
    print(f'\n[{grade}학교] obs={len(sub)}')
    print(res.summary.tables[1])

# ── 시각화 ─────────────────────────────────────────────────
fig, axes = plt.subplots(2, 2, figsize=(16, 11))

# (1) 학력향상 Lag 계수 학교급별
ax = axes[0,0]
keys = ['학력향상_학생당_천원','학력향상_lag1','학력향상_lag2']
labels = ['t','t-1','t-2']
for grade, color in [('중','steelblue'),('고','crimson')]:
    r = results_grade[grade]
    vals = [r.params[k] for k in keys]
    ses = [r.std_errors[k] for k in keys]
    xs = np.arange(len(labels)) + (0.1 if grade=='고' else -0.1)
    ax.errorbar(xs, vals, yerr=[1.96*s for s in ses], fmt='o',
                color=color, capsize=5, markersize=10, label=f'{grade}학교')
ax.set_xticks(np.arange(len(labels))); ax.set_xticklabels(labels)
ax.axhline(0, color='black', linewidth=0.5)
ax.set_title('학력향상지원 시차별 효과 (학교급별, 95% CI)')
ax.set_ylabel('계수 (학생당 1천원 → 위험도 점수)')
ax.legend(); ax.grid(alpha=0.3)

# (2) 학교급별 4정책 계수
ax = axes[0,1]
pol = ['학력향상_학생당_천원','누리과정_학생당_천원',
       '다문화이탈주민_학생당_천원','돌봄교실_학생당_천원']
pol_labels = ['학력향상','누리과정','다문화·이탈','돌봄']
for grade, color in [('중','steelblue'),('고','crimson')]:
    r = cs_results[grade]
    vals = [r.params[k] for k in pol]
    ses = [r.std_errors[k] for k in pol]
    xs = np.arange(len(pol_labels)) + (0.1 if grade=='고' else -0.1)
    ax.errorbar(xs, vals, yerr=[1.96*s for s in ses], fmt='o',
                color=color, capsize=5, markersize=10, label=f'{grade}학교')
ax.set_xticks(np.arange(len(pol_labels))); ax.set_xticklabels(pol_labels, rotation=15)
ax.axhline(0, color='black', linewidth=0.5)
ax.set_title('4정책 동시 투입 계수 (2022-2024, 학교급별)')
ax.set_ylabel('계수'); ax.legend(); ax.grid(alpha=0.3)

# (3) 학교급별 위험도 추세 (전체)
ax = axes[1,0]
for grade, color in [('중','steelblue'),('고','crimson')]:
    avg = df[df['학제']==grade].groupby('연도')['위험도_점수'].mean()
    ax.plot(avg.index, avg.values, 'o-', color=color, linewidth=2, label=f'{grade}학교 평균')
ax.set_title('학교급별 위험도 점수 추세 (전 시도 평균)')
ax.set_xlabel('연도'); ax.set_ylabel('위험도 점수')
ax.legend(); ax.grid(alpha=0.3)

# (4) 부산 vs 타시도 학교급별
ax = axes[1,1]
years = sorted(df['연도'].unique())
for grade in ['중','고']:
    busan = df[(df['시도']=='부산')&(df['학제']==grade)].groupby('연도')['위험도_점수'].mean()
    others = df[(df['시도']!='부산')&(df['학제']==grade)].groupby('연도')['위험도_점수'].mean()
    ls = '-' if grade=='중' else '--'
    ax.plot(busan.index, busan.values, ls, color='steelblue', linewidth=2,
            label=f'부산 {grade}', marker='o' if grade=='중' else 's')
    ax.plot(others.index, others.values, ls, color='gray', linewidth=2,
            label=f'타시도 {grade}', marker='o' if grade=='중' else 's', alpha=0.6)
ax.set_title('부산 vs 타시도 평균 (학교급별)')
ax.set_xlabel('연도'); ax.set_ylabel('위험도 점수')
ax.legend(fontsize=8); ax.grid(alpha=0.3)

plt.tight_layout()
figp = OUT / 'policy_lag_by_grade.png'
plt.savefig(figp, dpi=130, bbox_inches='tight')
print(f'\n그래프 저장: {figp}')

# ── 요약 저장 ──
summary = {
    '학교급별_학력향상_Lag': {
        grade: {
            't': {'beta': round(float(r.params['학력향상_학생당_천원']),5),
                  'p': round(float(r.pvalues['학력향상_학생당_천원']),4)},
            't-1': {'beta': round(float(r.params['학력향상_lag1']),5),
                    'p': round(float(r.pvalues['학력향상_lag1']),4)},
            't-2': {'beta': round(float(r.params['학력향상_lag2']),5),
                    'p': round(float(r.pvalues['학력향상_lag2']),4)},
        } for grade, r in results_grade.items()
    },
    '학교급별_4정책_2022_2024': {
        grade: {p: {'beta': round(float(r.params[p]),5),
                    'p': round(float(r.pvalues[p]),4)}
                for p in pol}
        for grade, r in cs_results.items()
    },
    '학교급별_신규3정책_Lag1': {
        grade: {p: {'beta': round(float(r.params[p+'_lag1' if p!='다문화이탈주민' else '다문화이탈주민_lag1']),5),
                    'p': round(float(r.pvalues[p+'_lag1' if p!='다문화이탈주민' else '다문화이탈주민_lag1']),4)}
                for p in ['누리','다문화이탈주민','돌봄']}
        for grade, r in lag3_results.items()
    },
    '학교급별_학력향상_5년누적': {
        grade: {'beta': round(float(r.params['학력향상_5년누적']),5),
                'p': round(float(r.pvalues['학력향상_5년누적']),4)}
        for grade, r in cum_results.items()
    },
}
with open(OUT / 'policy_lag_grade_summary.json', 'w', encoding='utf-8') as f:
    json.dump(summary, f, ensure_ascii=False, indent=2)
print(f'요약 저장: {OUT / "policy_lag_grade_summary.json"}')
