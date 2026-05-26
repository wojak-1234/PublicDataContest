# 🔌 MODEL_API_SPEC — 백엔드 인터페이스 명세서

> **목적**: 분석가가 학습한 모델을 백엔드가 API 서버로 띄울 때 필요한 모든 정보.
> **분석가 결과물**: `models/` 폴더의 7개 파일.
> **백엔드 책임**: 이 파일들을 로드해서 FastAPI/Flask 등으로 노출 + 캐싱·배포.

---

## 📦 분석가가 전달하는 산출물

```
models/
├── risk_v4.pkl                    # M1: Ridge (시도 위험도)
├── risk_school_v8.pkl             # M2: Ridge (학교급별, 중/고)
├── coefficients.json              # M5,M6,M7,M8: 계수 모음
├── sc_weights.json                # M3: Synthetic Control 가중치
├── precomputed_risk_sido.csv      # 시도×연도 위험도 사전 계산
├── precomputed_risk_school.csv    # 시도×연도×학교급 위험도 사전 계산
├── precomputed_cv.csv             # 시도별 변동계수
└── meta.json                      # 학습 시점·데이터 해시·버전
```

**용량**: 합계 약 36 KB (모두 메모리 적재 부담 없음)

---

## 🚀 백엔드 통합 — 서버 시작 시 1회 로드

```python
# app.py (FastAPI 예시)
from fastapi import FastAPI
from pydantic import BaseModel
import joblib, json
import pandas as pd
from pathlib import Path

app = FastAPI(title="BERIM API", version="1.0")

# ⭐ 글로벌 변수에 1회 로드 — 요청마다 로드 X
MODELS_DIR = Path("./models")
M1 = joblib.load(MODELS_DIR / "risk_v4.pkl")
M2 = joblib.load(MODELS_DIR / "risk_school_v8.pkl")
COEFS = json.load(open(MODELS_DIR / "coefficients.json", encoding="utf-8"))
SC_WEIGHTS = json.load(open(MODELS_DIR / "sc_weights.json", encoding="utf-8"))
PRECOMP_SIDO = pd.read_csv(MODELS_DIR / "precomputed_risk_sido.csv", encoding="utf-8-sig")
PRECOMP_SCHOOL = pd.read_csv(MODELS_DIR / "precomputed_risk_school.csv", encoding="utf-8-sig")
PRECOMP_CV = pd.read_csv(MODELS_DIR / "precomputed_cv.csv", encoding="utf-8-sig")
META = json.load(open(MODELS_DIR / "meta.json", encoding="utf-8"))
```

---

## 📡 API 엔드포인트 명세 — 7개

### 1️⃣ `GET /api/risk/sido` — 시도별 위험도 (사전 계산 조회)

**입력**: query parameter
| 파라미터 | 타입 | 설명 | 예시 |
|---|---|---|---|
| `시도` | string | 시도명 (선택, 없으면 전체) | `부산` |
| `연도` | int | 연도 (선택) | `2024` |

**출력**:
```json
{
  "results": [
    {"연도": 2024, "시도": "부산", "위험도_pct": 5.82, "위험도_점수": 60.63}
  ]
}
```

**구현 코드**:
```python
@app.get("/api/risk/sido")
def get_sido_risk(시도: str = None, 연도: int = None):
    df = PRECOMP_SIDO
    if 시도: df = df[df['시도'] == 시도]
    if 연도: df = df[df['연도'] == 연도]
    return {"results": df.to_dict(orient="records")}
```

---

### 2️⃣ `GET /api/risk/school` — 학교급별 위험도 (사전 계산 조회)

**입력**:
| 파라미터 | 타입 | 예시 |
|---|---|---|
| `시도` | string | `부산` |
| `학제` | string | `중` 또는 `고` |
| `연도` | int | `2024` |

**출력**:
```json
{
  "results": [
    {"연도": 2024, "시도": "부산", "학제": "중", "위험도_pct": 2.4, "위험도_점수": 23.7}
  ]
}
```

---

### 3️⃣ `POST /api/predict_risk` — 위험도 실시간 예측 (M1)

**입력** (Pydantic):
```python
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
```

**출력**:
```json
{ "위험도_pct": 5.82, "위험도_점수": 60.63 }
```

