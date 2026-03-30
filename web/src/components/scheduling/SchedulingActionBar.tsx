import { Loader2, Play, RefreshCcw, Square } from 'lucide-react';
import type { SchedulingTaskStatus } from '../../types/api';
import { Pill, Surface } from '../workbench/atoms';

interface SchedulingActionBarProps {
  selectedCount: number;
  taskStatus: SchedulingTaskStatus;
  taskId: string | null;
  connectionState: 'connecting' | 'connected' | 'disconnected' | 'error';
  isExecuting: boolean;
  isCancelling: boolean;
  onExecute: () => void;
  onCancel: () => void;
  onRefresh: () => void;
}

function statusTone(status: SchedulingTaskStatus) {
  if (status === 'completed') {
    return 'success';
  }
  if (status === 'failed' || status === 'cancelled') {
    return 'danger';
  }
  if (status === 'running' || status === 'queued' || status === 'cancelled_requested') {
    return 'warning';
  }
  return 'neutral';
}

function statusLabel(status: SchedulingTaskStatus) {
  switch (status) {
    case 'queued':
      return '排队中';
    case 'running':
      return '执行中';
    case 'completed':
      return '已完成';
    case 'failed':
      return '失败';
    case 'cancelled_requested':
      return '取消中';
    case 'cancelled':
      return '已取消';
    default:
      return '空闲';
  }
}

function connectionLabel(state: SchedulingActionBarProps['connectionState']) {
  switch (state) {
    case 'connected':
      return '已连接';
    case 'connecting':
      return '连接中';
    case 'error':
      return '异常';
    default:
      return '未连接';
  }
}

export function SchedulingActionBar({
  selectedCount,
  taskStatus,
  taskId,
  connectionState,
  isExecuting,
  isCancelling,
  onExecute,
  onCancel,
  onRefresh,
}: SchedulingActionBarProps) {
  const isBusy =
    taskStatus === 'running' ||
    taskStatus === 'queued' ||
    taskStatus === 'cancelled_requested' ||
    isExecuting;
  const canExecute = selectedCount > 0 && !isBusy;
  const canCancel = taskStatus === 'running' || taskStatus === 'queued';

  return (
    <Surface eyebrow="控制" title="任务执行">
      <div className="flex flex-col gap-4">
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#f9f3e7] px-4 py-3">
            <div className="text-[0.72rem] uppercase tracking-[0.28em] text-[#7b6b55]">已选课程</div>
            <div className="mt-2 text-2xl font-semibold text-[#1b2a22]">{selectedCount}</div>
          </div>
          <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#f9f3e7] px-4 py-3">
            <div className="text-[0.72rem] uppercase tracking-[0.28em] text-[#7b6b55]">任务状态</div>
            <div className="mt-2 flex items-center gap-2">
              <Pill tone={statusTone(taskStatus)}>{statusLabel(taskStatus)}</Pill>
              {isBusy ? <Loader2 className="h-4 w-4 animate-spin text-[#7f6a48]" /> : null}
            </div>
          </div>
          <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#f9f3e7] px-4 py-3">
            <div className="text-[0.72rem] uppercase tracking-[0.28em] text-[#7b6b55]">WS</div>
            <div className="mt-2 flex items-center gap-2">
              <Pill
                tone={
                  connectionState === 'connected'
                    ? 'success'
                    : connectionState === 'connecting'
                      ? 'warning'
                      : 'danger'
                }
              >
                {connectionLabel(connectionState)}
              </Pill>
              {taskId ? (
                <span className="text-xs text-[#6f6659]">{taskId}</span>
              ) : (
                <span className="text-xs text-[#6f6659]">尚未创建任务</span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={onExecute}
            disabled={!canExecute}
            className="inline-flex items-center gap-2 rounded-full bg-[#173327] px-5 py-3 text-sm font-medium text-white transition hover:bg-[#204232] disabled:cursor-not-allowed disabled:opacity-45"
          >
            <Play className="h-4 w-4" />
            {isExecuting ? '启动中' : '开始排课'}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={!canCancel}
            className="inline-flex items-center gap-2 rounded-full border border-[#d9cdb9] bg-white px-5 py-3 text-sm font-medium text-[#24312c] transition hover:bg-[#f7f0e4] disabled:cursor-not-allowed disabled:opacity-45"
          >
            {isCancelling ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Square className="h-4 w-4" />
            )}
            取消任务
          </button>
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-2 rounded-full border border-[#d9cdb9] bg-white px-5 py-3 text-sm font-medium text-[#24312c] transition hover:bg-[#f7f0e4]"
          >
            <RefreshCcw className="h-4 w-4" />
            刷新状态
          </button>
        </div>
      </div>
    </Surface>
  );
}

export default SchedulingActionBar;
