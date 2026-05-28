# PublicDataContest 배포 및 아키텍처 분석 가이드라인

본 문서는 `PublicDataContest` 프로젝트의 아키텍처 분석 결과와 Vercel 및 클라우드 호스팅 서비스를 활용한 최적의 배포 방안을 제시합니다.

---

## 1. 프로젝트 아키텍처 분석

### 1.1 프론트엔드 (React + Vite + TypeScript)
- **역할**: 사용자 대시보드 시각화, 정책 시나리오 시муля레이터 UI, Gemini API 기반 맞춤 정책 리포트 생성
- **핵심 파일**:
  - [src/services/api.ts](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/src/services/api.ts): 백엔드 API 서버(`http://localhost:8000`) 및 외부 Gemini API와 연동을 담당합니다.
  - [src/pages/AiPrediction.tsx](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/src/pages/AiPrediction.tsx): 예측 결과를 화면에 렌더링하고 시뮬레이션을 요청합니다.
- **의존성 환경 변수**:
  - `VITE_GEMINI_API_KEY`: AI 보고서 생성을 위해 클라이언트에서 직접 Google Gemini API를 호출할 때 사용합니다.
  - `VITE_API_BASE_URL` (추가 필요): 백엔드 API 주소를 동적으로 주입하기 위해 필요한 환경 변수입니다.

### 1.2 백엔드 (FastAPI + Machine Learning Models)
- **역할**: 기계 학습 Ridge 회귀 모델을 활용한 위험도 실시간 예측, 정책 시나리오 시뮬레이션, 사전 계산 데이터(Sido/School/CV) 조회 API 제공
- **핵심 파일**:
  - [backend/app.py](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/backend/app.py): API 엔드포인트 구현 및 CORS 허용 설정(`allow_origins=["*"]`)
  - [backend/models/](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/backend/models): Ridge 모델 객체(`*.pkl`), 정책 변동 계수 및 시도별 데이터(`*.csv`, `*.json`) 포함
- **자원 특징**: 모델 및 데이터 용량이 매우 작아(총합 50KB 미만), 서버리스 환경 및 저사양 컨테이너 환경에서도 구동 가능합니다.

---

## 2. 배포 가이드라인

가장 권장되는 방식인 **[시나리오 A: 프론트엔드/백엔드 이원화 배포]**와 프로젝트를 단일 서비스로 관리하는 **[시나리오 B: Vercel 서버리스 통합 배포]** 중 선택하여 진행할 수 있습니다.

### 시나리오 A: 프론트엔드(Vercel) + 백엔드(Render/Railway) 이원화 배포 (권장)
백엔드 코드를 거의 수정하지 않고 표준 컨테이너 환경에 배포하는 방식입니다.

#### 1단계: 프론트엔드 코드 수정 (API 엔드포인트 환경 변수화)
배포 시 백엔드 주소를 유연하게 설정할 수 있도록 [src/services/api.ts](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/src/services/api.ts)를 수정합니다.

- **대상 파일**: [src/services/api.ts](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/src/services/api.ts)
- **수정 내용**:
  ```typescript
  // AS-IS (Line 13)
  const API_BASE = 'http://localhost:8000';

  // TO-BE
  const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';
  ```

#### 2단계: 백엔드 배포 (Render.com 기준)
1. **GitHub 리포지토리 생성 및 업로드**: 프로젝트 코드를 GitHub에 업로드합니다.
2. **Render 가입 및 웹서비스 생성**:
   - Render 대시보드에서 **New +** > **Web Service**를 클릭합니다.
   - 프로젝트 저장소를 연동합니다.
3. **빌드 및 실행 설정**:
   - **Root Directory**: `backend` (FastAPI 코드가 있는 폴더로 지정)
   - **Runtime**: `Python 3` (또는 `Python`)
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn app:app --host 0.0.0.0 --port $PORT`
4. **배포 완료**: 배포가 성공하면 `https://public-data-contest-backend.onrender.com` 형태의 공용 URL이 발급됩니다.

