import { useState, useRef, useCallback, useEffect } from 'react';
import { documentsApi, searchDocuments } from '../api';
import DocProgressBar from '../components/DocProgressBar';

// ─── File type icon ─────────────────────────────────────────────
function FileTypeIcon({ filename }) {
  const ext = filename?.split('.').pop()?.toLowerCase();
  const config = {
    pdf:  { color: '#FF3366', label: 'PDF' },
    docx: { color: '#00C8FF', label: 'DOC' },
    txt:  { color: '#00E5A0', label: 'TXT' },
  }[ext] || { color: 'var(--muted)', label: ext?.toUpperCase() || '?' };

  return (
    <div style={{
      width: '38px', height: '38px',
      borderRadius: '8px',
      background: `${config.color}15`,
      border: `1px solid ${config.color}30`,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      flexShrink: 0,
    }}>
      <span style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.55rem',
        fontWeight: 700,
        color: config.color,
        letterSpacing: '0.05em',
      }}>
        {config.label}
      </span>
    </div>
  );
}

// ─── Upload Zone ─────────────────────────────────────────────────
function UploadZone({ onUploaded }) {
  const [isDragging,       setIsDragging]       = useState(false);
  const [isUploading,      setIsUploading]      = useState(false);
  const [uploadProgress,   setUploadProgress]   = useState(0);
  const [error,            setError]            = useState(null);
  const fileInputRef = useRef(null);

  const handleUpload = useCallback(async (file) => {
    if (!file) return;
    const allowed = ['application/pdf', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'];
    if (!allowed.includes(file.type) && !file.name.match(/\.(pdf|docx|txt)$/i)) {
      setError('Only PDF, DOCX, and TXT files are accepted.');
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError('File too large — maximum size is 10 MB.');
      return;
    }
    setError(null);
    setIsUploading(true);
    setUploadProgress(15);
    const formData = new FormData();
    formData.append('file', file);
    try {
      setUploadProgress(45);
      const { data } = await documentsApi.upload(formData);
      setUploadProgress(100);
      onUploaded(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsUploading(false);
      setTimeout(() => setUploadProgress(0), 800);
    }
  }, [onUploaded]);

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleUpload(file);
  };

  return (
    <div className="card-glass" style={{ padding: '1.5rem', marginBottom: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1rem' }}>
        <div style={{
          width: '28px', height: '28px',
          borderRadius: '7px',
          background: 'rgba(255,107,43,0.15)',
          border: '1px solid rgba(255,107,43,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <path d="M7 1v8M4 4l3-3 3 3M2 10v1a1 1 0 001 1h8a1 1 0 001-1v-1" stroke="var(--accent)" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
        <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>
          Upload Document
        </h2>
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
        onDragLeave={() => setIsDragging(false)}
        className={isDragging ? 'drag-zone-active' : ''}
        style={{
          cursor: 'pointer',
          borderRadius: '10px',
          border: `2px dashed ${isDragging ? 'var(--accent)' : 'var(--border-2)'}`,
          background: isDragging ? 'rgba(255,107,43,0.04)' : 'rgba(13,20,37,0.5)',
          padding: '2.5rem 1.5rem',
          textAlign: 'center',
          transition: 'all 0.2s ease',
          position: 'relative',
          overflow: 'hidden',
        }}
      >
        {/* Animated rings when dragging */}
        {isDragging && (
          <>
            <div style={{
              position: 'absolute',
              inset: '20px',
              borderRadius: '8px',
              border: '1px solid rgba(255,107,43,0.2)',
              animation: 'pulse-ring 1.2s ease-out infinite',
              pointerEvents: 'none',
            }} />
          </>
        )}

        <div style={{
          width: '48px', height: '48px',
          borderRadius: '12px',
          background: isDragging ? 'rgba(255,107,43,0.15)' : 'rgba(28,42,74,0.5)',
          border: `1px solid ${isDragging ? 'rgba(255,107,43,0.3)' : 'var(--border)'}`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          margin: '0 auto 1rem',
          transition: 'all 0.2s ease',
        }}>
          <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
            <path d="M11 3v12M7 7l4-4 4 4M3 17v1a2 2 0 002 2h12a2 2 0 002-2v-1" stroke={isDragging ? 'var(--accent)' : 'var(--muted)'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>

        <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.9rem', color: 'var(--text-2)', marginBottom: '0.25rem' }}>
          Drag & drop or{' '}
          <span style={{ color: 'var(--accent)', fontWeight: 600 }}>click to upload</span>
        </p>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--muted)', letterSpacing: '0.06em' }}>
          PDF · DOCX · TXT · MAX 10 MB
        </p>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt"
        style={{ display: 'none' }}
        onChange={(e) => handleUpload(e.target.files?.[0])}
      />

      {/* Upload progress */}
      {isUploading && (
        <div style={{ marginTop: '0.85rem' }}>
          <div style={{
            height: '4px',
            background: 'rgba(28,42,74,0.8)',
            borderRadius: '4px',
            overflow: 'hidden',
          }}>
            <div style={{
              height: '100%',
              width: `${uploadProgress}%`,
              background: 'linear-gradient(90deg, var(--accent), var(--cyan))',
              borderRadius: '4px',
              transition: 'width 0.4s ease',
              boxShadow: '0 0 8px rgba(255,107,43,0.4)',
            }} />
          </div>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--muted)', marginTop: '0.35rem', letterSpacing: '0.06em' }}>
            UPLOADING {uploadProgress}%
          </p>
        </div>
      )}

      {error && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: '0.4rem',
          marginTop: '0.75rem',
          padding: '0.5rem 0.75rem',
          background: 'rgba(255,51,102,0.08)',
          border: '1px solid rgba(255,51,102,0.2)',
          borderRadius: '7px',
          fontFamily: 'var(--font-display)',
          fontSize: '0.78rem',
          color: 'var(--danger)',
        }}>
          <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
            <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
            <path d="M6 4v2M6 7.5v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}

// ─── Document Row ─────────────────────────────────────────────────
function DocumentRow({ doc, isSelected, onToggleSelect }) {
  return (
    <div
      className="animate-fade-up"
      onClick={() => onToggleSelect(doc.doc_id)}
      style={{
        padding: '0.85rem 1rem',
        marginBottom: '0.5rem',
        display: 'flex',
        alignItems: 'flex-start',
        gap: '0.85rem',
        cursor: 'pointer',
        borderRadius: '10px',
        border: `1px solid ${isSelected ? 'rgba(255,107,43,0.4)' : 'var(--border)'}`,
        background: isSelected ? 'rgba(255,107,43,0.05)' : 'rgba(13,20,37,0.5)',
        transition: 'all 0.2s ease',
        backdropFilter: 'blur(8px)',
      }}
    >
      <FileTypeIcon filename={doc.filename} />

      <div style={{ flex: 1, minWidth: 0 }}>
        <p style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 600,
          fontSize: '0.875rem',
          color: isSelected ? 'var(--text)' : 'var(--text-2)',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
          marginBottom: '2px',
        }}>
          {doc.filename}
        </p>
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.62rem', color: 'var(--muted)' }}>
          {(doc.size_bytes / 1024).toFixed(1)} KB
        </p>
        <DocProgressBar docId={doc.doc_id} initialStatus={doc.status || 'QUEUED'} />
      </div>

      {/* Checkbox */}
      <div style={{
        width: '18px', height: '18px',
        borderRadius: '5px',
        border: `1.5px solid ${isSelected ? 'var(--accent)' : 'var(--border-2)'}`,
        background: isSelected ? 'rgba(255,107,43,0.2)' : 'transparent',
        flexShrink: 0,
        marginTop: '2px',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        transition: 'all 0.2s ease',
      }}>
        {isSelected && (
          <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
            <path d="M1 4L3.5 6.5L9 1" stroke="var(--accent)" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        )}
      </div>
    </div>
  );
}

// ─── RAG Query Panel ─────────────────────────────────────────────
function RagQueryPanel({ documents }) {
  const [query,          setQuery]          = useState('');
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [isSearching,    setIsSearching]    = useState(false);
  const [result,         setResult]         = useState(null);
  const [error,          setError]          = useState(null);
  const [openSource,     setOpenSource]     = useState(null);

  const toggleDoc = (id) =>
    setSelectedDocIds((prev) => prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;
    setIsSearching(true);
    setResult(null);
    setError(null);
    try {
      const docIds = selectedDocIds.length > 0 ? selectedDocIds : null;
      const { data } = await searchDocuments(query, docIds, 5);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsSearching(false);
    }
  };

  return (
    <div className="card-glass" style={{ padding: '1.5rem', marginTop: '1.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
        <div style={{
          width: '28px', height: '28px',
          borderRadius: '7px',
          background: 'rgba(0,200,255,0.15)',
          border: '1px solid rgba(0,200,255,0.2)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="6.5" cy="6.5" r="4.5" stroke="var(--cyan)" strokeWidth="1.3" />
            <path d="M10 10l3 3" stroke="var(--cyan)" strokeWidth="1.3" strokeLinecap="round" />
          </svg>
        </div>
        <div>
          <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.9rem', color: 'var(--text)' }}>
            Ask Your Documents
          </h2>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.6rem', color: 'var(--muted)', marginTop: '1px', letterSpacing: '0.06em' }}>
            AI-POWERED RAG SEARCH
          </p>
        </div>
      </div>

      {/* Doc multi-select */}
      {documents.length > 0 && (
        <div style={{ marginBottom: '1rem' }}>
          <p style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.6rem',
            color: 'var(--muted)',
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            marginBottom: '0.5rem',
          }}>
            {selectedDocIds.length === 0 ? 'Searching all documents' : `${selectedDocIds.length} doc${selectedDocIds.length > 1 ? 's' : ''} selected`}
          </p>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
            {documents.map((doc) => {
              const sel = selectedDocIds.includes(doc.doc_id);
              return (
                <button
                  key={doc.doc_id}
                  onClick={() => toggleDoc(doc.doc_id)}
                  style={{
                    padding: '3px 10px',
                    borderRadius: '6px',
                    border: `1px solid ${sel ? 'rgba(255,107,43,0.4)' : 'var(--border)'}`,
                    background: sel ? 'rgba(255,107,43,0.1)' : 'transparent',
                    color: sel ? 'var(--accent)' : 'var(--muted)',
                    fontFamily: 'var(--font-display)',
                    fontSize: '0.75rem',
                    cursor: 'pointer',
                    transition: 'all 0.15s',
                    maxWidth: '180px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  {doc.filename}
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Query form */}
      <form onSubmit={handleSearch}>
        <div style={{ position: 'relative', marginBottom: '0.75rem' }}>
          <textarea
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask a question about your documents…"
            rows={3}
            disabled={isSearching}
            style={{
              width: '100%',
              background: 'rgba(6,8,16,0.8)',
              border: '1px solid var(--border)',
              borderRadius: '10px',
              color: 'var(--text)',
              fontFamily: 'var(--font-display)',
              fontSize: '0.875rem',
              padding: '0.75rem 1rem',
              resize: 'vertical',
              outline: 'none',
              transition: 'border-color 0.2s, box-shadow 0.2s',
              lineHeight: '1.5',
            }}
            onFocus={(e) => { e.target.style.borderColor = 'var(--cyan)'; e.target.style.boxShadow = '0 0 0 3px rgba(0,200,255,0.1)'; }}
            onBlur={(e)  => { e.target.style.borderColor = 'var(--border)'; e.target.style.boxShadow = 'none'; }}
          />
        </div>
        <button
          type="submit"
          disabled={isSearching || !query.trim()}
          style={{
            display: 'flex', alignItems: 'center', gap: '0.5rem',
            padding: '0.6rem 1.25rem',
            fontFamily: 'var(--font-display)',
            fontWeight: 600,
            fontSize: '0.85rem',
            borderRadius: '8px',
            cursor: isSearching || !query.trim() ? 'not-allowed' : 'pointer',
            opacity: isSearching || !query.trim() ? 0.55 : 1,
            background: 'linear-gradient(135deg, rgba(0,200,255,0.15), rgba(0,200,255,0.08))',
            border: '1px solid rgba(0,200,255,0.3)',
            color: 'var(--cyan)',
            transition: 'all 0.2s',
          }}
          onMouseEnter={(e) => { if (!isSearching && query.trim()) e.currentTarget.style.background = 'rgba(0,200,255,0.2)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = 'linear-gradient(135deg, rgba(0,200,255,0.15), rgba(0,200,255,0.08))'; }}
        >
          {isSearching ? (
            <>
              <svg style={{ animation: 'spin-slow 0.8s linear infinite' }} width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="7" cy="7" r="5.5" stroke="rgba(0,200,255,0.3)" strokeWidth="2" />
                <path d="M7 1.5A5.5 5.5 0 0112.5 7" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              Searching…
            </>
          ) : (
            <>
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.3" />
                <path d="M10 10l3 3" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
              Search
            </>
          )}
        </button>
      </form>

      {error && (
        <div style={{
          marginTop: '1rem',
          padding: '0.65rem 0.85rem',
          background: 'rgba(255,51,102,0.08)',
          border: '1px solid rgba(255,51,102,0.2)',
          borderRadius: '8px',
          fontFamily: 'var(--font-display)',
          fontSize: '0.82rem',
          color: 'var(--danger)',
        }}>
          {error}
        </div>
      )}

      {result && (
        <div className="animate-fade-up" style={{ marginTop: '1.25rem' }}>
          {/* Answer */}
          <div style={{ marginBottom: '1rem' }}>
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--success)',
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              marginBottom: '0.5rem',
              fontWeight: 600,
            }}>
              Answer
            </p>
            <div style={{
              padding: '1rem',
              background: 'rgba(0,229,160,0.05)',
              border: '1px solid rgba(0,229,160,0.2)',
              borderLeft: '3px solid var(--success)',
              borderRadius: '0 10px 10px 0',
              fontFamily: 'var(--font-display)',
              fontSize: '0.875rem',
              color: 'var(--text)',
              lineHeight: '1.7',
              whiteSpace: 'pre-wrap',
            }}>
              {result.answer}
            </div>
          </div>

          {/* Sources */}
          {result.sources?.length > 0 && (
            <div>
              <p style={{
                fontFamily: 'var(--font-mono)',
                fontSize: '0.6rem',
                color: 'var(--muted)',
                letterSpacing: '0.1em',
                textTransform: 'uppercase',
                marginBottom: '0.5rem',
                fontWeight: 600,
              }}>
                Sources ({result.sources.length})
              </p>
              {result.sources.map((src, idx) => (
                <div key={idx} style={{ marginBottom: '0.4rem', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--border)' }}>
                  <button
                    onClick={() => setOpenSource(openSource === idx ? null : idx)}
                    style={{
                      width: '100%',
                      display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                      padding: '0.6rem 0.85rem',
                      background: 'rgba(13,20,37,0.8)',
                      border: 'none',
                      cursor: 'pointer',
                      color: 'var(--text)',
                      fontFamily: 'var(--font-display)',
                      fontSize: '0.8rem',
                      transition: 'background 0.15s',
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(28,42,74,0.6)'; }}
                    onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(13,20,37,0.8)'; }}
                  >
                    <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                      <span style={{
                        fontFamily: 'var(--font-mono)',
                        fontSize: '0.62rem',
                        color: 'var(--accent)',
                        padding: '1px 5px',
                        background: 'rgba(255,107,43,0.1)',
                        borderRadius: '3px',
                      }}>
                        {idx + 1}
                      </span>
                      {src.doc_name || src.document_name || 'Document'}
                      {src.page_number != null && (
                        <span style={{ color: 'var(--muted)', fontSize: '0.7rem' }}>· p.{src.page_number}</span>
                      )}
                    </span>
                    <svg
                      width="12" height="12" viewBox="0 0 12 12" fill="none"
                      style={{ transform: openSource === idx ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s', color: 'var(--muted)' }}
                    >
                      <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  {openSource === idx && (
                    <div style={{
                      padding: '0.75rem 0.85rem',
                      background: 'rgba(6,8,16,0.8)',
                      fontFamily: 'var(--font-mono)',
                      fontSize: '0.73rem',
                      color: 'var(--muted)',
                      lineHeight: '1.6',
                      borderTop: '1px solid var(--border)',
                      whiteSpace: 'pre-wrap',
                    }}>
                      {src.chunk_preview || src.text || ''}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Documents Page ──────────────────────────────────────────
export default function Documents() {
  const [documents,       setDocuments]       = useState([]);
  const [selectedDocIds,  setSelectedDocIds]  = useState([]);

  // Load existing documents on mount
  useEffect(() => {
    documentsApi.list().then(({ data }) => {
      setDocuments(data.documents || []);
    }).catch(() => {});
  }, []);

  const handleUploaded = (doc) => {
    // Use status from server response (not hardcoded)
    setDocuments((prev) => [doc, ...prev]);
  };

  const toggleSelect = (docId) =>
    setSelectedDocIds((prev) => prev.includes(docId) ? prev.filter((d) => d !== docId) : [...prev, docId]);

  return (
    <div className="mesh-bg" style={{ minHeight: '100vh', padding: '1.75rem' }}>
      <div style={{ maxWidth: '860px', margin: '0 auto' }}>
        {/* Header */}
        <div style={{ marginBottom: '1.75rem' }}>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: '1.6rem',
            color: 'var(--text)',
            letterSpacing: '-0.02em',
            marginBottom: '0.2rem',
          }}>
            Documents
          </h1>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--muted)' }}>
            Upload documents and search with AI-powered retrieval
          </p>
        </div>

        <UploadZone onUploaded={handleUploaded} />

        {documents.length > 0 && (
          <div style={{ marginBottom: '0.5rem' }}>
            <p style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: 'var(--muted)',
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              marginBottom: '0.75rem',
              fontWeight: 600,
            }}>
              Library · {documents.length} document{documents.length > 1 ? 's' : ''}
            </p>
            {documents.map((doc) => (
              <DocumentRow
                key={doc.doc_id}
                doc={doc}
                isSelected={selectedDocIds.includes(doc.doc_id)}
                onToggleSelect={toggleSelect}
              />
            ))}
          </div>
        )}

        {documents.length === 0 && (
          <div style={{
            textAlign: 'center',
            padding: '2rem 1rem',
            fontFamily: 'var(--font-display)',
            color: 'var(--muted)',
            fontSize: '0.82rem',
          }}>
            No documents uploaded yet.
          </div>
        )}

        <RagQueryPanel documents={documents} />
      </div>
    </div>
  );
}
