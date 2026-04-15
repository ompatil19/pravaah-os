import { BrowserRouter, Routes, Route, NavLink, useNavigate } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import ActiveCall from './pages/ActiveCall';
import CallDetail from './pages/CallDetail';
import Analytics from './pages/Analytics';
import Documents from './pages/Documents';
import Login from './pages/Login';
import AdminPage from './pages/AdminPage';
import ProtectedRoute from './components/ProtectedRoute';
import useAuth from './hooks/useAuth';

const NAV_LINKS = [
  {
    to: '/',
    end: true,
    label: 'Dashboard',
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <rect x="1" y="1" width="6" height="6" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="1" width="6" height="6" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <rect x="1" y="11" width="6" height="6" rx="2" stroke="currentColor" strokeWidth="1.5" />
        <rect x="11" y="11" width="6" height="6" rx="2" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    ),
  },
  {
    to: '/analytics',
    end: false,
    label: 'Analytics',
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <polyline points="1,14 5,9 9,11 13,5 17,7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="5" cy="9" r="1.5" fill="currentColor" />
        <circle cx="9" cy="11" r="1.5" fill="currentColor" />
        <circle cx="13" cy="5" r="1.5" fill="currentColor" />
      </svg>
    ),
  },
  {
    to: '/documents',
    end: false,
    label: 'Documents',
    icon: (
      <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
        <path d="M4 2h7l4 4v10a1 1 0 01-1 1H4a1 1 0 01-1-1V3a1 1 0 011-1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <path d="M11 2v4h4" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
        <line x1="6" y1="9" x2="12" y2="9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        <line x1="6" y1="12" x2="10" y2="12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    ),
  },
];

const ADMIN_ICON = (
  <svg width="18" height="18" viewBox="0 0 18 18" fill="none" aria-hidden="true">
    <circle cx="9" cy="6" r="3" stroke="currentColor" strokeWidth="1.5" />
    <path d="M3 16c0-3.314 2.686-6 6-6s6 2.686 6 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    <circle cx="14" cy="3" r="2" fill="var(--accent)" />
  </svg>
);

