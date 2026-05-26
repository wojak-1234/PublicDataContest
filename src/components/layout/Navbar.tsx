import React from 'react';
import { GraduationCap, BarChart2, TrendingUp, MessageSquare } from 'lucide-react';

interface NavbarProps {
  activeTab: 'dashboard' | 'policy' | 'ai';
  setActiveTab: (tab: 'dashboard' | 'policy' | 'ai') => void;
}

export const Navbar: React.FC<NavbarProps> = ({ activeTab, setActiveTab }) => {
  return (
    <header className="navbar">
      <div className="container">
        <div className="navbar-inner">
          <div className="navbar-brand">
            <GraduationCap className="navbar-brand-icon" />
            <div>
              <h1 className="navbar-title">기초학력 정책 분석 시스템 MVP</h1>
              <p className="navbar-subtitle">지역별 기초학력 지원 정책 비교 및 부산 적용 효과 예측</p>
            </div>
          </div>
          
          <div className="navbar-meta">
            <div className="navbar-meta-item">
              <span style={{color: 'var(--success)'}}>●</span> 
              데이터 기준: 2024년 학업성취도 평가
            </div>
            <div className="navbar-meta-item">
              분석 대상: 17개 시도교육청
            </div>
          </div>
        </div>
        
        <div className="nav-tabs">
          <button 
            className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
            onClick={() => setActiveTab('dashboard')}
          >
            <BarChart2 size={18} />
            현황 대시보드
          </button>
          <button 
            className={`nav-tab ${activeTab === 'policy' ? 'active' : ''}`}
            onClick={() => setActiveTab('policy')}
          >
            <TrendingUp size={18} />
            정책 비교 분석
          </button>
          <button 
            className={`nav-tab ${activeTab === 'ai' ? 'active' : ''}`}
            onClick={() => setActiveTab('ai')}
          >
            <MessageSquare size={18} />
            효과 예측 AI
          </button>
        </div>
      </div>
    </header>
  );
};
