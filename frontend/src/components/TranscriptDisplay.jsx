import { useEffect, useRef } from 'react';
import TranscriptBubble from './TranscriptBubble';

export default function TranscriptDisplay({ transcripts }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcripts]);

  if (!transcripts || transcripts.length === 0) {
    return (
      <div style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100%',
        minHeight: '200px',
        padding: '2rem',
      }}>
        <div style={{
          width: '52px', height: '52px',
          borderRadius: '14px',
          background: 'rgba(28,42,74,0.5)',
          border: '1px solid var(--border)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginBottom: '1rem',
          animation: 'float 4s ease-in-out infinite',
        }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" stroke="var(--muted)" strokeWidth="1.3" strokeLinejoin="round" />
            <path d="M8 9h8M8 13h5" stroke="var(--muted)" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </div>
        <p style={{
          fontFamily: 'var(--font-display)',
          fontSize: '0.85rem',
          color: 'var(--muted)',
          marginBottom: '0.25rem',
        }}>
          Waiting for transcript…
        </p>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.62rem',
          color: 'var(--border-2)',
          letterSpacing: '0.08em',
        }}>
          START RECORDING TO SEE LIVE TRANSCRIPT
        </p>
      </div>
    );
  }

  return (
    <div style={{ padding: '0.75rem 0.5rem', display: 'flex', flexDirection: 'column' }}>
      {transcripts.map((t, idx) => (
        <TranscriptBubble key={t.id ?? idx} transcript={t} />
      ))}
      <div ref={bottomRef} />
    </div>
  );
}
