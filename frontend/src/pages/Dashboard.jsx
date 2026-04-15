import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { callsApi } from '../api';
import CallStatusBadge from '../components/CallStatusBadge';
import LanguageBadge from '../components/LanguageBadge';
import NewCallModal from './NewCallModal';

const FILTERS = ['All', 'Active', 'Escalated', 'Completed'];

const STAT_ICONS = {
  'Active Calls': (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <circle cx="10" cy="10" r="8" stroke="currentColor" strokeWidth="1.5" />
      <path d="M10 6v4l2.5 2.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  'Calls Today': (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <rect x="3" y="4" width="14" height="13" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M3 8h14M7 2v4M13 2v4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
  'Avg Handle': (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <polyline points="3,15 7,10 10,12 14,6 17,9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  'Escalations': (
    <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
      <path d="M10 3l7 13H3L10 3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
      <path d="M10 9v3M10 14v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  ),
};

function StatCard({ label, value, color, delay = 0 }) {
  return (
    <div
      className="card-glass animate-fade-up"
      style={{
        padding: '1.25rem 1.5rem',
        animationDelay: `${delay}ms`,
        position: 'relative',
        overflow: 'hidden',
        transition: 'transform 0.2s ease, box-shadow 0.2s ease',
        cursor: 'default',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.transform = 'translateY(-2px)';
        e.currentTarget.style.boxShadow = `0 12px 40px rgba(0,0,0,0.3), 0 0 20px ${color || 'var(--border)'}22`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = '';
      }}
    >
      {/* Background accent */}
      <div style={{
        position: 'absolute',
        top: '-20px', right: '-20px',
        width: '80px', height: '80px',
        borderRadius: '50%',
        background: `radial-gradient(circle, ${color || 'var(--accent)'}22 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.62rem',
          color: 'var(--muted)',
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          fontWeight: 500,
        }}>
          {label}
        </p>
        <span style={{ color: color || 'var(--muted)', opacity: 0.7 }}>
          {STAT_ICONS[label] || STAT_ICONS['Calls Today']}
        </span>
      </div>

      <p className="stat-number" style={{ color: color || 'var(--text)', fontSize: '2.2rem' }}>
        {value ?? '—'}
      </p>
    </div>
  );
}

export default function Dashboard() {
  const navigate = useNavigate();
  const [calls,     setCalls]     = useState([]);
  const [total,     setTotal]     = useState(0);
  const [page,      setPage]      = useState(1);
  const [filter,    setFilter]    = useState('All');
  const [isLoading, setIsLoading] = useState(true);
  const [error,     setError]     = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [stats,     setStats]     = useState({ active: 0, today: 0, avgHandle: '—', escalation: '—' });

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const params = { page, per_page: 20 };
        if (filter === 'Active')    params.status = 'active';
        if (filter === 'Completed') params.status = 'ended';

        const { data } = await callsApi.list(params);
        if (cancelled) return;
        setCalls(data.calls || []);
        setTotal(data.total || 0);

        const activeCalls = (data.calls || []).filter((c) => c.status === 'active').length;
        const todayCalls  = (data.calls || []).filter((c) => {
          const d = new Date(c.created_at);
          return d.toDateString() === new Date().toDateString();
        }).length;
        const durations = (data.calls || []).filter((c) => c.duration_seconds).map((c) => c.duration_seconds);
        const avgSec = durations.length
          ? Math.round(durations.reduce((a, b) => a + b, 0) / durations.length)
          : 0;
        const avgHandle = avgSec ? `${Math.floor(avgSec / 60)}m ${avgSec % 60}s` : '—';

        setStats({ active: activeCalls, today: todayCalls, avgHandle, escalation: '—' });
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    load();
    return () => { cancelled = true; };
  }, [page, filter]);

  const formatDuration = (secs) => {
    if (!secs) return '—';
    return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  };

  const formatDate = (iso) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleString([], { month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="mesh-bg" style={{ flex: 1, display: 'flex', flexDirection: 'column', padding: '1.75rem', minHeight: '100vh', gap: '1.5rem' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
            <div style={{
              width: '8px', height: '8px', borderRadius: '50%',
              background: 'var(--success)',
              boxShadow: '0 0 0 3px rgba(0,229,160,0.2)',
              animation: 'pulse-glow 2s ease-in-out infinite',
            }} />
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--success)',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
            }}>
              Live
            </span>
          </div>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: '1.6rem',
            color: 'var(--text)',
            letterSpacing: '-0.02em',
          }}>
            Operations Center
          </h1>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--muted)', marginTop: '2px' }}>
            Real-time call intelligence dashboard
          </p>
        </div>

        <button
          onClick={() => setShowModal(true)}
          className="btn-accent"
          style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', padding: '0.65rem 1.25rem' }}
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v12M1 7h12" stroke="white" strokeWidth="2" strokeLinecap="round" />
          </svg>
          New Call
        </button>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '1rem' }}>
        <StatCard label="Active Calls" value={stats.active}     color="var(--success)" delay={0} />
        <StatCard label="Calls Today"  value={stats.today}      color="var(--cyan)"    delay={60} />
        <StatCard label="Avg Handle"   value={stats.avgHandle}  color="var(--warning)" delay={120} />
        <StatCard label="Escalations"  value={stats.escalation} color="var(--danger)"  delay={180} />
      </div>

      {/* Filter + Table */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {/* Filter tabs */}
        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginRight: '0.25rem' }}>
            Filter:
          </span>
          {FILTERS.map((f) => (
            <button
              key={f}
              onClick={() => { setFilter(f); setPage(1); }}
              style={{
                fontFamily: 'var(--font-display)',
                fontSize: '0.78rem',
                fontWeight: filter === f ? 600 : 400,
                padding: '0.35rem 0.85rem',
                borderRadius: '20px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                background: filter === f
                  ? 'linear-gradient(135deg, var(--accent), #FF8C52)'
                  : 'rgba(28,42,74,0.4)',
                color: filter === f ? '#fff' : 'var(--muted)',
                border: filter === f ? 'none' : '1px solid var(--border)',
                boxShadow: filter === f ? '0 4px 12px rgba(255,107,43,0.3)' : 'none',
              }}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Table container */}
        <div className="card-glass" style={{ flex: 1, overflow: 'hidden' }}>
          {isLoading && (
            <div style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="shimmer-skeleton" style={{ height: '52px', borderRadius: '8px', animationDelay: `${i * 80}ms` }} />
              ))}
            </div>
          )}

          {error && (
            <div style={{ padding: '1.5rem' }}>
              <p style={{ color: 'var(--danger)', fontFamily: 'var(--font-display)', fontSize: '0.875rem' }}>{error}</p>
            </div>
          )}

          {!isLoading && !error && calls.length === 0 && (
            <div style={{ padding: '4rem 1rem', textAlign: 'center' }}>
              <div style={{ marginBottom: '1rem' }}>
                <svg width="40" height="40" viewBox="0 0 40 40" fill="none" style={{ margin: '0 auto', opacity: 0.3 }}>
                  <circle cx="20" cy="20" r="18" stroke="var(--muted)" strokeWidth="1.5" />
                  <path d="M20 12v8M20 23v2" stroke="var(--muted)" strokeWidth="2" strokeLinecap="round" />
                </svg>
              </div>
              <p style={{ fontFamily: 'var(--font-display)', color: 'var(--muted)', fontSize: '0.875rem' }}>No calls found.</p>
            </div>
          )}

          {!isLoading && calls.length > 0 && (
            <div style={{ overflowX: 'auto' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Session', 'Agent', 'Date', 'Duration', 'Language', 'Status', 'Summary'].map((h) => (
                      <th
                        key={h}
                        style={{
                          textAlign: 'left',
                          padding: '0.85rem 1rem',
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.6rem',
                          fontWeight: 600,
                          color: 'var(--muted)',
                          letterSpacing: '0.1em',
                          textTransform: 'uppercase',
                          whiteSpace: 'nowrap',
                          background: 'rgba(13,20,37,0.5)',
                        }}
                      >
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {calls.map((call, idx) => (
                    <tr
                      key={call.session_id}
                      onClick={() => navigate(`/call/${call.session_id}/detail`)}
                      className="table-row-hover"
                      style={{
                        borderBottom: '1px solid rgba(28,42,74,0.5)',
                        cursor: 'pointer',
                        animation: 'fade-up 0.3s ease both',
                        animationDelay: `${idx * 40}ms`,
                      }}
                    >
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--cyan)', letterSpacing: '0.04em' }}>
                          {call.session_id.slice(0, 8)}…
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span style={{ fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--text)', fontWeight: 500 }}>
                          {call.agent_id}
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.72rem', color: 'var(--text-2)', whiteSpace: 'nowrap' }}>
                          {formatDate(call.created_at)}
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--warning)' }}>
                          {formatDuration(call.duration_seconds)}
                        </span>
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <LanguageBadge language={call.language} />
                      </td>
                      <td style={{ padding: '0.85rem 1rem' }}>
                        <CallStatusBadge status={call.status} />
                      </td>
                      <td style={{ padding: '0.85rem 1rem', maxWidth: '200px' }}>
                        <span style={{
                          fontFamily: 'var(--font-display)',
                          fontSize: '0.78rem',
                          color: 'var(--muted)',
                          overflow: 'hidden',
                          display: 'block',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap',
                        }} title={call.summary_preview}>
                          {call.summary_preview || '—'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {total > 20 && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '0.85rem 1rem',
              borderTop: '1px solid var(--border)',
            }}>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.7rem', color: 'var(--muted)' }}>
                {(page - 1) * 20 + 1}–{Math.min(page * 20, total)} of {total}
              </span>
              <div style={{ display: 'flex', gap: '0.5rem' }}>
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-ghost"
                  style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem', opacity: page === 1 ? 0.4 : 1 }}
                >
                  ← Prev
                </button>
                <button
                  onClick={() => setPage((p) => p + 1)}
                  disabled={page * 20 >= total}
                  className="btn-ghost"
                  style={{ padding: '0.3rem 0.75rem', fontSize: '0.75rem', opacity: page * 20 >= total ? 0.4 : 1 }}
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {showModal && <NewCallModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
