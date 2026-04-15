import { useState } from 'react';

const PRIORITY_CONFIG = {
  high:   { color: 'var(--danger)',  bg: 'rgba(255,51,102,0.1)',  label: 'HIGH',   dot: '#FF3366' },
  medium: { color: 'var(--warning)', bg: 'rgba(255,184,0,0.1)',   label: 'MED',    dot: '#FFB800' },
  low:    { color: 'var(--success)', bg: 'rgba(0,229,160,0.1)',   label: 'LOW',    dot: '#00E5A0' },
};

export default function ActionItemRow({ item, onToggle }) {
  const [done, setDone] = useState(item.status === 'done');

  const handleToggle = () => {
    const next = !done;
    setDone(next);
    if (onToggle) onToggle(item.id, next ? 'done' : 'open');
  };

  const cfg = PRIORITY_CONFIG[item.priority] || PRIORITY_CONFIG.medium;

  return (
    <div style={{
      display: 'flex',
      alignItems: 'flex-start',
      gap: '0.65rem',
      padding: '0.65rem 0.75rem',
      borderRadius: '8px',
      marginBottom: '0.4rem',
      background: done ? 'transparent' : 'rgba(19,29,56,0.5)',
      border: `1px solid ${done ? 'rgba(28,42,74,0.3)' : 'var(--border)'}`,
      transition: 'all 0.2s ease',
      opacity: done ? 0.55 : 1,
    }}>
      {/* Priority badge */}
      <div style={{
        flexShrink: 0,
        marginTop: '2px',
        display: 'flex',
        alignItems: 'center',
        gap: '4px',
      }}>
        <span style={{
          width: '6px', height: '6px',
          borderRadius: '50%',
          background: cfg.dot,
          boxShadow: `0 0 6px ${cfg.dot}80`,
          display: 'inline-block',
          flexShrink: 0,
        }} />
        <span style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.52rem',
          color: cfg.color,
          letterSpacing: '0.08em',
          padding: '1px 4px',
          background: cfg.bg,
          borderRadius: '3px',
        }}>
          {cfg.label}
        </span>
      </div>

      {/* Text */}
      <span style={{
        flex: 1,
        fontFamily: 'var(--font-display)',
        fontSize: '0.82rem',
        color: done ? 'var(--muted)' : 'var(--text-2)',
        textDecoration: done ? 'line-through' : 'none',
        lineHeight: '1.5',
      }}>
        {item.text}
      </span>

      {/* Assignee */}
      {item.assignee && (
        <span style={{
          flexShrink: 0,
          fontFamily: 'var(--font-mono)',
          fontSize: '0.6rem',
          fontWeight: 600,
          padding: '2px 7px',
          borderRadius: '5px',
          background: 'rgba(255,107,43,0.1)',
          color: 'var(--accent)',
          border: '1px solid rgba(255,107,43,0.2)',
          whiteSpace: 'nowrap',
        }}>
          {item.assignee}
        </span>
      )}

      {/* Checkbox */}
      <button
        onClick={handleToggle}
        title={done ? 'Mark as open' : 'Mark as done'}
        style={{
          flexShrink: 0,
          width: '20px', height: '20px',
          borderRadius: '5px',
          border: `1.5px solid ${done ? 'var(--success)' : 'var(--border-2)'}`,
          background: done ? 'rgba(0,229,160,0.15)' : 'transparent',
          cursor: 'pointer',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          transition: 'all 0.2s ease',
        }}
      >
        {done && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke="var(--success)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </button>
    </div>
  );
}
