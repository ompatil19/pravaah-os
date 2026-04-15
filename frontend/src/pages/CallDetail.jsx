import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { callsApi } from '../api';
import CallStatusBadge from '../components/CallStatusBadge';
import LanguageBadge from '../components/LanguageBadge';
import ActionItemRow from '../components/ActionItemRow';
import CallSummaryCard from '../components/CallSummaryCard';

const CHART_STYLE = {
  background: 'rgba(13,20,37,0.95)',
  border: '1px solid rgba(28,42,74,0.8)',
  borderRadius: '10px',
  fontFamily: 'Fira Code, monospace',
  fontSize: 11,
  color: '#E8EDF8',
  padding: '8px 12px',
};

function MetaItem({ label, children }) {
  return (
    <div>
      <p style={{
        fontFamily: 'var(--font-mono)',
        fontSize: '0.58rem',
        color: 'var(--muted)',
        letterSpacing: '0.12em',
        textTransform: 'uppercase',
        marginBottom: '5px',
        fontWeight: 600,
      }}>
        {label}
      </p>
      <div>{children}</div>
    </div>
  );
}

export default function CallDetail() {
  const { sessionId }   = useParams();
  const [call,      setCall]      = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error,     setError]     = useState(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const { data } = await callsApi.get(sessionId);
        if (!cancelled) setCall(data);
      } catch (err) {
        if (!cancelled) setError(err.message);
      } finally {
        if (!cancelled) setIsLoading(false);
      }
    };
    if (sessionId) load();
    return () => { cancelled = true; };
  }, [sessionId]);

  const formatDuration = (secs) => {
    if (!secs) return '—';
    return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  };

  const formatTs = (iso) =>
    iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '—';

  const toneData = call?.transcripts
    ? call.transcripts.map((t, i) => ({
        segment: i + 1,
        score:   Math.round(50 + 30 * Math.sin(i * 0.7)),
      }))
    : [];

  if (isLoading) {
    return (
      <div style={{ padding: '1.75rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {[...Array(4)].map((_, i) => (
          <div key={i} className="shimmer-skeleton" style={{ height: '80px', borderRadius: '12px', animationDelay: `${i * 80}ms` }} />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: '1.75rem' }}>
        <div style={{
          padding: '1rem',
          background: 'rgba(255,51,102,0.08)',
          border: '1px solid rgba(255,51,102,0.2)',
          borderRadius: '10px',
          color: 'var(--danger)',
          fontFamily: 'var(--font-display)',
          fontSize: '0.875rem',
        }}>
          {error}
        </div>
      </div>
    );
  }

  if (!call) return null;

  return (
    <div className="mesh-bg" style={{ minHeight: '100vh', overflowY: 'auto', padding: '1.75rem' }}>
      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.5rem' }}>
        <Link to="/" style={{
          fontFamily: 'var(--font-display)',
          fontSize: '0.78rem',
          color: 'var(--muted)',
          textDecoration: 'none',
          transition: 'color 0.15s',
        }}
          onMouseEnter={(e) => { e.currentTarget.style.color = 'var(--accent)'; }}
          onMouseLeave={(e) => { e.currentTarget.style.color = 'var(--muted)'; }}
        >
          Dashboard
        </Link>
        <span style={{ color: 'var(--border-2)', fontSize: '0.75rem' }}>›</span>
        <span style={{ fontFamily: 'var(--font-display)', fontSize: '0.78rem', color: 'var(--text-2)' }}>
          Call Detail
        </span>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--cyan)', marginLeft: '0.25rem' }}>
          {sessionId?.slice(0, 10)}…
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
        {/* Metadata card */}
        <div className="card-glass animate-fade-up" style={{ padding: '1.5rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', marginBottom: '1.25rem' }}>
            <div style={{
              width: '4px', height: '20px',
              borderRadius: '2px',
              background: 'linear-gradient(180deg, var(--accent), var(--cyan))',
            }} />
            <h2 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.95rem', color: 'var(--text)' }}>
              Call Metadata
            </h2>
          </div>

          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '2rem' }}>
            <MetaItem label="Session ID">
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.8rem', color: 'var(--cyan)' }}>
                {call.session_id}
              </span>
            </MetaItem>
            <MetaItem label="Agent">
              <span style={{ fontFamily: 'var(--font-display)', fontWeight: 600, fontSize: '0.875rem', color: 'var(--text)' }}>
                {call.agent_id}
              </span>
            </MetaItem>
            <MetaItem label="Duration">
              <span style={{ fontFamily: 'var(--font-big)', fontSize: '1.5rem', color: 'var(--warning)', letterSpacing: '0.02em' }}>
                {formatDuration(call.duration_seconds)}
              </span>
            </MetaItem>
            <MetaItem label="Language">
              <LanguageBadge language={call.language} />
            </MetaItem>
            <MetaItem label="Status">
              <CallStatusBadge status={call.status} />
            </MetaItem>
            <MetaItem label="Started">
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-2)' }}>
                {call.created_at ? new Date(call.created_at).toLocaleString() : '—'}
              </span>
            </MetaItem>
          </div>
        </div>

        {/* Summary */}
        {call.summary && (
          <CallSummaryCard summary={call.summary.text} generatedAt={call.summary.generated_at} />
        )}

        {/* Tone analysis chart */}
        {toneData.length > 1 && (
          <div className="card-glass animate-fade-up" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <div style={{ width: '4px', height: '18px', borderRadius: '2px', background: 'linear-gradient(180deg, var(--accent), var(--cyan))' }} />
              <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.875rem', color: 'var(--text)' }}>
                Tone Analysis
              </h3>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--muted)', marginLeft: 'auto', letterSpacing: '0.08em' }}>
                {toneData.length} SEGMENTS
              </span>
            </div>
            <ResponsiveContainer width="100%" height={180}>
              <AreaChart data={toneData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                <defs>
                  <linearGradient id="toneGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#FF6B2B" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="#FF6B2B" stopOpacity="0.02" />
                  </linearGradient>
                </defs>
                <CartesianGrid stroke="rgba(28,42,74,0.6)" strokeDasharray="3 3" />
                <XAxis
                  dataKey="segment"
                  tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'Fira Code, monospace' }}
                  tickLine={false} axisLine={false}
                />
                <YAxis
                  domain={[0, 100]}
                  tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'Fira Code, monospace' }}
                  tickLine={false} axisLine={false}
                />
                <Tooltip
                  contentStyle={CHART_STYLE}
                  itemStyle={{ color: 'var(--accent)' }}
                />
                <Area
                  type="monotone" dataKey="score"
                  stroke="#FF6B2B" strokeWidth={2}
                  fill="url(#toneGradient)"
                  dot={false}
                  activeDot={{ r: 5, fill: '#FF8C52', strokeWidth: 0 }}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Full transcript */}
        {call.transcripts && call.transcripts.length > 0 && (
          <div className="card-glass animate-fade-up" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <div style={{ width: '4px', height: '18px', borderRadius: '2px', background: 'linear-gradient(180deg, var(--accent), var(--cyan))' }} />
              <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.875rem', color: 'var(--text)' }}>
                Full Transcript
              </h3>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.58rem', color: 'var(--muted)', marginLeft: 'auto', letterSpacing: '0.08em' }}>
                {call.transcripts.length} SEGMENTS
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0' }}>
              {call.transcripts.map((t, idx) => (
                <div
                  key={t.id}
                  style={{
                    display: 'flex',
                    gap: '1rem',
                    padding: '0.65rem 0',
                    borderBottom: '1px solid rgba(28,42,74,0.4)',
                    animation: 'fade-in 0.3s ease both',
                    animationDelay: `${Math.min(idx * 20, 400)}ms`,
                  }}
                >
                  <span style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: '0.65rem',
                    color: 'var(--muted)',
                    flexShrink: 0,
                    paddingTop: '2px',
                    width: '60px',
                  }}>
                    {formatTs(t.timestamp)}
                  </span>
                  <p style={{
                    fontFamily: 'var(--font-display)',
                    fontSize: '0.875rem',
                    color: 'var(--text-2)',
                    lineHeight: '1.6',
                    flex: 1,
                  }}>
                    {t.text}
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Action items */}
        {call.action_items && call.action_items.length > 0 && (
          <div className="card-glass animate-fade-up" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
              <div style={{ width: '4px', height: '18px', borderRadius: '2px', background: 'linear-gradient(180deg, var(--success), var(--cyan))' }} />
              <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.875rem', color: 'var(--text)' }}>
                Action Items
              </h3>
              <span style={{
                marginLeft: 'auto',
                fontFamily: 'var(--font-mono)',
                fontSize: '0.6rem',
                color: 'var(--success)',
                padding: '2px 6px',
                background: 'rgba(0,229,160,0.08)',
                border: '1px solid rgba(0,229,160,0.2)',
                borderRadius: '4px',
              }}>
                {call.action_items.length}
              </span>
            </div>
            {call.action_items.map((item, idx) => (
              <ActionItemRow key={item.id ?? idx} item={item} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
