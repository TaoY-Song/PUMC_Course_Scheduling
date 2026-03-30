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

export function SchedulingProgressPanel({
  taskStatus,
  message,
  percent,
  error,
  logs,
}: SchedulingProgressPanelProps) {
  const progressValue = Math.max(0, Math.min(100, percent ?? (taskStatus === 'completed' ? 100 : 0)));

  return (
    <Surface eyebrow="进度" title="任务流转">
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Pill tone={progressTone(taskStatus)}>{statusLabel(taskStatus)}</Pill>
            <span className="text-sm text-[#566158]">{message || '等待任务触发'}</span>
          </div>
          <Sparkles className="h-5 w-5 text-[#8f7340]" />
        </div>

        <div className="overflow-hidden rounded-full bg-[#e8dfcf]">
          <div
            className={`h-2 rounded-full transition-all duration-300 ${
              taskStatus === 'failed' || taskStatus === 'cancelled'
                ? 'bg-rose-500'
                : taskStatus === 'completed'
                  ? 'bg-emerald-500'
                  : 'bg-[#7d6a4c]'
            }`}
            style={{ width: `${progressValue}%` }}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
          <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
            <div className="mb-3 flex items-center gap-2 text-sm font-medium text-[#24312c]">
              <Radio className="h-4 w-4 text-[#8f7340]" />
              实时日志
            </div>
            <div className="space-y-3">
              {logs.length === 0 ? (
                <div className="rounded-[0.9rem] border border-dashed border-[#d8ccb8] bg-white px-4 py-6 text-sm text-[#6b756d]">
                  暂无进度消息。若后端没有持续推送，页面会继续通过轮询补齐状态。
                </div>
              ) : (
                logs.map((entry) => (
                  <div key={entry.id} className="rounded-[0.9rem] border border-[#e3d9c6] bg-white px-4 py-3">
                    <div className="flex items-start justify-between gap-3">
                      <div className="font-medium text-[#213028]">{entry.title}</div>
                      <Pill
                        tone={
                          entry.level === 'success'
                            ? 'success'
                            : entry.level === 'warning'
                              ? 'warning'
                              : entry.level === 'error'
                                ? 'danger'
                                : 'neutral'
                        }
                      >
                        {entry.level}
                      </Pill>
                    </div>
                    <div className="mt-1 text-sm leading-6 text-[#59645c]">{entry.message}</div>
                    <div className="mt-2 text-xs text-[#8a7f6d]">{entry.timestamp}</div>
                  </div>
                ))
              )}
            </div>
          </div>

          <div className="space-y-4">
            <div className="rounded-[1rem] border border-[#e1d6c2] bg-[#fbf7ef] p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-medium text-[#24312c]">
                <CheckCircle2 className="h-4 w-4 text-[#2f7b4f]" />
                状态说明
              </div>
              <div className="space-y-2 text-sm leading-6 text-[#59645c]">
                <p>优先接收 WebSocket 实时事件，连接不稳定时自动退回轮询。</p>
                <p>如果后端暂时仍返回同步结果，页面会自动兼容，不会卡死在中间状态。</p>
              </div>
            </div>

            {error ? (
              <div className="rounded-[1rem] border border-rose-200 bg-rose-50 p-4">
                <div className="mb-2 flex items-center gap-2 text-sm font-medium text-rose-700">
                  <AlertTriangle className="h-4 w-4" />
                  错误区
                </div>
                <div className="text-sm leading-6 text-rose-700">{error}</div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </Surface>
  );
}

export default SchedulingProgressPanel;
