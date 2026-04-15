import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import useAuth from '../hooks/useAuth';

function AnimatedOrb({ style }) {
  return (
    <div style={{
      position: 'absolute',
      borderRadius: '50%',
      filter: 'blur(60px)',
      pointerEvents: 'none',
      animation: 'float 6s ease-in-out infinite',
      ...style,
    }} />
  );
}

export default function Login() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  const [username, setUsername]   = useState('');
  const [password, setPassword]   = useState('');
  const [error, setError]         = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [mounted, setMounted]     = useState(false);

  useEffect(() => {
    setTimeout(() => setMounted(true), 50);
  }, []);

  if (isAuthenticated) {
    navigate('/', { replace: true });
    return null;
  }

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Invalid credentials. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: '100vh',
      background: 'var(--bg)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      padding: '1rem',
      position: 'relative',
      overflow: 'hidden',
    }}>
      {/* Grid dot background */}
      <div className="grid-dots" style={{ position: 'absolute', inset: 0, opacity: 0.4 }} />

      {/* Animated orbs */}
      <AnimatedOrb style={{
        width: '500px', height: '500px',
        background: 'rgba(255,107,43,0.12)',
        top: '-100px', left: '-150px',
        animationDelay: '0s',
      }} />
      <AnimatedOrb style={{
        width: '400px', height: '400px',
        background: 'rgba(0,200,255,0.08)',
        bottom: '-80px', right: '-100px',
        animationDelay: '2s',
      }} />
      <AnimatedOrb style={{
        width: '300px', height: '300px',
        background: 'rgba(255,107,43,0.06)',
        top: '60%', left: '60%',
        animationDelay: '4s',
      }} />

      {/* Card */}
      <div
        className="card-glass animate-fade-up"
        style={{
          width: '100%',
          maxWidth: '420px',
          padding: '2.5rem',
          position: 'relative',
          zIndex: 10,
          opacity: mounted ? 1 : 0,
          transform: mounted ? 'translateY(0)' : 'translateY(24px)',
          transition: 'opacity 0.5s ease, transform 0.5s cubic-bezier(0.16,1,0.3,1)',
        }}
      >
        {/* Logo area */}
        <div style={{ textAlign: 'center', marginBottom: '2.25rem' }}>
          <div style={{
            width: '56px', height: '56px',
            borderRadius: '16px',
            background: 'linear-gradient(135deg, var(--accent), #FF8C52)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 1rem',
            boxShadow: '0 8px 24px rgba(255,107,43,0.4)',
          }}>
            <svg width="26" height="26" viewBox="0 0 16 16" fill="none">
              <path d="M8 1C4.5 1 2 4 2 4S4.5 5 4.5 8c0 2.5 1.5 4.5 3.5 6 2-1.5 3.5-3.5 3.5-6 0-3 2.5-4 2.5-4S11.5 1 8 1z" fill="white" fillOpacity="0.95" />
              <path d="M8 5v4.5" stroke="rgba(255,107,43,0.8)" strokeWidth="1.3" strokeLinecap="round" />
              <circle cx="8" cy="5" r="1" fill="rgba(255,107,43,0.9)" />
            </svg>
          </div>

          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: '1.8rem',
            background: 'linear-gradient(135deg, var(--text) 0%, var(--accent) 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            backgroundClip: 'text',
            marginBottom: '0.35rem',
            letterSpacing: '-0.02em',
          }}>
            Pravaah OS
          </h1>

          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.65rem',
            color: 'var(--muted)',
            letterSpacing: '0.12em',
            textTransform: 'uppercase',
          }}>
            Voice Intelligence Platform
          </p>
        </div>

        {/* Divider with label */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '1.5rem' }}>
          <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
            Sign In
          </span>
          <div style={{ flex: 1, height: '1px', background: 'var(--border)' }} />
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate>
          {/* Username */}
          <div style={{ marginBottom: '1rem' }}>
            <label htmlFor="username" style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontFamily: 'var(--font-display)',
              fontSize: '0.78rem',
              fontWeight: 500,
              color: 'var(--text-2)',
              marginBottom: '0.5rem',
              letterSpacing: '0.01em',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="4" r="2.5" stroke="currentColor" strokeWidth="1.3" />
                <path d="M1.5 11c0-2.485 2.015-4.5 4.5-4.5s4.5 2.015 4.5 4.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={isLoading}
              className="input-field"
              placeholder="Enter your username"
            />
          </div>

          {/* Password */}
          <div style={{ marginBottom: '1.5rem' }}>
            <label htmlFor="password" style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.4rem',
              fontFamily: 'var(--font-display)',
              fontSize: '0.78rem',
              fontWeight: 500,
              color: 'var(--text-2)',
              marginBottom: '0.5rem',
              letterSpacing: '0.01em',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <rect x="2" y="5" width="8" height="6" rx="1.5" stroke="currentColor" strokeWidth="1.3" />
                <path d="M4 5V3.5a2 2 0 014 0V5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
                <circle cx="6" cy="8" r="1" fill="currentColor" />
              </svg>
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={isLoading}
              className="input-field"
              placeholder="Enter your password"
            />
          </div>

          {/* Error */}
          {error && (
            <div style={{
              background: 'rgba(255,51,102,0.08)',
              border: '1px solid rgba(255,51,102,0.25)',
              borderRadius: '8px',
              padding: '0.75rem 1rem',
              marginBottom: '1rem',
              fontFamily: 'var(--font-display)',
              fontSize: '0.82rem',
              color: 'var(--danger)',
              display: 'flex',
              alignItems: 'center',
              gap: '0.5rem',
            }}>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style={{ flexShrink: 0 }}>
                <circle cx="7" cy="7" r="6" stroke="currentColor" strokeWidth="1.3" />
                <path d="M7 4v3.5M7 9.5v.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
              </svg>
              {error}
            </div>
          )}

          {/* Submit */}
          <button
            type="submit"
            className="btn-accent"
            disabled={isLoading || !username || !password}
            style={{
              width: '100%',
              padding: '0.8rem',
              fontSize: '0.95rem',
              fontWeight: 600,
              letterSpacing: '0.02em',
              opacity: isLoading || !username || !password ? 0.55 : 1,
              cursor: isLoading || !username || !password ? 'not-allowed' : 'pointer',
              transform: 'none',
            }}
          >
            {isLoading ? (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: 'spin-slow 0.8s linear infinite' }}>
                  <circle cx="8" cy="8" r="6.5" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
                  <path d="M8 1.5A6.5 6.5 0 0114.5 8" stroke="white" strokeWidth="2" strokeLinecap="round" />
                </svg>
                Authenticating…
              </span>
            ) : (
              <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.5rem' }}>
                Access Platform
                <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                  <path d="M3 7h8M8 4l3 3-3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
              </span>
            )}
          </button>
        </form>

        {/* Footer */}
        <p style={{
          marginTop: '1.5rem',
          textAlign: 'center',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.6rem',
          color: 'var(--muted)',
          letterSpacing: '0.06em',
        }}>
          PRAVAAH OS · MISSION CONTROL · v2.0
        </p>
      </div>
    </div>
  );
}
