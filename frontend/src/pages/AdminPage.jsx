import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { listJobs, createUser } from '../api';
import api from '../api';
import useAuth from '../hooks/useAuth';

const API_URL = import.meta.env.VITE_API_URL || '';

function StatusBadge({ status }) {
  const cfg = {
    queued:   { color: 'var(--muted)',    bg: 'rgba(90,100,128,0.12)',  border: 'rgba(90,100,128,0.2)' },
    started:  { color: 'var(--warning)',  bg: 'rgba(255,184,0,0.1)',    border: 'rgba(255,184,0,0.25)',   pulse: true },
    finished: { color: 'var(--success)',  bg: 'rgba(0,229,160,0.1)',    border: 'rgba(0,229,160,0.25)' },
    failed:   { color: 'var(--danger)',   bg: 'rgba(255,51,102,0.1)',   border: 'rgba(255,51,102,0.25)' },
  }[status?.toLowerCase()] || { color: 'var(--muted)', bg: 'rgba(90,100,128,0.12)', border: 'rgba(90,100,128,0.2)' };

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.35rem',
      padding: '2px 8px',
      borderRadius: '5px',
      background: cfg.bg,
      border: `1px solid ${cfg.border}`,
      color: cfg.color,
      fontFamily: 'var(--font-mono)',
      fontSize: '0.62rem',
      fontWeight: 600,
      letterSpacing: '0.08em',
      animation: cfg.pulse ? 'accent-pulse 1.2s ease-in-out infinite' : 'none',
    }}>
      <span style={{
        width: '5px', height: '5px',
        borderRadius: '50%',
        background: cfg.color,
        display: 'inline-block',
      }} />
      {status?.toUpperCase() || 'UNKNOWN'}
    </span>
  );
}

function SectionHeader({ title, badge, action }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <div style={{ width: '4px', height: '18px', borderRadius: '2px', background: 'linear-gradient(180deg, var(--accent), var(--cyan))' }} />
        <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '1rem', color: 'var(--text)' }}>
          {title}
        </h2>
        {badge && (
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.6rem',
            color: 'var(--muted)',
            padding: '2px 6px',
            background: 'rgba(28,42,74,0.5)',
            border: '1px solid var(--border)',
            borderRadius: '4px',
          }}>
            {badge}
          </span>
        )}
      </div>
      {action}
    </div>
  );
}

