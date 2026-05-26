"""
부산 기초학력미달 정책 효과 예측 모델
=====================================
전체 파이프라인: 데이터 로딩 → Proxy Index 구축 → 모델 학습 → 예측 → 시뮬레이션

사용법:
1. data/raw/ 폴더에 CSV 파일들을 넣고
2. python pipeline.py 실행
3. 또는 각 단계를 Jupyter Notebook에서 개별 실행
"""

import os
import json
import warnings
import numpy as np
import pandas as pd
from pathlib import Path
from sklearn.model_selection import KFold, cross_val_score
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import r2_score, mean_squared_error, mean_absolute_error
from scipy import stats
import xgboost as xgb
import shap
import joblib

warnings.filterwarnings("ignore")

# ============================================================
# 0. 설정 & 경로
# ============================================================

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
MODEL_DIR = BASE_DIR / "models"
OUTPUT_DIR = BASE_DIR / "outputs"

for d in [RAW_DIR, PROCESSED_DIR, MODEL_DIR, OUTPUT_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# 17개 시도 목록
REGIONS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주"
]

# ============================================================
# 1. 데이터 로딩 & 전처리
# ============================================================

class DataLoader:
    """
    CSV 파일들을 로딩하고 하나의 통합 데이터셋으로 합치는 클래스.
    
    기대하는 CSV 형식:
    - 모든 CSV에 'year'(연도)와 'region'(시도명) 컬럼 필수
    - 나머지 컬럼은 해당 지표의 값
    
    예시 (학업중단율.csv):
    year, region, dropout_rate_mid, dropout_rate_high
    2015, 서울,   0.8,              1.2
    2015, 부산,   0.9,              1.5
    ...
    """
    
    def __init__(self, raw_dir: Path = RAW_DIR):
        self.raw_dir = raw_dir
    
    def load_single_csv(self, filepath: str) -> pd.DataFrame:
        """단일 CSV 파일 로딩 + 기본 정제"""
        df = pd.read_csv(filepath, encoding="utf-8")
        
        # 컬럼명 공백 제거
        df.columns = df.columns.str.strip()
        
        # year, region 필수 확인
        assert "year" in df.columns, f"'year' 컬럼이 없습니다: {filepath}"
        assert "region" in df.columns, f"'region' 컬럼이 없습니다: {filepath}"
        
        # region 공백 제거
        df["region"] = df["region"].str.strip()
        
        return df
    
    def load_all_csvs(self) -> pd.DataFrame:
        """raw/ 폴더의 모든 CSV를 로딩하고 year+region 기준으로 병합"""
        csv_files = list(self.raw_dir.glob("**/*.csv"))
        
        if not csv_files:
            print(f"⚠️  {self.raw_dir}에 CSV 파일이 없습니다.")
            print("   샘플 데이터를 생성합니다...")
            return self._generate_sample_data()
        
        print(f"📂 {len(csv_files)}개 CSV 파일 발견:")
        
        merged = None
        for f in csv_files:
            print(f"   ├── {f.name}")
            df = self.load_single_csv(str(f))
            
            if merged is None:
                merged = df
            else:
                # year + region 기준으로 outer join
                merged = pd.merge(merged, df, on=["year", "region"], how="outer")
        
        print(f"✅ 통합 완료: {merged.shape[0]}행 × {merged.shape[1]}열")
        return merged
    
    def _generate_sample_data(self) -> pd.DataFrame:
        """
        실제 데이터가 없을 때 테스트용 샘플 데이터 생성.
        실제 통계와 유사한 범위의 값을 사용합니다.
        *** 실제 데이터 수집 후 이 함수는 사용하지 마세요! ***
        """
        np.random.seed(42)
        years = range(2015, 2024)
        rows = []
        
        for year in years:
            for i, region in enumerate(REGIONS):
                # 지역별 기본 특성 (시드값)
                base = {
                    "서울": 0, "부산": 1, "대구": 2, "인천": 3, "광주": 4,
                    "대전": 5, "울산": 6, "세종": 7, "경기": 8, "강원": 9,
                    "충북": 10, "충남": 11, "전북": 12, "전남": 13,
                    "경북": 14, "경남": 15, "제주": 16
                }
                b = base[region]
                yr_effect = (year - 2015) * 0.1  # 연도 효과
                
                row = {
                    "year": year,
                    "region": region,
                    
                    # --- 1등급 Proxy 변수 ---
                    # 학업성취 미흡비율 (%) : 5~25% 범위
                    "achievement_low_rate": max(3, 8 + b * 0.8 + np.random.normal(0, 2) - yr_effect * 0.5),
                    
                    # 교육급여 수급 학생 비율 (%) : 1~8%
                    "edu_subsidy_rate": max(0.5, 2 + b * 0.3 + np.random.normal(0, 0.5)),
                    
                    # 교육복지우선지원 학교 비율 (%) : 3~20%
                    "welfare_school_rate": max(1, 5 + b * 0.7 + np.random.normal(0, 1.5)),
                    
                    # --- 2등급 Proxy 변수 ---
                    # 특수교육대상학생 비율 (%)
                    "special_edu_rate": max(0.5, 1.5 + b * 0.1 + np.random.normal(0, 0.3)),
                    
                    # 학교폭력 피해응답률 (%)
                    "school_violence_rate": max(0.2, 1.0 + b * 0.05 + np.random.normal(0, 0.3) - yr_effect * 0.1),
                    
                    # --- 3등급 Proxy 변수 ---
                    # 사교육 참여율 (%)
                    "private_edu_rate": max(50, 80 - b * 1.5 + np.random.normal(0, 3)),
                    
                    # 교원 1인당 학생수
                    "student_per_teacher": max(8, 12 + b * 0.3 + np.random.normal(0, 1) - yr_effect * 0.3),
                    
                    # 학급당 학생수
                    "student_per_class": max(15, 24 + b * 0.2 + np.random.normal(0, 1.5) - yr_effect * 0.4),
                    
                    # 다문화학생 비율 (%)
                    "multicultural_rate": max(0.5, 2 + b * 0.15 + np.random.normal(0, 0.5) + yr_effect * 0.3),
                    
                    # 학업중단율 (%)
                    "dropout_rate_mid": max(0.3, 0.7 + b * 0.05 + np.random.normal(0, 0.1)),
                    "dropout_rate_high": max(0.5, 1.5 + b * 0.08 + np.random.normal(0, 0.2)),
                    
                    # --- 정책 변수 (X) ---
                    # 기초학력 관련 예산 (억원)
                    "budget_basic_lit": max(10, 100 - b * 4 + np.random.normal(0, 10) + yr_effect * 5),
                    
                    # 협력수업 운영 학교 수
                    "coop_teaching_schools": max(5, int(80 - b * 3 + np.random.normal(0, 10) + yr_effect * 8)),
                    
                    # 학습지원 튜터 수
                    "tutor_count": max(10, int(200 - b * 8 + np.random.normal(0, 20) + yr_effect * 10)),
                    
                    # 다중지원팀 운영 학교 수 (2020년부터)
                    "multi_support_schools": max(0, int((year - 2019) * 5 - b * 0.5 + np.random.normal(0, 3))) if year >= 2020 else 0,
                    
                    # AI 학습 프로그램 도입 (0 or 1, 2021년부터)
                    "ai_program": 1 if (year >= 2021 and np.random.random() > 0.3 - b * 0.02) else 0,
                    
                    # --- 통제 변수 ---
                    # 1인당 GRDP (만원)
                    "grdp_per_capita": max(2000, 4000 - b * 100 + np.random.normal(0, 200) + yr_effect * 50),
                    
                    # 인구밀도 (명/km²)
                    "pop_density": max(50, 5000 - b * 280 + np.random.normal(0, 200)),
                    
                    # 재정자립도 (%)
                    "fiscal_independence": max(15, 60 - b * 2.5 + np.random.normal(0, 3)),
                }
                
                rows.append(row)
        
        df = pd.DataFrame(rows)
        
        # 샘플 데이터 저장
        sample_path = RAW_DIR / "_sample_data.csv"
        df.to_csv(sample_path, index=False, encoding="utf-8-sig")
        print(f"📝 샘플 데이터 저장: {sample_path}")
        print(f"   ⚠️  이것은 테스트용 가상 데이터입니다!")
        print(f"   ⚠️  실제 KOSIS/KESS 데이터로 교체하세요.")
        
        return df


