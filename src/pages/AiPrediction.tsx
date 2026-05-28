import React, { useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell } from 'recharts';
import { Bot, RefreshCw, BarChart2, FileText, Settings, Award } from 'lucide-react';
import { simulatePolicy, generateAiReport } from '../services/api';
import type { PredictionResult } from '../types';

// 마크다운 파싱 및 UI 카드 렌더러 컴포넌트
const MarkdownReportRenderer: React.FC<{ text: string }> = ({ text }) => {
  if (!text) return null;

  // 줄바꿈으로 라인 분리 및 정리
  const lines = text.split('\n').map(line => line.trim()).filter(line => line.length > 0);
  
  // 섹션별 데이터 구조화
  let currentSection = '';
  const sections: { [key: string]: string[] } = {
    summary: [],
    analysis: [],
    suggestions: []
  };

  lines.forEach(line => {
    if (line.includes('정책 분석 요약')) {
      currentSection = 'summary';
    } else if (line.includes('통계적 인과 해석')) {
      currentSection = 'analysis';
    } else if (line.includes('핵심 교육 제언')) {
      currentSection = 'suggestions';
    } else if (currentSection) {
      // 리스트 기호(-) 제거 및 내용만 보관
      const cleanedLine = line.startsWith('-') ? line.substring(1).trim() : line;
      sections[currentSection].push(cleanedLine);
    }
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      
      {/* 1. 정책 분석 요약 */}
      {sections.summary.length > 0 && (
        <div style={{ 
          backgroundColor: 'var(--primary-light)', 
          color: 'var(--primary)',
          padding: '1.25rem',
          borderRadius: 'var(--radius-md)',
          borderLeft: '4px solid var(--primary)',
          fontWeight: 600,
          fontSize: '0.92rem',
          lineHeight: '1.6',
          display: 'flex',
          alignItems: 'flex-start',
          gap: '12px'
        }}>
          <span style={{ fontSize: '1.2rem', marginTop: '-2px' }}>📢</span>
          <div>{sections.summary.join(' ')}</div>
        </div>
      )}

      {/* 2. 통계적 인과 해석 */}
      {sections.analysis.length > 0 && (
        <div style={{ 
          backgroundColor: 'var(--bg-tertiary)',
          padding: '1.25rem',
          borderRadius: 'var(--radius-md)',
          border: '1px dashed var(--border-color)',
          fontSize: '0.88rem',
          lineHeight: '1.7',
          color: 'var(--text-secondary)'
        }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', marginBottom: '0.5rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
            <span>🧬</span> 통계적 인과 해석
          </div>
          <div>{sections.analysis.join(' ')}</div>
        </div>
      )}

      {/* 3. 핵심 교육 제언 */}
      {sections.suggestions.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div style={{ fontWeight: 600, color: 'var(--text-primary)', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '0.25rem' }}>
            <span>💡</span> 핵심 교육 제언
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {sections.suggestions.map((suggestion, idx) => (
              <div key={idx} style={{ 
                backgroundColor: 'var(--bg-primary)',
                border: '1px solid var(--border-color)',
                padding: '1rem 1.25rem',
                borderRadius: 'var(--radius-md)',
                display: 'flex',
                alignItems: 'flex-start',
                gap: '12px',
                boxShadow: 'var(--shadow-sm)'
              }}>
                <div style={{ 
                  backgroundColor: '#e6f9f0', 
                  color: 'var(--success)', 
                  padding: '4px', 
                  borderRadius: '50%',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  marginTop: '2px',
                  width: '20px',
                  height: '20px',
                  flexShrink: 0
                }}>
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                </div>
                <div style={{ fontSize: '0.86rem', lineHeight: '1.6', color: 'var(--text-primary)' }}>
                  {suggestion}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

    </div>
  );
};

export const AiPrediction: React.FC = () => {
  // 시뮬레이션 입력값 상태
  const [grade, setGrade] = useState<'중' | '고'>('중');
  const [budget, setBudget] = useState<number>(0);
  const [multi, setMulti] = useState<number>(0);
  const [care, setCare] = useState<number>(0);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [simResult, setSimResult] = useState<PredictionResult | null>(null);
  const [aiReport, setAiReport] = useState<string>('');

  // 시나리오 프리셋 정의
  const PRESETS = [
    { name: 'S0 현상유지', values: { h: 0, m: 0, c: 0 }, desc: '기존 예산 기조를 동일하게 유지합니다.' },
    { name: 'S2 분야균형', values: { h: 0, m: 5, c: 29 }, desc: '기초학력 복지 및 돌봄 지원을 균형 있게 증액합니다.' },
    { name: 'S3 적극강화', values: { h: 43, m: 5, c: 29 }, desc: '협력교사 배치, 튜터 증원, 돌봄 예산을 전폭 확대합니다.' },
    { name: 'S4 예산집중', values: { h: 47, m: 0, c: 0 }, desc: '예산을 학력향상(협력수업 등) 한 분야에 전면 투입합니다.' },
  ];

  // 시뮬레이션 계산 및 AI 분석 실행
  const handleRunSimulation = async () => {
    setLoading(true);
    setError('');
    try {
      // 1. 백엔드 /api/simulate 호출
      const prediction = await simulatePolicy(budget, multi, care, grade);
      setSimResult(prediction);

      // 2. 기여도(계수) 매핑 - 음수로 저감 효과를 표현
      const contributions = {
        학력향상_lag1: budget > 0 ? -prediction.shapData[0].impact : 0,
        다문화_lag1: multi > 0 ? -prediction.shapData[1].impact : 0,
        돌봄_lag1: care > 0 ? -prediction.shapData[2].impact : 0
      };

      // 3. Gemini API 기반 정성적 정책 리포트 생성
      const report = await generateAiReport(
        { d_h: budget, d_m: multi, d_c: care, grade },
        { 
          newRisk: prediction.newProxyIndex, 
          delta: -prediction.improvement, 
          contributions 
        }
      );
      setAiReport(report);
    } catch (err: any) {
      console.error(err);
      setError(err.message || '시뮬레이션 구동 및 리포트 생성 중 오류가 발생했습니다.');
    } finally {
      setLoading(false);
    }
  };

  // 프리셋 일괄 적용
  const handleApplyPreset = (h: number, m: number, c: number) => {
    setBudget(h);
    setMulti(m);
    setCare(c);
  };

  // 슬라이더 리셋
  const handleReset = () => {
    setBudget(0);
    setMulti(0);
    setCare(0);
    setSimResult(null);
    setAiReport('');
  };

  return (
    <div className="page-container container">
      <div className="banner" style={{ marginBottom: '2rem' }}>
        <div className="banner-content">
          <h2>데이터 기반 기초학력 정책 시뮬레이터</h2>
          <p>학제 버튼을 선택하고 슬라이더를 조정하여 예산 정책 시나리오에 따른 취약도 저감 효과와 AI 심층 제언 리포트를 실시간 확인하십시오.</p>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderLeft: '4px solid var(--danger)', marginBottom: '1.5rem', padding: '1rem' }}>
          <p style={{ color: 'var(--danger)', fontWeight: 500 }}>⚠️ {error}</p>
        </div>
      )}

      {/* 2단 그리드 구성: 좌측 컨트롤 / 우측 결과 */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '2rem' }}>
        
        {/* 좌측: 제어 패널 */}
        <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--border-color)', paddingBottom: '1rem' }}>
            <Settings size={20} style={{ color: 'var(--primary)' }} />
            <h3 className="text-h3">시나리오 조절 패널</h3>
          </div>

          {/* 1. 학교급 선택 */}
          <div>
            <label className="text-body" style={{ fontWeight: 600, display: 'block', marginBottom: '0.75rem' }}>1. 학교급(학제) 선택</label>
            <div style={{ display: 'flex', gap: '10px' }}>
              <button 
                className="preset-btn"
                style={{ 
                  flex: 1, 
                  justifyContent: 'center', 
                  backgroundColor: grade === '중' ? 'var(--primary)' : 'var(--bg-tertiary)',
                  color: grade === '중' ? 'white' : 'var(--text-primary)',
                  borderColor: grade === '중' ? 'var(--primary)' : 'var(--border-color)'
                }}
                onClick={() => setGrade('중')}
              >
                중학교
              </button>
              <button 
                className="preset-btn"
                style={{ 
                  flex: 1, 
                  justifyContent: 'center', 
                  backgroundColor: grade === '고' ? 'var(--primary)' : 'var(--bg-tertiary)',
                  color: grade === '고' ? 'white' : 'var(--text-primary)',
                  borderColor: grade === '고' ? 'var(--primary)' : 'var(--border-color)'
                }}
                onClick={() => setGrade('고')}
              >
                고등학교
              </button>
            </div>
          </div>

          {/* 2. 예산 슬라이더 조절 */}
          <div>
            <label className="text-body" style={{ fontWeight: 600, display: 'block', marginBottom: '1rem' }}>
              2. 예산 조정량 설정 (단위: 천원/명)
            </label>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* 학력향상 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="text-body" style={{ fontWeight: 500 }}>학력향상 예산 증액 (t-1년 시차효과)</span>
                  <span style={{ color: 'var(--primary)', fontWeight: 600 }}>+{budget} 천원</span>
                </div>
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={budget} 
                  onChange={(e) => setBudget(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--primary)' }}
                />
              </div>

              {/* 다문화 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="text-body" style={{ fontWeight: 500 }}>다문화이탈주민 지원 예산 증액</span>
                  <span style={{ color: 'var(--primary)', fontWeight: 600 }}>+{multi} 천원</span>
                </div>
                <input 
                  type="range" 
                  min="0" 
                  max="20" 
                  value={multi} 
                  onChange={(e) => setMulti(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--primary)' }}
                />
              </div>

              {/* 돌봄 */}
              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.5rem' }}>
                  <span className="text-body" style={{ fontWeight: 500 }}>돌봄 예산 증액</span>
                  <span style={{ color: 'var(--primary)', fontWeight: 600 }}>+{care} 천원</span>
                </div>
                <input 
                  type="range" 
                  min="0" 
                  max="100" 
                  value={care} 
                  onChange={(e) => setCare(Number(e.target.value))}
                  style={{ width: '100%', accentColor: 'var(--primary)' }}
                />
              </div>
            </div>
          </div>

          {/* 3. 프리셋 선택 */}
          <div>
            <label className="text-body" style={{ fontWeight: 600, display: 'block', marginBottom: '0.75rem' }}>
              3. 권장 시나리오 프리셋
            </label>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              {PRESETS.map((p, idx) => (
                <button 
                  key={idx}
                  className="preset-btn"
                  style={{ fontSize: '0.85rem', padding: '0.6rem 1rem', display: 'flex', flexDirection: 'column', alignItems: 'flex-start' }}
                  onClick={() => handleApplyPreset(p.values.h, p.values.m, p.values.c)}
                >
                  <span style={{ fontWeight: 600, color: 'var(--primary)' }}>{p.name}</span>
                  <span style={{ color: 'var(--text-secondary)', fontSize: '0.75rem', marginTop: '2px' }}>{p.desc}</span>
                </button>
              ))}
            </div>
          </div>

          {/* 실행 및 리셋 버튼 */}
          <div style={{ display: 'flex', gap: '10px', marginTop: '1rem' }}>
            <button 
              className="preset-btn" 
              style={{ width: '35%', justifyContent: 'center', backgroundColor: 'var(--bg-tertiary)' }}
              onClick={handleReset}
            >
              <RefreshCw size={16} style={{ marginRight: '6px' }} />
              리셋
            </button>
            <button 
              className="preset-btn"
              style={{ 
                width: '65%', 
                justifyContent: 'center', 
                backgroundColor: 'var(--primary)', 
                color: 'white',
                border: 'none',
                fontWeight: 600
              }}
              onClick={handleRunSimulation}
              disabled={loading}
            >
              {loading ? '분석 중...' : '예측 및 AI 리포트 생성'}
            </button>
          </div>
        </div>

        {/* 우측: 시뮬레이션 결과 및 AI 보고서 */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '2rem' }}>
          
          {loading && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '400px' }}>
              <Bot size={48} style={{ color: 'var(--primary)', animation: 'bounce 2s infinite', marginBottom: '1.5rem' }} />
              <h3 className="text-h3" style={{ marginBottom: '1rem' }}>예측 모델 연산 및 AI 리포트 작성 중</h3>
              <p className="text-body" style={{ color: 'var(--text-secondary)', marginBottom: '1.5rem' }}>데이터를 분석하여 통계적 제언을 준비하고 있습니다.</p>
              <div className="loader">
                <div className="loader-dot"></div>
                <div className="loader-dot"></div>
                <div className="loader-dot"></div>
              </div>
            </div>
          )}

          {!loading && !simResult && (
            <div className="card" style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', minHeight: '400px', backgroundColor: 'var(--bg-tertiary)', border: 'none' }}>
              <Bot size={48} style={{ color: 'var(--text-muted)', marginBottom: '1rem' }} />
              <h3 className="text-h3" style={{ color: 'var(--text-secondary)' }}>시뮬레이션 대기 중</h3>
              <p className="text-body" style={{ color: 'var(--text-muted)', textAlign: 'center', marginTop: '0.5rem' }}>좌측 조절 패널에서 조정한 후<br/>[예측 및 AI 리포트 생성] 버튼을 클릭하십시오.</p>
            </div>
          )}

          {!loading && simResult && (
            <>
              {/* 1. 종합 예측 지표 */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
                  <Award size={20} style={{ color: 'var(--primary)' }} />
                  <h3 className="text-h3">종합 예측 지수</h3>
                </div>
                <div style={{ display: 'flex', gap: '20px' }}>
                  <div style={{ flex: 1, backgroundColor: 'var(--bg-tertiary)', padding: '1.25rem', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>예상 취약도 지수</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--danger)' }}>{simResult.newProxyIndex}점</div>
                  </div>
                  <div style={{ flex: 1, backgroundColor: 'var(--bg-tertiary)', padding: '1.25rem', borderRadius: 'var(--radius-md)', textAlign: 'center' }}>
                    <div style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '4px' }}>취약도 개선폭 (기존 60.63 대비)</div>
                    <div style={{ fontSize: '2rem', fontWeight: 700, color: 'var(--success)' }}>
                      {simResult.improvement > 0 ? `-${simResult.improvement}점` : '0.0점'}
                    </div>
                  </div>
                </div>
              </div>

              {/* 2. 기여도 분석 차트 */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
                  <BarChart2 size={20} style={{ color: 'var(--primary)' }} />
                  <h3 className="text-h3">정책 요인별 기여도 (SHAP Value 절대값)</h3>
                </div>
                <div className="chart-container" style={{ height: '180px' }}>
                  <ResponsiveContainer width="100%" height="100%" minWidth={0}>
                    <BarChart layout="vertical" data={simResult.shapData} margin={{ top: 10, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-color)" />
                      <XAxis type="number" domain={[0, 'dataMax + 0.5']} />
                      <YAxis dataKey="feature" type="category" fontSize={11} width={130} />
                      <RechartsTooltip cursor={{ fill: 'transparent' }} />
                      <Bar dataKey="impact" name="저감 기여도" radius={[0, 4, 4, 0]} barSize={16}>
                        {simResult.shapData.map((entry, index) => (
                          <Cell key={`cell-${index}`} fill={entry.impact > 0 ? 'var(--primary)' : 'var(--text-muted)'} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              {/* 3. AI 상세 보고서 */}
              <div className="card" style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', borderBottom: '1px solid var(--border-color)', paddingBottom: '0.75rem' }}>
                  <FileText size={20} style={{ color: 'var(--primary)' }} />
                  <h3 className="text-h3">Gemini AI 정책 제언 리포트</h3>
                </div>
                {/* 기존 pre-wrap 줄글 형식을 마크다운 라인 파서 컴포넌트로 교체 적용 */}
                <MarkdownReportRenderer text={aiReport} />
              </div>
            </>
          )}

        </div>
      </div>
    </div>
  );
};
