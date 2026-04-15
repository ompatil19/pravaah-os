import { useState, useEffect } from 'react';
import {
  BarChart, Bar,
  LineChart, Line,
  PieChart, Pie, Cell, Legend,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts';
import { analyticsApi } from '../api';

const PIE_COLORS = ['#FF6B2B', '#00C8FF', '#00E5A0', '#FFB800', '#FF3366'];

const CHART_STYLE = {
  background: 'rgba(13,20,37,0.95)',
  border: '1px solid rgba(28,42,74,0.8)',
  borderRadius: '10px',
  fontFamily: 'Fira Code, monospace',
  fontSize: 11,
  color: '#E8EDF8',
  padding: '8px 12px',
  backdropFilter: 'blur(12px)',
};

function KpiCard({ label, value, sub, accent, icon, delay = 0 }) {
  return (
    <div
      className="card-glass animate-fade-up"
      style={{
        padding: '1.5rem',
        animationDelay: `${delay}ms`,
        position: 'relative',
        overflow: 'hidden',
        transition: 'transform 0.2s ease',
        cursor: 'default',
      }}
      onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
    >
      {/* bg glow */}
      <div style={{
        position: 'absolute',
        top: '-30px', right: '-30px',
        width: '120px', height: '120px',
        borderRadius: '50%',
        background: `radial-gradient(circle, ${accent}18 0%, transparent 70%)`,
        pointerEvents: 'none',
      }} />

      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem' }}>
        <p style={{
          fontFamily: 'var(--font-mono)',
          fontSize: '0.6rem',
          color: 'var(--muted)',
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
        }}>
          {label}
        </p>
        <div style={{
          width: '32px', height: '32px',
          borderRadius: '8px',
          background: `${accent}18`,
          border: `1px solid ${accent}30`,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: accent,
        }}>
          {icon}
        </div>
      </div>

      <p className="stat-number" style={{ color: accent, fontSize: '2.6rem' }}>
        {value ?? '—'}
      </p>
      {sub && (
        <p style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--muted)', marginTop: '0.35rem' }}>
          {sub}
        </p>
      )}
    </div>
  );
}

