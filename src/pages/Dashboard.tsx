import React, { useEffect, useState } from 'react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip as RechartsTooltip, ResponsiveContainer, BarChart, Bar, Cell, LabelList } from 'recharts';
import { AlertTriangle, Users, BookOpen, DollarSign, ArrowDownRight } from 'lucide-react';
import { fetchDashboardData } from '../services/api';
import type { MetricData, TrendData, ProxyIndexData } from '../types';

export const Dashboard: React.FC = () => {
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [trends, setTrends] = useState<TrendData[]>([]);
  const [proxyIndex, setProxyIndex] = useState<ProxyIndexData[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const data = await fetchDashboardData();
        setMetrics(data.metrics);
        setTrends(data.trends);
        setProxyIndex(data.proxyIndex);
      } catch (error) {
        console.error("Failed to load dashboard data", error);
      } finally {
        setLoading(false);
      }
    };
    loadData();
  }, []);

  const getIcon = (type: string) => {
    switch (type) {
      case 'budget': return <DollarSign size={20} />;
      case 'school': return <BookOpen size={20} />;
      case 'gap': return <AlertTriangle size={20} />;
      case 'tutor': return <Users size={20} />;
      default: return <BookOpen size={20} />;
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

  return (
    <div className="page-container container">
      <div className="banner">
        <div className="banner-content">
          <h2>기초학력 미달 학생, 코로나19 이후 2~3배 증가</h2>
          <p>부산 지역 학생들의 기초학력 보장을 위한 선제적 대응이 필요한 시점입니다.</p>
        </div>
        <div className="banner-stats">
          <div className="banner-stat-box">
            <div className="banner-stat-label">중학 수학 미달</div>
            <div className="banner-stat-value">12.7%</div>
          </div>
          <div className="banner-stat-box">
            <div className="banner-stat-label">중학 국어 미달</div>
            <div className="banner-stat-value">10.1%</div>
          </div>
        </div>
      </div>

      <div className="card-grid-4">
        {metrics.map(metric => (
          <div key={metric.id} className="card metric-card">
            <div className="metric-header">
              <span className="metric-title">{metric.label}</span>
              <div className={`metric-icon ${metric.status}`}>
                {getIcon(metric.iconType)}
              </div>
            </div>
            <div className="metric-value">{metric.value}</div>
            <div className="metric-subtext">
              {metric.badge && (
                <span className={`metric-badge ${metric.status === 'danger' ? 'badge-danger' : ''}`}>
                  {metric.badge.includes('하락') ? <ArrowDownRight size={12}/> : <AlertTriangle size={12}/>}
                  {metric.badge}
                </span>
              )}
              {metric.subtext}
            </div>
          </div>
        ))}
      </div>

      <div className="card-grid-2">
        <div className="card">
          <h3 className="text-h3" style={{ marginBottom: '1.5rem' }}>기초학력 미달률 추이 (2019-2024)</h3>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <AreaChart data={trends} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorMath" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--primary)" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="var(--primary)" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorKorean" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="var(--warning)" stopOpacity={0.8}/>
                    <stop offset="95%" stopColor="var(--warning)" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="year" />
                <YAxis domain={[0, 15]} unit="%" />
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border-color)" />
                <RechartsTooltip />
                <Area type="monotone" dataKey="math" name="수학 미달률" stroke="var(--primary)" fillOpacity={1} fill="url(#colorMath)" />
                <Area type="monotone" dataKey="korean" name="국어 미달률" stroke="var(--warning)" fillOpacity={1} fill="url(#colorKorean)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="card">
          <h3 className="text-h3" style={{ marginBottom: '1.5rem' }}>취약도 지수 비교 (Proxy Index - 낮을수록 양호)</h3>
          <div className="chart-container">
            <ResponsiveContainer width="100%" height="100%" minWidth={0}>
              <BarChart layout="vertical" data={proxyIndex} margin={{ top: 10, right: 30, left: 20, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" horizontal={true} vertical={false} stroke="var(--border-color)" />
                <XAxis type="number" domain={[0, 100]} />
                <YAxis dataKey="region" type="category" />
                <RechartsTooltip cursor={{fill: 'transparent'}} />
                <Bar dataKey="index" radius={[0, 4, 4, 0]} barSize={24}>
                  {proxyIndex.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.isTarget ? 'var(--busan-color)' : 'var(--primary-light)'} />
                  ))}
                  <LabelList dataKey="index" position="right" style={{ fill: 'var(--text-secondary)', fontSize: '12px' }} />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      <div className="card-grid-2">
        <div className="card" style={{ backgroundColor: 'var(--bg-tertiary)', border: 'none' }}>
          <h3 className="text-h3" style={{ marginBottom: '1rem' }}>연구 배경</h3>
          <p className="text-body" style={{ color: 'var(--text-secondary)' }}>
            본 시스템은 부산 지역의 기초학력 현황을 다각도로 분석하고, 타 시도의 성공적인 교육 정책을 부산에 적용했을 때의 기대 효과를 시뮬레이션하기 위해 개발된 시뮬레이터입니다.
          </p>
        </div>
        <div className="card" style={{ backgroundColor: 'var(--bg-tertiary)', border: 'none' }}>
          <h3 className="text-h3" style={{ marginBottom: '1rem' }}>부산의 현황과 과제</h3>
          <p className="text-body" style={{ color: 'var(--text-secondary)' }}>
            현재 부산은 기초학력 지원 예산이 상대적으로 부족하며, 동서 간 교육 격차가 심화되고 있습니다. 효과적인 자원 배분과 데이터 기반의 정책 의사결정이 절실히 요구됩니다.
          </p>
        </div>
      </div>
    </div>
  );
};
