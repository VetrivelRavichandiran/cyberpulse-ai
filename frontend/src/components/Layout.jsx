import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../context/ToastContext.jsx';
import { notifications, alerts } from '../api/endpoints';

const NAV = [
  { to: '/', label: 'Dashboard', ico: '◧', end: true },
  { to: '/map', label: 'Live Map', ico: '◎' },
  { to: '/predictions', label: 'Predictions', ico: '📈' },
  { to: '/alerts', label: 'Alerts', ico: '⚠' },
  { to: '/investigations', label: 'Investigations', ico: '🗂' },
  { to: '/model', label: 'Model & AI', ico: '🧠' },
  { to: '/demo', label: 'Demo Scenario', ico: '▶' },
  { to: '/activity', label: 'Activity', ico: '≡' },
];

const TITLES = {
  '/': 'Command Dashboard',
  '/map': 'Live Threat Map',
  '/predictions': 'Withdrawal Predictions',
  '/alerts': 'Alert Center',
  '/investigations': 'Investigations',
  '/model': 'Model & Explainability',
  '/demo': 'Live Demo Scenario',
  '/activity': 'Activity & Audit',
};

function useClock() {
  const [now, setNow] = useState(new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export default function Layout() {
  const { user, logout } = useAuth();
  const { connected } = useWebSocket();
  const toast = useToast();
  const location = useLocation();
  const navigate = useNavigate();
  const now = useClock();
  const [unread, setUnread] = useState(0);
  const [alertCount, setAlertCount] = useState(0);

  const title = TITLES[location.pathname] || (location.pathname.startsWith('/investigations/') ? 'Case Detail' : 'CYBERPULSE AI');

  // poll notifications + new-alert count lightly
  useEffect(() => {
    let alive = true;
    async function poll() {
      try {
        const [notifs, alertList] = await Promise.all([
          notifications.list(50),
          alerts.list(100),
        ]);
        if (!alive) return;
        setUnread(notifs.filter((n) => !n.read).length);
        setAlertCount(alertList.filter((a) => a.status === 'NEW').length);
      } catch {}
    }
    poll();
    const t = setInterval(poll, 20000);
    return () => { alive = false; clearInterval(t); };
  }, []);

  const initials = (user?.full_name || user?.username || 'U').split(' ').map((s) => s[0]).slice(0, 2).join('').toUpperCase();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-logo">CP</div>
          <div>
            <div className="brand-name">CYBERPULSE</div>
            <div className="brand-sub">AI Command</div>
          </div>
        </div>
        <nav className="nav">
          {NAV.map((n) => (
            <NavLink key={n.to} to={n.to} end={n.end} className={({ isActive }) => `nav-item${isActive ? ' active' : ''}`}>
              <span className="ico">{n.ico}</span>
              <span>{n.label}</span>
              {n.to === '/alerts' && alertCount > 0 && <span className="badge-count">{alertCount}</span>}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="user-chip">
            <div className="user-avatar">{initials}</div>
            <div className="user-meta">
              <div className="user-name">{user?.full_name || user?.username}</div>
              <div className="user-role">{user?.role}</div>
            </div>
          </div>
          <button className="logout-btn" onClick={logout}>Sign out</button>
          <div className="synthetic-badge">Prototype · synthetic data<br />AI-assisted decision support</div>
        </div>
      </aside>

      <div className="main-col">
        <header className="header">
          <div className="header-title">{title}</div>
          <div className="header-spacer" />
          <div className={`conn-dot ${connected ? 'on' : ''}`} title={connected ? 'Realtime stream connected' : 'Realtime stream offline'}>
            <span className="dot" /> {connected ? 'LIVE' : 'OFFLINE'}
          </div>
          <div className="header-clock">{now.toLocaleTimeString('en-GB')}</div>
          <div className="bell" title="Notifications" onClick={() => navigate('/activity')}>
            🔔{unread > 0 && <span className="bell-count">{unread > 99 ? '99+' : unread}</span>}
          </div>
        </header>
        <main className="content">
          <Outlet />
        </main>
        <div className="footer-note">
          CYBERPULSE AI · Prototype validated using synthetic data — AI-assisted decision support, not a determination of guilt.
        </div>
      </div>
    </div>
  );
}