import type {
  MetricData,
  TrendData,
  ProxyIndexData,
  PolicyData,
  CharacteristicData,
  PredictionResult,
  SchoolRiskInputData,
  SchoolPredictionResult
} from '../types';

// API 서버 베이스 URL 설정 (로컬 환경과 배포 환경 동적 감지)
const isLocalhost = Boolean(
  window.location.hostname === 'localhost' ||
  window.location.hostname === '[::1]' ||
  window.location.hostname.match(/^127(?:\.(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)){3}$/)
);

const API_BASE = import.meta.env.VITE_API_BASE_URL || (isLocalhost ? 'http://localhost:8000' : '/_/backend');


// 1️⃣ 대시보드 데이터 로드 (FastAPI 연동)
export const fetchDashboardData = async () => {
  try {
    const [sidoRes, cvRes] = await Promise.all([
      fetch(`${API_BASE}/api/risk/sido`),
      fetch(`${API_BASE}/api/cv`)
    ]);

    if (!sidoRes.ok || !cvRes.ok) {
      throw new Error("API server responded with error status");
    }

    const sidoJson = await sidoRes.json();
    const cvJson = await cvRes.json();

    const sidoData = sidoJson.results;
    const cvData = cvJson.ranking;

    // 2024년 부산 데이터 추출
    const busan2024 = sidoData.find((d: any) => d['시도'] === '부산' && d['연도'] === 2024);
    const busanCV = cvData.find((d: any) => d['시도'] === '부산');
    const seoulCV = cvData.find((d: any) => d['시도'] === '서울');

    const busanRiskPct = busan2024 ? parseFloat(busan2024['위험도_pct']) : 5.82;
    const busanRiskScore = busan2024 ? parseFloat(busan2024['위험도_점수']) : 60.63;
    const busanMeanBudget = busanCV ? parseFloat(busanCV['mean']) : 86.9;
    const busanCVPct = busanCV ? parseFloat(busanCV['CV_pct']) : 43.5;
    const busanRank = busanCV ? busanCV['rank'] : 14;

    // 4대 지표 구성
    const metrics: MetricData[] = [
      {
        id: 'budget',
        label: '부산 기초학력 평균 예산',
        value: `${busanMeanBudget.toFixed(1)}천원/명`,
        subtext: `서울(${seoulCV ? parseFloat(seoulCV['mean']).toFixed(1) : '71.9'}천원) 대비 120.8%`,
        iconType: 'budget',
        status: 'info'
      },
      {
        id: 'school',
        label: '부산 종합 위험도 비율',
        value: `${busanRiskPct.toFixed(2)}%`,
        subtext: '2024년 기준 예측치',
        iconType: 'school',
        status: 'warning'
      },
      {
        id: 'gap',
        label: '부산 취약도 지수',
        value: `${busanRiskScore.toFixed(1)}점`,
        subtext: '100점 만점 기준',
        iconType: 'gap',
        status: 'danger',
        badge: '위험'
      },
      {
        id: 'tutor',
        label: '예산 변동계수(CV)',
        value: `${busanCVPct.toFixed(1)}%`,
        subtext: `16개 시도 중 변동성 순위 ${busanRank}위`,
        iconType: 'tutor',
        status: 'info'
      }
    ];

    // 연도별 위험도 트렌드 (2019 ~ 2024) - math(부산 위험도_pct), korean(서울 위험도_pct) 매핑
    const years = [2019, 2020, 2021, 2022, 2023, 2024];
    const trends: TrendData[] = years.map(yr => {
      const busanYr = sidoData.find((d: any) => d['시도'] === '부산' && d['연도'] === yr);
      const seoulYr = sidoData.find((d: any) => d['시도'] === '서울' && d['연도'] === yr);
      return {
        year: yr.toString(),
        math: busanYr ? parseFloat(parseFloat(busanYr['위험도_pct']).toFixed(2)) : 0,
        korean: seoulYr ? parseFloat(parseFloat(seoulYr['위험도_pct']).toFixed(2)) : 0
      };
    });

    // 취약도 지수 비교 (Proxy Index - 2024년 기준 대표 시도)
    const targetRegions = ['대구', '부산', '서울', '경기', '충남'];
    const s2024 = sidoData.filter((d: any) => d['연도'] === 2024);
    
    const proxyIndex: ProxyIndexData[] = targetRegions.map(reg => {
      const found = s2024.find((d: any) => d['시도'] === reg);
      return {
        region: reg,
        index: found ? parseFloat(parseFloat(found['위험도_점수']).toFixed(1)) : 50,
        isTarget: reg === '부산'
      };
    });

    // 전국평균 계산
    const validScores = s2024.map((d: any) => parseFloat(d['위험도_점수'])).filter((v: number) => !isNaN(v));
    const nationalAvg = validScores.reduce((acc: number, cur: number) => acc + cur, 0) / (validScores.length || 1);
    proxyIndex.push({
      region: '전국평균',
      index: parseFloat(nationalAvg.toFixed(1))
    });

    proxyIndex.sort((a, b) => a.index - b.index);

    return { metrics, trends, proxyIndex };
  } catch (error) {
    console.warn("fetchDashboardData API fetch failed, using fallback", error);
    return {
      metrics: [
        { id: 'budget', label: '부산 기초학력 예산', value: '95억원', subtext: '서울 대비 37%', iconType: 'budget', status: 'danger', badge: '↓ 하락' },
        { id: 'school', label: '부산 두드림학교', value: '320교', subtext: '서울 1,326교 운영 중', iconType: 'school', status: 'warning' },
        { id: 'gap', label: '동서 학력격차', value: '15.2%p', subtext: '해운대 vs 사상구', iconType: 'gap', status: 'danger', badge: '위험' },
        { id: 'tutor', label: '학습지원 튜터', value: '180명', subtext: '서울 850명 배치', iconType: 'tutor', status: 'info' }
      ] as MetricData[],
      trends: [
        { year: '2019', math: 8.5, korean: 6.2 },
        { year: '2020', math: 10.1, korean: 7.5 },
        { year: '2021', math: 11.2, korean: 8.9 },
        { year: '2022', math: 11.8, korean: 9.3 },
        { year: '2023', math: 12.5, korean: 9.8 },
        { year: '2024', math: 12.7, korean: 10.1 }
      ] as TrendData[],
      proxyIndex: [
        { region: '대구', index: 26.9 },
        { region: '부산', index: 37.6, isTarget: true },
        { region: '전국평균', index: 52.8 },
        { region: '서울', index: 56.1 },
        { region: '경기', index: 61.2 },
        { region: '충남', index: 98.5 }
      ].sort((a, b) => a.index - b.index) as ProxyIndexData[]
    };
  }
};