**구현 코드**:
```python
import numpy as np
RISK_MIN, RISK_MAX = 0.87, 6.02  # min-max 정규화용 (coefficients.json에서)

@app.post("/api/predict_risk")
def predict_risk(inp: RiskInput):
    feature_order = M1['features']  # 학습 시 정의된 순서
    X = np.array([[getattr(inp, f) for f in feature_order]])
    Xs = M1['scaler'].transform(X)
    pred_pct = max(0, float(M1['model'].predict(Xs)[0]))
    score = 100 * (pred_pct - RISK_MIN) / (RISK_MAX - RISK_MIN)
    return {"위험도_pct": round(pred_pct, 3), "위험도_점수": round(score, 2)}
```

---

### 4️⃣ `POST /api/simulate` — 시나리오 시뮬레이션 (M8 핵심) ⭐

**입력**:
```python
class SimInput(BaseModel):
    baseline_위험도: float = 60.63       # 부산 2024 기본값
    delta_학력향상: float = 0            # 학생당 천원 변화량
    delta_다문화: float = 0
    delta_돌봄: float = 0
    학교급: str = "중"                    # "중" or "고"
```

**출력**:
```json
{
  "예상_위험도": 58.29,
  "delta": -2.34,
  "기여도": {
    "학력향상_lag1": 0.0,
    "다문화_lag1": -1.15,
    "돌봄_lag1": -1.19
  }
}
```

**구현 코드**:
```python
@app.post("/api/simulate")
def simulate(inp: SimInput):
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
```

### 시나리오 프리셋 (S0~S4)
프론트엔드에서 쉽게 호출 가능:
| 시나리오 | 호출 인자 |
|---|---|
| S0 현상유지 | `delta_*` 모두 0 |
| S1 안정화만 | `delta_*` 모두 0 (메시지만 다름) |
| S2 분야균형 | `delta_학력향상=0, delta_다문화=5, delta_돌봄=29` |
| S3 적극강화 | `delta_학력향상=43, delta_다문화=5, delta_돌봄=29` |
| S4 양만 증액 | `delta_학력향상=47, delta_다문화=0, delta_돌봄=0` |

---

### 5️⃣ `GET /api/sc/{시도}` — Synthetic Control 가중치 조회

**입력**: path parameter `시도` ∈ {`서울`, `경기`, `부산`}

**출력**:
```json
{
  "target": "부산",
  "weights": {"광주": 0.3124, "경남": 0.2958, "인천": 0.1972, "...": "..."}
}
```

**구현 코드**:
```python
@app.get("/api/sc/{시도}")
def get_sc(시도: str):
    if 시도 not in SC_WEIGHTS:
        return {"error": "지원 시도: 서울/경기/부산"}
    return {"target": 시도, "weights": SC_WEIGHTS[시도]}
```

---

### 6️⃣ `GET /api/cv` — 시도별 정책 변동계수 (M9)

**출력**:
```json
{
  "ranking": [
    {"시도": "경기", "mean": 57.1, "std": 41.8, "CV_pct": 73.1, "rank": 1},
    {"시도": "부산", "mean": 86.9, "std": 37.8, "CV_pct": 43.5, "rank": 14},
    {"...": "..."}
  ]
}
```

---

### 7️⃣ `GET /api/meta` — 모델 메타 정보

**출력**: 학습 시점·데이터 해시·버전 (`meta.json` 그대로 반환)
```json
{
  "version": "2026.05.26",
  "trained_at": "2026-05-26T...",
  "data_files": {"v6": {"md5": "..."}, "v8": {"md5": "..."}}
}
```

---

## 🔢 모델 계수 참고 (coefficients.json 핵심)

### M5 정책 Lag (시도 단위)
| 계수 | 값 | p-value | 의미 |
|---|---|---|---|
| `학력향상_t` | +0.0004 | 0.96 | 즉시 효과 없음 |
| `학력향상_t-1` ★ | **-0.0219** | **0.002** | 1년 후 위험도 감소 동행 |
| `학력향상_t-2` | -0.0119 | 0.23 | 비유의 |

