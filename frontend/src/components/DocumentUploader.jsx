import { useState, useRef, useCallback } from 'react';
import { documentsApi } from '../api';

export default function DocumentUploader({ sessionId }) {
  const [isDragging,  setIsDragging]  = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadedDoc, setUploadedDoc] = useState(null);
  const [error,       setError]       = useState(null);
  const [progress,    setProgress]    = useState(0);
  const fileInputRef = useRef(null);

  const handleUpload = useCallback(async (file) => {
    if (!file) return;
    const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
    if (!allowed.includes(file.type) && !file.name.match(/\.(pdf|docx|txt)$/i)) {
      setError('Only PDF, DOCX, and TXT files are accepted.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File too large — maximum 10 MB.');
      return;
    }
    setError(null);
    setIsUploading(true);
    setProgress(15);
    const formData = new FormData();
    formData.append('file', file);
    if (sessionId) formData.append('call_session_id', sessionId);
    try {
      setProgress(45);
      const { data } = await documentsApi.upload(formData);
      setProgress(100);
      setUploadedDoc(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
    }
  }, [sessionId]);

  const onDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  }, [handleUpload]);

  return (
    <div className="card-glass" style={{ padding: '1.25rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '0.85rem' }}>
        <div style={{
          width: '28px', height: '28px',
          borderRadius: '7px',
          background: 'rgba(255,184,0,0.15)',
          border: '1px solid rgba(255,184,0,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <path d="M6.5 1v7M4 3.5l2.5-2.5 2.5 2.5M2 10v.5a1 1 0 001 1h7a1 1 0 001-1V10" stroke="var(--warning)" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <span style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.82rem', color: 'var(--text)' }}>
          Attach Document
        </span>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        style={{
          cursor: 'pointer',
          borderRadius: '8px',
          border: `2px dashed ${isDragging ? 'var(--warning)' : 'var(--border-2)'}`,
          background: isDragging ? 'rgba(255,184,0,0.04)' : 'rgba(13,20,37,0.4)',
          padding: '1.25rem',
          textAlign: 'center',
          transition: 'all 0.2s ease',
        }}
      >
        <svg style={{ margin: '0 auto 0.5rem', display: 'block' }} width="20" height="20" viewBox="0 0 20 20" fill="none">
          <path d="M10 3v10M7 6l3-3 3 3M3 15v1a2 2 0 002 2h10a2 2 0 002-2v-1" stroke={isDragging ? 'var(--warning)' : 'var(--muted)'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.78rem', color: 'var(--text-2)' }}>
          Drop file or <span style={{ color: 'var(--warning)', fontWeight: 600 }}>click to upload</span>
        </p>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--muted)', marginTop: '2px', letterSpacing: '0.06em' }}>
          PDF · DOCX · TXT · MAX 10MB
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        style={{ display: 'none' }}
        onChange={(e) => handleUpload(e.target.files?.[0])}
      />

      {isUploading && (
        <div style={{ marginTop: '0.75rem' }}>
          <div style={{ height: '3px', background: 'rgba(28,42,74,0.8)', borderRadius: '3px', overflow: 'hidden' }}>
            <div style={{
              height: '100%',
              width: `${progress}%`,
              background: 'linear-gradient(90deg, var(--warning), #FFDA6B)',
              borderRadius: '3px',
              transition: 'width 0.4s ease',
            }} />
          </div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', marginTop: '3px' }}>
            Uploading {progress}%…
          </p>
        </div>
      )}

      {error && (
        <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.75rem', color: 'var(--danger)', marginTop: '0.5rem' }}>
          {error}
        </p>
      )}

      {uploadedDoc && !isUploading && (
        <div className="animate-fade-up" style={{
          marginTop: '0.75rem',
          padding: '0.65rem 0.85rem',
          background: 'rgba(0,229,160,0.06)',
          border: '1px solid rgba(0,229,160,0.2)',
          borderRadius: '8px',
        }}>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.68rem', color: 'var(--success)', fontWeight: 600 }}>
            ✓ {uploadedDoc.filename}
          </p>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', marginTop: '2px' }}>
            {(uploadedDoc.size_bytes / 1024).toFixed(1)} KB · {uploadedDoc.mime_type}
          </p>
        </div>
      )}
    </div>
  );
}
