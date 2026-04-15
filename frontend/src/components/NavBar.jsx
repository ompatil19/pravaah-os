import { NavLink } from 'react-router-dom';

const NAV_ITEMS = [
  {
    to: '/',
    label: 'Dashboard',
    end: true,
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <rect x="1" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
        <rect x="9" y="1" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
        <rect x="1" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
        <rect x="9" y="9" width="6" height="6" rx="1" stroke="currentColor" strokeWidth="1.4" />
      </svg>
    ),
  },
  {
    to: '/analytics',
    label: 'Analytics',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
        <path d="M2 13h12M4 10V7M7 10V4M10 10V6M13 10V2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
      </svg>
    ),
  },
];

export default function NavBar() {
  return (
    <aside
      className="flex flex-col gap-1 w-56 min-h-screen px-4 py-6"
      style={{
        background: 'var(--surface)',
        borderRight: '1px solid var(--border)',
      }}
    >
      {/* Logo */}
      <div className="flex items-center gap-2 mb-8 px-2">
        <span
          className="inline-flex items-center justify-center w-8 h-8 rounded-lg font-sora font-bold text-sm"
          style={{ background: 'var(--accent)', color: '#fff' }}
        >
          P
        </span>
        <span className="font-sora font-semibold text-base" style={{ color: 'var(--text)' }}>
          Pravaah OS
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map(({ to, label, end, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-sora font-medium transition-colors ${
                isActive
                  ? 'bg-accent text-white'
                  : 'hover:bg-[var(--border)]'
              }`
            }
            style={({ isActive }) => ({
              background: isActive ? 'var(--accent)' : undefined,
              color: isActive ? '#fff' : 'var(--muted)',
            })}
          >
            {icon}
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Bottom version */}
      <div className="mt-auto px-2">
        <p className="text-[10px] font-mono" style={{ color: 'var(--border)' }}>
          v1.0.0
        </p>
      </div>
    </aside>
  );
}
