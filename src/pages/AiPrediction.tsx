import React, { useState } from 'react';
import { Bot, Send, ChevronRight, X, Check, BarChart2, Zap } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';
import { predictPolicyEffect } from '../services/api';
import type { PredictionResult } from '../types';

const PRESET_QUESTIONS = [
  "서울의 협력수업 정책을 부산에 적용하면?",
  "대구의 기초학력 지원 정책을 부산에 도입하면?",
  "경기의 튜터 배치를 부산에 확대 적용하면?",
  "세종의 AI 학습 프로그램을 부산에 도입하면?"
];

export const AiPrediction: React.FC = () => {
  const [inputValue, setInputValue] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PredictionResult | null>(null);

  const handlePredict = async (question: string) => {
    if (!question.trim()) return;
    
    setInputValue('');
    setLoading(true);
    setResult(null);
    
    try {
      const prediction = await predictPolicyEffect(question);
      setResult(prediction);
    } catch (error) {
      console.error("Prediction failed", error);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handlePredict(inputValue);
    }
  };

  return (
    <div className="page-container container" style={{ maxWidth: '1000px' }}>
      
      {!result && !loading && (
        <div className="ai-intro animation-fadeIn">
          <div className="ai-icon-wrapper">
            <Bot size={36} />
          </div>
          <h2>정책 효과 예측 AI</h2>
          <p>타 시도의 정책을 부산에 도입했을 때의 예상 효과와<br/>기초학력 취약도 지수 변화를 시뮬레이션 해보세요.</p>
        </div>
      )}

      {loading && (
        <div className="card" style={{ textAlign: 'center', padding: '4rem 2rem', marginBottom: '2rem' }}>
          <div className="ai-icon-wrapper" style={{ animation: 'bounce 2s infinite' }}>
            <Bot size={36} />
          </div>
          <h3 className="text-h3" style={{ marginBottom: '1rem' }}>데이터 분석 및 시나리오 모델링 중...</h3>
          <div className="loader">
            <div className="loader-dot"></div>
            <div className="loader-dot"></div>
            <div className="loader-dot"></div>
          </div>
        </div>
      )}

      {result && !loading && (
        <div>
          <div className="chat-bubble-user">
            {result.question}
          </div>
          
          <div className="chat-bubble-ai">
            <div className="prediction-header">
              <Bot size={24} style={{ color: 'var(--primary)' }} />
              <h3 className="text-h3">AI 예측 결과 리포트</h3>
            </div>
            
            <p style={{ marginBottom: '2rem', color: 'var(--text-secondary)' }}>
              해당 정책 도입 시, 부산의 기초학력 취약도 지수는 <strong style={{color: 'var(--success)', fontSize: '1.2rem'}}>{result.improvement.toFixed(1)}p 개선</strong>되어 
              <strong> {result.newProxyIndex.toFixed(1)}</strong> 수준이 될 것으로 예측됩니다.
            </p>

            <div className="card-grid-2">
              <div className="card" style={{ boxShadow: 'none', border: '1px solid var(--border-color)' }}>
                <h4 className="text-h3" style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <BarChart2 size={18} /> 예상 취약도 지수 비교
                </h4>
                <div style={{ height: '250px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart layout="vertical" data={result.chartData} margin={{ top: 0, right: 30, left: 10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                      <XAxis type="number" domain={[0, 80]} />
                      <YAxis dataKey="region" type="category" width={50} />
                      <RechartsTooltip cursor={{fill: 'transparent'}} />
                      <Bar dataKey="index" radius={[0, 4, 4, 0]} barSize={20}>
                        {result.chartData.map((entry, index) => {
                          let fillColor = 'var(--primary-light)';
                          if (entry.region === '부산') fillColor = 'var(--success)';
                          return <Cell key={`cell-${index}`} fill={fillColor} />;
                        })}
                        <LabelList dataKey="index" position="right" formatter={(val: any) => val.toFixed(1)} style={{ fill: 'var(--text-secondary)', fontSize: '12px' }} />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="card" style={{ boxShadow: 'none', border: '1px solid var(--border-color)' }}>
                <h4 className="text-h3" style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <Zap size={18} /> SHAP 정책 기여도
                </h4>
                <div style={{ height: '250px' }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart layout="vertical" data={result.shapData} margin={{ top: 0, right: 30, left: 30, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} />
                      <XAxis type="number" />
                      <YAxis dataKey="feature" type="category" width={80} />
                      <RechartsTooltip cursor={{fill: 'transparent'}} />
                      <Bar dataKey="impact" fill="var(--primary)" radius={[0, 4, 4, 0]} barSize={20}>
                        <LabelList dataKey="impact" position="right" formatter={(val: any) => `+${val.toFixed(1)}`} style={{ fill: 'var(--text-secondary)', fontSize: '12px' }} />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </div>

            <div style={{ marginTop: '2rem' }}>
              <h4 className="text-h3" style={{ marginBottom: '1rem' }}>도입 후 정책 변화 시뮬레이션</h4>
              <div style={{ overflowX: 'auto' }}>
                <table className="custom-table" style={{ border: '1px solid var(--border-color)', borderRadius: 'var(--radius-lg)' }}>
                  <thead>
                    <tr>
                      <th>시도</th>
                      <th>기초학력 예산</th>
                      <th>협력수업</th>
                      <th>특이사항 (예측)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.policyComparison.filter(p => p.region === '서울' || p.region === '부산').map((policy, idx) => (
                      <tr key={idx} className={policy.region === '부산' ? 'busan-row' : ''}>
                        <td style={{ fontWeight: 600 }}>{policy.region}</td>
                        <td style={{ color: policy.region === '부산' ? 'var(--success)' : 'inherit', fontWeight: policy.region === '부산' ? 'bold' : 'normal' }}>
                          {policy.budget}
                        </td>
                        <td>
                          {policy.coTeaching ? 
                            <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}><Check size={16}/> 시행</span> : 
                            <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '4px' }}><X size={16}/> 미시행</span>}
                        </td>
                        <td>{policy.note}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        </div>
      )}

      {!result && !loading && (
        <div className="preset-questions">
          {PRESET_QUESTIONS.map((q, idx) => (
            <button key={idx} className="preset-btn" onClick={() => handlePredict(q)}>
              {q}
              <ChevronRight size={20} />
            </button>
          ))}
        </div>
      )}

      <div className="chat-input-wrapper">
        <input 
          type="text" 
          className="chat-input"
          placeholder="예: 서울의 협력수업 정책을 부산에 적용하면?"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
        />
        <button 
          className="chat-send-btn" 
          onClick={() => handlePredict(inputValue)}
          disabled={!inputValue.trim() || loading}
        >
          <Send size={18} />
        </button>
      </div>

    </div>
  );
};
