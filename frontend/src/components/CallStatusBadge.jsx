export default function CallStatusBadge({ status }) {
  if (status === 'active') {
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.4rem',
        padding: '0.25rem 0.65rem',
        borderRadius: '20px',
        background: 'rgba(0,229,160,0.1)',
        border: '1px solid rgba(0,229,160,0.25)',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.65rem',
        fontWeight: 600,
        color: 'var(--success)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
      }}>
        <span style={{ position: 'relative', display: 'inline-flex' }}>
          <span style={{
            width: '6px', height: '6px',
            borderRadius: '50%',
            background: 'var(--success)',
            display: 'inline-block',
          }} />
          <span style={{
            position: 'absolute',
            inset: 0,
            borderRadius: '50%',
            background: 'var(--success)',
            animation: 'pulse-ring 1.8s ease-out infinite',
          }} />
        </span>
        Live
      </span>
    );
  }

  if (status === 'escalated') {
    return (
      <span style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '0.4rem',
        padding: '0.25rem 0.65rem',
        borderRadius: '20px',
        background: 'rgba(255,51,102,0.1)',
        border: '1px solid rgba(255,51,102,0.25)',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.65rem',
        fontWeight: 600,
        color: 'var(--danger)',
        letterSpacing: '0.08em',
        textTransform: 'uppercase',
      }}>
        <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
          <path d="M4 1L7 7H1L4 1z" fill="currentColor" />
        </svg>
        Escalated
      </span>
    );
  }

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      gap: '0.4rem',
      padding: '0.25rem 0.65rem',
      borderRadius: '20px',
      background: 'rgba(90,100,128,0.15)',
      border: '1px solid rgba(90,100,128,0.25)',
      fontFamily: 'var(--font-mono)',
      fontSize: '0.65rem',
      fontWeight: 600,
      color: 'var(--muted)',
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
    }}>
      <span style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--muted)', display: 'inline-block' }} />
      {status ? status : 'Ended'}
    </span>
  );
}
