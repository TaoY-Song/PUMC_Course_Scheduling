import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Download, Loader2, Wifi, WifiOff } from 'lucide-react';
import { AcademicTimetable } from '../components/scheduling/AcademicTimetable';
import { SchedulingActionBar } from '../components/scheduling/SchedulingActionBar';
import { SchedulingConfigPanel } from '../components/scheduling/SchedulingConfigPanel';
import {
  SchedulingProgressPanel,
  type SchedulingLogEntry,
} from '../components/scheduling/SchedulingProgressPanel';
import { SchedulingResultPanel } from '../components/scheduling/SchedulingResultPanel';
import { MetricCard } from '../components/workbench/atoms';
import { isCategoryUnset } from '../lib/categories';
import {
  cancelSchedulingTask,
  createSchedulingTask,
  downloadScheduleResultExport,
  getSchedulingConfig,
  getSchedulingTaskResult,
  getSchedulingTaskStatus,
  getSelectedCourses,
  normalizeScheduleResult,
  subscribeSchedulingStream,
  updateSchedulingConfig,
} from '../lib/workbenchApi';
import type {
  SchedulingCompletedPayload,
  SchedulingFailedPayload,
  SchedulingProgressPayload,
  SchedulingStartedPayload,
  SchedulingTaskHandle,
  SchedulingTaskStatus,
  SchedulingWebSocketMessage,
} from '../types/api';
import type { ScheduleResult, SchedulingConfig, SelectedCourse } from '../types/models';

const DEFAULT_CONFIG: SchedulingConfig = {
  credit_constraint_mode: 'OPTIMAL',
  campus_conflict_mode: 'DAILY',
  campus_equivalence_groups: [],
  max_solutions: 1,
  time_limit: 60,
  credit_overflow: 1.0,
};

function sameCampusGroups(left: string[][], right: string[][]) {
  return JSON.stringify(left) === JSON.stringify(right);
}

function sameConfig(left: SchedulingConfig, right: SchedulingConfig) {
  return (
    left.credit_constraint_mode === right.credit_constraint_mode &&
    left.campus_conflict_mode === right.campus_conflict_mode &&
    sameCampusGroups(left.campus_equivalence_groups, right.campus_equivalence_groups) &&
    left.max_solutions === right.max_solutions &&
    left.time_limit === right.time_limit &&
    left.credit_overflow === right.credit_overflow
  );
}

function normalizeTaskStatus(value: string | undefined): SchedulingTaskStatus {
  const raw = (value || 'idle').toLowerCase();
  if (raw === 'pending' || raw === 'queued') {
    return 'queued';
  }
  if (raw === 'running' || raw === 'completed' || raw === 'failed' || raw === 'cancelled') {
    return raw;
  }
  if (raw === 'cancelled_requested' || raw === 'cancel_requested') {
    return 'cancelled_requested';
  }
  return 'idle';
}

function isTerminalStatus(status: SchedulingTaskStatus) {
  return status === 'completed' || status === 'failed' || status === 'cancelled';
}