// 2️⃣ 정책 비교 및 가중치 데이터 로드 (FastAPI 연동)
export const fetchPolicyData = async () => {
  try {
    const [cvRes, sidoRes] = await Promise.all([
      fetch(`${API_BASE}/api/cv`),
      fetch(`${API_BASE}/api/risk/sido`)
    ]);

    if (!cvRes.ok || !sidoRes.ok) {
      throw new Error("Policy API server responded with error status");
    }

    const cvJson = await cvRes.json();
    const sidoJson = await sidoRes.json();

    const cvData = cvJson.ranking;
    const sidoData = sidoJson.results;

    const getCVInfo = (region: string) => {
      const found = cvData.find((d: any) => d['시도'] === region);
      if (!found) return { mean: 50, std: 20, cv: 40, rank: 10 };
      return {
        mean: parseFloat(found['mean']),
        std: parseFloat(found['std']),
        cv: parseFloat(found['CV_pct']),
        rank: found['rank']
      };
    };

    // 4대 주요 시도 정책 비교 테이블 빌드
    const regions = ['서울', '경기', '대구', '부산'];
    const policies: PolicyData[] = regions.map(reg => {
      const info = getCVInfo(reg);
      let note = `정책 예산 변동계수 ${info.cv.toFixed(1)}% (${info.rank}위)`;
      if (reg === '부산') note += ' - 변동성 매우 낮음';
      if (reg === '경기') note += ' - 예산 분산 최대';

      return {
        region: reg,
        budget: `${info.mean.toFixed(1)}천원/명`,
        dodream: `표준편차 ${info.std.toFixed(1)}`,
        coTeaching: reg !== '부산',
        aiCourseware: reg !== '부산' && reg !== '대구',
        ordinance: reg !== '경기',
        note,
        isTarget: reg === '부산'
      };
    });

    // 17개 시도 전체 2024년 위험도 점수 리스트 빌드 (차트용)
    const s2024 = sidoData.filter((d: any) => d['연도'] === 2024);
    const proxyIndexAll: ProxyIndexData[] = s2024.map((d: any) => ({
      region: d['시도'],
      index: parseFloat(parseFloat(d['위험도_점수']).toFixed(1)),
      isTarget: d['시도'] === '부산'
    }));
    proxyIndexAll.sort((a, b) => a.index - b.index);

    const characteristics: CharacteristicData[] = [
      { id: 'c1', title: '동서 학력격차', description: '지역 내 인프라 격차에 따른 학업 취약도 심화', iconType: 'gap' },
      { id: 'c2', title: '인구 구조 변화', description: '지방 소멸 위험 및 학령인구 급감으로 소규모 학교 증가', iconType: 'population' },
      { id: 'c3', title: '다문화 학생 증가', description: '다문화 및 중도입국 학생 비율 지속적 증가세 (위험도 상승 영향)', iconType: 'multicultural' }
    ];

    return { policies, characteristics, proxyIndexAll };
  } catch (error) {
    console.warn("fetchPolicyData API fetch failed, using fallback", error);
    return {
      policies: [
        { region: '서울', budget: '280억', dodream: '1,326교', coTeaching: true, aiCourseware: true, ordinance: true, note: '선도적 지원' },
        { region: '경기', budget: '450억', dodream: '2,100교', coTeaching: true, aiCourseware: true, ordinance: false, note: '최대 예산' },
        { region: '대구', budget: '110억', dodream: '450교', coTeaching: true, aiCourseware: true, ordinance: true, note: '높은 효율성' },
        { region: '부산', budget: '95억', dodream: '320교', coTeaching: false, aiCourseware: false, ordinance: true, note: '예산 확충 필요', isTarget: true }
      ] as PolicyData[],
      characteristics: [
        { id: 'c1', title: '동서 학력격차', description: '15%p 이상 발생 (해운대 vs 사상구)', iconType: 'gap' },
        { id: 'c2', title: '인구 구조 변화', description: '소규모 학교 및 학령인구 급감', iconType: 'population' },
        { id: 'c3', title: '다문화 학생', description: '비율 2.1% 지속적 증가세', iconType: 'multicultural' }
      ] as CharacteristicData[],
      proxyIndexAll: [
        { region: '대구', index: 26.9 },
        { region: '부산', index: 37.6, isTarget: true },
        { region: '서울', index: 56.1 },
        { region: '경기', index: 61.2 },
        { region: '충남', index: 98.5 }
      ].sort((a, b) => a.index - b.index) as ProxyIndexData[]
    };
  }
};

