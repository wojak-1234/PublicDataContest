import React, { useEffect, useState } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, Cell, LabelList } from 'recharts';
import { X, Check, ArrowRight, TrendingDown, Users, Globe } from 'lucide-react';
import { fetchPolicyData } from '../services/api';
import type { PolicyData, CharacteristicData, ProxyIndexData } from '../types';

export const PolicyAnalysis: React.FC = () => {
  const [policies, setPolicies] = useState<PolicyData[]>([]);
  const [characteristics, setCharacteristics] = useState<CharacteristicData[]>([]);
  const [proxyIndexAll, setProxyIndexAll] = useState<ProxyIndexData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const data = await fetchPolicyData();
        setPolicies(data.policies);
        setCharacteristics(data.characteristics);
        setProxyIndexAll(data.proxyIndexAll);
      } catch (error) {
        console.error("Failed to load policy data", error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const getCharIcon = (type: string) => {
    switch(type) {
      case 'gap': return <TrendingDown size={24} />;
      case 'population': return <Users size={24} />;
      case 'multicultural': return <Globe size={24} />;
      default: return <ArrowRight size={24} />;
    }
  };

  if (loading) {
    return (
      <div className="loader">
        <div className="loader-dot"></div>
        <div className="loader-dot"></div>
        <div className="loader-dot"></div>
      </div>
    );
  }

  // Create budget comparison data
  const budgetData = policies.map(p => ({
    region: p.region,
    budget: parseInt(p.budget.replace(/[^0-9]/g, '')),
    isTarget: p.isTarget
  })).sort((a, b) => b.budget - a.budget);

  return (
    <div className="page-container container">
      
      <div className="card" style={{ marginBottom: '2rem' }}>
        <h2 className="text-h2" style={{ marginBottom: '1.5rem' }}>주요 시도교육청 정책 비교</h2>
        <div style={{ overflowX: 'auto' }}>
          <table className="custom-table">
            <thead>
              <tr>
                <th>시도</th>
                <th>기초학력 예산</th>
                <th>두드림학교 수</th>
                <th>협력수업</th>
                <th>AI 코스웨어</th>
                <th>기초학력 조례</th>
                <th>특이사항</th>
              </tr>
            </thead>
            <tbody>
              {policies.map((policy, idx) => (
                <tr key={idx} className={`table-row ${policy.isTarget ? 'busan-row' : ''}`}>
                  <td style={{ fontWeight: 600 }}>
                    {policy.region} {policy.isTarget && <span className="metric-badge" style={{ backgroundColor: 'var(--busan-color)', color: 'white' }}>대상</span>}
                  </td>
                  <td>{policy.budget}</td>
                  <td>{policy.dodream}</td>
                  <td>
                    {policy.coTeaching ? 
                      <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}><Check size={16}/> 시행</span> : 
                      <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '4px' }}><X size={16}/> 미시행</span>}
                  </td>
                  <td>
                    {policy.aiCourseware ? 
                      <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}><Check size={16}/> 도입</span> : 
                      <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '4px' }}><X size={16}/> 미도입</span>}
                  </td>
                  <td>
                    {policy.ordinance ? 
                      <span style={{ color: 'var(--success)', display: 'flex', alignItems: 'center', gap: '4px' }}><Check size={16}/> 제정</span> : 
                      <span style={{ color: 'var(--danger)', display: 'flex', alignItems: 'center', gap: '4px' }}><X size={16}/> 미제정</span>}
                  </td>
                  <td style={{ color: 'var(--text-secondary)' }}>{policy.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="card-grid-2">
        <div className="card">
          <h3 className="text-h3" style={{ marginBottom: '1.5rem' }}>시도별 기초학력 예산 비교 (단위: 억원)</h3>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart layout="vertical" data={budgetData} margin={{ top: 10, right: 30, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-color)" />
                <XAxis type="number" />
                <YAxis dataKey="region" type="category" />
                <RechartsTooltip cursor={{fill: 'transparent'}} formatter={(val) => [`${val}억원`, '예산']} />
                <Bar dataKey="budget" radius={[0, 4, 4, 0]} barSize={24}>
                  {budgetData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.isTarget ? 'var(--busan-color)' : 'var(--primary)'} />
                  ))}
                  <LabelList dataKey="budget" position="right" style={{ fill: 'var(--text-secondary)', fontSize: '12px' }} formatter={(val: any) => `${val}억`} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h3 className="text-h3" style={{ marginBottom: '1.5rem' }}>시도별 기초학력 취약도 지수 (17개 시도 전체)</h3>
          <div className="chart-container" style={{ height: '500px' }}>
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart layout="vertical" data={proxyIndexAll} margin={{ top: 10, right: 40, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-color)" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="region" type="category" interval={0} fontSize={12} />
                <RechartsTooltip cursor={{fill: 'transparent'}} />
                <Bar dataKey="index" radius={[0, 4, 4, 0]} barSize={16}>
                  {proxyIndexAll.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.region === '부산' ? 'var(--busan-color)' : 'var(--text-muted)'} />
                  ))}
                  <LabelList dataKey="index" position="right" style={{ fill: 'var(--text-secondary)', fontSize: '11px' }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <h2 className="text-h2" style={{ marginTop: '3rem', marginBottom: '1.5rem' }}>부산 지역 특수성</h2>
      <div className="card-grid-3">
        {characteristics.map(char => (
          <div key={char.id} className="card flex items-center gap-4">
            <div style={{ backgroundColor: 'var(--primary-light)', color: 'var(--primary)', padding: '1rem', borderRadius: 'var(--radius-lg)' }}>
              {getCharIcon(char.iconType)}
            </div>
            <div>
              <h4 className="text-h3">{char.title}</h4>
              <p className="text-body" style={{ color: 'var(--text-secondary)', marginTop: '0.25rem' }}>{char.description}</p>
            </div>
          </div>
        ))}
      </div>

    </div>
  );
};
