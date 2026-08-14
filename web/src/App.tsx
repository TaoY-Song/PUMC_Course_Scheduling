import { useEffect, useState } from 'react';
import {
  BookOpenText,
  BrainCircuit,
  FlaskConical,
  ShieldCheck,
  Activity,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { NavLink, Navigate, Outlet, Route, Routes, useLocation } from 'react-router-dom';
import { healthCheck } from './lib/workbenchApi';
import { CoursesPage } from './pages/CoursesPage';
import { SchedulingPage } from './pages/SchedulingPage';
import { SettingsPage } from './pages/SettingsPage';
import { SupplementPage } from './pages/SupplementPage';

type HealthState = {
  status: string;
  version?: string;
} | null;

const NAV_ITEMS = [
  {
    to: '/courses',
    label: '课程工作台',
    short: '课程',
    icon: BookOpenText,
  },
  {
    to: '/scheduling',
    label: '智能排课',
    short: '排课',
    icon: BrainCircuit,
  },
  {
    to: '/settings',
    label: '学分设置',
    short: '学分',
    icon: ShieldCheck,
  },
  {
    to: '/supplement',
    label: '补充测试',
    short: '测试',
    icon: FlaskConical,
  },
] as const;

// ─── Sidebar SVG grid pattern ─────────────────────────────────────────────────
function GridPattern() {
  return (
    <svg
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 h-full w-full"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <pattern id="sidebar-grid" width="28" height="28" patternUnits="userSpaceOnUse">
          <path d="M 28 0 L 0 0 0 28" fill="none" stroke="rgba(255,255,255,0.04)" strokeWidth="0.5" />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#sidebar-grid)" />
    </svg>
  );
}

// ─── Page title lookup ────────────────────────────────────────────────────────
const PAGE_META: Record<string, { title: string; sub: string }> = {
  '/courses':    { title: '课程工作台', sub: 'Course Workbench' },
  '/scheduling': { title: '智能排课',   sub: 'Scheduling Engine' },
  '/settings':   { title: '学分设置',   sub: 'Credit Settings' },
  '/supplement': { title: '补充测试',   sub: 'Supplement Test' },
};

function AppShell({
  health,
  loading,
  error,
}: {
  health: HealthState;
  loading: boolean;
  error: string | null;
}) {
  const { pathname } = useLocation();
  const meta = PAGE_META[pathname] ?? { title: 'PUMC 排课', sub: 'Workbench' };

  return (
    <div className="flex min-h-svh">

      {/* ── Sidebar ─────────────────────────────────────────────────────────── */}
      <aside
        className="sidebar-grid relative hidden w-56 shrink-0 flex-col lg:flex"
        style={{ background: '#071615', color: '#e8eeec' }}
      >
        <GridPattern />

        {/* Logo area */}
        <div className="relative z-10 flex flex-col gap-1 border-b px-5 pb-5 pt-6"
             style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
          <div className="flex items-center gap-2.5">
            <div className="flex h-7 w-7 items-center justify-center rounded-md overflow-hidden border"
                 style={{ borderColor: 'rgba(255,255,255,0.12)', background: 'rgba(255,255,255,0.06)' }}>
              <img src="/PUMClogo.ico" alt="" className="h-5 w-5 object-contain" />
            </div>
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em]"
                  style={{ color: '#8faaa6' }}>
              PUMC
            </span>
          </div>
          <p className="mt-2 font-mono text-base font-semibold leading-tight tracking-tight"
             style={{ color: '#e8eeec' }}>
            排课系统
          </p>
          <p className="font-mono text-[10px]" style={{ color: '#4d7770' }}>v2.0.0</p>
        </div>

        {/* Nav */}
        <nav aria-label="主导航" className="relative z-10 flex flex-col gap-0.5 px-3 py-4">
          {NAV_ITEMS.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                [
                  'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-all duration-150',
                  isActive
                    ? 'text-white'
                    : 'hover:bg-white/5',
                ].join(' ')
              }
              style={({ isActive }) => isActive
                ? { background: 'var(--accent-ui)', color: 'white' }
                : { color: '#8faaa6' }}
            >
              {({ isActive }) => (
                <>
                  <Icon
                    className="h-4 w-4 shrink-0"
                    style={{ opacity: isActive ? 1 : 0.7 }}
                  />
                  {label}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Status footer */}
        <div className="relative z-10 mt-auto border-t px-4 py-4"
             style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
          <div className="flex items-center gap-2.5">
            {loading
              ? <span className="dot-loading" />
              : error
                ? <span className="dot-offline" />
                : <span className="dot-online" />}
            <div>
              <p className="text-[11px] font-medium" style={{ color: '#8faaa6' }}>
                {loading ? '连接中…' : error ? '后端离线' : `${health?.status ?? 'healthy'}`}
              </p>
              {!loading && !error && (
                <p className="text-[10px]" style={{ color: '#3d5c58' }}>
                  v{health?.version ?? '1.0.0'} · local
                </p>
              )}
            </div>
            <div className="ml-auto">
              {error
                ? <WifiOff className="h-3.5 w-3.5" style={{ color: '#f87171', opacity: 0.8 }} />
                : <Wifi className="h-3.5 w-3.5" style={{ color: '#4ade80', opacity: loading ? 0.4 : 0.8 }} />}
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main ────────────────────────────────────────────────────────────── */}
      <div className="flex min-w-0 flex-1 flex-col" style={{ background: 'var(--bg-base)' }}>

        {/* Topbar */}
        <header
          className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b px-4 py-3 sm:px-6"
          style={{
            background: 'rgba(244,242,237,0.88)',
            backdropFilter: 'blur(12px)',
            borderColor: 'var(--border-card)',
          }}
        >
          {/* Mobile brand + active page */}
          <div className="flex items-center gap-3 lg:gap-0">
            <img
              src="/PUMClogo.ico"
              alt="PUMC"
              className="h-7 w-7 rounded object-contain lg:hidden"
            />
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] lg:hidden"
                 style={{ color: 'var(--text-muted)' }}>
                {meta.sub}
              </p>
              <h1 className="text-sm font-semibold lg:text-base" style={{ color: 'var(--text-primary)' }}>
                {meta.title}
              </h1>
            </div>
          </div>

          {/* Right area */}
          <div className="flex items-center gap-2">
            {/* Health indicator — desktop */}
            <div className="hidden items-center gap-2 rounded-md border px-2.5 py-1 text-xs lg:flex"
                 style={{ borderColor: 'var(--border-card)', color: 'var(--text-muted)' }}>
              <Activity className="h-3 w-3" />
              {loading ? '检查中' : error ? '后端离线' : '系统正常'}
            </div>
          </div>
        </header>

        {/* Mobile nav strip */}
        <nav
          aria-label="主导航"
          className="flex gap-1 overflow-x-auto border-b px-3 py-2 lg:hidden"
          style={{ borderColor: 'var(--border-card)' }}
        >
          {NAV_ITEMS.map(({ to, short, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                [
                  'flex shrink-0 items-center gap-1.5 rounded-md px-3 py-2 text-xs font-medium transition-all',
                  isActive ? 'text-white' : 'text-[--text-secondary]',
                ].join(' ')
              }
              style={({ isActive }) =>
                isActive
                  ? { background: 'var(--accent-ui)', color: 'white' }
                  : { color: 'var(--text-secondary)' }}
            >
              {({ isActive }) => (
                <>
                  <Icon className="h-3.5 w-3.5" style={{ opacity: isActive ? 1 : 0.6 }} />
                  {short}
                </>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Content */}
        <main className="flex-1 px-4 py-5 sm:px-6 sm:py-6">
          {error ? (
            <div
              className="mx-auto mt-8 max-w-lg rounded-xl border p-6"
              style={{ borderColor: '#fca5a5', background: '#fff5f5' }}
              role="alert"
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em]"
                 style={{ color: '#b91c1c' }}>
                Connection Error
              </p>
              <h2 className="mt-2 text-base font-semibold" style={{ color: '#7f1d1d' }}>
                无法连接到 Web 后端
              </h2>
              <p className="mt-1.5 text-sm leading-6" style={{ color: '#991b1b' }}>
                {error}
              </p>
              <div className="mt-4 rounded-lg border px-3 py-2 font-mono text-xs"
                   style={{ borderColor: '#fca5a5', color: '#7f1d1d' }}>
                python app_web.py --dev
              </div>
            </div>
          ) : (
            <Outlet />
          )}
        </main>
      </div>
    </div>
  );
}

function App() {
  const [health, setHealth] = useState<HealthState>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    healthCheck()
      .then((data) => { setHealth(data); setError(null); })
      .catch((err) => { setError(err instanceof Error ? err.message : '无法连接到后端'); })
      .finally(() => setLoading(false));
  }, []);

  return (
    <Routes>
      <Route element={<AppShell health={health} loading={loading} error={error} />}>
        <Route path="/" element={<Navigate to="/courses" replace />} />
        <Route path="/courses"    element={<CoursesPage />} />
        <Route path="/scheduling" element={<SchedulingPage />} />
        <Route path="/settings"   element={<SettingsPage />} />
        <Route path="/supplement" element={<SupplementPage />} />
      </Route>
    </Routes>
  );
}

export default App;
