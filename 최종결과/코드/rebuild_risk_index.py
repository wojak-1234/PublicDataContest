"""
시나리오 C: proxy_index를 위험도 합성지수(risk score)로 재설계
- 학습: 2012-2016 시도별 실측 미달률(80 obs)을 종속변수로 Ridge 회귀
- 예측: 전 기간(2012-2024) 위험도 점수 산출
- 산출: proxy_risk_pct (% 단위 예측 미달률), proxy_risk_score (0-100 정규화)
- 절대 미달률 해석 X. 시도 간/연도 간 상대 위험도 비교에만 사용.
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import LeaveOneOut, cross_val_score
import warnings
warnings.filterwarnings('ignore')

SRC = Path(r'C:/ai_contest2026/통합_proxy_dataset_v3.csv')
OUT = Path(r'C:/ai_contest2026/통합_proxy_dataset_v4.csv')
META = Path(r'C:/ai_contest2026/out/risk_index_model.json')

df = pd.read_csv(SRC, encoding='utf-8-sig')

# GRDP 결측 처리 (2023-2024): 시도별 forward fill
df = df.sort_values(['시도', '연도'])
df['GRDP_1인당'] = df.groupby('시도')['GRDP_1인당'].ffill()

# ── 대용변수 정의 ──────────────────────────────────────────────
FEATURES = [
    '학업중단률', '자퇴_비율',
    '다문화학생_비율', '중도입국_비율', '해외출국_비율',
    '학급당_학생수', '특수학급_비율',
    '사교육_참여율', '사교육비_1인당_만원',
    'GRDP_1인당',
    '교원1인당_학생수',
    '학생1인당_건물면적_평균', '학생1인당_교지면적_평균',
]
TARGET = '미달률_평균_실측'

# ── 학습 데이터: 실측 가용 + 세종 제외 ─────────────────────────
train = df[(df[TARGET].notna()) & (df['시도'] != '세종')].copy()
print(f'학습 데이터: {len(train)} obs (16시도 × 2012-2016)')

X = train[FEATURES].values
y = train[TARGET].values

scaler = StandardScaler().fit(X)
Xs = scaler.transform(X)

# ── Ridge with CV ─────────────────────────────────────────────
alphas = np.logspace(-2, 3, 30)
model = RidgeCV(alphas=alphas, cv=5).fit(Xs, y)
print(f'선택 α: {model.alpha_:.3f}')

# LOO-CV 성능 (overfitting 점검)
loo = LeaveOneOut()
loo_r2 = cross_val_score(RidgeCV(alphas=alphas, cv=5), Xs, y,
                         cv=loo, scoring='r2').mean()
loo_rmse = np.sqrt(-cross_val_score(RidgeCV(alphas=alphas, cv=5), Xs, y,
                                    cv=loo, scoring='neg_mean_squared_error').mean())
print(f'In-sample R²: {model.score(Xs, y):.3f}, LOO R²: {loo_r2:.3f}, LOO RMSE: {loo_rmse:.3f} %p')

# ── 계수 (표준화 단위) ─────────────────────────────────────────
coef_df = pd.DataFrame({
    '변수': FEATURES,
    '표준화_계수': np.round(model.coef_, 3),
}).sort_values('표준화_계수', key=lambda s: -s.abs())
print('\n[표준화 회귀계수 (절대값 큰 순)]')
print(coef_df.to_string(index=False))

# ── 전 기간 예측 ──────────────────────────────────────────────
# 세종 포함 전체 행에 대해 예측 (세종은 학습에서 제외했으므로 extrapolation)
X_all = df[FEATURES].values
Xs_all = scaler.transform(X_all)
pred_pct = model.predict(Xs_all)
pred_pct = np.clip(pred_pct, 0, None)  # 음수 방지
df['proxy_risk_pct'] = np.round(pred_pct, 3)

# 0-100 정규화 (전체 데이터 기준 min-max). 세종 제외 분포로 정규화.
mask_nosjong = df['시도'] != '세종'
mn = df.loc[mask_nosjong, 'proxy_risk_pct'].min()
mx = df.loc[mask_nosjong, 'proxy_risk_pct'].max()
df['proxy_risk_score'] = np.round(100 * (df['proxy_risk_pct'] - mn) / (mx - mn), 2)

# 기존 proxy_index 컬럼 보존 + 새 컬럼 위주로 사용 안내
df['proxy_index_v3'] = df['proxy_index']
df['proxy_index'] = df['proxy_risk_score']  # 표준 컬럼명은 위험도 점수로 재정의
df['proxy_index_source'] = '위험도합성지수(Ridge)'

# ── 저장 ──
df.to_csv(OUT, index=False, encoding='utf-8-sig')
print(f'\n저장: {OUT}')

# ── 요약 ──
print('\n[연도별 proxy_risk_score 분포 (세종 제외)]')
print(df[mask_nosjong].groupby('연도')['proxy_risk_score'].agg(['mean','min','max']).round(2))

print('\n[부산 시계열]')
b = df[df['시도']=='부산'].sort_values('연도')[['연도','proxy_risk_pct','proxy_risk_score','proxy_index_v3']]
print(b.to_string(index=False))

# 학습된 모델 메타 저장
meta = {
    'features': FEATURES,
    'target': TARGET,
    'n_train': int(len(train)),
    'ridge_alpha': float(model.alpha_),
    'in_sample_R2': float(model.score(Xs, y)),
    'loo_R2': float(loo_r2),
    'loo_RMSE_pct': float(loo_rmse),
    'std_coefficients': dict(zip(FEATURES, [float(c) for c in model.coef_])),
    'intercept': float(model.intercept_),
    'risk_pct_range_used_for_score_norm': [float(mn), float(mx)],
    'note': '시나리오 C: 위험도 합성지수. 인과해석 금지. 시도 간/연도 간 상대 위험도 비교용.',
}
with open(META, 'w', encoding='utf-8') as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)
print(f'모델 메타 저장: {META}')
