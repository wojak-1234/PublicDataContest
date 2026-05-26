from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import joblib
import json
import pandas as pd
from pathlib import Path
import numpy as np

app = FastAPI(
    title="BERIM API (Public Data Contest Backend)",
    description="Model API Spec backend endpoints implementation.",
    version="1.0"
)

# CORS 설정 (React 프론트엔드 포트 등 모든 오리진 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 데이터 및 모델 파일 경로 설정
MODELS_DIR = Path(__file__).parent / "models"

# 서버 시작 시 1회 파일 로드
try:
    M1 = joblib.load(MODELS_DIR / "risk_v4.pkl")
    M2 = joblib.load(MODELS_DIR / "risk_school_v8.pkl")
    COEFS = json.load(open(MODELS_DIR / "coefficients.json", encoding="utf-8"))
    SC_WEIGHTS = json.load(open(MODELS_DIR / "sc_weights.json", encoding="utf-8"))
    PRECOMP_SIDO = pd.read_csv(MODELS_DIR / "precomputed_risk_sido.csv", encoding="utf-8-sig")
    PRECOMP_SCHOOL = pd.read_csv(MODELS_DIR / "precomputed_risk_school.csv", encoding="utf-8-sig")
    PRECOMP_CV = pd.read_csv(MODELS_DIR / "precomputed_cv.csv", encoding="utf-8-sig")
    META = json.load(open(MODELS_DIR / "meta.json", encoding="utf-8"))
    print("All models and data files loaded successfully.")
except Exception as e:
    print(f"Error initializing models/data: {e}")
    raise RuntimeError(f"Initialization Failed: {e}")


# 입력 스키마 정의
class RiskInput(BaseModel):
    학업중단률: float
    자퇴_비율: float
    다문화학생_비율: float
    중도입국_비율: float
    해외출국_비율: float
    학급당_학생수: float
    특수학급_비율: float
    사교육_참여율: float
    사교육비_1인당_만원: float
    GRDP_1인당: float
    교원1인당_학생수: float
    학생1인당_건물면적_평균: float
    학생1인당_교지면적_평균: float

class SchoolRiskInput(BaseModel):
    학업중단률_급: float
    자퇴_비율_급: float
    다문화_비율_급: float
    중도입국_비율_급: float
    외국인가정_비율_급: float
    해외출국_비율_급: float
    학급당_학생수_급: float
    특수학급_비율_급: float
    사교육_참여율: float
    사교육비_1인당_만원: float
    GRDP_1인당: float
    교원1인당_학생수: float
    학생1인당_교지면적: float
    학생1인당_건물면적: float
    학교급: str  # "중" 또는 "고"

class SimInput(BaseModel):
    baseline_위험도: float = 60.63
    delta_학력향상: float = 0.0
    delta_다문화: float = 0.0
    delta_돌봄: float = 0.0
    학교급: str = "중"  # "중" 또는 "고"


