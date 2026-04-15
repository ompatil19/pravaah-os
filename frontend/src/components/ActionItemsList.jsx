import ActionItemRow from './ActionItemRow';

export default function ActionItemsList({ items = [], onToggle }) {
  const done = items.filter((i) => i.status === 'done').length;

  return (
    <div className="card-glass" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
        <div style={{
          width: '28px', height: '28px',
          borderRadius: '7px',
          background: 'linear-gradient(135deg, rgba(0,229,160,0.2), rgba(0,229,160,0.06))',
          border: '1px solid rgba(0,229,160,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M2 4h1.5M2 7h1.5M2 10h1.5M5.5 4h6.5M5.5 7h6.5M5.5 10h4" stroke="var(--success)" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </div>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.85rem', color: 'var(--text)' }}>
          Action Items
        </span>

        {items.length > 0 && (
          <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <span style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--success)',
              padding: '2px 6px',
              background: 'rgba(0,229,160,0.08)',
              border: '1px solid rgba(0,229,160,0.2)',
              borderRadius: '4px',
            }}>
              {done}/{items.length}
            </span>
          </div>
        )}
      </div>

      {/* Progress bar */}
      {items.length > 0 && (
        <div style={{
          height: '3px',
          background: 'rgba(28,42,74,0.8)',
          borderRadius: '4px',
          marginBottom: '0.75rem',
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${(done / items.length) * 100}%`,
            background: 'linear-gradient(90deg, var(--success), var(--cyan))',
            borderRadius: '4px',
            transition: 'width 0.4s ease',
          }} />
        </div>
      )}

      {items.length === 0 ? (
        <div style={{
          padding: '1.5rem 0',
          textAlign: 'center',
          fontFamily: 'var(--font-display)',
          fontSize: '0.82rem',
          color: 'var(--muted)',
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" style={{ margin: '0 auto 0.5rem', opacity: 0.3 }}>
            <path d="M9 12l2 2 4-4M7 2H17a2 2 0 012 2v16a2 2 0 01-2 2H7a2 2 0 01-2-2V4a2 2 0 012-2z" stroke="var(--muted)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          No action items yet
        </div>
      ) : (
        <div>
          {items.map((item, idx) => (
            <ActionItemRow key={item.id ?? idx} item={item} onToggle={onToggle} />
          ))}
        </div>
      )}
    </div>
  );
}