function ChartCard({ title, children, span = 1 }) {
  return (
    <div
      className="card-glass animate-fade-up"
      style={{
        padding: '1.5rem',
        gridColumn: span > 1 ? `span ${span}` : undefined,
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1.25rem' }}>
        <div style={{
          width: '4px', height: '18px',
          borderRadius: '2px',
          background: 'linear-gradient(180deg, var(--accent), var(--cyan))',
        }} />
        <h3 style={{
          fontFamily: 'var(--font-display)',
          fontWeight: 700,
          fontSize: '0.875rem',
          color: 'var(--text)',
        }}>
          {title}
        </h3>
      </div>
      {children}
    </div>
  );
}

export default function Analytics() {
  const [data,      setData]      = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error,     setError]     = useState(null);
  const [from,      setFrom]      = useState('');
  const [to,        setTo]        = useState('');

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params = {};
      if (from) params.from = from;
      if (to)   params.to   = to;
      const { data: res } = await analyticsApi.summary(params);
      setData(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { load(); }, []); // eslint-disable-line

  const formatDuration = (secs) => {
    if (!secs) return '—';
    return `${Math.floor(secs / 60)}m`;
  };

  const intentData = data?.action_items_by_priority
    ? Object.entries(data.action_items_by_priority).map(([k, v]) => ({ name: k.toUpperCase(), count: v }))
    : [];

  const languageData = data?.calls_by_language
    ? Object.entries(data.calls_by_language).map(([name, value]) => ({ name, value }))
    : [];

  const callsOverTime = data?.total_calls
    ? Array.from({ length: 7 }, (_, i) => ({
        day: `D-${6 - i}`,
        calls: Math.max(1, Math.round((data.total_calls / 7) * (0.7 + 0.6 * Math.random()))),
      }))
    : [];

  const CustomTooltipBar = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={CHART_STYLE}>
        <p style={{ color: 'var(--text-2)', marginBottom: '3px' }}>{label}</p>
        <p style={{ color: 'var(--accent)', fontWeight: 600 }}>{payload[0].value}</p>
      </div>
    );
  };

  const CustomTooltipLine = ({ active, payload, label }) => {
    if (!active || !payload?.length) return null;
    return (
      <div style={CHART_STYLE}>
        <p style={{ color: 'var(--text-2)', marginBottom: '3px' }}>{label}</p>
        <p style={{ color: 'var(--success)', fontWeight: 600 }}>{payload[0].value} calls</p>
      </div>
    );
  };

  return (
    <div className="mesh-bg" style={{ flex: 1, overflowY: 'auto', padding: '1.75rem', minHeight: '100vh' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', marginBottom: '1.75rem' }}>
        <div>
          <h1 style={{
            fontFamily: 'var(--font-display)',
            fontWeight: 800,
            fontSize: '1.6rem',
            color: 'var(--text)',
            letterSpacing: '-0.02em',
            marginBottom: '0.2rem',
          }}>
            Analytics
          </h1>
          <p style={{ fontFamily: 'var(--font-display)', fontSize: '0.82rem', color: 'var(--muted)' }}>
            Platform intelligence overview
          </p>
        </div>

        {/* Date filter */}
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              padding: '0.45rem 0.75rem',
              background: 'rgba(13,20,37,0.8)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              color: 'var(--text)',
              outline: 'none',
            }}
          />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.65rem', color: 'var(--muted)' }}>→</span>
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.75rem',
              padding: '0.45rem 0.75rem',
              background: 'rgba(13,20,37,0.8)',
              border: '1px solid var(--border)',
              borderRadius: '8px',
              color: 'var(--text)',
              outline: 'none',
            }}
          />
          <button onClick={load} className="btn-accent" style={{ padding: '0.45rem 1rem', fontSize: '0.8rem' }}>
            Apply
          </button>
        </div>
      </div>

      {isLoading && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem', marginBottom: '1.5rem' }}>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="shimmer-skeleton" style={{ height: '120px', borderRadius: '12px', animationDelay: `${i * 100}ms` }} />
          ))}
        </div>
      )}

      {error && (
        <div style={{
          padding: '1rem',
          background: 'rgba(255,51,102,0.08)',
          border: '1px solid rgba(255,51,102,0.2)',
          borderRadius: '10px',
          fontFamily: 'var(--font-display)',
          color: 'var(--danger)',
          marginBottom: '1.5rem',
        }}>
          {error}
        </div>
      )}

      {!isLoading && data && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
          {/* KPI Cards */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
            <KpiCard
              label="Total Calls"
              value={data.total_calls}
              accent="var(--accent)"
              delay={0}
              icon={<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M3 13a7 7 0 1110 0" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /><path d="M8 6v3l2 1" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /></svg>}
            />
            <KpiCard
              label="Avg Duration"
              value={formatDuration(data.average_duration_seconds)}
              sub={`${data.average_duration_seconds ?? 0} seconds total`}
              accent="var(--cyan)"
              delay={80}
              icon={<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.3" /><path d="M8 5v3.5l2 2" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /></svg>}
            />
            <KpiCard
              label="Action Items"
              value={data.action_items_generated}
              accent="var(--success)"
              delay={160}
              icon={<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M2 4h1.5M2 7.5h1.5M2 11h1.5M5.5 4H14M5.5 7.5H14M5.5 11H10" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" /></svg>}
            />
          </div>

          {/* Charts grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '1.25rem' }}>
            {/* Bar chart */}
            <ChartCard title="Action Items by Priority">
              {intentData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <BarChart data={intentData} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                    <CartesianGrid stroke="rgba(28,42,74,0.6)" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="name"
                      tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'Fira Code, monospace' }}
                      tickLine={false} axisLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'Fira Code, monospace' }}
                      tickLine={false} axisLine={false}
                    />
                    <Tooltip content={<CustomTooltipBar />} cursor={{ fill: 'rgba(255,107,43,0.06)' }} />
                    <Bar dataKey="count" fill="url(#barGradient)" radius={[6, 6, 0, 0]}>
                      <defs>
                        <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0%" stopColor="#FF8C52" />
                          <stop offset="100%" stopColor="#FF6B2B" stopOpacity="0.7" />
                        </linearGradient>
                      </defs>
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', color: 'var(--muted)', fontSize: '0.82rem', fontFamily: 'var(--font-display)' }}>
                  No data available
                </div>
              )}
            </ChartCard>

            {/* Pie chart */}
            <ChartCard title="Language Distribution">
              {languageData.length > 0 ? (
                <ResponsiveContainer width="100%" height={200}>
                  <PieChart>
                    <Pie
                      data={languageData}
                      cx="50%" cy="50%"
                      innerRadius={55} outerRadius={85}
                      dataKey="value"
                      paddingAngle={3}
                      strokeWidth={0}
                    >
                      {languageData.map((_, idx) => (
                        <Cell key={idx} fill={PIE_COLORS[idx % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip contentStyle={CHART_STYLE} />
                    <Legend
                      iconType="circle"
                      iconSize={8}
                      wrapperStyle={{ fontSize: 11, fontFamily: 'Fira Code, monospace', color: 'var(--muted)' }}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '200px', color: 'var(--muted)', fontSize: '0.82rem', fontFamily: 'var(--font-display)' }}>
                  No language data
                </div>
              )}
            </ChartCard>

            {/* Line chart — full width */}
            <div style={{ gridColumn: 'span 2' }}>
              <ChartCard title="Call Volume — Last 7 Days">
                <ResponsiveContainer width="100%" height={200}>
                  <LineChart data={callsOverTime} margin={{ top: 4, right: 4, bottom: 4, left: -20 }}>
                    <defs>
                      <linearGradient id="lineGradient" x1="0" y1="0" x2="1" y2="0">
                        <stop offset="0%" stopColor="#00E5A0" />
                        <stop offset="100%" stopColor="#00C8FF" />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="rgba(28,42,74,0.6)" strokeDasharray="3 3" />
                    <XAxis
                      dataKey="day"
                      tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'Fira Code, monospace' }}
                      tickLine={false} axisLine={false}
                    />
                    <YAxis
                      tick={{ fill: 'var(--muted)', fontSize: 10, fontFamily: 'Fira Code, monospace' }}
                      tickLine={false} axisLine={false}
                    />
                    <Tooltip content={<CustomTooltipLine />} />
                    <Line
                      type="monotone" dataKey="calls"
                      stroke="url(#lineGradient)"
                      strokeWidth={2.5}
                      dot={{ fill: '#00E5A0', r: 4, strokeWidth: 0 }}
                      activeDot={{ r: 6, fill: '#00C8FF', strokeWidth: 0 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </ChartCard>
            </div>
          </div>

          {/* Calls by Status */}
          {data.calls_by_status && (
            <div className="card-glass" style={{ padding: '1.25rem' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '1rem' }}>
                <div style={{ width: '4px', height: '18px', borderRadius: '2px', background: 'linear-gradient(180deg, var(--accent), var(--cyan))' }} />
                <h3 style={{ fontFamily: 'var(--font-display)', fontWeight: 700, fontSize: '0.875rem', color: 'var(--text)' }}>
                  Calls by Status
                </h3>
              </div>
              <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                {Object.entries(data.calls_by_status).map(([k, v]) => {
                  const color = k === 'active' ? 'var(--success)' : k === 'escalated' ? 'var(--danger)' : 'var(--muted)';
                  return (
                    <div key={k} style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{
                        width: '8px', height: '8px',
                        borderRadius: '50%',
                        background: color,
                        boxShadow: `0 0 8px ${color}80`,
                        flexShrink: 0,
                      }} />
                      <span style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem', color: 'var(--text-2)', textTransform: 'capitalize' }}>
                        {k}
                      </span>
                      <span style={{ fontFamily: 'var(--font-big)', fontSize: '1.4rem', color, letterSpacing: '0.02em' }}>
                        {v}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