# 1️⃣ 시도별 위험도 사전 계산 조회
@app.get("/api/risk/sido")
def get_sido_risk(시도: str = None, 연도: int = None):
    try:
        df = PRECOMP_SIDO.copy()
        if 시도:
            df = df[df['시도'] == 시도]
        if 연도:
            df = df[df['연도'] == 연도]
        df = df.replace({np.nan: None})
        return {"results": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 2️⃣ 학교급별 위험도 사전 계산 조회
@app.get("/api/risk/school")
def get_school_risk(시도: str = None, 학제: str = None, 연도: int = None):
    try:
        df = PRECOMP_SCHOOL.copy()
        if 시도:
            df = df[df['시도'] == 시도]
        if 학제:
            df = df[df['학제'] == 학제]
        if 연도:
            df = df[df['연도'] == 연도]
        df = df.replace({np.nan: None})
        return {"results": df.to_dict(orient="records")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 3️⃣ 위험도 실시간 예측 (M1 Ridge 모델 이용)
@app.post("/api/predict_risk")
def predict_risk(inp: RiskInput):
    try:
        feature_order = M1['features']
        # 입력받은 객체에서 피처 리스트 순서에 맞게 추출
        X = np.array([[getattr(inp, f) for f in feature_order]])
        # 스케일러 변환 및 예측
        Xs = M1['scaler'].transform(X)
        pred_pct = max(0.0, float(M1['model'].predict(Xs)[0]))
        
        # RISK_MIN, RISK_MAX 기반 정규화 점수 (0-100) 산정
        risk_min, risk_max = 0.87, 6.02
        score = 100.0 * (pred_pct - risk_min) / (risk_max - risk_min)
        score = max(0.0, min(100.0, score))
        
        return {
            "위험도_pct": round(pred_pct, 3),
            "위험도_점수": round(score, 2)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 3-2️⃣ 학교급별 실시간 예측 (M2 Ridge 모델 이용)
@app.post("/api/predict_school_risk")
def predict_school_risk(inp: SchoolRiskInput):
    try:
        if inp.학교급 not in ["중", "고"]:
            raise HTTPException(status_code=400, detail="학교급 파라미터는 '중' 또는 '고'여야 합니다.")
            
        sub_model = M2[inp.학교급]
        feature_order = M2['features']
        
        # 입력받은 객체에서 피처 리스트 순서에 맞게 추출
        X = np.array([[getattr(inp, f) for f in feature_order]])
        
        # 스케일러 변환 및 예측
        Xs = sub_model['scaler'].transform(X)
        pred_pct = max(0.0, float(sub_model['model'].predict(Xs)[0]))
        
        # 학교급별 위험도 수치 min/max 기반 정규화 점수 (0-100) 산정
        if inp.학교급 == "중":
            risk_min, risk_max = 1.0, 13.0
        else:
            risk_min, risk_max = 1.0, 20.0
            
        score = 100.0 * (pred_pct - risk_min) / (risk_max - risk_min)
        score = max(0.0, min(100.0, score))
        
        return {
            "위험도_pct": round(pred_pct, 3),
            "위험도_점수": round(score, 2),
            "학교급": inp.학교급
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4️⃣ 시나리오 시뮬레이션 (M8 기반)
@app.post("/api/simulate")
def simulate(inp: SimInput):
    try:
        if inp.학교급 not in ["중", "고"]:
            raise HTTPException(status_code=400, detail="학교급 파라미터는 '중' 또는 '고'여야 합니다.")
            
        b_lag1 = COEFS["M5_lag_panel"]["학력향상_t-1"]["beta"]
        b_multi = COEFS["M6_school_4policy"][inp.학교급]["다문화이탈주민_lag1"]
        b_care = COEFS["M6_school_4policy"][inp.학교급]["돌봄_lag1"]
        
        c_h = b_lag1 * inp.delta_학력향상
        c_m = b_multi * inp.delta_다문화
        c_c = b_care * inp.delta_돌봄
        delta = c_h + c_m + c_c
        
        return {
            "예상_위험도": round(inp.baseline_위험도 + delta, 2),
            "delta": round(delta, 2),
            "기여도": {
                "학력향상_lag1": round(c_h, 3),
                "다문화_lag1": round(c_m, 3),
                "돌봄_lag1": round(c_c, 3),
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 5️⃣ Synthetic Control 가중치 조회
@app.get("/api/sc/{시도}")
def get_sc(시도: str):
    if 시도 not in SC_WEIGHTS:
        raise HTTPException(status_code=404, detail="지원하는 시도는 '서울', '경기', '부산' 입니다.")
    return {"target": 시도, "weights": SC_WEIGHTS[시도]}


# 6️⃣ 시도별 정책 변동계수 (M9) 및 변동계수 순위
@app.get("/api/cv")
def get_cv():
    try:
        df = PRECOMP_CV.copy()
        df = df.replace({np.nan: None})
        
        # CV_pct 내림차순 정렬 및 순위 추가
        df = df.sort_values(by="CV_pct", ascending=False)
        records = df.to_dict(orient="records")
        ranking = []
        for i, rec in enumerate(records):
            rec["rank"] = i + 1
            ranking.append(rec)
            
        return {"ranking": ranking}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 7️⃣ 모델 메타 정보 반환
@app.get("/api/meta")
def get_meta():
    return META
