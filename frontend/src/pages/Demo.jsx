import React, { useEffect, useState } from 'react';
import { demo } from '../api/endpoints';
import { useWebSocket } from '../hooks/useWebSocket';
import { useToast } from '../context/ToastContext.jsx';

export default function Demo() {
  const toast = useToast(); const { events: stream, connected } = useWebSocket(); const [busy, setBusy] = useState(false); const [events, setEvents] = useState([]);
  useEffect(() => { const relevant = stream.filter((m) => String(m.type || '').startsWith('demo_') || ['complaints_added','transactions_added','graph_updated','predictions_generated','hotspot','alert_created'].includes(m.type)); setEvents(relevant.slice(-30).reverse()); }, [stream]);
  async function run() { setBusy(true); try { await demo.run(); toast.success('Demo scenario started. Follow the live event stream.'); } catch (e) { toast.error(e.message); } finally { setBusy(false); } }
  async function reset() { setBusy(true); try { const r = await demo.reset(); toast.success(`Demo reset: ${r.counts?.predictions || 0} predictions rebuilt`); } catch (e) { toast.error(e.message); } finally { setBusy(false); } }
  return <div className="page"><div className="panel"><div className="panel-title">Live Demo Scenario <span className="count">{connected ? 'stream connected' : 'stream offline'}</span></div><p className="text-sm muted">Run a staged synthetic scenario: complaint surge → transaction surge → graph signal → model prediction → alert.</p><div className="flex"><button className="btn btn-primary" disabled={busy} onClick={run}>{busy ? 'Working…' : '▶ Run scenario'}</button><button className="btn" disabled={busy} onClick={reset}>Reset derived demo state</button></div></div><div className="panel"><div className="panel-title">Event Stream</div>{events.length ? events.map((event, index) => <div className="timeline-item" key={index}><b>{String(event.type || 'event').replaceAll('_', ' ')}</b><div className="text-sm muted">{event.payload?.detail || JSON.stringify(event.payload || {})}</div></div>) : <div className="empty-state"><div className="ico">▶</div><div style={{ fontWeight: 600 }}>Awaiting demo events</div><div className="text-sm">Run the scenario to populate the event stream.</div></div>}</div></div>;
}
