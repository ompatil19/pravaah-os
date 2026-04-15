export default function TranscriptBubble({ transcript }) {
  const { text, isFinal, speaker, timestamp, language } = transcript;

  const isAgent = speaker !== 'customer';
  const timeLabel = timestamp
    ? new Date(timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : '';

  const langTag = language || detectLangTag(text);

  const langColors = {
    'HI-EN': { bg: 'rgba(0,200,255,0.1)', color: 'var(--cyan)', border: 'rgba(0,200,255,0.2)' },
    'HI':    { bg: 'rgba(255,184,0,0.1)', color: 'var(--warning)', border: 'rgba(255,184,0,0.2)' },
    'EN':    { bg: 'rgba(0,229,160,0.1)', color: 'var(--success)', border: 'rgba(0,229,160,0.2)' },
  };
  const langStyle = langColors[langTag] || { bg: 'rgba(255,107,43,0.1)', color: 'var(--accent)', border: 'rgba(255,107,43,0.2)' };

  return (
    <div style={{
      display: 'flex',
      width: '100%',
      marginBottom: '0.85rem',
      justifyContent: isAgent ? 'flex-start' : 'flex-end',
      animation: isFinal
        ? isAgent ? 'slide-in-left 0.35s cubic-bezier(0.16,1,0.3,1) both' : 'slide-in-right 0.35s cubic-bezier(0.16,1,0.3,1) both'
        : 'none',
    }}>
      {/* Agent avatar — left side */}
      {isAgent && (
        <div style={{
          width: '30px', height: '30px',
          borderRadius: '8px',
          background: 'linear-gradient(135deg, rgba(255,107,43,0.25), rgba(255,107,43,0.1))',
          border: '1px solid rgba(255,107,43,0.25)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
          marginRight: '0.6rem',
          alignSelf: 'flex-end',
          fontFamily: 'var(--font-display)',
          fontSize: '0.65rem',
          fontWeight: 700,
          color: 'var(--accent)',
          letterSpacing: '0.02em',
        }}>
          AG
        </div>
      )}

      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: isAgent ? 'flex-start' : 'flex-end',
        gap: '4px',
        maxWidth: '72%',
      }}>
        {/* Meta row */}
        <div style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.4rem',
          padding: '0 2px',
        }}>
          <span style={{
            fontFamily: 'var(--font-display)',
            fontSize: '0.72rem',
            fontWeight: 600,
            color: isAgent ? 'var(--accent)' : 'var(--text-2)',
          }}>
            {isAgent ? 'Agent' : 'Customer'}
          </span>
          {langTag && (
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.55rem',
              fontWeight: 600,
              padding: '1px 5px',
              borderRadius: '4px',
              background: langStyle.bg,
              color: langStyle.color,
              border: `1px solid ${langStyle.border}`,
              letterSpacing: '0.08em',
            }}>
              {langTag}
            </span>
          )}
          {timeLabel && (
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--muted)' }}>
              {timeLabel}
            </span>
          )}
        </div>

        {/* Bubble */}
        <div
          style={{
            padding: '0.6rem 0.9rem',
            borderRadius: isAgent ? '4px 14px 14px 14px' : '14px 4px 14px 14px',
            fontFamily: 'var(--font-mono)',
            fontSize: '0.82rem',
            lineHeight: '1.6',
            opacity: isFinal ? 1 : 0.5,
            fontStyle: isFinal ? 'normal' : 'italic',
            transition: 'opacity 0.3s ease',
            ...(isAgent ? {
              background: 'rgba(13,20,37,0.9)',
              border: '1px solid var(--border-2)',
              color: 'var(--text)',
              backdropFilter: 'blur(8px)',
            } : {
              background: 'linear-gradient(135deg, var(--accent) 0%, #FF8C52 100%)',
              color: '#fff',
              boxShadow: '0 4px 16px rgba(255,107,43,0.3)',
            }),
          }}
        >
          {text}
          {!isFinal && (
            <span style={{ animation: 'blink 1s step-end infinite', marginLeft: '3px', color: isAgent ? 'var(--muted)' : 'rgba(255,255,255,0.6)' }}>
              |
            </span>
          )}
        </div>
      </div>

      {/* Customer avatar — right side */}
      {!isAgent && (
        <div style={{
          width: '30px', height: '30px',
          borderRadius: '8px',
          background: 'linear-gradient(135deg, rgba(0,200,255,0.2), rgba(0,200,255,0.08))',
          border: '1px solid rgba(0,200,255,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          flexShrink: 0,
          marginLeft: '0.6rem',
          alignSelf: 'flex-end',
          fontFamily: 'var(--font-display)',
          fontSize: '0.65rem',
          fontWeight: 700,
          color: 'var(--cyan)',
          letterSpacing: '0.02em',
        }}>
          CX
        </div>
      )}
    </div>
  );
}

function detectLangTag(text) {
  if (!text) return null;
  const hasDevanagari = /[\u0900-\u097F]/.test(text);
  const hasLatin      = /[a-zA-Z]/.test(text);
  if (hasDevanagari && hasLatin) return 'HI-EN';
  if (hasDevanagari) return 'HI';
  return 'EN';
}
