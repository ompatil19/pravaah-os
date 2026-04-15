export default function LanguageBadge({ language }) {
  if (!language) return null;

  const label = language.toUpperCase().replace('-', '\u2011'); // non-breaking hyphen

  const colorMap = {
    'HI\u2011EN': { bg: 'rgba(0,200,255,0.1)', border: 'rgba(0,200,255,0.25)', color: 'var(--cyan)' },
    'HI':        { bg: 'rgba(255,184,0,0.1)',  border: 'rgba(255,184,0,0.25)', color: 'var(--warning)' },
    'EN':        { bg: 'rgba(0,229,160,0.1)',  border: 'rgba(0,229,160,0.25)', color: 'var(--success)' },
  };

  const style = colorMap[label] || {
    bg: 'rgba(255,107,43,0.1)',
    border: 'rgba(255,107,43,0.25)',
    color: 'var(--accent)',
  };

  return (
    <span style={{
      display: 'inline-flex',
      alignItems: 'center',
      padding: '0.2rem 0.5rem',
      borderRadius: '6px',
      background: style.bg,
      border: `1px solid ${style.border}`,
      fontFamily: 'var(--font-mono)',
      fontSize: '0.62rem',
      fontWeight: 600,
      color: style.color,
      letterSpacing: '0.08em',
    }}>
      {label}
    </span>
  );
}
