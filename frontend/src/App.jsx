import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { ResearchProvider } from './context/ResearchContext';
import AppLayout from './components/layout/AppLayout';
import Overview from './pages/Overview';
import NewResearch from './pages/NewResearch';
import ResearchResults from './pages/ResearchResults';
import Verification from './pages/Verification';
import AIInsights from './pages/AIInsights';
import AnalyticsDashboard from './pages/AnalyticsDashboard';
import AgentActivity from './pages/AgentActivity';

export default function App() {
  return (
    <ResearchProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<AppLayout />}>
            <Route index element={<Overview />} />
            <Route path="new-research" element={<NewResearch />} />
            <Route path="results" element={<ResearchResults />} />
            <Route path="research-results" element={<Navigate to="/results" replace />} />
            <Route path="verification" element={<Verification />} />
            <Route path="insights" element={<AIInsights />} />
            <Route path="dashboard" element={<AnalyticsDashboard />} />
            <Route path="activity" element={<AgentActivity />} />
            <Route path="agents" element={<Navigate to="/activity" replace />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ResearchProvider>
  );
}

