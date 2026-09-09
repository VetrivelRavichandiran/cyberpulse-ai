import React, { useEffect, useState, useCallback, useMemo } from 'react';
import { Link } from 'react-router-dom';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis, Tooltip, CartesianGrid,
  BarChart, Bar, PieChart, Pie, Cell, LineChart, Line,
} from 'recharts';
import { dashboard, predictions, alerts } from '../api/endpoints';
import { KpiCard, RiskBadge, Spinner, ErrorState, EmptyState, RiskGauge } from '../components/common.jsx';
import { riskColor, severityColor } from '../utils/risk';
import { fmtNum, fmtDate, timeAgo } from '../utils/format';
import { useWebSocket } from '../hooks/useWebSocket';

const STATUS_COLORS = {
  NEW: '#22d3ee', ACKNOWLEDGED: '#fbbf24', INVESTIGATING: '#a78bfa',
  ESCALATED: '#fb923c', RESOLVED: '#34d399',
};

// small inline sparkline used inside KPI cards
function Spark({ data, color = 'var(--cyan)', dataKey = 'count' }) {
  if (!data || data.length < 2) return <div style={{ height: 30 }} />;
  return (
    <div style={{ height: 30, marginTop: 6 }}>
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
          <defs>
            <linearGradient id={`sp-${color.replace(/[^a-z0-9]/gi, '')}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={color} stopOpacity={0.4} />
              <stop offset="100%" stopColor={color} stopOpacity={0} />
            </linearGradient>
          </defs>
          <Area type="monotone" dataKey={dataKey} stroke={color} strokeWidth={1.5}
            fill={`url(#sp-${color.replace(/[^a-z0-9]/gi, '')})`} isAnimationActive={false} />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}

function ChartTooltip({ active, payload, label }) {
  if (!active || !payload || !payload.length) return null;
  return (
    <div className="ctip">
      <div className="ctip-label">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="ctip-row">
          <span className="ctip-dot" style={{ background: p.color || p.stroke || p.fill }} />
          {p.name}: <b>{typeof p.value === 'number' ? fmtNum(p.value) : p.value}</b>
        </div>
      ))}
    </div>
  );
}

export default function Dashboard() {
  const [summary, setSummary] = useState(null);
  const [complaintTrend, setComplaintTrend] = useState([]);
  const [txActivity, setTxActivity] = useState([]);
  const [riskTrend, setRiskTrend] = useState([]);
  const [districtRisk, setDistrictRisk] = useState([]);
  const [alertStatus, setAlertStatus] = useState([]);
  const [hotspots, setHotspots] = useState([]);
  const [recentAlerts, setRecentAlerts] = useState([]);
  const [liveEvents, setLiveEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { subscribe } = useWebSocket();

  const load = useCallback(async () => {
    try {
      const [s, ct, ta, rt, dr, as, hs, al] = await Promise.all([
        dashboard.summary(),
        dashboard.complaintTrend(14),
        dashboard.transactionActivity(14),
        dashboard.riskTrend(14),
        dashboard.districtRisk(),
        dashboard.alertStatus(),
        predictions.hotspots(),
        alerts.list(8),
      ]);
      setSummary(s); setComplaintTrend(ct); setTxActivity(ta); setRiskTrend(rt);
      setDistrictRisk(dr); setAlertStatus(as); setHotspots(hs); setRecentAlerts(al);
      setError('');
    } catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  // live event ticker (realtime)
  useEffect(() => {
    const off1 = subscribe('alert_created', (m) => {
      setLiveEvents((prev) => [{ type: 'alert', text: `New ${m.payload?.severity} alert — ${m.payload?.atm_id} (${m.payload?.district || '—'})`, at: Date.now() }, ...prev].slice(0, 8));
      load();
    });
    const off2 = subscribe('predictions_generated', (m) => {
      setLiveEvents((prev) => [{ type: 'pred', text: `Prediction run: ${m.payload?.n_predictions} ATMs scored, ${m.payload?.alerts_created ?? 0} alerts`, at: Date.now() }, ...prev].slice(0, 8));
      load();
    });
    const off3 = subscribe('notification', (m) => {
      setLiveEvents((prev) => [{ type: 'note', text: m.payload?.title || 'Notification', at: Date.now() }, ...prev].slice(0, 8));
    });
    return () => { off1(); off2(); off3(); };
  }, [subscribe, load]);

  const topDistricts = useMemo(
    () => [...districtRisk].sort((a, b) => b.max_risk - a.max_risk).slice(0, 6),
    [districtRisk]
  );
  const alertTotal = alertStatus.reduce((s, x) => s + x.count, 0);

  if (loading) return <Spinner label="Loading command dashboard…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!summary) return <EmptyState title="No data" />;

  const avgRisk = summary.average_risk || 0;
  const threat = avgRisk >= 75 ? 'CRITICAL' : avgRisk >= 60 ? 'ELEVATED' : avgRisk >= 40 ? 'GUARDED' : 'NOMINAL';
  const trendData = complaintTrend.map((c, i) => ({
    date: c.date,
    complaints: c.count,
    risk: riskTrend[i] ? riskTrend[i].avg_risk : null,
  }));

  return (
    <div className="page">
      {/* ── Hero: threat level + live feed ─────────────────────────── */}
      <div className="grid grid-3 dash-hero">
        <div className="panel threat-panel">
          <div className="panel-title">System Threat Level <span className="count">{threat}</span></div>
          <div className="threat-body">
            <RiskGauge score={Math.round(avgRisk)} size={170} />
            <div className="threat-meta">
              <div><b>{fmtNum(summary.active_threats)}</b><span>active threats</span></div>
              <div><b style={{ color: 'var(--red)' }}>{fmtNum(summary.critical_hotspots)}</b><span>critical</span></div>
              <div><b style={{ color: 'var(--orange)' }}>{fmtNum(summary.high_risk)}</b><span>high risk</span></div>
              <div><b style={{ color: 'var(--cyan)' }}>{fmtNum(summary.predicted_events)}</b><span>predicted</span></div>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Live Activity <span className="count live">streaming</span></div>
          <div className="live-feed">
            {liveEvents.length === 0 && recentAlerts.length === 0 && (
              <div className="muted text-sm" style={{ padding: 12 }}>No live events yet — run a prediction or the demo scenario.</div>
            )}
            {liveEvents.slice(0, 5).map((e, i) => (
              <div key={i} className="live-item">
                <span className={`live-dot live-${e.type}`} />
                <span className="live-text">{e.text}</span>
                <span className="live-at">{timeAgo(new Date(e.at).toISOString())}</span>
              </div>
            ))}
            {liveEvents.length === 0 && recentAlerts.slice(0, 5).map((a) => (
              <div key={a.alert_id} className="live-item">
                <span className="live-dot live-alert" />
                <span className="live-text">{a.severity} · {a.atm_id} ({a.district}) — risk {a.risk_score}</span>
                <span className="live-at">{timeAgo(a.created_at)}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Alert Pipeline <span className="count">{alertTotal} total</span></div>
          {alertTotal === 0 ? <EmptyState title="No alerts yet" hint="Run predictions or the demo scenario." /> : (
            <>
              <div className="chart-box-sm">
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={alertStatus} dataKey="count" nameKey="status" cx="50%" cy="50%"
                      innerRadius={42} outerRadius={70} paddingAngle={3} dataKey="count">
                      {alertStatus.map((a, i) => <Cell key={i} fill={STATUS_COLORS[a.status] || '#8b98ab'} />)}
                    </Pie>
                    <Tooltip content={<ChartTooltip />} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="flex" style={{ flexWrap: 'wrap', gap: '6px 14px', marginTop: 6 }}>
                {alertStatus.map((a) => (
                  <span key={a.status} className="text-sm" style={{ color: STATUS_COLORS[a.status] }}>
                    ● {a.status} · {a.count}
                  </span>
                ))}
              </div>
            </>
          )}
        </div>
      </div>

      {/* ── KPI row ─────────────────────────────────────────────────── */}
      <div className="grid grid-4">
        <KpiCard label="Active Threats" value={fmtNum(summary.active_threats)} accent="var(--red)"
          sub={`${summary.open_investigations} open investigations`} spark={<Spark data={complaintTrend} color="var(--red)" />} />
        <KpiCard label="Critical Hotspots" value={fmtNum(summary.critical_hotspots)} accent="var(--orange)"
          sub="Risk ≥ 81, next window" spark={<Spark data={riskTrend.map((r) => ({ count: r.max_risk }))} color="var(--orange)" />} />
        <KpiCard label="Active Alerts" value={fmtNum(summary.active_alerts)} accent="var(--amber)"
          sub={`${alertTotal} total alerts`} />
        <KpiCard label="Avg Response" value={summary.avg_response_minutes != null ? `${summary.avg_response_minutes}m` : '—'}
          accent="var(--cyan)" sub="Alert → first action" />
      </div>
      <div className="grid grid-4">
        <KpiCard label="Complaints (24h)" value={fmtNum(summary.complaints_24h)} accent="var(--purple)"
          sub="New cybercrime reports" spark={<Spark data={complaintTrend} color="var(--purple)" />} />
        <KpiCard label="Transactions (24h)" value={fmtNum(summary.transactions_24h)} accent="var(--green)"
          sub="ATM + UPI monitored" spark={<Spark data={txActivity} color="var(--green)" />} />
        <KpiCard label="Predicted Events" value={fmtNum(summary.predicted_events)} accent="var(--cyan)"
          sub="Suspicious withdrawal windows" spark={<Spark data={riskTrend.map((r) => ({ count: r.predictions }))} color="var(--cyan)" />} />
        <KpiCard label="Average Risk" value={avgRisk.toFixed(1)} accent="var(--orange)"
          sub="Across all ATMs" />
      </div>

      {/* ── Charts row ──────────────────────────────────────────────── */}
      <div className="grid grid-2">
        <div className="panel">
          <div className="panel-title">Complaints & Risk Trend <span className="count">14d</span></div>
          <div className="chart-box">
            <ResponsiveContainer>
              <AreaChart data={trendData} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                <defs>
                  <linearGradient id="comp" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#a78bfa" stopOpacity={0.5} />
                    <stop offset="100%" stopColor="#a78bfa" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="#1f2a3d" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#8b98ab', fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fill: '#8b98ab', fontSize: 10 }} allowDecimals={false} />
                <Tooltip content={<ChartTooltip />} />
                <Area type="monotone" dataKey="complaints" stroke="#a78bfa" strokeWidth={2} fill="url(#comp)" name="Complaints" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Predicted Risk Trend <span className="count">avg / max</span></div>
          <div className="chart-box">
            {riskTrend.length === 0 ? <EmptyState title="No prediction history" hint="Run the prediction pipeline to build the trend." /> : (
              <ResponsiveContainer>
                <LineChart data={riskTrend} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                  <CartesianGrid stroke="#1f2a3d" strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="date" tick={{ fill: '#8b98ab', fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                  <YAxis domain={[0, 100]} tick={{ fill: '#8b98ab', fontSize: 10 }} />
                  <Tooltip content={<ChartTooltip />} />
                  <Line type="monotone" dataKey="max_risk" stroke="#f87171" strokeWidth={1.5} dot={false} name="Max risk" />
                  <Line type="monotone" dataKey="avg_risk" stroke="#22d3ee" strokeWidth={2} dot={false} name="Avg risk" />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-2">
        <div className="panel">
          <div className="panel-title">District Risk <span className="count">max risk</span></div>
          <div className="chart-box">
            {topDistricts.length === 0 ? <EmptyState title="No district data" hint="Run predictions to score districts." /> : (
              <ResponsiveContainer>
                <BarChart data={topDistricts} layout="vertical" margin={{ top: 4, right: 20, left: 30, bottom: 0 }}>
                  <CartesianGrid stroke="#1f2a3d" strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" domain={[0, 100]} tick={{ fill: '#8b98ab', fontSize: 10 }} />
                  <YAxis type="category" dataKey="district" width={120} tick={{ fill: '#e5e9f0', fontSize: 11 }} />
                  <Tooltip content={<ChartTooltip />} />
                  <Bar dataKey="max_risk" radius={[0, 3, 3, 0]} name="Max risk">
                    {topDistricts.map((d, i) => (
                      <Cell key={i} fill={riskColor(d.max_risk)} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-title">Transaction Activity <span className="count">14d</span></div>
          <div className="chart-box">
            <ResponsiveContainer>
              <BarChart data={txActivity} margin={{ top: 6, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid stroke="#1f2a3d" strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="date" tick={{ fill: '#8b98ab', fontSize: 10 }} tickFormatter={(d) => d.slice(5)} />
                <YAxis tick={{ fill: '#8b98ab', fontSize: 10 }} />
                <Tooltip content={<ChartTooltip />} />
                <Bar dataKey="count" fill="#22d3ee" radius={[3, 3, 0, 0]} name="Transactions" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* ── Top hotspots table ──────────────────────────────────────── */}
      <div className="panel">
        <div className="panel-title">Top Predicted Hotspots <span className="count">{hotspots.length}</span></div>
        {hotspots.length === 0 ? (
          <EmptyState title="No hotspots in the current window" hint="Run the prediction pipeline from the Predictions page." />
        ) : (
          <div className="table-wrap">
            <table className="data">
              <thead>
                <tr><th>ATM</th><th>District</th><th>Window</th><th>Risk</th><th>Probability</th><th>Confidence</th><th></th></tr>
              </thead>
              <tbody>
                {hotspots.slice(0, 8).map((h) => (
                  <tr key={h.prediction_id}>
                    <td className="mono">{h.atm_id}</td>
                    <td>{h.district}</td>
                    <td className="text-sm muted">{fmtDate(h.window_start)} {h.window_start.slice(11, 16)} UTC</td>
                    <td><RiskBadge score={h.risk_score} showBand /></td>
                    <td className="mono">{(h.probability * 100).toFixed(0)}%</td>
                    <td className="mono">{(h.confidence * 100).toFixed(0)}%</td>
                    <td><Link to="/map" className="btn btn-sm">View on map</Link></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}