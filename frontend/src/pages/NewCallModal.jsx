import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { callsApi } from '../api';

export default function NewCallModal({ onClose }) {
  const navigate = useNavigate();
  const [agentId,   setAgentId]   = useState('');
  const [language,  setLanguage]  = useState('hi-en');
  const [isLoading, setIsLoading] = useState(false);
  const [error,     setError]     = useState(null);

  const handleStart = async () => {
    setError(null);
    setIsLoading(true);
    try {
      const { data } = await callsApi.start({ agent_id: agentId || 'unknown', language });
      onClose?.();
      navigate(`/call/${data.session_id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 50,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'rgba(4,6,14,0.8)',
        backdropFilter: 'blur(12px)',
        WebkitBackdropFilter: 'blur(12px)',
        animation: 'fade-in 0.2s ease both',
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose?.(); }}
    >
      <div
        className="card-glass animate-fade-up"
        style={{ width: '100%', maxWidth: '440px', padding: '2rem', position: 'relative' }}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.75rem' }}>
          <div>
            <h2 style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 700,
              fontSize: '1.2rem',
              color: 'var(--text)',
              letterSpacing: '-0.01em',
            }}>
              New Call Session
            </h2>
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', letterSpacing: '0.08em', marginTop: '2px', textTransform: 'uppercase' }}>
              Configure & launch
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              width: '32px', height: '32px',
              borderRadius: '8px',
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--border)',
              cursor: 'pointer',
              color: 'var(--muted)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,51,102,0.1)'; e.currentTarget.style.color = 'var(--danger)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,255,255,0.04)'; e.currentTarget.style.color = 'var(--muted)'; }}
          >
            <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
              <path d="M1.5 1.5l10 10M11.5 1.5l-10 10" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
          </button>
        </div>

        {/* Divider */}
        <div style={{ height: '1px', background: 'linear-gradient(90deg, transparent, var(--border), transparent)', marginBottom: '1.5rem' }} />

        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Agent ID */}
          <div>
            <label style={{
              display: 'block',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.62rem',
              fontWeight: 600,
              color: 'var(--muted)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              marginBottom: '0.5rem',
            }}>
              Agent ID
            </label>
            <input
              type="text"
              value={agentId}
              onChange={(e) => setAgentId(e.target.value)}
              placeholder="e.g. agent-42"
              className="input-field"
              style={{ fontFamily: 'var(--font-mono)', fontSize: '0.85rem' }}
            />
          </div>

          {/* Language */}
          <div>
            <label style={{
              display: 'block',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.62rem',
              fontWeight: 600,
              color: 'var(--muted)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              marginBottom: '0.5rem',
            }}>
              Language Mode
            </label>
            <select
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              className="input-field"
              style={{ fontFamily: 'var(--font-display)', fontSize: '0.875rem' }}
            >
              <option value="hi-en">Hindi + English (Hinglish)</option>
              <option value="hi">Hindi only</option>
              <option value="en">English only</option>
            </select>
          </div>

          {error && (
            <div style={{
              padding: '0.65rem 0.85rem',
              background: 'rgba(255,51,102,0.08)',
              border: '1px solid rgba(255,51,102,0.25)',
              borderRadius: '8px',
              fontFamily: 'var(--font-display)',
              fontSize: '0.8rem',
              color: 'var(--danger)',
            }}>
              {error}
            </div>
          )}

          <button
            onClick={handleStart}
            disabled={isLoading}
            className="btn-accent"
            style={{
              width: '100%',
              padding: '0.85rem',
              fontSize: '0.95rem',
              marginTop: '0.25rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '0.5rem',
              opacity: isLoading ? 0.7 : 1,
            }}
          >
            {isLoading ? (
              <>
                <svg style={{ animation: 'spin-slow 0.8s linear infinite' }} width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <circle cx="7.5" cy="7.5" r="6" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
                  <path d="M7.5 1.5A6 6 0 0113.5 7.5" stroke="white" strokeWidth="2" strokeLinecap="round" />
                </svg>
                Launching…
              </>
            ) : (
              <>
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <circle cx="7.5" cy="7.5" r="6" stroke="white" strokeWidth="1.5" />
                  <path d="M5.5 7.5l1.5 1.5L10 5.5" stroke="white" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                </svg>
                Launch Call
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
