import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { callsApi } from '../api';
import CallStatusBadge from '../components/CallStatusBadge';
import LanguageBadge from '../components/LanguageBadge';

/**
 * CallHistoryPage
 * Route: /history
 * Filterable, paginated table of all calls with CSV export.
 */
export default function CallHistoryPage() {
  const navigate    = useNavigate();
  const [calls,      setCalls]      = useState([]);
  const [total,      setTotal]      = useState(0);
  const [page,       setPage]       = useState(1);
  const [agentId,    setAgentId]    = useState('');
  const [status,     setStatus]     = useState('');
  const [fromDate,   setFromDate]   = useState('');
  const [toDate,     setToDate]     = useState('');
  const [isLoading,  setIsLoading]  = useState(true);
  const [error,      setError]      = useState(null);

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = { page, per_page: 20 };
      if (agentId)  params.agent_id = agentId;
      if (status)   params.status   = status;
      if (fromDate) params.from     = fromDate;
      if (toDate)   params.to       = toDate;
      const { data } = await callsApi.list(params);
      setCalls(data.calls || []);
      setTotal(data.total  || 0);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { load(); }, [page]); // eslint-disable-line react-hooks/exhaustive-deps

  const handleSearch = () => { setPage(1); load(); };

  const exportCsv = () => {
    const headers = ['Session ID', 'Agent', 'Date', 'Duration', 'Language', 'Status', 'Summary'];
    const rows = calls.map((c) => [
      c.session_id,
      c.agent_id,
      c.created_at,
      c.duration_seconds ?? '',
      c.language,
      c.status,
      (c.summary_preview || '').replace(/,/g, ';'),
    ]);
    const csv = [headers, ...rows].map((r) => r.join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const a    = document.createElement('a');
    a.href     = URL.createObjectURL(blob);
    a.download = 'calls_export.csv';
    a.click();
  };

  const formatDuration = (secs) => (secs ? `${Math.floor(secs / 60)}m ${secs % 60}s` : '—');
  const formatDate     = (iso)  => iso ? new Date(iso).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' }) : '—';

  return (
    <div className="flex-1 flex flex-col p-6 min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="font-sora font-bold text-xl" style={{ color: 'var(--text)' }}>
            Call History
          </h1>
          <p className="text-xs mt-0.5" style={{ color: 'var(--muted)' }}>
            {total} total records
          </p>
        </div>
        <button onClick={exportCsv} className="btn-accent text-xs py-1.5 px-3">
          Export CSV
        </button>
      </div>

      {/* Filters */}
      <div
        className="card p-4 flex flex-wrap gap-3 mb-4"
        style={{ borderBottom: '1px solid var(--border)' }}
      >
        <input
          type="text"
          placeholder="Agent ID"
          value={agentId}
          onChange={(e) => setAgentId(e.target.value)}
          className="text-xs font-mono px-3 py-1.5 rounded-lg outline-none"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)', width: 140 }}
        />
        <select
          value={status}
          onChange={(e) => setStatus(e.target.value)}
          className="text-xs font-mono px-3 py-1.5 rounded-lg outline-none"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)' }}
        >
          <option value="">All Status</option>
          <option value="active">Active</option>
          <option value="ended">Ended</option>
        </select>
        <input
          type="date"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          className="text-xs font-mono px-3 py-1.5 rounded-lg outline-none"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)' }}
        />
        <input
          type="date"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          className="text-xs font-mono px-3 py-1.5 rounded-lg outline-none"
          style={{ background: 'var(--bg)', border: '1px solid var(--border)', color: 'var(--text)' }}
        />
        <button onClick={handleSearch} className="btn-accent text-xs py-1.5 px-3">
          Filter
        </button>
      </div>

      {/* Table */}
      <div className="card flex-1 overflow-auto">
        {isLoading && (
          <div className="p-6 space-y-3">
            {[...Array(8)].map((_, i) => <div key={i} className="shimmer-skeleton h-10 rounded" />)}
          </div>
        )}

        {error && <p className="p-6" style={{ color: 'var(--danger)' }}>{error}</p>}

        {!isLoading && !error && calls.length === 0 && (
          <p className="p-12 text-center" style={{ color: 'var(--muted)' }}>No calls found.</p>
        )}

        {!isLoading && calls.length > 0 && (
          <table className="w-full text-sm">
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Session', 'Agent', 'Date', 'Duration', 'Language', 'Status', 'Summary'].map((h) => (
                  <th
                    key={h}
                    className="text-left px-4 py-3 text-xs font-mono font-semibold uppercase tracking-wider"
                    style={{ color: 'var(--muted)' }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {calls.map((call) => (
                <tr
                  key={call.session_id}
                  onClick={() => navigate(`/call/${call.session_id}/detail`)}
                  className="cursor-pointer hover:bg-[var(--border)] transition-colors"
                  style={{ borderBottom: '1px solid var(--border)' }}
                >
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--muted)' }}>
                    {call.session_id.slice(0, 8)}…
                  </td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--text)' }}>{call.agent_id}</td>
                  <td className="px-4 py-3 text-xs" style={{ color: 'var(--muted)' }}>{formatDate(call.created_at)}</td>
                  <td className="px-4 py-3 font-mono text-xs" style={{ color: 'var(--text)' }}>{formatDuration(call.duration_seconds)}</td>
                  <td className="px-4 py-3"><LanguageBadge language={call.language} /></td>
                  <td className="px-4 py-3"><CallStatusBadge status={call.status} /></td>
                  <td
                    className="px-4 py-3 text-xs max-w-[200px] truncate"
                    style={{ color: 'var(--muted)' }}
                    title={call.summary_preview}
                  >
                    {call.summary_preview || '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}

        {/* Pagination */}
        {total > 20 && (
          <div
            className="flex items-center justify-between px-4 py-3"
            style={{ borderTop: '1px solid var(--border)' }}
          >
            <span className="text-xs" style={{ color: 'var(--muted)' }}>
              {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
            </span>
            <div className="flex gap-2">
              <button
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="text-xs px-2 py-1 rounded disabled:opacity-40"
                style={{ background: 'var(--border)', color: 'var(--text)' }}
              >
                ← Prev
              </button>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={page * 20 >= total}
                className="text-xs px-2 py-1 rounded disabled:opacity-40"
                style={{ background: 'var(--border)', color: 'var(--text)' }}
              >
                Next →
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
