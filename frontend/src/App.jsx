import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { useAuth } from './hooks/useAuth';
import Layout from './components/Layout.jsx';
import Login from './pages/Login.jsx';
import Dashboard from './pages/Dashboard.jsx';
import LiveMap from './pages/LiveMap.jsx';
import Predictions from './pages/Predictions.jsx';
import Alerts from './pages/Alerts.jsx';
import Investigations from './pages/Investigations.jsx';
import InvestigationDetail from './pages/InvestigationDetail.jsx';
import Model from './pages/Model.jsx';
import Demo from './pages/Demo.jsx';
import Activity from './pages/Activity.jsx';

function Protected({ children }) {
  const { user, loading } = useAuth();
  if (loading) return <div className="page-loading"><div className="spinner" /><p>Authenticating…</p></div>;
  if (!user) return <Navigate to="/login" replace />;
  return children;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Protected><Layout /></Protected>}>
        <Route index element={<Dashboard />} />
        <Route path="map" element={<LiveMap />} />
        <Route path="predictions" element={<Predictions />} />
        <Route path="alerts" element={<Alerts />} />
        <Route path="investigations" element={<Investigations />} />
        <Route path="investigations/:caseId" element={<InvestigationDetail />} />
        <Route path="model" element={<Model />} />
        <Route path="demo" element={<Demo />} />
        <Route path="activity" element={<Activity />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}