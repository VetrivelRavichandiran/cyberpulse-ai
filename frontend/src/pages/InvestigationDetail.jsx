import React, { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { investigations } from '../api/endpoints';
import { EmptyState, ErrorState, Spinner, StatusBadge } from '../components/common.jsx';
import { fmtDateTime } from '../utils/format';
import { useToast } from '../context/ToastContext.jsx';

export default function InvestigationDetail() {
  const { caseId } = useParams(); const toast = useToast();
  const [item, setItem] = useState(null); const [loading, setLoading] = useState(true); const [error, setError] = useState(''); const [note, setNote] = useState(''); const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setItem(await investigations.get(caseId)); setError(''); } catch (e) { setError(e.message); } finally { setLoading(false); } }, [caseId]);
  useEffect(() => { load(); }, [load]);
  async function addNote(e) { e.preventDefault(); if (!note.trim()) return; setBusy(true); try { await investigations.addNote(caseId, note.trim()); setNote(''); await load(); toast.success('Case note added'); } catch (e) { toast.error(e.message); } finally { setBusy(false); } }
  async function changeStatus(status) { setBusy(true); try { await investigations.setStatus(caseId, status); await load(); toast.success(`Case status set to ${status}`); } catch (e) { toast.error(e.message); } finally { setBusy(false); } }
  async function download() { try { const blob = await investigations.reportBlob(caseId); const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${caseId}-report.pdf`; a.click(); URL.revokeObjectURL(url); } catch (e) { toast.error(e.message); } }
  if (loading) return <Spinner label="Loading case…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  if (!item) return <EmptyState title="Case not found" />;
  const timeline = item.timeline || []; const notes = item.notes || [];
  return <div className="page"><div className="flex-between"><div><Link className="text-sm muted" to="/investigations">← All investigations</Link><h2 style={{ margin: '8px 0 4px' }}>{item.title}</h2><span className="mono text-sm muted">{item.case_id}</span></div><div className="flex"><StatusBadge status={item.status} /><button className="btn btn-sm" onClick={download}>Download report</button></div></div>
    <div className="grid grid-2"><div className="panel"><div className="panel-title">Case Summary</div><div className="text-sm" style={{ lineHeight: 1.6 }}>{item.summary || 'No summary recorded.'}</div><div className="divider" /><div className="grid grid-2 text-sm"><div><span className="muted">Priority</span><br />{item.priority}</div><div><span className="muted">District</span><br />{item.district || '—'}</div><div><span className="muted">Assigned to</span><br />{item.assigned_to || 'Unassigned'}</div><div><span className="muted">Created</span><br />{fmtDateTime(item.created_at)}</div></div><div className="divider" /><div className="flex" style={{ flexWrap: 'wrap' }}>{['OPEN','IN_PROGRESS','ESCALATED','RESOLVED','CLOSED'].map((s) => <button key={s} disabled={busy || item.status === s} className="btn btn-sm" onClick={() => changeStatus(s)}>{s}</button>)}</div></div>
      <div className="panel"><div className="panel-title">Timeline</div>{timeline.length ? timeline.map((event, i) => <div key={i} className="timeline-item"><div style={{ fontWeight: 600 }}>{event.title}</div><div className="text-sm muted">{event.detail}</div><div className="text-xs muted">{fmtDateTime(event.occurred_at)}</div></div>) : <EmptyState title="No timeline events" />}</div></div>
    <div className="panel"><div className="panel-title">Case Notes</div><form className="flex" onSubmit={addNote}><input className="input" value={note} onChange={(e) => setNote(e.target.value)} placeholder="Add an investigation note…" /><button disabled={busy} className="btn btn-primary">Add note</button></form><div className="divider" />{notes.length ? notes.map((n, i) => <div key={i} className="timeline-item"><b>{n.author}</b><div className="text-sm">{n.note}</div><div className="text-xs muted">{fmtDateTime(n.created_at)}</div></div>) : <div className="muted text-sm">No notes recorded.</div>}</div>
  </div>;
}
