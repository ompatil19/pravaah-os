import { useState, useEffect, useCallback } from 'react';
import socket from '../socket';

const STATUS_CONFIG = {
  QUEUED:     { label: 'Queued',     color: 'var(--muted)',    bg: 'rgba(90,100,128,0.12)',  progress: 5,    pulse: false },
  EXTRACTING: { label: 'Extracting', color: 'var(--warning)',  bg: 'rgba(255,184,0,0.1)',    progress: 30,   pulse: true  },
  EMBEDDING:  { label: 'Embedding',  color: 'var(--cyan)',     bg: 'rgba(0,200,255,0.1)',    progress: null, pulse: true  },
  DONE:       { label: 'Done',       color: 'var(--success)',  bg: 'rgba(0,229,160,0.1)',    progress: 100,  pulse: false },
  FAILED:     { label: 'Failed',     color: 'var(--danger)',   bg: 'rgba(255,51,102,0.1)',   progress: 100,  pulse: false },
};

export default function DocProgressBar({ docId, initialStatus = 'QUEUED', onComplete }) {
  const [status,            setStatus]            = useState(initialStatus?.toUpperCase() || 'QUEUED');
  const [embeddingProgress, setEmbeddingProgress] = useState(0);
  const [meta,              setMeta]              = useState({ totalPages: null, totalChunks: null });

  const handleDocProgress = useCallback((data) => {
    if (data.doc_id !== docId) return;
    const newStatus = data.status?.toUpperCase();
    if (newStatus) setStatus(newStatus);
    if (newStatus === 'EMBEDDING' && data.progress != null) setEmbeddingProgress(data.progress);
    if (newStatus === 'DONE') {
      setMeta({ totalPages: data.total_pages ?? null, totalChunks: data.total_chunks ?? null });
      if (onComplete) onComplete(data);
    }
  }, [docId, onComplete]);

  useEffect(() => {
    if (!socket.connected) socket.connect();
    socket.on('doc_progress', handleDocProgress);
    return () => socket.off('doc_progress', handleDocProgress);
  }, [handleDocProgress]);

  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.QUEUED;
  const progressPct = status === 'EMBEDDING'
    ? Math.max(31, Math.min(99, embeddingProgress))
    : cfg.progress;

  const isDone   = status === 'DONE';
  const isFailed = status === 'FAILED';

  const progressColor = isDone
    ? 'linear-gradient(90deg, var(--success), var(--cyan))'
    : isFailed
      ? 'var(--danger)'
      : status === 'EMBEDDING'
        ? 'linear-gradient(90deg, var(--cyan), var(--success))'
        : cfg.color;

  return (
    <div style={{ marginTop: '0.4rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.35rem' }}>
        <span style={{
          display: 'inline-flex',
          alignItems: 'center',
          gap: '4px',
          padding: '1px 6px',
          borderRadius: '4px',
          background: cfg.bg,
          color: cfg.color,
          fontFamily: 'var(--font-mono)',
          fontSize: '0.6rem',
          fontWeight: 600,
          letterSpacing: '0.08em',
          animation: cfg.pulse ? 'accent-pulse 1.2s ease-in-out infinite' : 'none',
        }}>
          {cfg.pulse && (
            <span style={{
              width: '5px', height: '5px',
              borderRadius: '50%',
              background: cfg.color,
              display: 'inline-block',
            }} />
          )}
          {cfg.label}
          {status === 'EMBEDDING' && embeddingProgress > 0 && ` ${embeddingProgress}%`}
        </span>

        {isDone && meta.totalPages != null && (
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)' }}>
            {meta.totalPages}p · {meta.totalChunks}c
          </span>
        )}
      </div>

      <div style={{ height: '3px', background: 'rgba(28,42,74,0.8)', borderRadius: '3px', overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${progressPct ?? 100}%`,
          background: progressColor,
          borderRadius: '3px',
          transition: 'width 0.5s ease',
          boxShadow: isDone ? '0 0 6px rgba(0,229,160,0.4)' : 'none',
        }} />
      </div>
    </div>
  );
}
