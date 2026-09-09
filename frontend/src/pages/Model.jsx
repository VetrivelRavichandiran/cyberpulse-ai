import React, { useCallback, useEffect, useState } from 'react';
import { model } from '../api/endpoints';
import { ErrorState, FactorBars, Spinner } from '../components/common.jsx';

export default function Model() {
  const [info, setInfo] = useState(null); const [evaluation, setEvaluation] = useState(null); const [features, setFeatures] = useState([]); const [error, setError] = useState(''); const [loading, setLoading] = useState(true);
  const load = useCallback(async () => { try { const [i, e, f] = await Promise.all([model.info(), model.evaluation(), model.featureImportance()]); setInfo(i); setEvaluation(e); setFeatures(f); setError(''); } catch (err) { setError(err.message); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load]);
  if (loading) return <Spinner label="Loading model details…" />; if (error) return <ErrorState message={error} onRetry={load} />;
  const metrics = evaluation?.metrics || evaluation || {}; const version = info?.version || info?.model_version || '—';
  return <div className="page"><div className="grid grid-4"><div className="kpi-card"><div className="kpi-label">Model version</div><div className="kpi-value" style={{ fontSize: 21 }}>{version}</div><div className="kpi-sub">Active model artifact</div></div>{['roc_auc','precision','recall'].map((k) => <div className="kpi-card" key={k}><div className="kpi-label">{k.replace('_', ' ').toUpperCase()}</div><div className="kpi-value">{metrics[k] != null ? `${(Number(metrics[k]) * 100).toFixed(1)}%` : '—'}</div><div className="kpi-sub">Evaluation metric</div></div>)}</div><div className="panel"><div className="panel-title">Model Information</div><pre className="text-sm" style={{ whiteSpace: 'pre-wrap', color: 'var(--text)' }}>{JSON.stringify(info, null, 2)}</pre></div><div className="panel"><div className="panel-title">Feature Importance</div><FactorBars factors={features} max={Math.max(...features.map((f) => f.importance || 0), 0.001)} /></div></div>;
}