// 3️⃣ 정책 효과 예측 시뮬레이션 (FastAPI /api/simulate 호출)
export const simulatePolicy = async (
  d_h: number,
  d_m: number,
  d_c: number,
  grade: '중' | '고'
): Promise<PredictionResult> => {
  try {
    const simRes = await fetch(`${API_BASE}/api/simulate`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        baseline_위험도: 60.63,
        delta_학력향상: d_h,
        delta_다문화: d_m,
        delta_돌봄: d_c,
        학교급: grade
      })
    });

    if (!simRes.ok) {
      throw new Error("Simulation server error");
    }

    const simData = await simRes.json();
    const newIndex = simData.예상_위험도;
    const totalDelta = simData.delta;
    const improvement = Math.abs(totalDelta);

    // 차트 데이터 갱신 (부산 수치 변경 반영)
    const dashboard = await fetchDashboardData();
    const updatedProxy = dashboard.proxyIndex.map(p => {
      if (p.region === '부산') {
        return { ...p, index: newIndex };
      }
      return p;
    }).sort((a, b) => a.index - b.index);

    // 정책 비교표 업데이트
    const policyData = await fetchPolicyData();
    const updatedPolicies = policyData.policies.map(p => {
      if (p.region === '부산') {
        return {
          ...p,
          coTeaching: d_h > 0,
          budget: `86.9 (+${d_h}) 천원/명`,
          note: `시뮬레이션 (학력향상:+${d_h}, 다문화:+${d_m}, 돌봄:+${d_c})`
        };
      }
      return p;
    });

    return {
      isLoading: false,
      question: `학제: ${grade}학교, 예산조정: [학력향상: +${d_h}천원/명, 다문화: +${d_m}천원/명, 돌봄: +${d_c}천원/명]`,
      newProxyIndex: newIndex,
      improvement: parseFloat(improvement.toFixed(2)),
      chartData: updatedProxy,
      shapData: [
        { feature: '학력향상 예산 기여도', impact: Math.abs(simData.기여도.학력향상_lag1) },
        { feature: '다문화이탈주민 지원 기여도', impact: Math.abs(simData.기여도.다문화_lag1) },
        { feature: '돌봄 예산 기여도', impact: Math.abs(simData.기여도.돌봄_lag1) }
      ],
      policyComparison: updatedPolicies
    };
  } catch (error) {
    console.error("simulatePolicy failed, using fallback", error);
    return {
      isLoading: false,
      question: "시뮬레이션 에러 발생",
      newProxyIndex: 60.63,
      improvement: 0,
      chartData: [],
      shapData: [
        { feature: '학력향상 예산 기여도', impact: 0 },
        { feature: '다문화이탈주민 지원 기여도', impact: 0 },
        { feature: '돌봄 예산 기여도', impact: 0 }
      ],
      policyComparison: []
    };
  }
};

