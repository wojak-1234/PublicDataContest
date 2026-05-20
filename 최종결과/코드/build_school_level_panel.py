"""
raw 폴더 데이터로 학교급별(초/중/고) 패널 구축
- 시도 × 학교급 × 연도 단위
- 학교급별 학업중단률·다문화 유형별·시설 정보
- 시도별 정책 변수는 동일 적용 (학력향상·누리·다문화·돌봄)
- 학교급별 위험도 지수 별도 학습 (중·고)
"""
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')

RAW = Path(r'C:/ai_contest2026/data/raw/proxy')
DATA = Path(r'C:/ai_contest2026/data')
OUT = Path(r'C:/ai_contest2026/out')

# 시도명 통일
SIDO_MAP = {
    '서울특별시':'서울','부산광역시':'부산','대구광역시':'대구','인천광역시':'인천',
    '광주광역시':'광주','대전광역시':'대전','울산광역시':'울산','세종특별자치시':'세종',
    '경기도':'경기','강원도':'강원','강원특별자치도':'강원','충청북도':'충북','충청남도':'충남',
    '전라북도':'전북','전북특별자치도':'전북','전라남도':'전남','경상북도':'경북','경상남도':'경남',
    '제주특별자치도':'제주','제주도':'제주',
}
def norm_sido(s):
    s = str(s).strip()
    return SIDO_MAP.get(s, s)

# ── raw CSV 로드 ─────────────────────────────────────────────
df01 = pd.read_csv(RAW/'01_학년별_학급수_학생수.csv', encoding='utf-8-sig')
df02 = pd.read_csv(RAW/'02_학생변동상황.csv', encoding='utf-8-sig')
df03 = pd.read_csv(RAW/'03_학업중단률_사유.csv', encoding='utf-8-sig')
df04 = pd.read_csv(RAW/'04_다문화_유형별_학생수.csv', encoding='utf-8-sig')
df05 = pd.read_csv(RAW/'05_유학생_유형별_학생수.csv', encoding='utf-8-sig')
df06 = pd.read_csv(RAW/'06_시설현황.csv', encoding='utf-8-sig')

for d in [df01, df02, df04, df06]:
    d['시도'] = d['시도'].apply(norm_sido)
df03['시도'] = df03['시도'].apply(norm_sido)
df05['시도'] = df05['시도'].apply(norm_sido)

# 03은 학년도+연도가 같이 있음. '연도'(데이터 시점)를 사용
df03 = df03.rename(columns={'학업중단률_전체':'학업중단률_급'})
df05 = df05.rename(columns={'해외출국_계':'해외출국_급'})

# 학제명 통일
def norm_grade(s):
    s = str(s).strip()
    if s in ['초등학교','초']: return '초'
    if s in ['중학교','중']: return '중'
    if s in ['고등학교','고']: return '고'
    return s
for d in [df01, df02, df03, df04, df05, df06]:
    d['학제'] = d['학제'].apply(norm_grade)

# ── 학교급별 핵심 변수 추출 ──────────────────────────────────
base = df01[['연도','시도','학제','학급수_계','학급수_특수','학생수_전체']].copy()
base = base.rename(columns={'학급수_계':'학급수','학생수_전체':'학생수'})

mc = df02[['연도','시도','학제','학업중단자_전체','자퇴_전체','전출_전체','전입_전체']].copy()
base = base.merge(mc, on=['연도','시도','학제'], how='left')

dr = df03[['연도','시도','학제','학업중단률_급']].copy()
base = base.merge(dr, on=['연도','시도','학제'], how='left')

mu = df04[['연도','시도','학제','다문화학생_계','국제결혼_국내출생_전체',
           '국제결혼_중도입국_전체','외국인가정_전체']].copy()
base = base.merge(mu, on=['연도','시도','학제'], how='left')

oh = df05[['연도','시도','학제','해외출국_급']].copy()
base = base.merge(oh, on=['연도','시도','학제'], how='left')

fc = df06[['연도','시도','학제','학생1인당_교지면적','학생1인당_건물면적',
           '일반교실수','교과교실수','특별교실수']].copy()
base = base.merge(fc, on=['연도','시도','학제'], how='left')

# 파생 비율
base['학급당_학생수_급'] = base['학생수'] / base['학급수']
base['특수학급_비율_급'] = base['학급수_특수'] / base['학급수'] * 100
base['다문화_비율_급'] = base['다문화학생_계'] / base['학생수'] * 100
base['중도입국_비율_급'] = base['국제결혼_중도입국_전체'] / base['학생수'] * 100
base['외국인가정_비율_급'] = base['외국인가정_전체'] / base['학생수'] * 100
base['해외출국_비율_급'] = base['해외출국_급'] / base['학생수'] * 100
base['자퇴_비율_급'] = base['자퇴_전체'] / base['학생수'] * 100
base['교실_학생당'] = (base['일반교실수']+base['교과교실수']+base['특별교실수']) / base['학생수'] * 1000

# 세종 제외
base = base[base['시도'] != '세종'].copy()
print(f'학교급별 기본 패널: {base.shape} (시도×학교급×연도)')
print(f'학제 분포: {base["학제"].value_counts().to_dict()}')

