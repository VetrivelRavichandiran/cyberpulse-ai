import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { investigations } from '../api/endpoints';
import { EmptyState, ErrorState, Spinner, StatusBadge } from '../components/common.jsx';
import { fmtDateTime } from '../utils/format';

export default function Investigations() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const load = useCallback(async () => {
    try { setRows(await investigations.list()); setError(''); }
    catch (e) { setError(e.message); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  if (loading) return <Spinner label="Loading investigations…" />;
  if (error) return <ErrorState message={error} onRetry={load} />;
  return <div className="page">
    <div className="flex-between"><div className="text-sm muted">{rows.length} investigation case{rows.length === 1 ? '' : 's'}</div><button className="btn btn-sm" onClick={load}>⟳ Refresh</button></div>
    {rows.length === 0 ? <div className="panel"><EmptyState icon="🗂" title="No investigations open" hint="Open an investigation from an alert to begin case management." /></div> :
      <div className="table-wrap"><table className="data"><thead><tr><th>Case</th><th>Title</th><th>Priority</th><th>Status</th><th>District</th><th>Assigned to</th><th>Created</th><th /></tr></thead><tbody>
        {rows.map((item) => <tr key={item.case_id}><td className="mono">{item.case_id}</td><td>{item.title}</td><td><span className="badge">{item.priority}</span></td><td><StatusBadge status={item.status} /></td><td>{item.district || '—'}</td><td>{item.assigned_to || 'Unassigned'}</td><td className="text-sm muted">{fmtDateTime(item.created_at)}</td><td><Link className="btn btn-sm btn-primary" to={`/investigations/${item.case_id}`}>Open</Link></td></tr>)}
      </tbody></table></div>}
  </div>;
}
