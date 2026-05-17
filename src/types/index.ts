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
