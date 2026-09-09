import React, { useEffect, useState, useCallback } from 'react';
import { predictions } from '../api/endpoints';
import { RiskBadge, FactorBars, Spinner, ErrorState, EmptyState } from '../components/common.jsx';
import { riskColor } from '../utils/risk';
import { fmtDate } from '../utils/format';
import { useToast } from '../context/ToastContext.jsx';
import { useWebSocket } from '../hooks/useWebSocket';

export default function Predictions() {
  const toast = useToast();
  const { subscribe } = useWebSocket();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [sortKey, setSortKey] = useState('risk_score');
  const [sortDir, setSortDir] = useState(-1);
  const [selected, setSelected] = useState(null);
  const [generating, setGenerating] = useState(false);

  const load = useCallback(async () => {
    try {
      const r = await predictions.list(200);
      setRows(r); setError('');
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // generation now runs in the background; reload when it completes
  useEffect(() => {
    const off = subscribe('predictions_generated', (m) => {
      setGenerating(false);
      toast.success(`Generated ${m.payload?.n_predictions} predictions — ${m.payload?.alerts_created ?? 0} alerts`);
      load();
    });
    const off2 = subscribe('predictions_error', (m) => {
      setGenerating(false);
      toast.error(m.payload?.error || 'Prediction generation failed');
    });
    return () => { off(); off2(); };
  }, [subscribe, load, toast]);

  async function generate() {
    setGenerating(true);
    toast.info('Running the model over all ATMs for the next 6h window…');
    try {
      await predictions.generate();
    } catch (e) { toast.error(e.message); setGenerating(false); }
  }

  function toggleSort(k) {
    if (sortKey === k) setSortDir((d) => -d);
    else { setSortKey(k); setSortDir(-1); }
  }

  const sorted = [...rows].sort((a, b) => {
    const av = a[sortKey], bv = b[sortKey];
    if (av === bv) return 0;
    return (av > bv ? 1 : -1) * sortDir;
  });

  if (loading) return <Spinner label="Loading predictions…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  const highRisk = rows.filter((r) => r.risk_score >= 60).length;

  return (
    <div className="page">
      <div className="flex-between">
        <div>
          <div className="text-sm muted">
            {rows.length} predictions · <span style={{ color: riskColor(75) }}>{highRisk} high-risk (≥60)</span> · next 6h window
          </div>
        </div>
        <button className="btn btn-primary" onClick={generate} disabled={generating}>
          {generating ? 'Running model…' : '⟳ Generate for next window'}
        </button>
      </div>

      {rows.length === 0 ? (
        <div className="panel"><EmptyState title="No predictions yet" hint="Click 'Generate for next window' to run the model." /></div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr>
                <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('atm_id')}>ATM {sortKey === 'atm_id' && (sortDir < 0 ? '↓' : '↑')}</th>
                <th>District</th>
                <th>Window</th>
                <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('risk_score')}>Risk {sortKey === 'risk_score' && (sortDir < 0 ? '↓' : '↑')}</th>
                <th style={{ cursor: 'pointer' }} onClick={() => toggleSort('probability')}>Probability {sortKey === 'probability' && (sortDir < 0 ? '↓' : '↑')}</th>
                <th>Confidence</th>
                <th>Model</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((p) => (
                <tr key={p.prediction_id} className="clickable" onClick={() => setSelected(p)}>
                  <td className="mono">{p.atm_id}</td>
                  <td>{p.district}</td>
                  <td className="text-sm muted">{fmtDate(p.window_start)} {p.window_start?.slice(11, 16)}</td>
                  <td><RiskBadge score={p.risk_score} showBand /></td>
                  <td className="mono">{(p.probability * 100).toFixed(1)}%</td>
                  <td className="mono">{(p.confidence * 100).toFixed(0)}%</td>
                  <td className="mono text-xs muted">{p.model_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Detail drawer */}
      {selected && (
        <div className="panel" style={{ position: 'fixed', right: 20, top: 80, width: 380, zIndex: 2000, maxHeight: 'calc(100vh - 120px)', overflowY: 'auto', boxShadow: '0 20px 60px rgba(0,0,0,0.5)' }}>
          <div className="flex-between mb-2">
            <div>
              <div className="mono" style={{ fontSize: 16, fontWeight: 700 }}>{selected.atm_id}</div>
              <div className="text-sm muted">{selected.district}, {selected.state}</div>
            </div>
            <button className="btn btn-sm" onClick={() => setSelected(null)}>✕</button>
          </div>
          <div className="flex" style={{ justifyContent: 'space-around', padding: '6px 0' }}>
            <div style={{ textAlign: 'center' }}><div style={{ fontSize: 24, fontWeight: 700, color: riskColor(selected.risk_score) }}>{selected.risk_score}</div><div className="text-xs muted">RISK</div></div>
            <div style={{ textAlign: 'center' }}><div style={{ fontSize: 24, fontWeight: 700, color: 'var(--cyan)' }}>{(selected.probability * 100).toFixed(1)}%</div><div className="text-xs muted">PROBABILITY</div></div>
            <div style={{ textAlign: 'center' }}><div style={{ fontSize: 24, fontWeight: 700, color: 'var(--purple)' }}>{(selected.confidence * 100).toFixed(0)}%</div><div className="text-xs muted">CONFIDENCE</div></div>
          </div>
          <div className="text-xs muted">Window: {fmtDate(selected.window_start)} {selected.window_start?.slice(11, 16)} → {selected.window_end?.slice(11, 16)} UTC</div>
          <div className="divider" />
          <div className="panel-title" style={{ marginBottom: 8 }}>Key Drivers (SHAP)</div>
          <FactorBars factors={selected.factors || []} />
          {selected.recommended_action && (
            <>
              <div className="divider" />
              <div className="panel-title" style={{ marginBottom: 6 }}>Recommended Action</div>
              <div className="text-sm" style={{ lineHeight: 1.5 }}>{selected.recommended_action}</div>
            </>
          )}
        </div>
      )}
    </div>
  );
}