function isActiveStatus(status: SchedulingTaskStatus) {
  return status === 'queued' || status === 'running' || status === 'cancelled_requested';
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

function connectionLabel(state: 'connecting' | 'connected' | 'disconnected' | 'error') {
  switch (state) {
    case 'connected':
      return '已连接';
    case 'connecting':
      return '连接中';
    case 'error':
      return '连接异常';
    default:
      return '未连接';
  }
}

function formatTimestamp(date = new Date()) {
  return date.toLocaleTimeString('zh-CN', {
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function useLogBuffer() {
  const [logs, setLogs] = useState<SchedulingLogEntry[]>([]);

  const pushLog = useCallback((level: SchedulingLogEntry['level'], title: string, message: string) => {
    setLogs((current) => [
      ...current.slice(-11),
      {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        level,
        title,
        message,
        timestamp: formatTimestamp(),
      },
    ]);
  }, []);

  const resetLogs = useCallback(() => setLogs([]), []);

  return { logs, pushLog, resetLogs };
}

export function SchedulingPage() {
  const [savedConfig, setSavedConfig] = useState<SchedulingConfig>(DEFAULT_CONFIG);
  const [draftConfig, setDraftConfig] = useState<SchedulingConfig>(DEFAULT_CONFIG);
  const [selectedCourses, setSelectedCourses] = useState<SelectedCourse[]>([]);
  const [result, setResult] = useState<ScheduleResult | null>(null);
  const [taskRuntime, setTaskRuntime] = useState<{
    taskId: string | null;
    status: SchedulingTaskStatus;
    message: string;
    percent?: number;
    mode: 'async' | 'sync';
    source: 'ws' | 'poll' | 'sync' | 'fallback';
  }>({
    taskId: null,
    status: 'idle',
    message: '等待排课任务',
    percent: 0,
    mode: 'sync',
    source: 'fallback',
  });
  const [connectionState, setConnectionState] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>(
    'disconnected',
  );
  const [isBooting, setIsBooting] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const pollingTimerRef = useRef<number | null>(null);
  const pollingBusyRef = useRef(false);
  const activeTaskIdRef = useRef<string | null>(null);
  const { logs, pushLog, resetLogs } = useLogBuffer();

  const isDirty = useMemo(() => !sameConfig(savedConfig, draftConfig), [draftConfig, savedConfig]);
  const resultCourses = result?.selected_courses ?? [];
  const taskId = taskRuntime.taskId;
  const availableCampuses = useMemo(
    () => Array.from(
      new Set(
        selectedCourses
          .map((course) => (course.course.campus || '').trim())
          .filter(Boolean),
      ),
    ).sort((left, right) => left.localeCompare(right, 'zh-CN')),
    [selectedCourses],
  );

  const stopPolling = useCallback(() => {
    if (pollingTimerRef.current !== null) {
      window.clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }
  }, []);

  const applyTaskSnapshot = useCallback(
    (
      next: Partial<{
        taskId: string | null;
        status: SchedulingTaskStatus;
        message: string;
        percent?: number;
        mode: 'async' | 'sync';
        source: 'ws' | 'poll' | 'sync' | 'fallback';
      }>,
    ) => {
      if (next.taskId !== undefined) {
        activeTaskIdRef.current = next.taskId;
      }

      setTaskRuntime((current) => {
        const status = next.status ?? current.status;
        const snapshot = {
          ...current,
          ...next,
          status,
          taskId: next.taskId ?? current.taskId,
          message: next.message ?? current.message,
          percent: next.percent ?? current.percent,
        };

        if (isTerminalStatus(snapshot.status)) {
          stopPolling();
        }

        return snapshot;
      });
    },
    [stopPolling],
  );

  const syncTaskStatus = useCallback(
    async (id: string) => {
      if (id !== activeTaskIdRef.current || pollingBusyRef.current) {
        return;
      }
      pollingBusyRef.current = true;

      try {
        const statusResponse = await getSchedulingTaskStatus(id);
        if (id !== activeTaskIdRef.current) {
          return;
        }
        const nextStatus = normalizeTaskStatus(
          typeof statusResponse.status === 'string' ? statusResponse.status : undefined,
        );

        applyTaskSnapshot({
          taskId: statusResponse.task_id || id,
          status: nextStatus,
          message:
            statusResponse.message ||
            statusResponse.error_message ||
            (nextStatus === 'completed'
              ? '排课完成'
              : nextStatus === 'failed'
                ? '排课失败'
                : nextStatus === 'running'
                  ? '排课进行中'
                  : nextStatus === 'cancelled_requested'
                    ? '取消请求已提交'
                    : '排课任务已创建'),
          percent: statusResponse.percent,
          source: 'poll',
        });

        if (statusResponse.result) {
          setResult(statusResponse.result);
          pushLog('success', '轮询返回结果', '状态接口已直接返回最终排课结果。');
        } else if (isTerminalStatus(nextStatus)) {
          const resultResponse = await getSchedulingTaskResult(id);
          if (id !== activeTaskIdRef.current) {
            return;
          }
          if (resultResponse.result) {
            setResult(resultResponse.result);
            pushLog('success', '结果已补齐', '任务结束后通过结果接口拉回最终数据。');
          }
        }
      } catch (fetchError) {
        pushLog('warning', '状态轮询失败', fetchError instanceof Error ? fetchError.message : '状态接口暂时不可用');
      } finally {
        pollingBusyRef.current = false;
      }
    },
    [applyTaskSnapshot, pushLog],
  );

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      void syncTaskStatus(id);
      pollingTimerRef.current = window.setInterval(() => {
        void syncTaskStatus(id);
      }, 1600);
    },
    [stopPolling, syncTaskStatus],
  );

  const loadInitialState = useCallback(async () => {
    setIsBooting(true);
    setError(null);

    try {
      const [configResult, selectedResult, statusResult, resultResponse] = await Promise.allSettled([
        getSchedulingConfig(),
        getSelectedCourses(),
        getSchedulingTaskStatus(),
        getSchedulingTaskResult(),
      ]);

      if (configResult.status === 'fulfilled') {
        setSavedConfig(configResult.value);
        setDraftConfig(configResult.value);
      } else {
        setError(configResult.reason instanceof Error ? configResult.reason.message : '配置加载失败');
      }

      if (selectedResult.status === 'fulfilled') {
        setSelectedCourses(selectedResult.value);
      }

      if (statusResult.status === 'fulfilled') {
        const statusValue = statusResult.value;
        const normalizedStatus = normalizeTaskStatus(
          typeof statusValue.status === 'string' ? statusValue.status : undefined,
        );
        applyTaskSnapshot({
          taskId: statusValue.task_id || null,
          status: normalizedStatus,
          message:
            statusValue.message ||
            (normalizedStatus === 'completed'
              ? '排课已完成'
              : normalizedStatus === 'running'
                ? '排课正在进行'
                : normalizedStatus === 'queued'
                  ? '排课任务排队中'
                  : '等待排课'),
          percent: statusValue.percent,
          source: 'poll',
        });
        if (statusValue.result) {
          setResult(statusValue.result);
        }
      }

      if (resultResponse.status === 'fulfilled') {
        setResult(resultResponse.value.result ?? null);
      }

      pushLog('info', '页面加载完成', '已同步配置、已选课程和最近一次排课状态。');
    } catch (initialError) {
      const message = initialError instanceof Error ? initialError.message : '初始化失败';
      setError(message);
      pushLog('error', '初始化失败', message);
    } finally {
      setIsBooting(false);
    }
  }, [applyTaskSnapshot, pushLog]);

  useEffect(() => {
    void loadInitialState();
  }, [loadInitialState]);

  useEffect(() => {
    if (taskRuntime.taskId && isActiveStatus(taskRuntime.status)) {
      if (pollingTimerRef.current === null) {
        startPolling(taskRuntime.taskId);
      }
      return;
    }

    stopPolling();
  }, [startPolling, stopPolling, taskRuntime.status, taskRuntime.taskId]);

  useEffect(() => {
    setConnectionState('connecting');

    const connection = subscribeSchedulingStream({
      onOpen: () => {
        setConnectionState('connected');
        pushLog('info', 'WebSocket 已连接', '开始订阅 scheduling 事件流。');
      },
      onClose: () => {
        setConnectionState('disconnected');
      },
      onError: () => {
        setConnectionState('error');
      },
      onMessage: (message: SchedulingWebSocketMessage) => {
        const currentTaskId = activeTaskIdRef.current;
        const payload = message.data as Record<string, unknown>;
        const eventTaskId = typeof payload.task_id === 'string' ? payload.task_id : null;

        // 所有任务事件都必须可归属；旧任务和无 task_id 的消息不能污染当前界面。
        if (message.type.startsWith('scheduling.')) {
          if (!currentTaskId || !eventTaskId || eventTaskId !== currentTaskId) {
            return;
          }
        }

        if (message.type === 'scheduling.started') {
          const started = payload as SchedulingStartedPayload;
          applyTaskSnapshot({
            taskId: (started.task_id as string) || currentTaskId,
            status: 'running',
            message: (started.message as string) || '排课任务开始执行',
            percent: 0,
            source: 'ws',
          });
          pushLog('info', '任务开始', (started.message as string) || '排课任务开始执行。');
          return;
        }

        if (message.type === 'scheduling.progress') {
          const progress = payload as SchedulingProgressPayload;
          const nextPercent = typeof progress.percent === 'number' ? progress.percent : undefined;
          applyTaskSnapshot({
            taskId: (progress.task_id as string) || currentTaskId,
            status: 'running',
            message: (progress.message as string) || '排课进行中',
            percent: nextPercent,
            source: 'ws',
          });
          pushLog('info', '进度更新', (progress.message as string) || '排课进行中。');
          return;
        }

        if (message.type === 'scheduling.completed') {
          const completed = payload as SchedulingCompletedPayload;
          applyTaskSnapshot({
            taskId: (completed.task_id as string) || currentTaskId,
            status: 'completed',
            message: (completed.message as string) || '排课完成',
            percent: 100,
            source: 'ws',
          });
          if (completed.result) {
            const normalizedResult = normalizeScheduleResult(completed.result);
            if (normalizedResult) {
              setResult(normalizedResult);
            }
          }
          pushLog('success', '任务完成', (completed.message as string) || '排课已完成。');
          stopPolling();
          return;
        }

        if (message.type === 'scheduling.failed') {
          const failed = payload as SchedulingFailedPayload;
          const messageText = (failed.error as string) || (failed.message as string) || '排课失败';
          applyTaskSnapshot({
            taskId: (failed.task_id as string) || currentTaskId,
            status: 'failed',
            message: messageText,
            source: 'ws',
          });
          setError(messageText);
          pushLog('error', '任务失败', messageText);
          stopPolling();
          return;
        }

        if (message.type === 'config.updated' && payload.config) {
          setSavedConfig(payload.config as SchedulingConfig);
          setDraftConfig(payload.config as SchedulingConfig);
        }
      },
    });

    if (!connection) {
      setConnectionState('error');
      return undefined;
    }

    return () => {
      connection.close();
      stopPolling();
    };
  }, [applyTaskSnapshot, pushLog, stopPolling]);

  const saveConfig = useCallback(async () => {
    setIsSaving(true);
    setError(null);

    try {
      const response = await updateSchedulingConfig(draftConfig);
      if (response.success === false) {
        throw new Error(response.message || '配置保存失败');
      }
      setSavedConfig(draftConfig);
      pushLog('success', '配置已保存', '排课参数已写入当前会话。');
    } catch (saveError) {
      const message = saveError instanceof Error ? saveError.message : '配置保存失败';
      setError(message);
      pushLog('error', '保存失败', message);
    } finally {
      setIsSaving(false);
    }
  }, [draftConfig, pushLog]);

  const executeScheduling = useCallback(async () => {
    setIsExecuting(true);
    setError(null);
    setNotice(null);

    try {
      if (isDirty) {
        const response = await updateSchedulingConfig(draftConfig);
        if (response.success === false) {
          throw new Error(response.message || '配置保存失败');
        }
        setSavedConfig(draftConfig);
      }

      resetLogs();
      setResult(null);
      activeTaskIdRef.current = null;
      pushLog('info', '开始执行', '任务准备中，正在提交排课请求。');

      const handle: SchedulingTaskHandle = await createSchedulingTask({
        course_ids: selectedCourses.map((course) => course.id),
      });

      applyTaskSnapshot({
        taskId: handle.task_id,
        status: handle.status,
        message: handle.message || (handle.status === 'completed' ? '排课完成' : '排课任务已创建'),
        percent: handle.percent,
        mode: handle.mode,
        source: handle.source,
      });

      if (handle.result) {
        setResult(handle.result);
      }

      if (handle.status === 'completed' && handle.result) {
        pushLog('success', '同步完成', '后端本次直接返回了完整排课结果。');
      } else if (handle.status === 'failed') {
        const failureMessage = handle.message || '排课失败';
        setError(failureMessage);
        pushLog('error', '任务失败', failureMessage);
      } else {
        pushLog('info', '任务已创建', `task_id = ${handle.task_id}`);
      }
    } catch (executeError) {
      const message = executeError instanceof Error ? executeError.message : '排课执行失败';
      setError(message);
      applyTaskSnapshot({
        status: 'failed',
        message,
        source: 'fallback',
      });
      pushLog('error', '执行失败', message);
    } finally {
      setIsExecuting(false);
    }
  }, [applyTaskSnapshot, draftConfig, isDirty, pushLog, resetLogs, selectedCourses]);

  const cancelScheduling = useCallback(async () => {
    if (!taskId) {
      return;
    }

    setIsCancelling(true);
    setError(null);
    setNotice(null);

    try {
      const response = await cancelSchedulingTask(taskId);
      if (response.success === false) {
        throw new Error(response.message || '取消任务失败');
      }

      const nextStatus = normalizeTaskStatus(
        typeof response.status === 'string' ? response.status : 'cancel_requested',
      );

      applyTaskSnapshot({
        taskId: response.task_id || taskId,
        status: nextStatus,
        message: response.message || (nextStatus === 'cancelled' ? '任务已取消' : '取消请求已提交'),
        source: 'fallback',
      });

      pushLog('warning', '取消请求', response.message || '排课任务正在取消。');
    } catch (cancelError) {
      const message = cancelError instanceof Error ? cancelError.message : '取消任务失败';
      setError(message);
      pushLog('error', '取消失败', message);
    } finally {
      setIsCancelling(false);
    }
  }, [applyTaskSnapshot, pushLog, taskId]);

  const refreshStatus = useCallback(async () => {
    if (!taskId) {
      const resultResponse = await getSchedulingTaskResult();
      if (resultResponse.result) {
        setResult(resultResponse.result);
      }
      return;
    }

    await syncTaskStatus(taskId);
  }, [syncTaskStatus, taskId]);

  const exportScheduleResult = useCallback(async () => {
    setIsExporting(true);
    setError(null);
    setNotice(null);

    try {
      const filename = await downloadScheduleResultExport();
      setNotice(`排课结果已导出：${filename}`);
      pushLog('success', '结果已导出', `文件 ${filename} 已下载到浏览器默认目录。`);
    } catch (exportError) {
      const message = exportError instanceof Error ? exportError.message : '导出排课结果失败';
      setError(message);
      pushLog('error', '导出失败', message);
    } finally {
      setIsExporting(false);
    }
  }, [pushLog]);

  // 类别仍为 nan 的课程不计入任何学分要求，排课引擎会静默丢弃它们。
  // 在启动前拦下来，而不是让用户排完才发现结果里少了课。
  const unsetCategoryCourses = selectedCourses.filter((course) =>
    isCategoryUnset(course.custom_category),
  );
  const hasUnsetCategory = unsetCategoryCourses.length > 0;

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.22em]"
             style={{ color: 'var(--text-muted)' }}>Scheduling Engine</p>
          <h2 className="mt-0.5 text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>智能排课</h2>
        </div>
        <Link
          to="/courses"
          className="btn-ghost"
        >
          <ArrowRight className="h-3.5 w-3.5 rotate-180" />
          返回课程
        </Link>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <MetricCard label="任务状态" value={statusLabel(taskRuntime.status)} hint={taskRuntime.message} tone="pine" />
        <MetricCard label="已选课程" value={String(selectedCourses.length)} hint="排课输入源" tone="teal" />
        <MetricCard
          label="连接状态"
          value={connectionLabel(connectionState)}
          hint={connectionState === 'connected' ? '实时推送可用' : '轮询兜底中'}
          tone="sand"
        />
      </div>

      {hasUnsetCategory && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border px-4 py-3 text-sm"
          style={{ borderColor: 'var(--danger-border)', background: 'var(--danger-bg)', color: 'var(--danger-text)' }}
        >
          <span className="font-medium">
            {unsetCategoryCourses.length} 门课程未设置类别，无法开始排课
          </span>
          <span className="font-mono text-[11px] opacity-80">
            {unsetCategoryCourses.map((course) => course.course.course_code).join('、')}
          </span>
          <Link to="/courses" className="btn-ghost ml-auto">
            去设置类别
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      )}

      <div className="grid gap-4 2xl:grid-cols-[1.08fr_0.92fr]">
        <div className="space-y-4">
          <SchedulingConfigPanel
            value={draftConfig}
            campuses={availableCampuses}
            isDirty={isDirty}
            isSaving={isSaving}
            onChange={setDraftConfig}
            onSave={saveConfig}
            onReset={() => setDraftConfig(savedConfig)}
          />

          <SchedulingActionBar
            selectedCount={selectedCourses.length}
            taskStatus={taskRuntime.status}
            taskId={taskRuntime.taskId}
            connectionState={connectionState}
            isExecuting={isExecuting || isBooting}
            isCancelling={isCancelling}
            blockedReason={
              hasUnsetCategory
                ? `${unsetCategoryCourses.length} 门课程未设置类别，请先在课程工作台完成设置`
                : null
            }
            onExecute={executeScheduling}
            onCancel={cancelScheduling}
            onRefresh={refreshStatus}
          />

          <SchedulingProgressPanel
            taskStatus={taskRuntime.status}
            message={taskRuntime.message}
            percent={taskRuntime.percent}
            error={error}
            logs={logs}
          />
        </div>

        <div className="space-y-4">
          <SchedulingResultPanel
            result={result}
            courses={resultCourses}
            action={
              <button
                type="button"
                onClick={() => {
                  void exportScheduleResult();
                }}
                disabled={!result || isExporting}
                className="btn-ghost"
              >
                {isExporting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Download className="h-4 w-4" />}
                导出 Excel
              </button>
            }
          />
          <div className="rounded-lg border px-4 py-3 text-xs leading-5"
               style={{ borderColor: 'var(--border-subtle)', color: 'var(--text-muted)' }}>
            <div className="flex items-center gap-2">
              {connectionState === 'connected'
                ? <Wifi className="h-3.5 w-3.5 text-emerald-500" />
                : <WifiOff className="h-3.5 w-3.5 text-rose-400" />}
              {connectionState === 'connected' ? 'WS 实时推送已就绪。' : 'WS 不可用，HTTP 轮询兜底中。'}
            </div>
          </div>
        </div>
      </div>

      <AcademicTimetable
        courses={resultCourses}
        title="周课表"
        description="排课结果可视化。导出 Excel 只含课程明细，不含本表。"
      />

      {error ? (
        <div role="alert" className="flex items-start gap-2 rounded-lg border px-4 py-3 text-sm"
             style={{ borderColor: 'var(--danger-border)', background: 'var(--danger-bg)', color: 'var(--danger-text)' }}>
          {error}
        </div>
      ) : null}

      {notice ? (
        <div role="status" aria-live="polite" className="flex items-start gap-2 rounded-lg border px-4 py-3 text-sm"
             style={{ borderColor: 'var(--success-border)', background: 'var(--success-bg)', color: 'var(--success-text)' }}>
          {notice}
        </div>
      ) : null}
    </div>
  );
}

export default SchedulingPage;