### M6 학교급별 정책 (중학교, 2023-2024)
| 계수 | 값 | p-value |
|---|---|---|
| `누리_lag1` | +0.009 | 0.18 |
| **`다문화이탈주민_lag1`** ★ | **-0.2302** | **<0.001** |
| **`돌봄_lag1`** ★ | **-0.0406** | **0.005** |

### M7 부산학력개발원 ITS
| 계수 | 값 | 의미 |
|---|---|---|
| `const` | 19.30 | 2013년 기준 위험도 |
| `t_trend` | +3.54 | 매년 추세 |
| `post2022_step` | -21.42 | 학개원 즉각 step |
| `t_post2022_slope_change` | +2.22 | 추세 변화 |

---

## ⚡ 권장 백엔드 최적화

### 1. 메모리 캐싱 (Python lru_cache)
```python
from functools import lru_cache

@lru_cache(maxsize=512)
def cached_simulate(d_h, d_m, d_c, baseline, grade):
    # 동일 입력은 캐시
    ...
```

### 2. Redis 캐싱 (응답 30초)
```python
import redis
r = redis.Redis()

@app.post("/api/simulate")
def simulate(inp: SimInput):
    key = f"sim:{inp.json()}"
    if cached := r.get(key):
        return json.loads(cached)
    result = compute_simulate(inp)
    r.setex(key, 30, json.dumps(result))
    return result
```

### 3. 응답 시간 SLO
| 엔드포인트 | 목표 응답시간 | 비고 |
|---|---|---|
| `GET /api/risk/sido` | < 5 ms | pandas filter |
| `POST /api/predict_risk` | < 10 ms | Ridge 추론 |
| `POST /api/simulate` | < 1 ms | 단순 산수 |
| `GET /api/sc/*` | < 1 ms | JSON 조회 |

---

## 🔄 모델 갱신 흐름 (Blue-Green 배포)

```
1. 분석가가 새 데이터로 train_and_save.py 실행 (월 1회)
   → models_new/ 폴더에 새 .pkl, .json 생성
2. 백엔드 검증: GET /api/meta 로 새 모델 해시 확인
3. 검증 통과 시 models/ ← models_new/ 교체
4. API 서버 재시작 (또는 핫리로드)
5. 이전 모델은 models_backup/yyyymmdd/ 로 백업
```

---

## 🐳 Docker 배포 예시

### Dockerfile (API)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY app.py .
COPY models/ ./models/
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### docker-compose.yml
```yaml
services:
  api:
    build: ./api
    ports: ["8000:8000"]
    volumes: ["./models:/app/models:ro"]
    restart: always
  
  trainer:
    build: ./trainer
    command: python train_and_save.py
    volumes:
      - "./models:/app/models:rw"
      - "./data:/app/data:ro"
    # cron으로 월 1회 실행 (host crontab)
  
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
```

### Cron (호스트)
```cron
# 매월 1일 새벽 3시 새 모델 학습
0 3 1 * * docker-compose run trainer
```

---

## ✅ 분석가 ↔ 백엔드 협업 체크리스트

### 분석가 (사용자)
- [x] `models/` 7개 파일 생성 완료
- [x] `train_and_save.py` 스크립트 작성 완료
- [x] `MODEL_API_SPEC.md` 명세서 작성 완료
- [ ] 새 데이터 수집 시 `train_and_save.py` 재실행

### 백엔드 (협업 팀)
- [ ] `models/` 폴더 받아서 서버에 배치
- [ ] FastAPI/Flask 앱에 7개 엔드포인트 구현 (위 코드 참고)
- [ ] Redis 캐싱 추가
- [ ] Docker 컨테이너화
- [ ] cron으로 trainer 자동화

---

## 📞 트러블슈팅

| 증상 | 원인 | 해결 |
|---|---|---|
| `joblib.load` 시 sklearn 버전 에러 | 학습·서빙 sklearn 버전 다름 | `requirements.txt`에 정확한 버전 명시 |
| 입력 변수 순서 틀림 | `inp.dict()` 순서 가정 X | `M1['features']` 리스트 순서 따를 것 |
| `coefficients.json` 인코딩 깨짐 | utf-8 미지정 | `open(..., encoding='utf-8')` |
| 한국어 컬럼명 처리 | DataFrame 컬럼 한글 | `encoding='utf-8-sig'` 사용 |