#### 3단계: 프론트엔드 배포 (Vercel 기준)
1. **Vercel 연동**: Vercel 대시보드에서 **Add New Project**를 선택하고 GitHub 저장소를 가져옵니다.
2. **빌드 설정**:
   - **Framework Preset**: `Vite`
   - **Root Directory**: `./` (프론트엔드 package.json이 있는 루트 디렉토리)
   - **Build Command**: `npm run build`
   - **Output Directory**: `dist`
3. **환경 변수(Environment Variables) 주입**:
   - `VITE_API_BASE_URL`: 2단계에서 발급받은 백엔드 URL을 기입합니다.
   - `VITE_GEMINI_API_KEY`: 사용 중인 Gemini API 키를 입력합니다.
4. **Deploy**: 배포 버튼을 눌러 완료합니다.

---

### 시나리오 B: Vercel Multi-Service (`experimentalServices`) 통합 배포
프론트엔드와 백엔드를 독립된 서비스로 정의하고, Vercel의 실험적 기능인 `experimentalServices` 설정을 통해 하나의 프로젝트로 한 번에 배포하는 방식입니다.

#### 1단계: `vercel.json` 구성
프로젝트 루트 디렉토리에 [vercel.json](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/vercel.json) 파일을 생성하여 다중 서비스 매핑 설정을 작성합니다.

```json
{
  "experimentalServices": {
    "frontend": {
      "routePrefix": "/",
      "framework": "vite"
    },
    "backend": {
      "root": "backend",
      "routePrefix": "/_/backend"
    }
  }
}
```
*설명: 프론트엔드는 루트 경로(`/`)에 Vite로 서빙되고, `backend` 폴더의 FastAPI 앱은 `/_/backend` 접두사 경로에 배포되어 프론트엔드에서 API 요청을 수신할 수 있게 됩니다.*

#### 2단계: 프론트엔드 API 베이스 주소 수정
Vercel 멀티 서비스 프록시 경로(`/ _/backend`)를 기본값으로 사용하도록 수정합니다.
- **대상 파일**: [src/services/api.ts](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/src/services/api.ts)
  ```typescript
  const API_BASE = import.meta.env.VITE_API_BASE_URL || '/_/backend';
  ```

#### 3단계: 로컬 개발 환경용 `.env` 수정
로컬 개발 시에는 로컬 백엔드 서버(`http://localhost:8000`)를 호출할 수 있도록 설정합니다.
- **대상 파일**: [.env](file:///c:/Users/PC/Desktop/PublicDataContest-frontend/.env)
  ```env
  VITE_API_BASE_URL=http://localhost:8000
  ```

#### 4단계: Vercel 배포 진행
1. **GitHub 저장소 연동 및 배포**: Vercel 대시보드에서 프로젝트를 연동하고 배포합니다. Vercel이 `vercel.json` 내의 `experimentalServices`를 감지하여 프론트엔드와 백엔드를 자동으로 함께 빌드하고 배포합니다.
2. **환경 변수**: Vercel 대시보드의 **Environment Variables** 설정에 `VITE_GEMINI_API_KEY`를 추가합니다. Vercel 환경에서는 기본값인 `/_/backend`가 프록시로 동작하므로 `VITE_API_BASE_URL` 변수는 입력하지 않아도 무방합니다.

---

## 3. 환경 변수 요약 테이블

| 환경 변수명 | 로컬 설정값 (`.env`) | 배포 설정값 (Vercel Web UI) | 역할 |
| :--- | :--- | :--- | :--- |
| `VITE_GEMINI_API_KEY` | `AI_KEY_VALUE` | `AI_KEY_VALUE` | Gemini API 인증에 사용 |
| `VITE_API_BASE_URL` | `http://localhost:8000` | 생략 가능 (기본값인 `/_/backend` 자동 적용) | 프론트엔드에서 API 요청을 보낼 주소 |