function TableContainer({ headers, children, isLoading, error, emptyMsg }) {
  return (
    <div className="card-glass" style={{ overflow: 'hidden', marginBottom: '2rem' }}>
      {isLoading && (
        <div style={{ padding: '1.25rem', display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="shimmer-skeleton" style={{ height: '42px', borderRadius: '6px', animationDelay: `${i * 80}ms` }} />
          ))}
        </div>
      )}
      {error && (
        <div style={{
          margin: '1rem',
          padding: '0.75rem 1rem',
          background: 'rgba(255,51,102,0.08)',
          border: '1px solid rgba(255,51,102,0.2)',
          borderRadius: '8px',
          fontFamily: 'var(--font-display)',
          fontSize: '0.82rem',
          color: 'var(--danger)',
        }}>
          {error}
        </div>
      )}
      {!isLoading && !error && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {headers.map((h) => (
                  <th key={h} style={{
                    padding: '0.75rem 1rem',
                    textAlign: 'left',
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.6rem',
                    fontWeight: 600,
                    color: 'var(--muted)',
                    letterSpacing: '0.1em',
                    textTransform: 'uppercase',
                    whiteSpace: 'nowrap',
                    background: 'rgba(13,20,37,0.5)',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>{children}</tbody>
          </table>
          {!children || (Array.isArray(children) && children.length === 0) && (
            <p style={{ padding: '1.5rem', textAlign: 'center', fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--muted)' }}>
              {emptyMsg}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Job Queue ────────────────────────────────────────────────────
function JobQueueSection() {
  const [jobs,    setJobs]    = useState([]);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);
  const [page,    setPage]    = useState(1);

  const fetchJobs = useCallback(async () => {
    try {
      const { data } = await listJobs(page, 20);
      setJobs(data.jobs || data || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [page]);

  useEffect(() => {
    fetchJobs();
    const interval = setInterval(fetchJobs, 10000);
    return () => clearInterval(interval);
  }, [fetchJobs]);

  const formatDate = (iso) => iso ? new Date(iso).toLocaleString() : '—';

  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <SectionHeader
        title="Job Queue"
        badge="AUTO-REFRESH 10s"
        action={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <a
              href={`${API_URL}/admin/rq`}
              target="_blank"
              rel="noopener noreferrer"
              style={{
                padding: '0.35rem 0.9rem',
                borderRadius: '7px',
                border: '1px solid rgba(255,107,43,0.3)',
                color: 'var(--accent)',
                fontFamily: 'var(--font-display)',
                fontSize: '0.78rem',
                fontWeight: 500,
                textDecoration: 'none',
                transition: 'all 0.2s',
                background: 'rgba(255,107,43,0.06)',
              }}
            >
              RQ Dashboard ↗
            </a>
            <button
              onClick={fetchJobs}
              className="btn-ghost"
              style={{ padding: '0.35rem 0.9rem', fontSize: '0.78rem' }}
            >
              Refresh
            </button>
          </div>
        }
      />

      <TableContainer
        headers={['Job ID', 'Type', 'Status', 'Created', 'Completed']}
        isLoading={loading}
        error={error}
        emptyMsg="No jobs found"
      >
        {jobs.map((job) => (
          <tr
            key={job.job_id || job.id}
            className="table-row-hover"
            style={{ borderBottom: '1px solid rgba(28,42,74,0.4)' }}
          >
            <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--cyan)' }}>
              {(job.job_id || job.id || '').slice(0, 12)}…
            </td>
            <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--text-2)' }}>
              {job.type || job.func_name || '—'}
            </td>
            <td style={{ padding: '0.7rem 1rem' }}>
              <StatusBadge status={job.status} />
            </td>
            <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
              {formatDate(job.created_at)}
            </td>
            <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--muted)', whiteSpace: 'nowrap' }}>
              {formatDate(job.completed_at)}
            </td>
          </tr>
        ))}
      </TableContainer>
    </section>
  );
}

// ─── Users ────────────────────────────────────────────────────────
function UsersSection() {
  const [users,       setUsers]       = useState([]);
  const [loading,     setLoading]     = useState(true);
  const [error,       setError]       = useState(null);
  const [showForm,    setShowForm]    = useState(false);
  const [newUser,     setNewUser]     = useState({ username: '', password: '', role: 'agent' });
  const [addError,    setAddError]    = useState(null);
  const [addLoading,  setAddLoading]  = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      const { data } = await api.get('/api/auth/users');
      setUsers(data.users || data || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleAddUser = async (e) => {
    e.preventDefault();
    setAddError(null);
    setAddLoading(true);
    try {
      await createUser(newUser.username, newUser.password, newUser.role);
      setNewUser({ username: '', password: '', role: 'agent' });
      setShowForm(false);
      fetchUsers();
    } catch (err) {
      setAddError(err.message);
    } finally {
      setAddLoading(false);
    }
  };

  const inputStyle = {
    padding: '0.5rem 0.75rem',
    background: 'rgba(6,8,16,0.8)',
    border: '1px solid var(--border)',
    borderRadius: '7px',
    color: 'var(--text)',
    fontFamily: 'var(--font-display)',
    fontSize: '0.85rem',
    outline: 'none',
  };

  return (
    <section style={{ marginBottom: '2.5rem' }}>
      <SectionHeader
        title="Users"
        action={
          <button
            onClick={() => setShowForm((v) => !v)}
            className={showForm ? 'btn-ghost' : 'btn-accent'}
            style={{ padding: '0.35rem 1rem', fontSize: '0.8rem' }}
          >
            {showForm ? '✕ Cancel' : '+ Add User'}
          </button>
        }
      />

      {showForm && (
        <div className="card-glass animate-fade-up" style={{ padding: '1.25rem', marginBottom: '1rem' }}>
          <form onSubmit={handleAddUser} style={{ display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end' }}>
            <div>
              <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.08em', marginBottom: '4px', textTransform: 'uppercase' }}>Username</label>
              <input
                type="text" required
                value={newUser.username}
                onChange={(e) => setNewUser({ ...newUser, username: e.target.value })}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.08em', marginBottom: '4px', textTransform: 'uppercase' }}>Password</label>
              <input
                type="password" required
                value={newUser.password}
                onChange={(e) => setNewUser({ ...newUser, password: e.target.value })}
                style={inputStyle}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.08em', marginBottom: '4px', textTransform: 'uppercase' }}>Role</label>
              <select
                value={newUser.role}
                onChange={(e) => setNewUser({ ...newUser, role: e.target.value })}
                style={inputStyle}
              >
                <option value="agent">Agent</option>
                <option value="admin">Admin</option>
                <option value="viewer">Viewer</option>
              </select>
            </div>
            <button
              type="submit"
              className="btn-accent"
              disabled={addLoading}
              style={{ padding: '0.5rem 1.1rem', fontSize: '0.82rem', opacity: addLoading ? 0.7 : 1 }}
            >
              {addLoading ? 'Creating…' : 'Create User'}
            </button>
          </form>
          {addError && (
            <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.78rem', color: 'var(--danger)', marginTop: '0.5rem' }}>
              {addError}
            </p>
          )}
        </div>
      )}

      <TableContainer
        headers={['Username', 'Role', 'Created', 'Status']}
        isLoading={loading}
        error={error}
        emptyMsg="No users found"
      >
        {users.map((u) => (
          <tr
            key={u.username || u.id}
            className="table-row-hover"
            style={{ borderBottom: '1px solid rgba(28,42,74,0.4)' }}
          >
            <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-display)', fontSize: '0.85rem', color: 'var(--text)', fontWeight: 500 }}>
              {u.username}
            </td>
            <td style={{ padding: '0.7rem 1rem' }}>
              <span style={{
                padding: '2px 8px',
                borderRadius: '5px',
                background: u.role === 'admin' ? 'rgba(255,107,43,0.12)' : u.role === 'viewer' ? 'rgba(0,200,255,0.1)' : 'rgba(90,100,128,0.12)',
                color: u.role === 'admin' ? 'var(--accent)' : u.role === 'viewer' ? 'var(--cyan)' : 'var(--muted)',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.62rem',
                fontWeight: 600,
                letterSpacing: '0.06em',
              }}>
                {u.role?.toUpperCase()}
              </span>
            </td>
            <td style={{ padding: '0.7rem 1rem', fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--muted)' }}>
              {u.created_at ? new Date(u.created_at).toLocaleDateString() : '—'}
            </td>
            <td style={{ padding: '0.7rem 1rem' }}>
              <span style={{
                padding: '2px 8px',
                borderRadius: '5px',
                background: u.is_active !== false ? 'rgba(0,229,160,0.1)' : 'rgba(255,51,102,0.1)',
                color: u.is_active !== false ? 'var(--success)' : 'var(--danger)',
                border: `1px solid ${u.is_active !== false ? 'rgba(0,229,160,0.25)' : 'rgba(255,51,102,0.25)'}`,
                fontFamily: 'var(--font-mono)',
                fontSize: '0.62rem',
                fontWeight: 600,
              }}>
                {u.is_active !== false ? 'ACTIVE' : 'INACTIVE'}
              </span>
            </td>
          </tr>
        ))}
      </TableContainer>
    </section>
  );
}

// ─── System Health ─────────────────────────────────────────────────
function SystemHealthSection() {
  const [health,  setHealth]  = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState(null);

  useEffect(() => {
    const fetchHealth = async () => {
      try {
        const { data } = await api.get('/health');
        setHealth(data);
        setError(null);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchHealth();
  }, []);

  const isHealthy = health?.status === 'ok' || health?.status === 'healthy';

  return (
    <section>
      <SectionHeader title="System Health" />

      {loading && (
        <div className="shimmer-skeleton" style={{ height: '80px', borderRadius: '12px' }} />
      )}

      {error && (
        <div style={{
          padding: '1rem',
          background: 'rgba(255,51,102,0.08)',
          border: '1px solid rgba(255,51,102,0.2)',
          borderRadius: '10px',
          fontFamily: 'var(--font-display)',
          fontSize: '0.82rem',
          color: 'var(--danger)',
        }}>
          {error}
        </div>
      )}

      {health && (
        <div className="card-glass animate-fade-up" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem' }}>
            <div>
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '6px' }}>Status</p>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                <span style={{ position: 'relative', display: 'inline-flex' }}>
                  <span style={{
                    width: '10px', height: '10px',
                    borderRadius: '50%',
                    background: isHealthy ? 'var(--success)' : 'var(--danger)',
                    display: 'inline-block',
                  }} />
                  {isHealthy && (
                    <span style={{
                      position: 'absolute', inset: 0,
                      borderRadius: '50%',
                      background: 'var(--success)',
                      animation: 'pulse-ring 2s ease-out infinite',
                    }} />
                  )}
                </span>
                <span style={{
                  fontFamily: 'var(--font-big)',
                  fontSize: '1.3rem',
                  color: isHealthy ? 'var(--success)' : 'var(--danger)',
                  letterSpacing: '0.05em',
                }}>
                  {health.status?.toUpperCase() || 'UNKNOWN'}
                </span>
              </div>
            </div>

            {health.version && (
              <div>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '6px' }}>Version</p>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem', color: 'var(--cyan)' }}>{health.version}</p>
              </div>
            )}

            {health.uptime != null && (
              <div>
                <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '6px' }}>Uptime</p>
                <p style={{ fontFamily: 'var(--font-big)', fontSize: '1.3rem', color: 'var(--warning)', letterSpacing: '0.02em' }}>
                  {typeof health.uptime === 'number'
                    ? `${Math.floor(health.uptime / 60)}m ${health.uptime % 60}s`
                    : health.uptime}
                </p>
              </div>
            )}

            {Object.entries(health)
              .filter(([k]) => !['status', 'version', 'uptime'].includes(k))
              .map(([k, v]) => (
                <div key={k}>
                  <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: '6px' }}>{k}</p>
                  <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.82rem', color: 'var(--text-2)' }}>{String(v)}</p>
                </div>
              ))}
          </div>
        </div>
      )}
    </section>
  );
}

// ─── Admin Page ────────────────────────────────────────────────────
export default function AdminPage() {
  const { role } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (role && role !== 'admin') navigate('/', { replace: true });
  }, [role, navigate]);

  if (role && role !== 'admin') return null;

  return (
    <div className="mesh-bg" style={{ minHeight: '100vh', padding: '1.75rem' }}>
      <div style={{ maxWidth: '1000px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '2rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.2rem' }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--accent)',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              padding: '2px 8px',
              background: 'rgba(255,107,43,0.1)',
              border: '1px solid rgba(255,107,43,0.2)',
              borderRadius: '4px',
            }}>
              Admin Only
            </span>
          </div>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: '1.6rem',
            color: 'var(--text)',
            letterSpacing: '-0.02em',
            marginBottom: '0.2rem',
          }}>
            Admin Console
          </h1>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--muted)' }}>
            Job queue, user management, and system health
          </p>
        </div>

        <JobQueueSection />
        <UsersSection />
        <SystemHealthSection />
      </div>
    </div>
  );
}
