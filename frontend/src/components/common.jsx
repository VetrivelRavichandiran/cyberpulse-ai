import React from 'react';
import { riskColor, riskBand, severityColor } from '../utils/risk';

export function KpiCard({ label, value, sub, accent = 'var(--cyan)', spark }) {
  return (
    <div className="kpi-card" style={{ '--accent': accent }}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {sub && <div className="kpi-sub">{sub}</div>}
      {spark && <div className="kpi-spark">{spark}</div>}
    </div>
  );
}

export function RiskBadge({ score, showBand = false }) {
  const c = riskColor(score);
  return (
    <span className="badge risk-badge" style={{ color: c, borderColor: c + '66', background: c + '14' }}>
      {score}{showBand && <span style={{ opacity: 0.7, fontWeight: 500 }}> · {riskBand(score)}</span>}
    </span>
  );
}

export function SeverityBadge({ sev }) {
  const c = severityColor(sev);
  return (
    <span className="badge" style={{ color: c, borderColor: c + '66', background: c + '14' }}>{sev}</span>
  );
}

export function StatusBadge({ status }) {
  const map = {
    NEW: '#22d3ee', ACKNOWLEDGED: '#fbbf24', INVESTIGATING: '#a78bfa',
    ESCALATED: '#fb923c', RESOLVED: '#34d399', OPEN: '#22d3ee',
    IN_PROGRESS: '#fbbf24', CLOSED: '#8b98ab',
  };
  const c = map[status] || '#8b98ab';
  return <span className="badge" style={{ color: c, borderColor: c + '66', background: c + '14' }}>{status}</span>;
}

export function Spinner({ label = 'Loading…' }) {
  return <div className="loading-block"><div className="spinner" /><p>{label}</p></div>;
}

export function EmptyState({ icon = '◌', title, hint }) {
  return (
    <div className="empty-state">
      <div className="ico">{icon}</div>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{title}</div>
      {hint && <div className="text-sm">{hint}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry }) {
  return (
    <div className="error-state">
      <div style={{ fontWeight: 600, marginBottom: 8 }}>⚠ Something went wrong</div>
      <div className="text-sm">{message}</div>
      {onRetry && <button className="btn btn-sm mt-2" onClick={onRetry}>Retry</button>}
    </div>
  );
}

// Horizontal factor/impact bars (SHAP / feature importance)
export function FactorBars({ factors, max = null }) {
  if (!factors || !factors.length) return <div className="muted text-sm">No factors available.</div>;
  const m = max || Math.max(...factors.map((f) => Math.abs(f.impact ?? f.importance ?? 0)), 0.001);
  return (
    <div>
      {factors.map((f, i) => {
        const val = f.impact ?? f.importance ?? 0;
        const pct = Math.min(100, (Math.abs(val) / m) * 100);
        const pos = val >= 0;
        const color = f.direction ? (pos ? 'var(--red)' : 'var(--green)') : 'var(--cyan)';
        return (
          <div className="factor-row" key={i}>
            <div className="factor-label" title={f.label || f.feature}>{f.label || f.feature}</div>
            <div className="factor-track">
              <div className="factor-fill" style={{
                left: pos ? '50%' : `${50 - pct / 2}%`,
                width: `${pct / 2}%`,
                background: color,
              }} />
              <div style={{ position: 'absolute', left: '50%', top: 0, bottom: 0, width: 1, background: 'var(--border-2)' }} />
            </div>
            <div className="factor-val" style={{ color }}>{val >= 0 ? '+' : ''}{Number(val).toFixed(2)}</div>
          </div>
        );
      })}
    </div>
  );
}

// Simple SVG radial gauge 0-100
export function RiskGauge({ score, size = 140 }) {
  const c = riskColor(score);
  const r = size / 2 - 12;
  const cx = size / 2, cy = size / 2;
  const startAngle = -220, endAngle = 40;
  const total = endAngle - startAngle;
  const valAngle = startAngle + (score / 100) * total;
  const arc = (a0, a1, radius) => {
    const p = (a) => {
      const rad = (a * Math.PI) / 180;
      return [cx + radius * Math.cos(rad), cy + radius * Math.sin(rad)];
    };
    const [x0, y0] = p(a0); const [x1, y1] = p(a1);
    const large = a1 - a0 > 180 ? 1 : 0;
    return `M ${x0} ${y0} A ${radius} ${radius} 0 ${large} 1 ${x1} ${y1}`;
  };
  return (
    <div className="gauge-wrap">
      <svg width={size} height={size * 0.72} viewBox={`0 0 ${size} ${size * 0.72}`}>
        <path d={arc(startAngle, endAngle, r)} fill="none" stroke="var(--bg-2)" strokeWidth={12} strokeLinecap="round" />
        <path d={arc(startAngle, valAngle, r)} fill="none" stroke={c} strokeWidth={12} strokeLinecap="round" />
      </svg>
      <div className="gauge-value" style={{ color: c }}>{score}</div>
      <div className="gauge-label">{riskBand(score)} risk</div>
    </div>
  );
}