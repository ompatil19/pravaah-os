/**
 * AudioRecorder
 * Minimal presenter component: shows recording state + controls.
 * Actual capture logic is in useAudioCapture hook.
 */
export default function AudioRecorder({ isRecording, onStart, onStop, error }) {
  return (
    <div className="flex flex-col items-center gap-2">
      {!isRecording ? (
        <button
          onClick={onStart}
          className="btn-accent flex items-center gap-2"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="5" r="3" stroke="currentColor" strokeWidth="1.5" />
            <path d="M2 9.5c0 2 2.24 3 5 3s5-1 5-3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          Start Recording
        </button>
      ) : (
        <button
          onClick={onStop}
          className="btn-danger flex items-center gap-2"
        >
          <span
            className="inline-block w-2 h-2 rounded-sm"
            style={{ background: '#fff' }}
          />
          Stop Recording
        </button>
      )}

      {error && (
        <p className="text-xs" style={{ color: 'var(--danger)' }}>
          {error}
        </p>
      )}
    </div>
  );
}
