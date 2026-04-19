import { useState, useCallback, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { callsApi } from '../api';
import useAudioCapture from '../hooks/useAudioCapture';
import useCallSocket from '../hooks/useCallSocket';
import WaveformVisualizer from '../components/WaveformVisualizer';
import TranscriptDisplay from '../components/TranscriptDisplay';
import LiveSummaryPanel from '../components/LiveSummaryPanel';
import ActionItemsList from '../components/ActionItemsList';
import DocumentUploader from '../components/DocumentUploader';
import socket from '../socket';

export default function ActiveCall() {
  const { sessionId } = useParams();
  const navigate      = useNavigate();

  const [isEnding,  setIsEnding]  = useState(false);
  const [endError,  setEndError]  = useState(null);

  // Track current TTS audio so we can stop it on interruption
  const currentAudioRef = useRef(null);

  const stopCurrentTts = useCallback(() => {
    if (currentAudioRef.current) {
      currentAudioRef.current.pause();
      currentAudioRef.current.src = '';
      currentAudioRef.current = null;
    }
  }, []);

  const {
    transcripts, aiReplies, summary, actionItems,
    isConnected, error: socketError, sendAudioChunk, disconnectSocket,
  } = useCallSocket(sessionId);

  const onData = useCallback((blob) => sendAudioChunk(blob), [sendAudioChunk]);
  const { start, stop, isRecording, analyserNode, error: micError } = useAudioCapture(onData);

  // Stop TTS when user starts speaking
  useEffect(() => {
    if (isRecording) stopCurrentTts();
  }, [isRecording, stopCurrentTts]);

  // TTS audio playback — stop any previous audio before playing new
  useEffect(() => {
    const handleTts = ({ session_id, audio }) => {
      if (session_id !== sessionId) return;
      stopCurrentTts();
      const bytes = Uint8Array.from(atob(audio), (c) => c.charCodeAt(0));
      const blob  = new Blob([bytes], { type: 'audio/mpeg' });
      const url   = URL.createObjectURL(blob);
      const el    = new Audio(url);
      currentAudioRef.current = el;
      el.play().catch(() => {});
      el.onended = () => {
        URL.revokeObjectURL(url);
        if (currentAudioRef.current === el) currentAudioRef.current = null;
      };
    };
    socket.on('tts_audio', handleTts);
    return () => socket.off('tts_audio', handleTts);
  }, [sessionId, stopCurrentTts]);

  const handleEndCall = async () => {
    stop();
    setIsEnding(true);
    setEndError(null);
    try {
      await callsApi.end(sessionId, {});
      disconnectSocket();
      navigate(`/call/${sessionId}/detail`);
    } catch (err) {
      setEndError(err.message);
      setIsEnding(false);
    }
  };

  const handleEscalate = async () => {
    stop();
    try { await callsApi.end(sessionId, { escalated: true }); } catch (_) {}
    disconnectSocket();
    navigate(`/call/${sessionId}/detail`);
  };

  const isDisconnected = !isConnected;
  const anyError = micError || socketError || endError;

  return (
    <div style={{
      flex: 1,
      display: 'flex',
      flexDirection: 'column',
      minHeight: '100vh',
      background: 'var(--bg)',
      position: 'relative',
    }}>
      {/* Reconnecting banner */}
      {isDisconnected && (
        <div className="reconnecting-banner">
          ⚡ RECONNECTING TO SERVER…
        </div>
      )}

      {/* Top bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '1rem 1.5rem',
        borderBottom: '1px solid var(--border)',
        background: 'rgba(10,15,30,0.8)',
        backdropFilter: 'blur(12px)',
        position: 'sticky',
        top: 0,
        zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Live indicator */}
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ position: 'relative', display: 'inline-flex' }}>
              <span style={{
                width: '10px', height: '10px',
                borderRadius: '50%',
                background: isRecording ? 'var(--danger)' : 'var(--muted)',
                display: 'inline-block',
                transition: 'background 0.3s',
              }} />
              {isRecording && (
                <span style={{
                  position: 'absolute',
                  inset: 0,
                  borderRadius: '50%',
                  background: 'var(--danger)',
                  animation: 'pulse-ring 1.5s ease-out infinite',
                }} />
              )}
            </span>
            <span style={{
              fontFamily: 'var(--font-display)',
              fontWeight: 600,
              fontSize: '0.85rem',
              color: isRecording ? 'var(--text)' : 'var(--muted)',
              transition: 'color 0.3s',
            }}>
              {isRecording ? 'Recording' : 'Standby'}
            </span>
          </div>

          <div style={{ height: '18px', width: '1px', background: 'var(--border)' }} />

          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.7rem',
            color: 'var(--cyan)',
            letterSpacing: '0.08em',
          }}>
            {sessionId?.slice(0, 12)}…
          </span>

          {/* Transcript count */}
          <span style={{
            fontFamily: 'var(--font-mono)',
            fontSize: '0.65rem',
            color: 'var(--muted)',
            padding: '2px 8px',
            background: 'rgba(28,42,74,0.5)',
            borderRadius: '4px',
            border: '1px solid var(--border)',
          }}>
            {transcripts.length} segments
          </span>
        </div>

        {/* Record controls */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          {!isRecording ? (
            <button onClick={start} className="btn-accent" style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.5rem 1rem', fontSize: '0.82rem',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="5" stroke="white" strokeWidth="1.2" />
                <circle cx="6" cy="6" r="2.5" fill="white" />
              </svg>
              Start Recording
            </button>
          ) : (
            <button onClick={stop} style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.5rem 1rem', fontSize: '0.82rem',
              fontFamily: 'var(--font-display)', fontWeight: 600,
              background: 'rgba(255,184,0,0.1)',
              border: '1px solid rgba(255,184,0,0.3)',
              color: 'var(--warning)',
              borderRadius: '8px', cursor: 'pointer',
              transition: 'all 0.2s',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <rect x="2" y="2" width="3" height="8" rx="1" fill="currentColor" />
                <rect x="7" y="2" width="3" height="8" rx="1" fill="currentColor" />
              </svg>
              Pause
            </button>
          )}
        </div>
      </div>

      {/* Waveform */}
      <div style={{ padding: '1rem 1.5rem 0.75rem' }}>
        <WaveformVisualizer analyserNode={analyserNode} isActive={isRecording} />
      </div>

      {/* Main panels */}
      <div style={{
        flex: 1,
        display: 'flex',
        gap: '1rem',
        padding: '0 1.5rem 1rem',
        minHeight: 0,
        overflow: 'hidden',
      }}>
        {/* Left: Transcript */}
        <div className="card-glass" style={{
          flex: '0 0 58%',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
        }}>
          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.6rem',
            padding: '0.85rem 1rem',
            borderBottom: '1px solid var(--border)',
          }}>
            <div style={{
              width: '24px', height: '24px',
              borderRadius: '6px',
              background: 'rgba(255,107,43,0.15)',
              border: '1px solid rgba(255,107,43,0.2)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M1 2.5h10M1 5h10M1 7.5h7" stroke="var(--accent)" strokeWidth="1.2" strokeLinecap="round" />
              </svg>
            </div>
            <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)' }}>
              Live Transcript
            </span>
            <span style={{
              marginLeft: 'auto',
              fontFamily: 'var(--font-mono)',
              fontSize: '0.6rem',
              color: isRecording ? 'var(--danger)' : 'var(--muted)',
              letterSpacing: '0.08em',
            }}>
              {isRecording ? '● LIVE' : '○ STANDBY'}
            </span>
          </div>
          <div style={{ flex: 1, overflowY: 'auto', padding: '0.75rem' }}>
            <TranscriptDisplay transcripts={transcripts} />
          </div>
        </div>

        {/* Right: Panels */}
        <div style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          overflowY: 'auto',
          minWidth: 0,
        }}>
          {/* AI Replies panel */}
          <div className="card-glass" style={{ flexShrink: 0 }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.6rem',
              padding: '0.75rem 1rem',
              borderBottom: '1px solid var(--border)',
            }}>
              <div style={{
                width: '24px', height: '24px', borderRadius: '6px',
                background: 'rgba(0,200,255,0.12)',
                border: '1px solid rgba(0,200,255,0.2)',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
              }}>
                <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                  <path d="M6 1a5 5 0 100 10A5 5 0 006 1z" stroke="var(--cyan)" strokeWidth="1.2"/>
                  <path d="M4 5h4M4 7h2.5" stroke="var(--cyan)" strokeWidth="1.1" strokeLinecap="round"/>
                </svg>
              </div>
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.82rem', color: 'var(--text)' }}>
                AI Replies
              </span>
              <span style={{
                marginLeft: 'auto',
                fontFamily: 'var(--font-mono)', fontSize: '0.6rem',
                color: 'var(--cyan)', letterSpacing: '0.08em',
              }}>
                {aiReplies.length} msg{aiReplies.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div style={{ padding: '0.75rem', maxHeight: '180px', overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {aiReplies.length === 0 ? (
                <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.78rem', color: 'var(--muted)', textAlign: 'center', padding: '0.5rem 0' }}>
                  AI replies appear here after you speak.
                </p>
              ) : (
                aiReplies.map((r) => (
                  <div key={r.id} style={{
                    padding: '0.5rem 0.75rem',
                    background: 'rgba(0,200,255,0.06)',
                    border: '1px solid rgba(0,200,255,0.15)',
                    borderRadius: '8px',
                  }}>
                    <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--text)', lineHeight: 1.5 }}>
                      {r.text}
                    </p>
                    <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--muted)', marginTop: '4px' }}>
                      {new Date(r.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                    </p>
                  </div>
                ))
              )}
            </div>
          </div>

          <LiveSummaryPanel summary={summary} />
          <ActionItemsList items={actionItems} />
          <DocumentUploader sessionId={sessionId} />
        </div>
      </div>

      {/* Bottom action bar */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '0.85rem 1.5rem',
        borderTop: '1px solid var(--border)',
        background: 'rgba(10,15,30,0.9)',
        backdropFilter: 'blur(12px)',
      }}>
        <div>
          {anyError && (
            <div style={{
              display: 'flex', alignItems: 'center', gap: '0.4rem',
              fontFamily: 'var(--font-display)',
              fontSize: '0.78rem',
              color: 'var(--danger)',
            }}>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <circle cx="6" cy="6" r="5" stroke="currentColor" strokeWidth="1.2" />
                <path d="M6 4v2.5M6 8v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
              </svg>
              {anyError}
            </div>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <button
            onClick={handleEscalate}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.55rem 1.1rem',
              fontFamily: 'var(--font-display)',
              fontWeight: 600,
              fontSize: '0.85rem',
              background: 'rgba(255,184,0,0.08)',
              border: '1px solid rgba(255,184,0,0.3)',
              color: 'var(--warning)',
              borderRadius: '8px', cursor: 'pointer',
              transition: 'all 0.2s',
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = 'rgba(255,184,0,0.15)'; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = 'rgba(255,184,0,0.08)'; }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M7 2L12.5 12H1.5L7 2z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
              <path d="M7 6v2.5M7 10v.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
            </svg>
            Escalate
          </button>

          <button
            onClick={handleEndCall}
            disabled={isEnding}
            className="btn-danger"
            style={{
              display: 'flex', alignItems: 'center', gap: '0.5rem',
              padding: '0.55rem 1.25rem',
              fontSize: '0.85rem',
              opacity: isEnding ? 0.7 : 1,
            }}
          >
            {isEnding ? (
              <>
                <svg style={{ animation: 'spin-slow 0.8s linear infinite' }} width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <circle cx="6.5" cy="6.5" r="5" stroke="rgba(255,255,255,0.3)" strokeWidth="2" />
                  <path d="M6.5 1.5A5 5 0 0111.5 6.5" stroke="white" strokeWidth="2" strokeLinecap="round" />
                </svg>
                Ending…
              </>
            ) : (
              <>
                <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
                  <path d="M2.5 2.5l8 8M10.5 2.5l-8 8" stroke="white" strokeWidth="1.5" strokeLinecap="round" />
                </svg>
                End Call
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