// 4️⃣ Gemini API 호출 및 맞춤 정책 리포트 생성
export const generateAiReport = async (
  inputs: { d_h: number; d_m: number; d_c: number; grade: '중' | '고' },
  results: { newRisk: number; delta: number; contributions: any }
): Promise<string> => {
  const apiKey = import.meta.env.VITE_GEMINI_API_KEY;
  if (!apiKey || apiKey === 'your_gemini_api_key_here') {
    throw new Error('API 키가 설정되지 않았습니다. .env 파일에 VITE_GEMINI_API_KEY를 입력해주세요.');
  }

  const prompt = `
[시나리오 데이터]
- 대상 학교급: ${inputs.grade}학교
- 예산 조정액: 학력향상 +${inputs.d_h}천원/명, 다문화 +${inputs.d_m}천원/명, 돌봄 +${inputs.d_c}천원/명
- 예측 결과: 예상 취약도 지수 ${results.newRisk}점 (변화량: ${results.delta}점)
- 요인별 기여도 수치: 
  * 학력향상 예산 기여도: ${results.contributions.학력향상_lag1.toFixed(3)}
  * 다문화이탈주민 지원 기여도: ${results.contributions.다문화_lag1.toFixed(3)}
  * 돌봄 예산 기여도: ${results.contributions.돌봄_lag1.toFixed(3)}

위 통계적 결과에 대해 정확히 아래의 마크다운 규격 포맷을 준수하여 보고서를 작성해 주십시오. 다른 안내말이나 인사말 등의 추가 텍스트는 일체 생략하고 오직 아래의 포맷 구조만을 반환하십시오.

## 📊 정책 분석 요약
(이 정책 조정 시나리오의 전체 요약 및 취약도 개선 성과를 1줄로만 요약해 작성하십시오.)

## 🧬 통계적 인과 해석
(학제 특성과 각 기여도 수치, 시차 효과(t-1년), p-value 유의성(다문화 및 돌봄의 통계적 확실성)을 근거로 삼아, 왜 이러한 위험도 변화량이 나타났는지 통계적인 맥락을 2~3줄로 설명하십시오.)

## 💡 핵심 교육 제언
- (예산 조정 결과 및 타 지자체 대비 부산의 부족분[돌봄 등]을 참고하여, 이 학제 단계에서 예산 투입 효율을 극대화하기 위해 당장 취해야 할 첫 번째 실질적 조언을 작성하십시오.)
- (두 번째 실질적 조언을 작성하십시오.)
`;

  const systemInstructionText = `당신은 대한민국 지방자치단체의 교육 정책을 분석하는 '정책비교분석 AI' 전문가입니다.
답변할 때 반드시 요청받은 3개의 마크다운 헤더(## 📊 정책 분석 요약, ## 🧬 통계적 인과 해석, ## 💡 핵심 교육 제언) 구조를 정확하게 유지해야 합니다. 
줄글로 늘어놓거나 기타 서두/결미의 인삿말("안녕하세요", "이상입니다" 등)을 출력하는 것은 엄격하게 금지됩니다.`;

  const response = await fetch(
    `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash:generateContent?key=${apiKey}`,
    {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        contents: [
          {
            parts: [
              {
                text: prompt
              }
            ]
          }
        ],
        systemInstruction: {
          parts: [
            {
              text: systemInstructionText
            }
          ]
        }
      }),
    }
  );

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new Error(errorData.error?.message || `API 호출 에러: ${response.status}`);
  }

  const data = await response.json();
  const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) {
    throw new Error('API 응답 파싱 에러');
  }

  return text;
};

// 5️⃣ 학교급별 실시간 예측 API 연동 (M2 모델)
export const predictSchoolRisk = async (
  inputData: SchoolRiskInputData
): Promise<SchoolPredictionResult> => {
  const response = await fetch(`${API_BASE}/api/predict_school_risk`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(inputData)
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    const errorMsg = typeof errorData.detail === 'string' ? errorData.detail : `API 호출 에러: ${response.status}`;
    throw new Error(errorMsg);
  }

  return response.json();
};

