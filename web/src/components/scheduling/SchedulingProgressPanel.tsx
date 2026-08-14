import { AlertTriangle, CheckCircle2, Radio, Sparkles } from 'lucide-react';
import type { SchedulingTaskStatus } from '../../types/api';
import { Pill, Surface } from '../workbench/atoms';

export interface SchedulingLogEntry {
  id: string;
  level: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: string;
}

interface SchedulingProgressPanelProps {
  taskStatus: SchedulingTaskStatus;
  message: string;
  percent?: number;
  error?: string | null;
  logs: SchedulingLogEntry[];
}

function progressTone(status: SchedulingTaskStatus) {
  if (status === 'completed') return 'success';
  if (status === 'failed' || status === 'cancelled') return 'danger';
  if (status === 'running' || status === 'queued' || status === 'cancelled_requested') return 'warning';
  return 'neutral';
}

function statusLabel(status: SchedulingTaskStatus) {
  switch (status) {
    case 'queued':             return '排队中';
    case 'running':            return '执行中';
    case 'completed':          return '已完成';
    case 'failed':             return '失败';
    case 'cancelled_requested':return '取消中';
    case 'cancelled':          return '已取消';
    default:                   return '空闲';
  }
}

const logLevelColor: Record<string, string> = {
  success: 'var(--accent-ui)',
  warning: '#d97706',
  error:   '#dc2626',
  info:    'var(--text-muted)',
};

export function SchedulingProgressPanel({
  taskStatus,
  message,
  percent,
  error,
  logs,
}: SchedulingProgressPanelProps) {
  const progressValue = Math.max(0, Math.min(100, percent ?? (taskStatus === 'completed' ? 100 : 0)));
  const barColor = taskStatus === 'failed' || taskStatus === 'cancelled'
    ? '#f87171'
    : taskStatus === 'completed'
      ? 'var(--accent-ui)'
      : '#14b8a6';

  return (
    <Surface>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>任务进度</h3>
        <div className="flex items-center gap-2">
          <Pill tone={progressTone(taskStatus)}>{statusLabel(taskStatus)}</Pill>
          <Sparkles className="h-3.5 w-3.5" style={{ color: 'var(--accent-ui)' }} />
        </div>
      </div>

      {/* Status message + progress bar */}
      <div className="space-y-2">
        <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
          {message || '等待任务触发'}
        </p>
        <div className="h-1.5 overflow-hidden rounded-full"
             style={{ background: 'var(--border-card)' }}>
          <div
            className="h-full rounded-full transition-all duration-300"
            style={{ width: `${progressValue}%`, background: barColor }}
          />
        </div>
        {progressValue > 0 && (
          <p className="text-right font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
            {progressValue}%
          </p>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="mt-3 flex items-start gap-2 rounded-lg border px-3 py-2.5 text-sm"
             style={{ borderColor: '#fca5a5', background: '#fff5f5', color: '#991b1b' }}
             role="alert">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Log entries */}
      <div className="mt-4">
        <div className="mb-2 flex items-center gap-1.5">
          <Radio className="h-3.5 w-3.5" style={{ color: 'var(--accent-ui)' }} />
          <span className="text-[11px] font-semibold uppercase tracking-[0.18em]"
                style={{ color: 'var(--text-muted)' }}>
            实时日志
          </span>
        </div>

        {logs.length === 0 ? (
          <div className="rounded-lg border border-dashed py-6 text-center text-xs"
               style={{ borderColor: 'var(--border-base)', color: 'var(--text-muted)' }}>
            暂无日志，任务启动后将在此显示。
          </div>
        ) : (
          <div className="max-h-64 space-y-1.5 overflow-y-auto">
            {logs.map((entry) => (
              <div key={entry.id} className="rounded-lg border px-3 py-2.5"
                   style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-card)' }}>
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-1.5">
                    <CheckCircle2
                      className="h-3.5 w-3.5 shrink-0"
                      style={{ color: logLevelColor[entry.level] }}
                    />
                    <span className="text-xs font-medium" style={{ color: 'var(--text-primary)' }}>
                      {entry.title}
                    </span>
                  </div>
                  <span className="shrink-0 font-mono text-[10px]"
                        style={{ color: 'var(--text-muted)' }}>
                    {entry.timestamp}
                  </span>
                </div>
                <p className="mt-0.5 pl-5 text-xs leading-5"
                   style={{ color: 'var(--text-secondary)' }}>
                  {entry.message}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </Surface>
  );
}

export default SchedulingProgressPanel;
