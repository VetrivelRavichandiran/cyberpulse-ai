import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { alerts, investigations } from '../api/endpoints';
import { RiskBadge, SeverityBadge, StatusBadge, Spinner, ErrorState, EmptyState } from '../components/common.jsx';
import { fmtDateTime, timeAgo } from '../utils/format';
import { useToast } from '../context/ToastContext.jsx';

const TABS = ['ALL', 'NEW', 'ACKNOWLEDGED', 'INVESTIGATING', 'ESCALATED', 'RESOLVED'];

export default function Alerts() {
  const toast = useToast();
  const navigate = useNavigate();
  const [rows, setRows] = useState([]);
  const [tab, setTab] = useState('ALL');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busyId, setBusyId] = useState('');

  const load = useCallback(async () => {
    try { setRows(await alerts.list(200)); setError(''); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function act(id, fn, verb) {
    setBusyId(id);
    try { await fn(); toast.success(`Alert ${verb}`); await load(); }
    catch (e) { toast.error(e.message); }
    finally { setBusyId(''); }
  }

  async function openInvestigation(alertId) {
    setBusyId(alertId);
    try {
      const inv = await investigations.fromAlert(alertId);
      toast.success(`Investigation ${inv.case_id} opened`);
      navigate(`/investigations/${inv.case_id}`);
    } catch (e) { toast.error(e.message); }
    finally { setBusyId(''); }
  }

  const filtered = tab === 'ALL' ? rows : rows.filter((r) => r.status === tab);
  const counts = {};
  rows.forEach((r) => { counts[r.status] = (counts[r.status] || 0) + 1; });

  if (loading) return <Spinner label="Loading alerts…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;

  return (
    <div className="page">
      <div className="tabs">
        {TABS.map((t) => (
          <div key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t}{t !== 'ALL' && counts[t] ? <span className="tab-count">{counts[t]}</span> : null}
          </div>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="panel"><EmptyState icon="⚠" title="No alerts in this state" hint="Run predictions or the demo scenario to generate alerts." /></div>
      ) : (
        <div className="table-wrap">
          <table className="data">
            <thead>
              <tr><th>Severity</th><th>Alert</th><th>ATM</th><th>District</th><th>Risk</th><th>Status</th><th>Created</th><th style={{ textAlign: 'right' }}>Actions</th></tr>
            </thead>
            <tbody>
              {filtered.map((a) => (
                <tr key={a.alert_id}>
                  <td><SeverityBadge sev={a.severity} /></td>
                  <td>
                    <div style={{ fontWeight: 500 }}>{a.title}</div>
                    <div className="mono text-xs muted">{a.alert_id}</div>
                  </td>
                  <td className="mono">{a.atm_id}</td>
                  <td>{a.district}</td>
                  <td><RiskBadge score={a.risk_score} /></td>
                  <td><StatusBadge status={a.status} /></td>
                  <td className="text-sm muted" title={fmtDateTime(a.created_at)}>{timeAgo(a.created_at)}</td>
                  <td>
                    <div className="flex" style={{ justifyContent: 'flex-end', gap: 6 }}>
                      {a.status === 'NEW' && <button className="btn btn-sm" disabled={busyId === a.alert_id} onClick={() => act(a.alert_id, () => alerts.acknowledge(a.alert_id), 'acknowledged')}>Acknowledge</button>}
                      {a.status === 'NEW' && <button className="btn btn-sm btn-danger" disabled={busyId === a.alert_id} onClick={() => act(a.alert_id, () => alerts.escalate(a.alert_id), 'escalated')}>Escalate</button>}
                      {['NEW', 'ACKNOWLEDGED', 'INVESTIGATING', 'ESCALATED'].includes(a.status) && (
                        <button className="btn btn-sm btn-primary" disabled={busyId === a.alert_id} onClick={() => openInvestigation(a.alert_id)}>Open investigation</button>
                      )}
                      {a.status !== 'RESOLVED' && <button className="btn btn-sm" disabled={busyId === a.alert_id} onClick={() => act(a.alert_id, () => alerts.resolve(a.alert_id), 'resolved')}>Resolve</button>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}