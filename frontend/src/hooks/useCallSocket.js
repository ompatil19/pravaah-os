import { useState, useEffect, useRef, useCallback } from 'react';
import socket from '../socket';

/**
 * useCallSocket
 * Returns { transcripts, summary, actionItems, isConnected, error, sendAudioChunk }
 */
export default function useCallSocket(sessionId) {
  const [transcripts,  setTranscripts]  = useState([]);
  const [summary,      setSummary]      = useState(null);
  const [actionItems,  setActionItems]  = useState([]);
  const [isConnected,  setIsConnected]  = useState(false);
  const [error,        setError]        = useState(null);

  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;

  // ─── Connect / disconnect lifecycle ───
  useEffect(() => {
    if (!sessionId) return;

    socket.connect();

    const onConnect = () => {
      setIsConnected(true);
      setError(null);
      socket.emit('join_call', { session_id: sessionId });
    };

    const onDisconnect = () => setIsConnected(false);

    const onConnectError = (err) => {
      setError(`Connection error: ${err.message}`);
      setIsConnected(false);
    };

    const onTranscriptInterim = (data) => {
      if (data.session_id !== sessionIdRef.current) return;
      setTranscripts((prev) => {
        const next = [...prev];
        // Replace last interim or append
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && !next[lastIdx].isFinal) {
          next[lastIdx] = { ...next[lastIdx], text: data.text };
        } else {
          next.push({
            id: `interim-${Date.now()}`,
            text: data.text,
            isFinal: false,
            timestamp: data.timestamp || new Date().toISOString(),
            speaker: data.speaker || 'agent',
          });
        }
        return next;
      });
    };

    const onTranscriptFinal = (data) => {
      if (data.session_id !== sessionIdRef.current) return;
      setTranscripts((prev) => {
        const next = [...prev];
        const lastIdx = next.length - 1;
        if (lastIdx >= 0 && !next[lastIdx].isFinal) {
          // Confirm the interim as final
          next[lastIdx] = {
            ...next[lastIdx],
            text: data.text,
            isFinal: true,
            id: `final-${Date.now()}`,
          };
        } else {
          next.push({
            id: `final-${Date.now()}`,
            text: data.text,
            isFinal: true,
            timestamp: data.timestamp || new Date().toISOString(),
            speaker: data.speaker || 'agent',
          });
        }
        return next;
      });
    };

    const onCallSummary = (data) => {
      if (data.session_id !== sessionIdRef.current) return;
      setSummary(data.summary);
    };

    const onActionItems = (data) => {
      if (data.session_id !== sessionIdRef.current) return;
      setActionItems(data.items || []);
    };

    const onError = (data) => {
      if (data.session_id !== sessionIdRef.current) return;
      setError(`[${data.code}] ${data.message}`);
    };

    // Register listeners
    socket.on('connect',            onConnect);
    socket.on('disconnect',         onDisconnect);
    socket.on('connect_error',      onConnectError);
    socket.on('transcript_interim', onTranscriptInterim);
    socket.on('transcript_final',   onTranscriptFinal);
    socket.on('call_summary',       onCallSummary);
    socket.on('action_items',       onActionItems);
    socket.on('error',              onError);

    return () => {
      socket.emit('leave_call', { session_id: sessionId });
      socket.off('connect',            onConnect);
      socket.off('disconnect',         onDisconnect);
      socket.off('connect_error',      onConnectError);
      socket.off('transcript_interim', onTranscriptInterim);
      socket.off('transcript_final',   onTranscriptFinal);
      socket.off('call_summary',       onCallSummary);
      socket.off('action_items',       onActionItems);
      socket.off('error',              onError);
      socket.disconnect();
    };
  }, [sessionId]);

  // ─── Send audio chunk (Blob → base64) ───
  const sendAudioChunk = useCallback((blob) => {
    if (!sessionIdRef.current) return;
    const reader = new FileReader();
    reader.onloadend = () => {
      const base64 = reader.result.split(',')[1];
      socket.emit('audio_chunk', {
        session_id: sessionIdRef.current,
        data: base64,
      });
    };
    reader.readAsDataURL(blob);
  }, []);

  return { transcripts, summary, actionItems, isConnected, error, sendAudioChunk };
}
