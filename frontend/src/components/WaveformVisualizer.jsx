import { useEffect, useRef } from 'react';

export default function WaveformVisualizer({ analyserNode, isActive, className = '' }) {
  const canvasRef = useRef(null);
  const rafRef    = useRef(null);
  const timeRef   = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const draw = (timestamp) => {
      rafRef.current = requestAnimationFrame(draw);
      timeRef.current = timestamp;

      const W = canvas.width;
      const H = canvas.height;

      // Clear
      ctx.clearRect(0, 0, W, H);

      // Background
      ctx.fillStyle = '#0D1425';
      ctx.fillRect(0, 0, W, H);

      // Grid lines (subtle)
      ctx.strokeStyle = 'rgba(28,42,74,0.5)';
      ctx.lineWidth = 0.5;
      for (let i = 1; i < 4; i++) {
        const y = (H / 4) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
      }
      for (let i = 1; i < 10; i++) {
        const x = (W / 10) * i;
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H);
        ctx.stroke();
      }

      if (!isActive || !analyserNode) {
        // Idle state — gentle sine wave
        const t = timestamp / 1000;
        ctx.beginPath();
        ctx.strokeStyle = 'rgba(90,100,128,0.4)';
        ctx.lineWidth = 1.5;
        for (let x = 0; x <= W; x++) {
          const y = H / 2 + Math.sin((x / W) * Math.PI * 4 + t) * 4;
          if (x === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Center label
        ctx.fillStyle = 'rgba(90,100,128,0.4)';
        ctx.font = '500 11px "Fira Code", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('STANDBY — CLICK START TO RECORD', W / 2, H / 2 - 16);
        return;
      }

      const bufferLength = analyserNode.fftSize;
      const dataArray    = new Uint8Array(bufferLength);
      analyserNode.getByteTimeDomainData(dataArray);

      // ── Main waveform fill ──
      // Create gradient fill
      const gradient = ctx.createLinearGradient(0, 0, 0, H);
      gradient.addColorStop(0, 'rgba(255,107,43,0)');
      gradient.addColorStop(0.4, 'rgba(255,107,43,0.35)');
      gradient.addColorStop(0.5, 'rgba(255,140,82,0.6)');
      gradient.addColorStop(0.6, 'rgba(255,107,43,0.35)');
      gradient.addColorStop(1, 'rgba(255,107,43,0)');

      const sliceWidth = W / bufferLength;
      let x = 0;

      // Filled waveform path
      ctx.beginPath();
      ctx.moveTo(0, H / 2);
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * H) / 2;
        if (i === 0) ctx.moveTo(0, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }
      ctx.lineTo(W, H / 2);
      ctx.closePath();
      ctx.fillStyle = gradient;
      ctx.fill();

      // ── Glow line on top ──
      ctx.beginPath();
      ctx.shadowBlur  = 20;
      ctx.shadowColor = '#FF6B2B';
      ctx.strokeStyle = '#FF8C52';
      ctx.lineWidth   = 2;
      x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = (v * H) / 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }
      ctx.stroke();
      ctx.shadowBlur = 0;

      // ── Reflection (mirror below center) ──
      ctx.save();
      ctx.globalAlpha = 0.15;
      ctx.scale(1, -1);
      ctx.translate(0, -H);
      ctx.beginPath();
      x = 0;
      for (let i = 0; i < bufferLength; i++) {
        const v = dataArray[i] / 128.0;
        const y = H - (v * H) / 2;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
        x += sliceWidth;
      }
      ctx.strokeStyle = '#FF6B2B';
      ctx.lineWidth = 1;
      ctx.stroke();
      ctx.restore();

      // ── Scan line effect ──
      const scanPos = ((timestamp % 3000) / 3000) * W;
      const scanGrad = ctx.createLinearGradient(scanPos - 40, 0, scanPos + 40, 0);
      scanGrad.addColorStop(0, 'rgba(0,200,255,0)');
      scanGrad.addColorStop(0.5, 'rgba(0,200,255,0.12)');
      scanGrad.addColorStop(1, 'rgba(0,200,255,0)');
      ctx.fillStyle = scanGrad;
      ctx.fillRect(scanPos - 40, 0, 80, H);

      // ── Recording indicator ──
      const blink = Math.sin(timestamp / 300) > 0;
      if (blink) {
        ctx.beginPath();
        ctx.arc(W - 20, 20, 5, 0, Math.PI * 2);
        ctx.fillStyle = 'var(--danger)';
        ctx.shadowBlur = 10;
        ctx.shadowColor = '#FF3366';
        ctx.fill();
        ctx.shadowBlur = 0;
      }
    };

    draw(0);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [analyserNode, isActive]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ro = new ResizeObserver(() => {
      canvas.width  = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    });
    ro.observe(canvas);
    canvas.width  = canvas.offsetWidth;
    canvas.height = canvas.offsetHeight;
    return () => ro.disconnect();
  }, []);

  return (
    <div style={{ position: 'relative', borderRadius: '12px', overflow: 'hidden' }}>
      <canvas
        ref={canvasRef}
        className={`w-full ${className}`}
        style={{
          borderRadius: '12px',
          height: '110px',
          display: 'block',
          border: '1px solid var(--border)',
          boxShadow: isActive ? '0 0 30px rgba(255,107,43,0.15), inset 0 0 20px rgba(255,107,43,0.05)' : 'none',
          transition: 'box-shadow 0.5s ease',
        }}
      />
      {/* Corner labels */}
      <div style={{
        position: 'absolute',
        top: '8px', left: '12px',
        fontFamily: 'var(--font-mono)',
        fontSize: '0.55rem',
        color: isActive ? 'var(--accent)' : 'var(--muted)',
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        opacity: 0.7,
        transition: 'color 0.3s',
        pointerEvents: 'none',
      }}>
        {isActive ? '● REC' : '○ IDLE'}
      </div>
    </div>
  );
}