function Sidebar() {
  const { isAuthenticated, role, logout, user } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login', { replace: true });
  };

  if (!isAuthenticated) return null;

  const initial = user?.username?.[0]?.toUpperCase() || '?';

  return (
    <aside style={{
      width: '240px',
      minHeight: '100vh',
      background: 'rgba(10, 15, 30, 0.95)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      flexShrink: 0,
      position: 'sticky',
      top: 0,
      height: '100vh',
      backdropFilter: 'blur(20px)',
      WebkitBackdropFilter: 'blur(20px)',
    }}>
      {/* Logo */}
      <div style={{
        padding: '1.75rem 1.5rem 1.25rem',
        borderBottom: '1px solid var(--border)',
        position: 'relative',
        overflow: 'hidden',
      }}>
        {/* Subtle glow behind logo */}
        <div style={{
          position: 'absolute',
          top: '-20px', left: '-20px',
          width: '100px', height: '100px',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(255,107,43,0.15) 0%, transparent 70%)',
          pointerEvents: 'none',
        }} />

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '4px' }}>
          {/* Logo icon */}
          <div style={{
            width: '32px', height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, var(--accent), #FF8C52)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 12px rgba(255,107,43,0.4)',
            flexShrink: 0,
          }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M8 2C5 2 3 4.5 3 4.5S5 5 5 8c0 2 1 4 3 5 2-1 3-3 3-5 0-3 2-3.5 2-3.5S11 2 8 2z" fill="white" fillOpacity="0.9" />
              <path d="M8 6v4M6.5 8l1.5 1.5L9.5 8" stroke="white" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>

          <span style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: '1.1rem',
            background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            letterSpacing: '-0.01em',
          }}>
            Pravaah OS
          </span>
        </div>

        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.6rem',
          color: 'var(--muted)',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          marginLeft: '40px',
        }}>
          Voice Intelligence
        </p>
      </div>

      {/* Nav */}
      <nav style={{ padding: '1rem 0.75rem', flex: 1 }}>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.58rem',
          color: 'var(--muted)',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          padding: '0 0.75rem',
          marginBottom: '0.5rem',
        }}>
          Navigation
        </p>

        {NAV_LINKS.map(({ to, end, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: '0.7rem',
              padding: '0.6rem 0.85rem',
              borderRadius: '10px',
              marginBottom: '3px',
              textDecoration: 'none',
              fontFamily: 'var(--font-display)',
              fontSize: '0.875rem',
              fontWeight: isActive ? 600 : 400,
              color: isActive ? 'var(--text)' : 'var(--muted)',
              background: isActive
                ? 'linear-gradient(135deg, rgba(255,107,43,0.15), rgba(255,107,43,0.05))'
                : 'transparent',
              border: isActive ? '1px solid rgba(255,107,43,0.2)' : '1px solid transparent',
              transition: 'all 0.2s ease',
              position: 'relative',
            })}
          >
            {({ isActive }) => (
              <>
                <span style={{ color: isActive ? 'var(--accent)' : 'inherit', transition: 'color 0.2s' }}>
                  {icon}
                </span>
                {label}
                {isActive && (
                  <span style={{
                    marginLeft: 'auto',
                    width: '6px', height: '6px',
                    borderRadius: '50%',
                    background: 'var(--accent)',
                    boxShadow: '0 0 8px var(--glow-accent)',
                  }} />
                )}
              </>
            )}
          </NavLink>
        ))}

        {role === 'admin' && (
          <>
            <div style={{ height: '1px', background: 'var(--border)', margin: '0.75rem 0.75rem' }} />
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.58rem',
              color: 'var(--muted)',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              padding: '0 0.75rem',
              marginBottom: '0.5rem',
            }}>
              System
            </p>
            <NavLink
              to="/admin"
              style={({ isActive }) => ({
                display: 'flex',
                alignItems: 'center',
                gap: '0.7rem',
                padding: '0.6rem 0.85rem',
                borderRadius: '10px',
                marginBottom: '3px',
                textDecoration: 'none',
                fontFamily: 'var(--font-display)',
                fontSize: '0.875rem',
                fontWeight: isActive ? 600 : 400,
                color: isActive ? 'var(--text)' : 'var(--muted)',
                background: isActive
                  ? 'linear-gradient(135deg, rgba(255,107,43,0.15), rgba(255,107,43,0.05))'
                  : 'transparent',
                border: isActive ? '1px solid rgba(255,107,43,0.2)' : '1px solid transparent',
                transition: 'all 0.2s ease',
                position: 'relative',
              })}
            >
              {({ isActive }) => (
                <>
                  <span style={{ color: isActive ? 'var(--accent)' : 'inherit', transition: 'color 0.2s' }}>
                    {ADMIN_ICON}
                  </span>
                  Admin
                  {isActive && (
                    <span style={{
                      marginLeft: 'auto',
                      width: '6px', height: '6px',
                      borderRadius: '50%',
                      background: 'var(--accent)',
                      boxShadow: '0 0 8px var(--glow-accent)',
                    }} />
                  )}
                </>
              )}
            </NavLink>
          </>
        )}
      </nav>

      {/* Footer */}
      <div style={{
        padding: '1rem 1.25rem',
        borderTop: '1px solid var(--border)',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.6rem' }}>
          {/* Avatar */}
          <div style={{
            width: '32px', height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, rgba(255,107,43,0.3), rgba(0,200,255,0.2))',
            border: '1px solid rgba(255,107,43,0.3)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontFamily: 'var(--font-display)',
            fontWeight: 700,
            fontSize: '0.8rem',
            color: 'var(--accent)',
            flexShrink: 0,
          }}>
            {initial}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <p style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 500,
              fontSize: '0.8rem',
              color: 'var(--text)',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}>
              {user?.username || 'User'}
            </p>
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--muted)',
              textTransform: 'uppercase',
              letterSpacing: '0.08em',
            }}>
              {role || 'agent'}
            </p>
          </div>
        </div>

        <button
          onClick={handleLogout}
          style={{
            width: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '0.4rem',
            padding: '0.4rem',
            background: 'rgba(255,51,102,0.06)',
            border: '1px solid rgba(255,51,102,0.15)',
            borderRadius: '7px',
            cursor: 'pointer',
            color: 'var(--muted)',
            fontFamily: 'var(--font-display)',
            fontSize: '0.75rem',
            fontWeight: 500,
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = 'rgba(255,51,102,0.12)';
            e.currentTarget.style.color = 'var(--danger)';
            e.currentTarget.style.borderColor = 'rgba(255,51,102,0.35)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = 'rgba(255,51,102,0.06)';
            e.currentTarget.style.color = 'var(--muted)';
            e.currentTarget.style.borderColor = 'rgba(255,51,102,0.15)';
          }}
        >
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <path d="M4.5 2H2a1 1 0 00-1 1v6a1 1 0 001 1h2.5M8 4l2.5 2L8 8M10.5 6H5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Sign Out
        </button>
      </div>
    </aside>
  );
}

function AppLayout({ children }) {
  const { isAuthenticated } = useAuth();
  return (
    <div style={{ display: 'flex', minHeight: '100vh', background: 'var(--bg)' }}>
      {isAuthenticated && <Sidebar />}
      <main style={{ flex: 1, minWidth: 0, overflowY: 'auto', position: 'relative' }}>
        {children}
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/login" element={<Login />} />

          <Route path="/" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
          <Route path="/call/:sessionId" element={<ProtectedRoute><ActiveCall /></ProtectedRoute>} />
          <Route path="/call/:sessionId/detail" element={<ProtectedRoute><CallDetail /></ProtectedRoute>} />
          <Route path="/analytics" element={<ProtectedRoute><Analytics /></ProtectedRoute>} />
          <Route path="/documents" element={<ProtectedRoute><Documents /></ProtectedRoute>} />
          <Route path="/admin" element={<ProtectedRoute role="admin"><AdminPage /></ProtectedRoute>} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}
