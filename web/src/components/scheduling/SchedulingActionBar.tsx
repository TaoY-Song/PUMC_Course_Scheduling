import { Loader2, Play, RefreshCcw, Square, Wifi, WifiOff } from 'lucide-react';
import type { SchedulingTaskStatus } from '../../types/api';
import { Pill, Surface } from '../workbench/atoms';

interface SchedulingActionBarProps {
  selectedCount: number;
  taskStatus: SchedulingTaskStatus;
  taskId: string | null;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error';
  isExecuting: boolean;
  isCancelling: boolean;
  /** 外部阻断原因（如“有课程未设置类别”）；为空表示可执行。 */
  blockedReason?: string | null;
  onExecute: () => void;
  onCancel: () => void;
  onRefresh: () => void;
}

function statusTone(status: SchedulingTaskStatus) {
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

function connectionLabel(state: SchedulingActionBarProps['connectionState']) {
  switch (state) {
    case 'connected':   return '已连接';
    case 'connecting':  return '连接中';
    case 'error':       return '异常';
    default:            return '未连接';
  }
}

export function SchedulingActionBar({
  selectedCount,
  taskStatus,
  taskId,
  connectionState,
  isExecuting,
  isCancelling,
  blockedReason,
  onExecute,
  onCancel,
  onRefresh,
}: SchedulingActionBarProps) {
  const isBusy = taskStatus === 'running' || taskStatus === 'queued'
    || taskStatus === 'cancelled_requested' || isExecuting;
  const canExecute = selectedCount > 0 && !isBusy && !blockedReason;
  const canCancel  = taskStatus === 'running' || taskStatus === 'queued';

  return (
    <Surface>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>任务执行</h3>
        <span className="tag tag-gray">CONTROL</span>
      </div>

      <div className="flex flex-col gap-4">
        {/* Info row */}
        <div className="grid grid-cols-3 gap-2">
          {[
            {
              label: '已选课程',
              value: <span className="text-xl font-semibold tabular-nums"
                          style={{ color: 'var(--text-primary)' }}>{selectedCount}</span>,
            },
            {
              label: '任务状态',
              value: (
                <div className="flex items-center gap-1.5">
                  <Pill tone={statusTone(taskStatus)}>{statusLabel(taskStatus)}</Pill>
                  {isBusy && <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: 'var(--accent-ui)' }} />}
                </div>
              ),
            },
            {
              label: 'WebSocket',
              value: (
                <div className="flex items-center gap-1.5">
                  {connectionState === 'connected'
                    ? <Wifi className="h-3.5 w-3.5 text-emerald-500" />
                    : <WifiOff className="h-3.5 w-3.5 text-rose-400" />}
                  <Pill
                    tone={connectionState === 'connected' ? 'success'
                         : connectionState === 'connecting' ? 'warning'
                         : 'danger'}
                  >
                    {connectionLabel(connectionState)}
                  </Pill>
                </div>
              ),
            },
          ].map(({ label, value }) => (
            <div key={label} className="rounded-lg border px-3 py-2.5"
                 style={{ borderColor: 'var(--border-subtle)', background: 'var(--bg-subtle)' }}>
              <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.2em]"
                 style={{ color: 'var(--text-muted)' }}>{label}</p>
              {value}
            </div>
          ))}
        </div>

        {/* Task ID */}
        {taskId && (
          <p className="font-mono text-[11px]" style={{ color: 'var(--text-muted)' }}>
            task: {taskId}
          </p>
        )}

        {blockedReason && (
          <p className="text-xs" style={{ color: 'var(--danger-text)' }}>
            {blockedReason}
          </p>
        )}

        {/* Actions */}
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onExecute}
            disabled={!canExecute}
            className="btn-primary px-5 py-2.5"
            title={blockedReason || undefined}
          >
            <Play className="h-4 w-4" />
            {isExecuting ? '启动中…' : '开始排课'}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={!canCancel}
            className="btn-ghost px-5 py-2.5"
          >
            {isCancelling
              ? <Loader2 className="h-4 w-4 animate-spin" />
              : <Square className="h-4 w-4" />}
            取消任务
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="btn-ghost px-5 py-2.5"
          >
            <RefreshCcw className="h-4 w-4" />
            刷新
          </button>
        </div>
      </div>
    </Surface>
  );
}

export default SchedulingActionBar;
