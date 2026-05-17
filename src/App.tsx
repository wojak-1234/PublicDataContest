import { useState } from 'react';
import { Navbar } from './components/layout/Navbar';
import { Dashboard } from './pages/Dashboard';
import { PolicyAnalysis } from './pages/PolicyAnalysis';
import { AiPrediction } from './pages/AiPrediction';

function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'policy' | 'ai'>('dashboard');

  return (
    <div className="app-root">
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      <main>
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'policy' && <PolicyAnalysis />}
        {activeTab === 'ai' && <AiPrediction />}
      </main>
    </div>
  );
}

export default App;