# ── 시도 단위 정책·환경 변수 v6에서 가져오기 ───────────────────
v6 = pd.read_csv(r'C:/ai_contest2026/통합_proxy_dataset_v6.csv', encoding='utf-8-sig')
v6 = v6[v6['시도']!='세종']
sido_vars = ['연도','시도','GRDP_1인당','사교육_참여율','사교육비_1인당_만원','교원1인당_학생수',
             '학력향상_억원','학력향상_세출비중','학력향상_학생당_천원',
             '누리과정_억원','누리과정_학생당_천원','누리과정_세출비중',
             '다문화이탈주민_억원','다문화이탈주민_학생당_천원','다문화이탈주민_세출비중',
             '돌봄교실_억원','돌봄교실_학생당_천원','돌봄교실_세출비중',
             '미달률_중_실측','미달률_고_실측']
v6_sido = v6[sido_vars].drop_duplicates()
panel = base.merge(v6_sido, on=['연도','시도'], how='left')

# 학교급별 종속변수 매핑 (중/고만 실측 가용)
panel['실측미달률'] = np.where(panel['학제']=='중', panel['미달률_중_실측'],
                       np.where(panel['학제']=='고', panel['미달률_고_실측'], np.nan))

# ── 학교급별 위험도 지수 학습 (Ridge, 학교급마다 별도) ────────
GRADE_FEATURES = [
    '학업중단률_급','자퇴_비율_급',
    '다문화_비율_급','중도입국_비율_급','외국인가정_비율_급','해외출국_비율_급',
    '학급당_학생수_급','특수학급_비율_급',
    '사교육_참여율','사교육비_1인당_만원','GRDP_1인당','교원1인당_학생수',
    '학생1인당_교지면적','학생1인당_건물면적',
]

panel = panel.sort_values(['시도','학제','연도']).reset_index(drop=True)
# GRDP 결측 처리
panel['GRDP_1인당'] = panel.groupby('시도')['GRDP_1인당'].ffill()

risk_models = {}
for grade in ['중','고']:
    sub = panel[panel['학제']==grade].copy()
    train = sub[sub['실측미달률'].notna()].copy()
    print(f'\n[{grade}학교] 학습 obs: {len(train)} (2012-2016)')
    X = train[GRADE_FEATURES].values
    y = train['실측미달률'].values
    # 결측 행 제거
    mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
    X, y = X[mask], y[mask]
    print(f'  결측제거 후: {len(y)} obs')

    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    model = RidgeCV(alphas=np.logspace(-2,3,30), cv=5).fit(Xs, y)
    print(f'  α={model.alpha_:.2f}, In-sample R²={model.score(Xs,y):.3f}')

    coef = pd.DataFrame({'변수':GRADE_FEATURES, '표준화_계수':np.round(model.coef_,3)})
    coef = coef.sort_values('표준화_계수', key=lambda s:-s.abs())
    print('  주요 계수:')
    print(coef.head(8).to_string(index=False))

    # 전 기간 예측
    sub_X = sub[GRADE_FEATURES].copy()
    # 결측은 시도별 ffill/bfill
    for c in GRADE_FEATURES:
        sub_X[c] = sub.groupby('시도')[c].transform(lambda s: s.ffill().bfill())
    sub_X_arr = sub_X.values
    valid = ~np.isnan(sub_X_arr).any(axis=1)
    pred = np.full(len(sub_X_arr), np.nan)
    pred[valid] = model.predict(scaler.transform(sub_X_arr[valid]))
    pred = np.clip(pred, 0, None)
    sub[f'위험도_pct'] = np.round(pred, 3)
    risk_models[grade] = (model, scaler, sub)

# 학교급별 위험도를 다시 panel에 합치기
panel['위험도_pct'] = np.nan
for grade in ['중','고']:
    sub = risk_models[grade][2]
    panel.loc[panel['학제']==grade, '위험도_pct'] = sub['위험도_pct'].values

# 0-100 정규화 (중·고 통합 분포 기준)
mid_high = panel[panel['학제'].isin(['중','고'])].copy()
mn = mid_high['위험도_pct'].min()
mx = mid_high['위험도_pct'].max()
panel['위험도_점수'] = np.round(100*(panel['위험도_pct']-mn)/(mx-mn), 2)

# ── 저장 ──
panel.to_csv(r'C:/ai_contest2026/통합_proxy_dataset_v8_학교급.csv',
             index=False, encoding='utf-8-sig')
print(f'\nv8(학교급별) dataset 저장')
print(f'  obs: {len(panel)}, 시도-학제-연도 단위')
print(f'  중/고 obs (위험도 산출됨): {panel[panel["학제"].isin(["중","고"])].shape[0]}')

# 요약 출력
print('\n[중학교 vs 고등학교 위험도 점수, 시도별 2024]')
view = panel[(panel['연도']==2024) & (panel['학제'].isin(['중','고']))].pivot_table(
    index='시도', columns='학제', values='위험도_점수')
print(view.round(2).to_string())
