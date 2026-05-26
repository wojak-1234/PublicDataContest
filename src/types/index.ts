export interface MetricData {
  id: string;
  label: string;
  value: string;
  subtext: string;
  iconType: 'budget' | 'school' | 'gap' | 'tutor';
  status: 'danger' | 'warning' | 'success' | 'info';
  badge?: string;
}

export interface TrendData {
  year: string;
  math: number;
  korean: number;
}

export interface ProxyIndexData {
  region: string;
  index: number;
  isTarget?: boolean;
}

export interface PolicyData {
  region: string;
  budget: string;
  dodream: string;
  coTeaching: boolean;
  aiCourseware: boolean;
  ordinance: boolean;
  note: string;
  isTarget?: boolean;
}

export interface CharacteristicData {
  id: string;
  title: string;
  description: string;
  iconType: 'gap' | 'population' | 'multicultural';
}

export interface PredictionResult {
  isLoading: boolean;
  question: string;
  newProxyIndex: number;
  improvement: number;
  chartData: ProxyIndexData[];
  shapData: { feature: string; impact: number }[];
  policyComparison: PolicyData[];
}

export interface SchoolRiskInputData {
  학업중단률_급: number;
  자퇴_비율_급: number;
  다문화_비율_급: number;
  중도입국_비율_급: number;
  외국인가정_비율_급: number;
  해외출국_비율_급: number;
  학급당_학생수_급: number;
  특수학급_비율_급: number;
  사교육_참여율: number;
  사교육비_1인당_만원: number;
  GRDP_1인당: number;
  교원1인당_학생수: number;
  학생1인당_교지면적: number;
  학생1인당_건물면적: number;
  학교급: '중' | '고';
}

export interface SchoolPredictionResult {
  위험도_pct: number;
  위험도_점수: number;
  학교급: '중' | '고';
}
