import React, { useCallback, useEffect, useState } from 'react';
import { audit, notifications } from '../api/endpoints';
import { ErrorState, Spinner } from '../components/common.jsx';
import { fmtDateTime } from '../utils/format';

export default function Activity() {
  const [logs, setLogs] = useState([]); const [notifs, setNotifs] = useState([]); const [loading, setLoading] = useState(true); const [error, setError] = useState('');
  const load = useCallback(async () => { try { const [a, n] = await Promise.all([audit.list(100), notifications.list(50)]); setLogs(a); setNotifs(n); setError(''); } catch (e) { setError(e.message); } finally { setLoading(false); } }, []);
  useEffect(() => { load(); }, [load]);
  if (loading) return <Spinner label="Loading activity…" />; if (error) return <ErrorState message={error} onRetry={load} />;
  return <div className="page"><div className="grid grid-2"><div className="panel"><div className="panel-title">Notifications <span className="count">{notifs.filter((n) => !n.read).length} unread</span></div>{notifs.length ? notifs.map((n) => <div key={n.id} className="timeline-item"><b>{n.title}</b><div className="text-sm muted">{n.body}</div><div className="text-xs muted">{fmtDateTime(n.created_at)}</div></div>) : <div className="muted text-sm">No notifications.</div>}</div><div className="panel"><div className="panel-title">Audit Activity</div>{logs.length ? logs.map((l) => <div key={l.id} className="timeline-item"><b>{l.action}</b><div className="text-sm muted">{l.username} · {l.resource || 'system'} {l.detail ? `· ${l.detail}` : ''}</div><div className="text-xs muted">{fmtDateTime(l.timestamp)}</div></div>) : <div className="muted text-sm">No audit activity.</div>}</div></div></div>;
}
