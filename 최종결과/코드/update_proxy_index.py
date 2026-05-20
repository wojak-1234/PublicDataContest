"""
proxy_index 업데이트:
- 2012-2016: 시도별 기초학력 미달률 실측치 (중·고 × 국·수·영 6개값 평균)
- 2014: 2013/2015 선형 보간
- 2017-2024: 시도별 2015-2016 baseline × 전국 추세비율
- 단위: % (기초학력 미달률)
"""
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(r'C:/ai_contest2026/data/기초학력 미달자 비율')
PROXY_CSV = Path(r'C:/Users/esse4/Downloads/통합_proxy_dataset_v2.csv')
OUT_CSV = Path(r'C:/ai_contest2026/통합_proxy_dataset_v3.csv')

# ── 1. 시도별 기초학력 미달률 (2010-2016) ──────────────────────
sido_path = DATA_DIR / '시도별 기초학력자 비율 (2010~2016).xlsm'
raw = pd.read_excel(sido_path, sheet_name='Sheet1', header=None)
sido = raw.iloc[3:].copy()
sido.columns = ['시도', '학년', '연도', '국어', '수학', '영어']
sido = sido.dropna(subset=['시도', '연도'])
for c in ['국어', '수학', '영어']:
    sido[c] = pd.to_numeric(sido[c], errors='coerce')
sido['연도'] = sido['연도'].astype(int)
sido['평균'] = sido[['국어', '수학', '영어']].mean(axis=1)

# 학년(중/고)별 평균 → 시도/연도 평균
sido_by_grade = sido.pivot_table(
    index=['시도', '연도'], columns='학년', values='평균', aggfunc='mean'
).reset_index()
sido_by_grade.columns.name = None
sido_by_grade = sido_by_grade.rename(columns={'중': '미달률_중_실측', '고': '미달률_고_실측'})
sido_by_grade['미달률_평균_실측'] = sido_by_grade[['미달률_중_실측', '미달률_고_실측']].mean(axis=1)

print('[시도별 실측 미달률 (2010-2016)]')
print(sido_by_grade.head(20).to_string(index=False))
print()

# ── 2. 전국 기초학력 미달률 (2015-2024) ────────────────────────
nat_path = DATA_DIR / '기초학력 미달자 비율.xlsx'
nat_raw = pd.read_excel(nat_path, sheet_name='Sheet0', header=None)
years_nat = [int(y) for y in nat_raw.iloc[2, 2:].tolist()]
# row 3: 중 국어, row 4: 중 수학, row 5: 중 영어, row 6: 고 국어, row 7: 고 수학, row 8: 고 영어
nat_mid = nat_raw.iloc[3:6, 2:].astype(float).values   # (3, n_years)
nat_high = nat_raw.iloc[6:9, 2:].astype(float).values  # (3, n_years)

nat_df = pd.DataFrame({
    '연도': years_nat,
    '전국_미달률_중': nat_mid.mean(axis=0),
    '전국_미달률_고': nat_high.mean(axis=0),
})
nat_df['전국_미달률_평균'] = (nat_df['전국_미달률_중'] + nat_df['전국_미달률_고']) / 2
print('[전국 실측 미달률 (2015-2024)]')
print(nat_df.to_string(index=False))
print()

# ── 3. 기존 proxy dataset 로드 ─────────────────────────────────
df = pd.read_csv(PROXY_CSV)
df = df.rename(columns={df.columns[0]: '연도'})  # BOM 제거
print(f'기존 dataset: {df.shape}, 연도 {df["연도"].min()}~{df["연도"].max()}')

# ── 4. 시도별 실측치 병합 ──────────────────────────────────────
df = df.merge(sido_by_grade, on=['시도', '연도'], how='left')

# 2014년 보간: 같은 시도의 2013/2015 평균
for col in ['미달률_중_실측', '미달률_고_실측', '미달률_평균_실측']:
    mask_2014 = (df['연도'] == 2014) & df[col].isna()
    for sido_name in df.loc[mask_2014, '시도'].unique():
        v13 = df.loc[(df['시도'] == sido_name) & (df['연도'] == 2013), col].values
        v15 = df.loc[(df['시도'] == sido_name) & (df['연도'] == 2015), col].values
        if len(v13) and len(v15) and not (np.isnan(v13[0]) or np.isnan(v15[0])):
            df.loc[(df['시도'] == sido_name) & (df['연도'] == 2014), col] = (v13[0] + v15[0]) / 2

# 세종 누락 보정 (시도별 데이터에 세종 없음): 같은 연도 다른 시도 평균
for col in ['미달률_중_실측', '미달률_고_실측', '미달률_평균_실측']:
    miss = (df['시도'] == '세종') & df[col].isna() & df['연도'].between(2012, 2016)
    for yr in df.loc[miss, '연도'].unique():
        mean_val = df.loc[(df['연도'] == yr) & (df['시도'] != '세종'), col].mean()
        df.loc[(df['시도'] == '세종') & (df['연도'] == yr), col] = mean_val

# ── 5. 전국 미달률 병합 (2015-2024) ────────────────────────────
df = df.merge(nat_df, on='연도', how='left')

# ── 6. proxy_index 업데이트 ────────────────────────────────────
# baseline: 시도별 2015-2016 평균 미달률
baseline = (
    df[df['연도'].isin([2015, 2016])]
    .groupby('시도')['미달률_평균_실측']
    .mean()
    .rename('baseline')
    .reset_index()
)
df = df.merge(baseline, on='시도', how='left')

# 전국 2015-2016 평균
nat_base = nat_df.loc[nat_df['연도'].isin([2015, 2016]), '전국_미달률_평균'].mean()
df['전국_추세비율'] = df['전국_미달률_평균'] / nat_base

new_proxy = []
for _, row in df.iterrows():
    yr = row['연도']
    if 2012 <= yr <= 2016 and not pd.isna(row['미달률_평균_실측']):
        new_proxy.append(row['미달률_평균_실측'])           # 실측
    elif yr >= 2017 and not pd.isna(row['baseline']) and not pd.isna(row['전국_추세비율']):
        new_proxy.append(row['baseline'] * row['전국_추세비율'])  # baseline × 전국추세
    else:
        new_proxy.append(np.nan)
df['proxy_index_old'] = df['proxy_index']
df['proxy_index'] = np.round(new_proxy, 3)

# 구성 출처 표기
def source(yr, val):
    if pd.isna(val):
        return ''
    if 2012 <= yr <= 2013 or yr in (2015, 2016):
        return '시도별_실측'
    if yr == 2014:
        return '보간(2013/2015)'
    if yr >= 2017:
        return '시도baseline×전국추세'
    return ''
df['proxy_index_source'] = [source(y, v) for y, v in zip(df['연도'], df['proxy_index'])]

# 정리: 보조 컬럼 정리
df = df.drop(columns=['baseline', '전국_추세비율'])

# ── 7. 저장 & 요약 ──────────────────────────────────────────────
df.to_csv(OUT_CSV, index=False, encoding='utf-8-sig')
print(f'\n저장: {OUT_CSV}')
print()
print('[업데이트된 proxy_index 요약]')
print(df.groupby('연도')['proxy_index'].agg(['mean', 'min', 'max']).round(2))
print()
print('[시도별 proxy_index 미리보기 (서울/경기/세종)]')
print(df[df['시도'].isin(['서울', '경기', '세종'])][
    ['연도', '시도', 'proxy_index', 'proxy_index_old', 'proxy_index_source']
].to_string(index=False))
print()
print('[결측 확인]')
print(df.groupby('연도')['proxy_index'].apply(lambda s: s.isna().sum()))
