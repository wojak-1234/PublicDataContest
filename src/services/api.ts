import type { 
  MetricData, 
  TrendData, 
  ProxyIndexData, 
  PolicyData, 
  CharacteristicData, 
  PredictionResult 
} from '../types';

// TODO: Replace these mock data constants with actual API endpoints when backend is ready.
// The backend should return data matching the interfaces defined in types/index.ts

const MOCK_METRICS: MetricData[] = [
  {
    id: 'budget',
    label: '부산 기초학력 예산',
    value: '95억원',
    subtext: '서울 대비 37%',
    iconType: 'budget',
    status: 'danger',
    badge: '↓ 하락'
  },
  {
    id: 'school',
    label: '부산 두드림학교',
    value: '320교',
    subtext: '서울 1,326교 운영 중',
    iconType: 'school',
    status: 'warning'
  },
  {
    id: 'gap',
    label: '동서 학력격차',
    value: '15.2%p',
    subtext: '해운대 vs 사상구',
    iconType: 'gap',
    status: 'danger',
    badge: '위험'
  },
  {
    id: 'tutor',
    label: '학습지원 튜터',
    value: '180명',
    subtext: '서울 850명 배치',
    iconType: 'tutor',
    status: 'info'
  }
];

const MOCK_TRENDS: TrendData[] = [
  { year: '2019', math: 8.5, korean: 6.2 },
  { year: '2020', math: 10.1, korean: 7.5 },
  { year: '2021', math: 11.2, korean: 8.9 },
  { year: '2022', math: 11.8, korean: 9.3 },
  { year: '2023', math: 12.5, korean: 9.8 },
  { year: '2024', math: 12.7, korean: 10.1 }
];

const MOCK_PROXY_INDEX: ProxyIndexData[] = [
  { region: '대구', index: 26.9 },
  { region: '부산', index: 37.6, isTarget: true },
  { region: '전국평균', index: 52.8 },
  { region: '서울', index: 56.1 },
  { region: '경기', index: 61.2 },
  { region: '충남', index: 98.5 },
].sort((a, b) => a.index - b.index);

const MOCK_POLICIES: PolicyData[] = [
  { region: '서울', budget: '280억', dodream: '1,326교', coTeaching: true, aiCourseware: true, ordinance: true, note: '선도적 지원' },
  { region: '경기', budget: '450억', dodream: '2,100교', coTeaching: true, aiCourseware: true, ordinance: false, note: '최대 예산' },
  { region: '대구', budget: '110억', dodream: '450교', coTeaching: true, aiCourseware: true, ordinance: true, note: '높은 효율성' },
  { region: '부산', budget: '95억', dodream: '320교', coTeaching: false, aiCourseware: false, ordinance: true, note: '예산 확충 필요', isTarget: true }
];

const MOCK_CHARACTERISTICS: CharacteristicData[] = [
  { id: 'c1', title: '동서 학력격차', description: '15%p 이상 발생 (해운대 vs 사상구)', iconType: 'gap' },
  { id: 'c2', title: '인구 구조 변화', description: '소규모 학교 및 학령인구 급감', iconType: 'population' },
  { id: 'c3', title: '다문화 학생', description: '비율 2.1% 지속적 증가세', iconType: 'multicultural' }
];

// Async Mock Functions
export const fetchDashboardData = async () => {
  // TODO: GET /api/v1/dashboard
  return new Promise<{ metrics: MetricData[], trends: TrendData[], proxyIndex: ProxyIndexData[] }>((resolve) => {
    setTimeout(() => {
      resolve({
        metrics: MOCK_METRICS,
        trends: MOCK_TRENDS,
        proxyIndex: MOCK_PROXY_INDEX
      });
    }, 400); // simulate network delay
  });
};

export const fetchPolicyData = async () => {
  // TODO: GET /api/v1/policies
  return new Promise<{ policies: PolicyData[], characteristics: CharacteristicData[], proxyIndexAll: ProxyIndexData[] }>((resolve) => {
    setTimeout(() => {
      // Create a fuller list for the 17 provinces chart
      const fullProxy = [
        ...MOCK_PROXY_INDEX.filter(p => p.region !== '전국평균'),
        { region: '인천', index: 58.2 },
        { region: '광주', index: 41.5 },
        { region: '대전', index: 39.8 },
        { region: '울산', index: 45.2 },
        { region: '세종', index: 32.1 },
        { region: '강원', index: 75.6 },
        { region: '충북', index: 68.4 },
        { region: '전북', index: 82.1 },
        { region: '전남', index: 89.3 },
        { region: '경북', index: 71.5 },
        { region: '경남', index: 65.8 },
        { region: '제주', index: 50.4 }
      ].sort((a, b) => a.index - b.index);

      resolve({
        policies: MOCK_POLICIES,
        characteristics: MOCK_CHARACTERISTICS,
        proxyIndexAll: fullProxy
      });
    }, 400);
  });
};

export const predictPolicyEffect = async (question: string): Promise<PredictionResult> => {
  // TODO: POST /api/v1/predict with body { query: question }
  return new Promise((resolve) => {
    setTimeout(() => {
      // Simulate an AI calculation
      const baseIndex = 37.6;
      const improvement = 8.4;
      const newIndex = baseIndex - improvement;

      const updatedProxy = [...MOCK_PROXY_INDEX];
      const busanIndex = updatedProxy.findIndex(p => p.region === '부산');
      if (busanIndex !== -1) {
        updatedProxy[busanIndex] = { ...updatedProxy[busanIndex], index: newIndex };
      }

      // Re-sort to show Busan moving up (lower is better)
      updatedProxy.sort((a, b) => a.index - b.index);

      const updatedPolicies = [...MOCK_POLICIES];
      const pBusanIndex = updatedPolicies.findIndex(p => p.region === '부산');
      if (pBusanIndex !== -1) {
        updatedPolicies[pBusanIndex] = { 
          ...updatedPolicies[pBusanIndex], 
          coTeaching: true, 
          budget: '150억 (예상)', 
          note: '협력수업 도입 시나리오' 
        };
      }

      resolve({
        isLoading: false,
        question,
        newProxyIndex: newIndex,
        improvement,
        chartData: updatedProxy,
        shapData: [
          { feature: '협력수업 도입', impact: 4.2 },
          { feature: '튜터 증원', impact: 2.5 },
          { feature: '예산 확대', impact: 1.7 }
        ],
        policyComparison: updatedPolicies
      });
    }, 1500); // Simulate longer delay for AI processing
  });
};
