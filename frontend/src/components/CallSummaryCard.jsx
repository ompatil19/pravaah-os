export default function CallSummaryCard({ summary, generatedAt }) {
  if (!summary) return null;

  let parsed = null;
  try {
    parsed = typeof summary === 'object' ? summary : JSON.parse(summary);
  } catch {
    parsed = null;
  }

  const timeLabel = generatedAt ? new Date(generatedAt).toLocaleString() : null;

  const labelMap = {
    customer_issue: { label: 'Customer Issue', color: 'var(--accent)', border: 'rgba(255,107,43,0.3)' },
    key_facts:      { label: 'Key Facts',      color: 'var(--cyan)',   border: 'rgba(0,200,255,0.3)' },
    promises:       { label: 'Promises Made',  color: 'var(--success)', border: 'rgba(0,229,160,0.3)' },
    next_action:    { label: 'Next Action',    color: 'var(--warning)', border: 'rgba(255,184,0,0.3)' },
  };

  return (
    <div className="card-glass animate-fade-up" style={{ padding: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <div style={{
            width: '32px', height: '32px',
            borderRadius: '8px',
            background: 'linear-gradient(135deg, rgba(255,107,43,0.25), rgba(255,107,43,0.08))',
            border: '1px solid rgba(255,107,43,0.2)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="1" width="14" height="14" rx="3" stroke="var(--accent)" strokeWidth="1.3" />
              <path d="M4 5.5h8M4 8h8M4 10.5h5" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round" />
            </svg>
          </div>
          <div>
            <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>
              Call Summary
            </h3>
            {timeLabel && (
              <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', marginTop: '1px' }}>
                Generated {timeLabel}
              </p>
            )}
          </div>
        </div>
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.55rem',
          color: 'var(--success)',
          padding: '3px 8px',
          background: 'rgba(0,229,160,0.08)',
          border: '1px solid rgba(0,229,160,0.2)',
          borderRadius: '4px',
          letterSpacing: '0.1em',
        }}>
          AI SUMMARY
        </span>
      </div>

      {parsed && typeof parsed === 'object' ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
          {Object.entries(parsed).filter(([, v]) => v).map(([k, v]) => {
            const cfg = labelMap[k] || { label: k.replace(/_/g, ' '), color: 'var(--text-2)', border: 'var(--border)' };
            return (
              <div key={k} style={{
                padding: '0.65rem 0.85rem',
                background: `${cfg.color}08`,
                border: `1px solid ${cfg.border}`,
                borderLeft: `3px solid ${cfg.color}`,
                borderRadius: '0 8px 8px 0',
              }}>
                <p style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: '0.6rem',
                  color: cfg.color,
                  textTransform: 'uppercase',
                  letterSpacing: '0.1em',
                  marginBottom: '0.3rem',
                  fontWeight: 600,
                }}>
                  {cfg.label}
                </p>
                <p style={{
                  fontFamily: 'var(--font-display)',
                  fontSize: '0.85rem',
                  color: 'var(--text-2)',
                  lineHeight: '1.55',
                }}>
                  {Array.isArray(v) ? v.join(', ') : String(v)}
                </p>
              </div>
            );
          })}
        </div>
      ) : (
        <p style={{
          fontFamily: 'var(--font-display)',
          fontSize: '0.875rem',
          color: 'var(--text-2)',
          lineHeight: '1.65',
          whiteSpace: 'pre-wrap',
          padding: '0.75rem',
          background: 'rgba(19,29,56,0.5)',
          border: '1px solid var(--border)',
          borderRadius: '8px',
        }}>
          {typeof summary === 'object' ? JSON.stringify(summary, null, 2) : String(summary)}
        </p>
      )}
    </div>
  );
}