def preprocess(df: pd.DataFrame) -> pd.DataFrame:
    """결측치 처리 + 이상치 제거 + 비율 변수 클리핑"""
    
    print("\n🔧 전처리 시작...")
    print(f"   원본: {df.shape[0]}행 × {df.shape[1]}열")
    
    # 1) 수치형 컬럼만 추출
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    numeric_cols = [c for c in numeric_cols if c != "year"]
    
    # 2) 결측치 처리: 같은 지역의 시계열 보간 → 나머지는 해당 연도 평균
    for col in numeric_cols:
        # 지역별 시계열 보간
        df[col] = df.groupby("region")[col].transform(
            lambda x: x.interpolate(method="linear", limit_direction="both")
        )
        # 남은 결측치는 해당 연도 전체 평균
        df[col] = df.groupby("year")[col].transform(
            lambda x: x.fillna(x.mean())
        )
    
    # 3) 비율 변수 클리핑 (0~100%)
    rate_cols = [c for c in numeric_cols if "rate" in c]
    for col in rate_cols:
        df[col] = df[col].clip(0, 100)
    
    missing_count = df[numeric_cols].isna().sum().sum()
    print(f"   결측치 처리 후 남은 결측: {missing_count}개")
    print(f"✅ 전처리 완료: {df.shape[0]}행 × {df.shape[1]}열")
    
    return df


