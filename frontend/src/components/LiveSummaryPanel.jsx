const SECTION_STYLES = {
  'Customer Issue': { accent: 'var(--accent)',  icon: '🎯' },
  'Key Facts':      { accent: 'var(--cyan)',    icon: '📋' },
  'Promises Made':  { accent: 'var(--success)', icon: '✅' },
  'Next Action':    { accent: 'var(--warning)', icon: '→' },
  'Summary':        { accent: 'var(--text-2)',  icon: '📝' },
};

export default function LiveSummaryPanel({ summary }) {
  if (!summary) {
    return (
      <div className="card-glass" style={{ padding: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
          <div style={{ width: '6px', height: '6px', borderRadius: '50%', background: 'var(--muted)', animation: 'pulse-glow 2s ease-in-out infinite' }} />
          <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.82rem', color: 'var(--text-2)' }}>
            Live Summary
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', marginLeft: 'auto', letterSpacing: '0.08em' }}>
            WAITING…
          </span>
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {[100, 80, 90, 65, 85, 70].map((w, i) => (
            <div key={i} className="shimmer-skeleton" style={{ height: '10px', width: `${w}%`, animationDelay: `${i * 120}ms` }} />
          ))}
        </div>
      </div>
    );
  }

  const sections = parseSummary(summary);

  return (
    <div className="card-glass animate-fade-up" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
        <div style={{
          width: '28px', height: '28px',
          borderRadius: '7px',
          background: 'linear-gradient(135deg, rgba(255,107,43,0.25), rgba(255,107,43,0.08))',
          border: '1px solid rgba(255,107,43,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <rect x="1" y="1" width="12" height="12" rx="2.5" stroke="var(--accent)" strokeWidth="1.3" />
            <path d="M4 5h6M4 7.5h6M4 10h4" stroke="var(--accent)" strokeWidth="1.1" strokeLinecap="round" />
          </svg>
        </div>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.85rem', color: 'var(--text)' }}>
          Live Summary
        </span>
        <span style={{
          marginLeft: 'auto',
          fontFamily: 'var(--font-mono)',
          fontSize: '0.55rem',
          color: 'var(--success)',
          letterSpacing: '0.1em',
          padding: '2px 6px',
          background: 'rgba(0,229,160,0.08)',
          border: '1px solid rgba(0,229,160,0.2)',
          borderRadius: '4px',
        }}>
          AI GENERATED
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {sections.map((section, idx) => {
          const style = SECTION_STYLES[section.label] || SECTION_STYLES['Summary'];
          return (
            <div
              key={section.label}
              style={{
                padding: '0.65rem 0.75rem',
                background: `${style.accent}08`,
                border: `1px solid ${style.accent}20`,
                borderLeft: `3px solid ${style.accent}`,
                borderRadius: '0 8px 8px 0',
                animation: 'fade-up 0.4s ease both',
                animationDelay: `${idx * 80}ms`,
              }}
            >
              <p style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.58rem',
                color: style.accent,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                marginBottom: '0.35rem',
                fontWeight: 600,
              }}>
                {section.label}
              </p>
              <p style={{
                fontFamily: 'var(--font-display)',
                fontSize: '0.82rem',
                color: 'var(--text-2)',
                lineHeight: '1.55',
              }}>
                {section.content}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function parseSummary(summary) {
  if (typeof summary === 'object' && summary !== null) {
    const labelMap = {
      customer_issue: 'Customer Issue',
      key_facts:      'Key Facts',
      promises:       'Promises Made',
      next_action:    'Next Action',
      summary:        'Summary',
    };
    return Object.entries(summary)
      .filter(([, v]) => v)
      .map(([k, v]) => ({
        label:   labelMap[k] || k.replace(/_/g, ' ').toUpperCase(),
        content: Array.isArray(v) ? v.join(', ') : String(v),
      }));
  }
  try {
    const parsed = JSON.parse(summary);
    return parseSummary(parsed);
  } catch {
    const sentences = String(summary).split(/\.\s+/).filter(Boolean);
    const labels    = ['Customer Issue', 'Key Facts', 'Promises Made', 'Next Action'];
    return sentences.slice(0, 4).map((s, i) => ({
      label:   labels[i] || `Point ${i + 1}`,
      content: s.trim() + '.',
    }));
  }
}
