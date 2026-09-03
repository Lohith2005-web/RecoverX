import React, { useState } from 'react';
import { Navbar } from './components/Navbar';
import type { NavTab } from './components/Navbar';
import { CommandCenter } from './pages/CommandCenter';
import { IncidentInvestigation } from './pages/IncidentInvestigation';
import { WhatIfSimulation } from './pages/WhatIfSimulation';
import { TransactionInvestigation } from './pages/TransactionInvestigation';

export const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [selectedTxnId] = useState<string>('txn_001160');

  const handleNavigateToIncident = (incidentId: string) => {
    setSelectedIncidentId(incidentId);
    setActiveTab('incidents');
  };

  const handleNavigateToWhatIf = () => {
    setActiveTab('simulation');
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col font-sans selection:bg-blue-600 selection:text-white">
      {/* Top Navigation Bar */}
      <Navbar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main Content View Container */}
      <main className="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeTab === 'dashboard' && (
          <CommandCenter
            onNavigateToIncident={handleNavigateToIncident}
            onNavigateToWhatIf={handleNavigateToWhatIf}
          />
        )}

        {activeTab === 'incidents' && (
          <IncidentInvestigation
            selectedIncidentId={selectedIncidentId}
            onBack={() => setActiveTab('dashboard')}
            onRunWhatIf={handleNavigateToWhatIf}
          />
        )}

        {activeTab === 'simulation' && <WhatIfSimulation />}

        {activeTab === 'transactions' && (
          <TransactionInvestigation
            initialTransactionId={selectedTxnId}
            onBack={() => setActiveTab('dashboard')}
          />
        )}
      </main>

      {/* Command Center Footer */}
      <footer className="border-t border-slate-900 bg-slate-950 py-4 text-center text-xs text-slate-500 font-mono">
        <p>RecoverX — Autonomous Revenue Recovery & Payment Intelligence Command Center</p>
      </footer>
    </div>
  );
};

export default App;
