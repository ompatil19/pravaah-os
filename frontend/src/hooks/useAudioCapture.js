import { useState, useRef, useCallback } from 'react';

/**
 * useAudioCapture
 * Returns { start, stop, isRecording, analyserNode, error }
 * Calls onDataAvailable(blob) every 250 ms with an audio/webm;codecs=opus Blob.
 */
export default function useAudioCapture(onDataAvailable) {
  const [isRecording, setIsRecording]   = useState(false);
  const [analyserNode, setAnalyserNode] = useState(null);
  const [error, setError]               = useState(null);

  const mediaRecorderRef = useRef(null);
  const audioContextRef  = useRef(null);
  const streamRef        = useRef(null);

  const start = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;

      // ─── AudioContext + AnalyserNode ───
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      audioContextRef.current = audioCtx;
      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256;
      const source = audioCtx.createMediaStreamSource(stream);
      source.connect(analyser);
      setAnalyserNode(analyser);

      // ─── MediaRecorder ───
      const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/ogg;codecs=opus')
        ? 'audio/ogg;codecs=opus'
        : '';

      const recorder = new MediaRecorder(
        stream,
        mimeType ? { mimeType } : {}
      );

      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0 && onDataAvailable) {
          onDataAvailable(e.data);
        }
      };

      recorder.onerror = (e) => {
        setError(`MediaRecorder error: ${e.error?.message || 'unknown'}`);
      };

      recorder.start(250); // 250 ms time slices
      mediaRecorderRef.current = recorder;
      setIsRecording(true);
    } catch (err) {
      setError(`Microphone access denied: ${err.message}`);
    }
  }, [onDataAvailable]);

  const stop = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
    }
    if (audioContextRef.current) {
      audioContextRef.current.close();
    }
    mediaRecorderRef.current = null;
    audioContextRef.current  = null;
    streamRef.current        = null;
    setAnalyserNode(null);
    setIsRecording(false);
  }, []);

  return { start, stop, isRecording, analyserNode, error };
}