# ============================================================
# 2. Proxy Index 구축
# ============================================================

class ProxyIndexBuilder:
    """
    기초학력미달 비율의 Proxy Index를 구축합니다.
    
    방법: 등급별 가중 합산
    - 1등급 변수: 가중치 높음
    - 2등급 변수: 가중치 중간
    - 3등급 변수: 가중치 낮음
    
    모든 변수는 표준화 후 합산하여 0~100 스케일로 변환합니다.
    """
    
    # 변수 등급 및 방향 정의
    # direction: "positive" = 값이 클수록 기초학력미달 위험 ↑
    #            "negative" = 값이 클수록 기초학력미달 위험 ↓
    VARIABLE_CONFIG = {
        # 1등급: 핵심 proxy
        "achievement_low_rate":  {"tier": 1, "direction": "positive", "weight": 3.0},
        "edu_subsidy_rate":      {"tier": 1, "direction": "positive", "weight": 2.5},
        "welfare_school_rate":   {"tier": 1, "direction": "positive", "weight": 2.0},
        
        # 2등급: 유의미한 관련
        "special_edu_rate":      {"tier": 2, "direction": "positive", "weight": 1.5},
        "school_violence_rate":  {"tier": 2, "direction": "positive", "weight": 1.0},
        
        # 3등급: 보조
        "private_edu_rate":      {"tier": 3, "direction": "negative", "weight": 0.5},
        "student_per_teacher":   {"tier": 3, "direction": "positive", "weight": 0.5},
        "student_per_class":     {"tier": 3, "direction": "positive", "weight": 0.3},
        "multicultural_rate":    {"tier": 3, "direction": "positive", "weight": 0.3},
        "dropout_rate_mid":      {"tier": 3, "direction": "positive", "weight": 0.2},
        "dropout_rate_high":     {"tier": 3, "direction": "positive", "weight": 0.2},
    }
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.available_vars = []
        self.weights = []
    
    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Proxy Index를 계산하여 'proxy_index' 컬럼을 추가"""
        
        print("\n📊 Proxy Index 구축...")
        
        # 데이터에 존재하는 변수만 사용
        self.available_vars = [v for v in self.VARIABLE_CONFIG if v in df.columns]
        missing_vars = [v for v in self.VARIABLE_CONFIG if v not in df.columns]
        
        if missing_vars:
            print(f"   ⚠️  누락 변수 ({len(missing_vars)}개): {missing_vars}")
        print(f"   사용 변수 ({len(self.available_vars)}개): {self.available_vars}")
        
        if not self.available_vars:
            raise ValueError("Proxy Index를 구축할 변수가 하나도 없습니다!")
        
        # 1) 표준화
        values = df[self.available_vars].values
        scaled = self.scaler.fit_transform(values)
        
        # 2) 방향 조정 (negative 방향 변수는 부호 반전)
        for i, var in enumerate(self.available_vars):
            config = self.VARIABLE_CONFIG[var]
            if config["direction"] == "negative":
                scaled[:, i] *= -1
        
        # 3) 가중 합산
        self.weights = np.array([
            self.VARIABLE_CONFIG[v]["weight"] for v in self.available_vars
        ])
        weighted_sum = scaled @ self.weights
        
        # 4) 0~100 스케일로 변환
        min_val, max_val = weighted_sum.min(), weighted_sum.max()
        if max_val > min_val:
            proxy_index = (weighted_sum - min_val) / (max_val - min_val) * 100
        else:
            proxy_index = np.full_like(weighted_sum, 50.0)
        
        df = df.copy()
        df["proxy_index"] = np.round(proxy_index, 2)
        
        print(f"   Proxy Index 범위: {df['proxy_index'].min():.1f} ~ {df['proxy_index'].max():.1f}")
        print(f"   부산 최근 Proxy Index: {df[df['region'] == '부산']['proxy_index'].iloc[-1]:.1f}")
        print(f"✅ Proxy Index 구축 완료")
        
        return df
    
    def validate(self, df: pd.DataFrame, actual_col: str = None) -> dict:
        """
        Proxy Index의 타당성을 검증합니다.
        
        actual_col이 제공되면 (2016년 이전 실제 기초학력미달 비율),
        상관분석으로 proxy의 설명력을 확인합니다.
        """
        results = {}
        
        print("\n🔍 Proxy Index 검증...")
        
        # 1) 기본 통계
        by_region = df.groupby("region")["proxy_index"].mean().sort_values()
        results["region_ranking"] = by_region.to_dict()
        print(f"   지역별 평균 Proxy Index (낮을수록 양호):")
        for region, val in by_region.items():
            marker = " ◀ 부산" if region == "부산" else ""
            print(f"     {region:4s}: {val:5.1f}{marker}")
        
        # 2) 실제 기초학력미달 데이터가 있으면 상관분석
        if actual_col and actual_col in df.columns:
            valid = df.dropna(subset=[actual_col, "proxy_index"])
            if len(valid) > 5:
                corr, p_value = stats.pearsonr(valid["proxy_index"], valid[actual_col])
                r_squared = corr ** 2
                results["correlation"] = round(corr, 4)
                results["r_squared"] = round(r_squared, 4)
                results["p_value"] = round(p_value, 6)
                
                print(f"\n   📈 실제 기초학력미달 비율과의 상관분석:")
                print(f"     상관계수 (r): {corr:.4f}")
                print(f"     결정계수 (R²): {r_squared:.4f}")
                print(f"     p-value: {p_value:.6f}")
                
                if corr > 0.7:
                    print(f"     ✅ 강한 양의 상관 → Proxy로 충분히 신뢰 가능")
                elif corr > 0.4:
                    print(f"     ⚠️  중간 정도의 상관 → 추가 변수 고려 필요")
                else:
                    print(f"     ❌ 약한 상관 → Proxy 변수 재설계 필요")
        
        # 3) 각 변수별 기여도
        print(f"\n   변수별 가중치:")
        for var, w in zip(self.available_vars, self.weights):
            config = self.VARIABLE_CONFIG[var]
            tier = config["tier"]
            print(f"     [{tier}등급] {var:30s} 가중치: {w:.1f}")
        
        return results


# ============================================================
# 3. 모델 학습
# ============================================================

class PolicyEffectModel:
    """
    정책 변수 + 지역 특성 → Proxy Index 변화량을 예측하는 모델.
    
    핵심 아이디어:
    - Y = 해당 연도 proxy_index - 전년도 proxy_index (변화량)
    - X = 정책 변수 + 지역 특성 변수
    - 부산에 타 지역 정책을 적용했을 때의 변화량을 예측
    """
    
    # 정책 변수 (독립변수)
    POLICY_FEATURES = [
        "budget_basic_lit",
        "coop_teaching_schools",
        "tutor_count",
        "multi_support_schools",
        "ai_program",
    ]
    
    # 지역 특성 변수 (통제변수)
    CONTROL_FEATURES = [
        "grdp_per_capita",
        "pop_density",
        "fiscal_independence",
    ]
    
    def __init__(self):
        self.model = None
        self.feature_names = []
        self.scaler = StandardScaler()
        self.metrics = {}
    
    def prepare_data(self, df: pd.DataFrame) -> tuple:
        """
        학습 데이터 준비:
        - Y: proxy_index의 전년 대비 변화량
        - X: 정책 변수 + 지역 특성 + 현재 proxy_index
        """
        
        print("\n📐 학습 데이터 준비...")
        
        # 사용 가능한 feature 확인
        available_policy = [f for f in self.POLICY_FEATURES if f in df.columns]
        available_control = [f for f in self.CONTROL_FEATURES if f in df.columns]
        
        print(f"   정책 변수: {available_policy}")
        print(f"   통제 변수: {available_control}")
        
        # proxy_index의 전년 대비 변화량 계산
        df = df.sort_values(["region", "year"]).copy()
        df["proxy_index_prev"] = df.groupby("region")["proxy_index"].shift(1)
        df["proxy_index_change"] = df["proxy_index"] - df["proxy_index_prev"]
        
        # 첫 연도는 변화량 계산 불가 → 제거
        df = df.dropna(subset=["proxy_index_change"])
        
        # Feature 구성: 정책 + 통제 + 현재 proxy
        self.feature_names = available_policy + available_control + ["proxy_index_prev"]
        
        missing_features = [f for f in self.feature_names if f not in df.columns]
        if missing_features:
            raise ValueError(f"누락된 feature: {missing_features}")
        
        X = df[self.feature_names].values
        y = df["proxy_index_change"].values
        regions = df["region"].values
        years = df["year"].values
        
        # 결측치 제거
        valid_mask = ~(np.isnan(X).any(axis=1) | np.isnan(y))
        X = X[valid_mask]
        y = y[valid_mask]
        regions = regions[valid_mask]
        years = years[valid_mask]
        
        print(f"   학습 데이터: {X.shape[0]}개 샘플, {X.shape[1]}개 feature")
        print(f"   Y(변화량) 범위: {y.min():.2f} ~ {y.max():.2f}")
        
        return X, y, regions, years, df
    
    def train(self, X: np.ndarray, y: np.ndarray) -> dict:
        """XGBoost 모델 학습 + 교차검증"""
        
        print("\n🤖 모델 학습 시작...")
        
        # 스케일링
        X_scaled = self.scaler.fit_transform(X)
        
        # XGBoost 하이퍼파라미터
        self.model = xgb.XGBRegressor(
            n_estimators=200,
            max_depth=4,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.1,
            reg_lambda=1.0,
            random_state=42,
            verbosity=0,
        )
        
        # 5-Fold 교차검증
        kf = KFold(n_splits=5, shuffle=True, random_state=42)
        cv_scores = cross_val_score(self.model, X_scaled, y, cv=kf, scoring="r2")
        cv_rmse = cross_val_score(
            self.model, X_scaled, y, cv=kf,
            scoring="neg_root_mean_squared_error"
        )
        
        print(f"   5-Fold CV R²: {cv_scores.mean():.4f} (±{cv_scores.std():.4f})")
        print(f"   5-Fold CV RMSE: {-cv_rmse.mean():.4f} (±{cv_rmse.std():.4f})")
        
        # 전체 데이터로 최종 학습
        self.model.fit(X_scaled, y)
        
        # 전체 데이터 성능
        y_pred = self.model.predict(X_scaled)
        self.metrics = {
            "r2": round(r2_score(y, y_pred), 4),
            "rmse": round(np.sqrt(mean_squared_error(y, y_pred)), 4),
            "mae": round(mean_absolute_error(y, y_pred), 4),
            "cv_r2_mean": round(cv_scores.mean(), 4),
            "cv_r2_std": round(cv_scores.std(), 4),
            "cv_rmse_mean": round(-cv_rmse.mean(), 4),
            "n_samples": len(y),
            "n_features": X.shape[1],
        }
        
        print(f"\n   📊 최종 모델 성능:")
        print(f"     R²:   {self.metrics['r2']}")
        print(f"     RMSE: {self.metrics['rmse']}")
        print(f"     MAE:  {self.metrics['mae']}")
        print(f"✅ 모델 학습 완료")
        
        return self.metrics
    
    def analyze_shap(self, X: np.ndarray) -> dict:
        """SHAP 분석: 각 정책 변수의 기여도 계산"""
        
        print("\n🔬 SHAP 분석...")
        
        X_scaled = self.scaler.transform(X)
        explainer = shap.TreeExplainer(self.model)
        shap_values = explainer.shap_values(X_scaled)
        
        # 변수별 평균 절대 SHAP value
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        importance = {
            self.feature_names[i]: round(float(mean_abs_shap[i]), 4)
            for i in range(len(self.feature_names))
        }
        
        # 중요도 순 정렬
        importance = dict(sorted(importance.items(), key=lambda x: x[1], reverse=True))
        
        print(f"   변수 중요도 (평균 |SHAP|):")
        for feat, val in importance.items():
            bar = "█" * int(val * 20 / max(importance.values())) if max(importance.values()) > 0 else ""
            print(f"     {feat:30s} {val:.4f} {bar}")
        
        print(f"✅ SHAP 분석 완료")
        
        return {
            "importance": importance,
            "shap_values": shap_values,
            "feature_names": self.feature_names,
        }
    
    def save(self, path: Path = None):
        """모델 저장"""
        if path is None:
            path = MODEL_DIR / "model.pkl"
        
        save_data = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "metrics": self.metrics,
        }
        joblib.dump(save_data, path)
        print(f"\n💾 모델 저장: {path}")
    
    @classmethod
    def load(cls, path: Path = None) -> "PolicyEffectModel":
        """저장된 모델 로딩"""
        if path is None:
            path = MODEL_DIR / "model.pkl"
        
        save_data = joblib.load(path)
        instance = cls()
        instance.model = save_data["model"]
        instance.scaler = save_data["scaler"]
        instance.feature_names = save_data["feature_names"]
        instance.metrics = save_data["metrics"]
        
        print(f"📂 모델 로딩: {path}")
        return instance


# ============================================================
# 4. 정책 시뮬레이션 (예측)
# ============================================================

class PolicySimulator:
    """
    타 지역 정책을 부산에 적용했을 때의 효과를 시뮬레이션합니다.
    
    사용법:
        simulator = PolicySimulator(model, df)
        result = simulator.simulate(
            source_region="서울",
            policy_overrides={"coop_teaching_schools": 300}
        )
    """
    
    def __init__(self, model: PolicyEffectModel, df: pd.DataFrame):
        self.model = model
        self.df = df
        self.busan_latest = self._get_latest_data("부산")
    
    def _get_latest_data(self, region: str) -> dict:
        """해당 지역의 최신 연도 데이터 반환"""
        region_df = self.df[self.df["region"] == region]
        if region_df.empty:
            raise ValueError(f"'{region}' 지역 데이터가 없습니다.")
        latest = region_df.sort_values("year").iloc[-1]
        return latest.to_dict()
    
    def simulate(
        self,
        source_region: str = None,
        policy_overrides: dict = None,
    ) -> dict:
        """
        부산에 정책을 적용했을 때의 효과 예측.
        
        Args:
            source_region: 참조할 타 지역 (해당 지역의 정책 수치를 가져옴)
            policy_overrides: 직접 지정할 정책 수치 (source_region보다 우선)
        
        Returns:
            예측 결과 딕셔너리
        """
        
        # 1) 부산 기본 데이터 복사
        busan = self.busan_latest.copy()
        
        # 2) 타 지역 정책 적용
        source_data = None
        if source_region:
            source_data = self._get_latest_data(source_region)
            for feat in self.model.POLICY_FEATURES:
                if feat in source_data:
                    busan[feat] = source_data[feat]
        
        # 3) 직접 지정 값으로 오버라이드
        if policy_overrides:
            busan.update(policy_overrides)
        
        # 4) feature 벡터 구성
        X = np.array([[busan.get(f, 0) for f in self.model.feature_names]])
        X_scaled = self.model.scaler.transform(X)
        
        # 5) 예측
        predicted_change = float(self.model.model.predict(X_scaled)[0])
        current_proxy = self.busan_latest.get("proxy_index", 50)
        predicted_proxy = current_proxy + predicted_change
        predicted_proxy = max(0, min(100, predicted_proxy))
        
        # 6) SHAP 기여도 (이 예측에 대한)
        explainer = shap.TreeExplainer(self.model.model)
        shap_values = explainer.shap_values(X_scaled)[0]
        
        feature_contributions = {
            self.model.feature_names[i]: round(float(shap_values[i]), 4)
            for i in range(len(self.model.feature_names))
        }
        feature_contributions = dict(
            sorted(feature_contributions.items(), key=lambda x: abs(x[1]), reverse=True)
        )
        
        # 7) 비교 데이터 구성
        comparison = [
            {
                "region": "부산(현재)",
                "proxy_index": round(current_proxy, 2),
                **{f: round(self.busan_latest.get(f, 0), 1) for f in self.model.POLICY_FEATURES if f in self.busan_latest}
            },
        ]
        
        if source_region and source_data:
            source_proxy = source_data.get("proxy_index", 0)
            comparison.append({
                "region": source_region,
                "proxy_index": round(source_proxy, 2),
                **{f: round(source_data.get(f, 0), 1) for f in self.model.POLICY_FEATURES if f in source_data}
            })
        
        comparison.append({
            "region": "부산(예측)",
            "proxy_index": round(predicted_proxy, 2),
            **{f: round(busan.get(f, 0), 1) for f in self.model.POLICY_FEATURES if f in busan}
        })
        
        # 8) 전체 시도 차트 데이터
        chart_data = []
        for region in REGIONS:
            region_df = self.df[self.df["region"] == region]
            if not region_df.empty:
                latest = region_df.sort_values("year").iloc[-1]
                chart_data.append({
                    "name": region,
                    "value": round(latest.get("proxy_index", 0), 2),
                })
        chart_data.append({
            "name": "부산(예측)",
            "value": round(predicted_proxy, 2),
        })
        chart_data.sort(key=lambda x: x["value"])
        
        result = {
            "prediction": {
                "current_proxy": round(current_proxy, 2),
                "predicted_proxy": round(predicted_proxy, 2),
                "change": round(predicted_change, 2),
                "change_pct": round(predicted_change / current_proxy * 100, 2) if current_proxy != 0 else 0,
            },
            "comparison": comparison,
            "chart_data": chart_data,
            "shap_contributions": feature_contributions,
            "source_region": source_region,
        }
        
        return result
    
    def simulate_all_regions(self) -> list:
        """모든 시도의 정책을 부산에 적용했을 때의 효과를 일괄 비교"""
        
        print("\n🔄 전체 시도 정책 시뮬레이션...")
        
        results = []
        for region in REGIONS:
            if region == "부산":
                continue
            try:
                result = self.simulate(source_region=region)
                results.append({
                    "source_region": region,
                    "predicted_change": result["prediction"]["change"],
                    "predicted_proxy": result["prediction"]["predicted_proxy"],
                    "change_pct": result["prediction"]["change_pct"],
                })
            except Exception as e:
                print(f"   ⚠️  {region} 시뮬레이션 실패: {e}")
        
        results.sort(key=lambda x: x["predicted_change"])
        
        print(f"\n   📊 시뮬레이션 결과 (부산에 적용 시 Proxy Index 변화량):")
        print(f"   {'지역':6s} {'변화량':>8s} {'변화율':>8s} {'예측 Proxy':>10s}")
        print(f"   {'─' * 36}")
        for r in results:
            direction = "↓" if r["predicted_change"] < 0 else "↑"
            print(
                f"   {r['source_region']:6s} "
                f"{r['predicted_change']:>+7.2f} "
                f"{r['change_pct']:>+7.2f}% "
                f"{r['predicted_proxy']:>9.2f} {direction}"
            )
        
        return results
    
    def format_for_api(self, result: dict) -> dict:
        """
        시뮬레이션 결과를 프론트엔드 API 응답 형식으로 변환.
        이 형식이 React 프론트엔드의 /api/chat 응답과 동일합니다.
        """
        
        return {
            "prediction": result["prediction"],
            "comparison": result["comparison"],
            "chart_data": result["chart_data"],
            "shap_values": [
                {"feature": k, "importance": abs(v)}
                for k, v in result["shap_contributions"].items()
            ],
        }


# ============================================================
# 5. 메인 파이프라인
# ============================================================

def run_pipeline():
    """전체 파이프라인 실행"""
    
    print("=" * 60)
    print("  부산 기초학력미달 정책 효과 예측 모델")
    print("  전체 파이프라인 실행")
    print("=" * 60)
    
    # --- Step 1: 데이터 로딩 ---
    loader = DataLoader()
    df = loader.load_all_csvs()
    
    # --- Step 2: 전처리 ---
    df = preprocess(df)
    
    # --- Step 3: Proxy Index 구축 ---
    proxy_builder = ProxyIndexBuilder()
    df = proxy_builder.build(df)
    
    # Proxy 검증 (실제 기초학력미달 데이터가 있으면)
    actual_col = "actual_underachieve_rate"  # 2016년 이전 데이터 컬럼명
    proxy_builder.validate(df, actual_col if actual_col in df.columns else None)
    
    # 전처리된 데이터 저장
    processed_path = PROCESSED_DIR / "merged_dataset.csv"
    df.to_csv(processed_path, index=False, encoding="utf-8-sig")
    print(f"\n💾 전처리 데이터 저장: {processed_path}")
    
    # --- Step 4: 모델 학습 ---
    model = PolicyEffectModel()
    X, y, regions, years, df_with_change = model.prepare_data(df)
    metrics = model.train(X, y)
    
    # SHAP 분석
    shap_results = model.analyze_shap(X)
    
    # 모델 저장
    model.save()
    
    # --- Step 5: 시뮬레이션 ---
    simulator = PolicySimulator(model, df)
    
    # 5-1: 전체 시도 일괄 시뮬레이션
    all_results = simulator.simulate_all_regions()
    
    # 5-2: 개별 시뮬레이션 예시
    print("\n" + "=" * 60)
    print("  개별 시뮬레이션 예시")
    print("=" * 60)
    
    # 예시 1: 서울 정책 적용
    result_seoul = simulator.simulate(source_region="서울")
    print(f"\n📍 서울 정책 → 부산 적용:")
    print(f"   현재 Proxy: {result_seoul['prediction']['current_proxy']}")
    print(f"   예측 Proxy: {result_seoul['prediction']['predicted_proxy']}")
    print(f"   변화량: {result_seoul['prediction']['change']:+.2f} ({result_seoul['prediction']['change_pct']:+.2f}%)")
    
    # 예시 2: 직접 정책 수치 지정
    result_custom = simulator.simulate(
        policy_overrides={
            "coop_teaching_schools": 500,  # 협력수업 학교를 500개로
            "tutor_count": 1000,           # 튜터를 1000명으로
        }
    )
    print(f"\n📍 커스텀 정책 (협력수업 500교 + 튜터 1000명) → 부산:")
    print(f"   현재 Proxy: {result_custom['prediction']['current_proxy']}")
    print(f"   예측 Proxy: {result_custom['prediction']['predicted_proxy']}")
    print(f"   변화량: {result_custom['prediction']['change']:+.2f} ({result_custom['prediction']['change_pct']:+.2f}%)")
    
    # --- 결과 저장 ---
    output = {
        "model_metrics": metrics,
        "shap_importance": shap_results["importance"],
        "all_region_simulation": all_results,
        "example_seoul": simulator.format_for_api(result_seoul),
        "example_custom": simulator.format_for_api(result_custom),
    }
    
    output_path = OUTPUT_DIR / "pipeline_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n💾 전체 결과 저장: {output_path}")
    
    print("\n" + "=" * 60)
    print("  ✅ 파이프라인 완료!")
    print("=" * 60)
    
    return model, simulator, df


# ============================================================
# 6. 백엔드 API용 추론 함수 (B가 import하여 사용)
# ============================================================

def predict_effect(
    source_region: str = None,
    policy_overrides: dict = None,
    model_path: str = None,
    data_path: str = None,
) -> dict:
    """
    백엔드 API에서 호출하는 추론 함수.
    
    Args:
        source_region: 참조 지역 ("서울", "대전" 등)
        policy_overrides: 직접 지정 정책 수치
            예: {"coop_teaching_schools": 300, "tutor_count": 500}
        model_path: 모델 파일 경로 (기본: models/model.pkl)
        data_path: 데이터 파일 경로 (기본: data/processed/merged_dataset.csv)
    
    Returns:
        프론트엔드 API 응답 형식의 딕셔너리
    
    사용 예시 (backend/services/predictor.py에서):
        from ml.predict import predict_effect
        
        result = predict_effect(
            source_region="서울",
            policy_overrides={"coop_teaching_schools": 300}
        )
    """
    
    # 모델 로딩
    m_path = Path(model_path) if model_path else MODEL_DIR / "model.pkl"
    model = PolicyEffectModel.load(m_path)
    
    # 데이터 로딩
    d_path = Path(data_path) if data_path else PROCESSED_DIR / "merged_dataset.csv"
    df = pd.read_csv(d_path)
    
    # 시뮬레이션
    simulator = PolicySimulator(model, df)
    result = simulator.simulate(
        source_region=source_region,
        policy_overrides=policy_overrides,
    )
    
    return simulator.format_for_api(result)


# ============================================================
# 실행
# ============================================================

if __name__ == "__main__":
    model, simulator, df = run_pipeline()
