import { useEffect, useState } from 'react';
import {
  BookOpenText,
  BrainCircuit,
  FlaskConical,
  LayoutDashboard,
  ShieldCheck,
} from 'lucide-react';
import { NavLink, Navigate, Outlet, Route, Routes } from 'react-router-dom';
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
    description: '导入课程、管理已选课程、编辑时间段',
    icon: BookOpenText,
  },
  {
    to: '/scheduling',
    label: '智能排课',
    description: '配置参数、执行排课、查看结果与周课表',
    icon: BrainCircuit,
  },
  {
    to: '/settings',
    label: '学分设置',
    description: '维护学分要求并查看完成进度',
    icon: ShieldCheck,
  },
  {
    to: '/supplement',
    label: '补充测试',
    description: '调用补充测试脚本并下载结果与日志',
    icon: FlaskConical,
  },
] as const;

function AppShell({
  health,
  loading,
  error,
}: {
  health: HealthState;
  loading: boolean;
  error: string | null;
}) {
  return (
    <div className="relative min-h-screen overflow-hidden text-[#17221d]">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[24rem] bg-[radial-gradient(circle_at_top_left,_rgba(205,169,89,0.26),_transparent_42%),radial-gradient(circle_at_top_right,_rgba(36,84,68,0.2),_transparent_36%)]" />
      <div className="relative mx-auto flex min-h-screen w-full max-w-[1600px] gap-6 px-4 py-4 sm:px-6 lg:px-8">
        <aside className="hidden w-[340px] shrink-0 rounded-[2rem] border border-[#d7cbb4] bg-[linear-gradient(180deg,rgba(18,33,28,0.98),rgba(29,53,45,0.95))] p-6 text-[#f6efe1] shadow-[0_30px_90px_rgba(10,21,18,0.25)] lg:flex lg:flex-col">
          <div>
            <div className="inline-flex items-center gap-3 rounded-full border border-white/15 bg-white/8 px-4 py-2 text-[0.72rem] uppercase tracking-[0.32em] text-[#d9c8a2]">
              <img
                src="/PUMClogo.ico"
                alt="PUMC Logo"
                className="h-5 w-5 rounded-sm object-contain"
              />
              PUMC Scheduling
            </div>
            <h1 className="mt-6 max-w-[16rem] font-['Iowan_Old_Style','Palatino_Linotype','Book_Antiqua',Georgia,serif] text-[2rem] leading-[1.12] tracking-[0.01em] text-[#f4edde]">
              <span className="block">PUMC排课系统</span>
              <span className="mt-1 block">V2.0.0</span>
            </h1>
            <p className="mt-5 max-w-[17rem] text-sm leading-7 text-[#d8ddcf]">
              用浏览器承接 Qt 版排班能力。课程导入、已选课程管理、智能排课、补充测试与结果导出统一收口到同一套工作流。
            </p>
          </div>

          <div className="mt-8 grid gap-3">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  className={({ isActive }) =>
                    [
                      'rounded-[1.5rem] border px-4 py-4 transition-all',
                      isActive
                        ? 'border-[#d1b575] bg-[#f5ebd4] text-[#10201b] shadow-[0_18px_50px_rgba(0,0,0,0.18)]'
                        : 'border-white/10 bg-white/5 text-[#edf1e8] hover:bg-white/8',
                    ].join(' ')
                  }
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5 rounded-2xl border border-current/15 bg-current/10 p-2.5">
                      <Icon className="h-[18px] w-[18px]" />
                    </div>
                    <div>
                      <div className="text-sm font-semibold">{item.label}</div>
                      <div className="mt-1 text-xs leading-5 opacity-80">{item.description}</div>
                    </div>
                  </div>
                </NavLink>
              );
            })}
          </div>

          <div className="mt-auto rounded-[1.5rem] border border-white/10 bg-white/5 p-4 text-sm">
            <div className="text-[0.68rem] uppercase tracking-[0.3em] text-[#c8b48a]">系统状态</div>
            <div className="mt-3 flex items-center justify-between">
              <span className="text-[#dfe8db]">后端健康</span>
              <span
                className={[
                  'inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium',
                  error
                    ? 'bg-[#5a2323] text-[#ffdfdf]'
                    : loading
                      ? 'bg-[#4e4524] text-[#f9efc2]'
                      : 'bg-[#1f4a3c] text-[#d4f2e3]',
                ].join(' ')}
              >
                {error ? '异常' : loading ? '检查中' : health?.status ?? '未知'}
              </span>
            </div>
            <div className="mt-2 text-xs text-[#c9d1c6]">
              版本 {health?.version ?? '1.0.0'} · 单用户本地会话
            </div>
          </div>
        </aside>

        <main className="flex min-h-[calc(100vh-2rem)] flex-1 flex-col rounded-[2rem] border border-[#ddd0bb] bg-[rgba(255,250,240,0.88)] shadow-[0_35px_90px_rgba(20,34,28,0.14)] backdrop-blur-xl">
          <header className="border-b border-[#eadfcb] px-5 py-4 sm:px-7">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-start gap-3">
                <img
                  src="/PUMClogo.ico"
                  alt="PUMC Logo"
                  className="mt-1 h-10 w-10 rounded-xl border border-[#dfd1ba] bg-white/80 p-1.5 object-contain shadow-sm lg:hidden"
                />
                <div>
                  <div className="text-[0.72rem] uppercase tracking-[0.34em] text-[#8a7c63]">
                    Browser Workbench
                  </div>
                  <h2 className="mt-2 text-2xl font-semibold text-[#16211d]">
                    PUMC 智能排班系统
                  </h2>
                </div>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-[#ddcfb7] bg-white/85 px-3 py-1.5 text-xs text-[#465048]">
                  <LayoutDashboard className="h-3.5 w-3.5" />
                  Qt 桌面版 + Web 工作台
                </div>
                <div className="inline-flex items-center gap-2 rounded-full border border-[#ddcfb7] bg-[#f4eddc] px-3 py-1.5 text-xs text-[#5c4d29]">
                  本地会话 / 浏览器可用
                </div>
              </div>
            </div>
          </header>

          <div className="flex-1 px-4 py-4 sm:px-6 sm:py-6 lg:px-7">
            {error ? (
              <div className="mx-auto mt-10 max-w-2xl rounded-[1.75rem] border border-[#e2c5bf] bg-[#fff7f5] p-8 shadow-[0_22px_55px_rgba(106,38,23,0.08)]">
                <div className="text-[0.72rem] uppercase tracking-[0.34em] text-[#b86c5d]">Backend</div>
                <h3 className="mt-3 text-2xl font-semibold text-[#702f22]">无法连接到 Web 后端</h3>
                <p className="mt-3 text-sm leading-7 text-[#87473b]">{error}</p>
                <div className="mt-6 rounded-2xl border border-[#ead2cb] bg-white px-4 py-3 font-mono text-sm text-[#5f2d25]">
                  python app_web.py --dev
                </div>
              </div>
            ) : (
              <Outlet />
            )}
          </div>
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
    const runHealthCheck = async () => {
      try {
        const data = await healthCheck();
        setHealth(data);
        setError(null);
      } catch (caughtError) {
        setError(caughtError instanceof Error ? caughtError.message : '无法连接到后端服务');
      } finally {
        setLoading(false);
      }
    };

    runHealthCheck().catch((caughtError) => {
      setError(caughtError instanceof Error ? caughtError.message : '健康检查失败');
      setLoading(false);
    });
  }, []);

  return (
    <Routes>
      <Route element={<AppShell health={health} loading={loading} error={error} />}>
        <Route path="/" element={<Navigate to="/courses" replace />} />
        <Route path="/courses" element={<CoursesPage />} />
        <Route path="/scheduling" element={<SchedulingPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="/supplement" element={<SupplementPage />} />
      </Route>
    </Routes>
  );
}

export default App;
