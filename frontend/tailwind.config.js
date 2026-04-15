/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  theme: {
    extend: {
      colors: {
        bg:        'var(--bg)',
        'bg-2':    'var(--bg-2)',
        surface:   'var(--surface)',
        'surface-2': 'var(--surface-2)',
        border:    'var(--border)',
        'border-2': 'var(--border-2)',
        accent:    'var(--accent)',
        cyan:      'var(--cyan)',
        success:   'var(--success)',
        warning:   'var(--warning)',
        danger:    'var(--danger)',
        text:      'var(--text)',
        'text-2':  'var(--text-2)',
        muted:     'var(--muted)',
      },
      fontFamily: {
        display: ['Outfit', 'sans-serif'],
        mono:    ['Fira Code', 'monospace'],
        big:     ['Bebas Neue', 'sans-serif'],
        // keep old aliases for compatibility
        sora:    ['Outfit', 'sans-serif'],
      },
      animation: {
        'pulse-glow':     'pulse-glow 1.8s ease-in-out infinite',
        'slide-in-left':  'slide-in-left 0.35s cubic-bezier(0.16,1,0.3,1)',
        'slide-in-right': 'slide-in-right 0.35s cubic-bezier(0.16,1,0.3,1)',
        'fade-up':        'fade-up 0.45s cubic-bezier(0.16,1,0.3,1)',
        'fade-in':        'fade-in 0.3s ease',
        'blink':          'blink 1s step-end infinite',
        'shimmer':        'shimmer 1.8s infinite',
        'spin-slow':      'spin-slow 1s linear infinite',
        'float':          'float 4s ease-in-out infinite',
        'gradient-shift': 'gradient-shift 6s ease infinite',
      },
      keyframes: {
        'pulse-glow': {
          '0%, 100%': { boxShadow: '0 0 4px 0 var(--success)' },
          '50%':       { boxShadow: '0 0 18px 6px var(--success)' },
        },
        'pulse-ring': {
          '0%':   { transform: 'scale(1)', opacity: '0.8' },
          '100%': { transform: 'scale(2.4)', opacity: '0' },
        },
        'slide-in-left': {
          from: { transform: 'translateX(-20px)', opacity: '0' },
          to:   { transform: 'translateX(0)', opacity: '1' },
        },
        'slide-in-right': {
          from: { transform: 'translateX(20px)', opacity: '0' },
          to:   { transform: 'translateX(0)', opacity: '1' },
        },
        'fade-up': {
          from: { transform: 'translateY(16px)', opacity: '0' },
          to:   { transform: 'translateY(0)', opacity: '1' },
        },
        'fade-in': {
          from: { opacity: '0' },
          to:   { opacity: '1' },
        },
        blink: {
          '0%, 100%': { opacity: '1' },
          '50%':       { opacity: '0' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        'spin-slow': {
          from: { transform: 'rotate(0deg)' },
          to:   { transform: 'rotate(360deg)' },
        },
        float: {
          '0%, 100%': { transform: 'translateY(0px)' },
          '50%':       { transform: 'translateY(-8px)' },
        },
        'gradient-shift': {
          '0%':   { backgroundPosition: '0% 50%' },
          '50%':  { backgroundPosition: '100% 50%' },
          '100%': { backgroundPosition: '0% 50%' },
        },
        'count-up': {
          from: { opacity: '0', transform: 'translateY(10px)' },
          to:   { opacity: '1', transform: 'translateY(0)' },
        },
      },
    },
  },
  plugins: [],
};
