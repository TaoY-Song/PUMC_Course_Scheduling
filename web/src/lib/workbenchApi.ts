import type { AxiosError, AxiosResponse } from 'axios';
import { apiClient } from '../api/client';
import type {
  ApiResponse,
  LoadCoursesResponse,
  SchedulingTaskCancelResponse,
  SchedulingTaskCreateRequest,
  SchedulingTaskHandle,
  SchedulingTaskResultResponse,
  SchedulingTaskStatus,
  SchedulingTaskStatusResponse,
  SupplementRunData,
  SchedulingWebSocketMessage,
} from '../types/api';
import type {
  Course,
  CreditRequirement,
  ScheduleResult,
  SchedulingConfig,
  SelectedCourse,
  TimeSlot,
} from '../types/models';

type UnknownRecord = Record<string, unknown>;

const DEFAULT_SCHEDULING_CONFIG: SchedulingConfig = {
  credit_constraint_mode: 'OPTIMAL',
  campus_conflict_mode: 'DAILY',
  max_solutions: 1,
  time_limit: 60,
  credit_overflow_ratio: 0.1,
  campus_transition_time: 30,
};

const SCHEDULING_WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : [];
}

function extractArray<T>(value: unknown, keys: string[]): T[] {
  if (Array.isArray(value)) {
    return value as T[];
  }

  if (!value || typeof value !== 'object') {
    return [];
  }

  const record = value as UnknownRecord;
  for (const key of keys) {
    const candidate = record[key];
    if (Array.isArray(candidate)) {
      return candidate as T[];
    }
  }

  return [];
}

function extractObject<T>(value: unknown, keys: string[]): T | null {
  if (!value || typeof value !== 'object') {
    return null;
  }

  const record = value as UnknownRecord;
  for (const key of keys) {
    const candidate = record[key];
    if (candidate && typeof candidate === 'object' && !Array.isArray(candidate)) {
      return candidate as T;
    }
  }

  return null;
}

function isRecord(value: unknown): value is UnknownRecord {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function unwrapData<T>(value: unknown, keys: string[] = ['data', 'result']): T | null {
  if (value === null || value === undefined) {
    return null;
  }

  if (isRecord(value)) {
    for (const key of keys) {
      const candidate = value[key];
      if (candidate !== undefined && candidate !== null) {
        return candidate as T;
      }
    }
  }

  return value as T;
}

function coerceNumber(value: unknown, fallback: number): number {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === 'string') {
    const parsed = Number(value);
    if (Number.isFinite(parsed)) {
      return parsed;
    }
  }
  return fallback;
}

function coerceString(value: unknown, fallback = ''): string {
  if (typeof value === 'string') {
    return value;
  }
  if (value === null || value === undefined) {
    return fallback;
  }
  return String(value);
}

function isMissingEndpointError(error: unknown): boolean {
  if (!error || typeof error !== 'object') {
    return false;
  }

  const axiosError = error as AxiosError<unknown>;
  const status = axiosError.response?.status;
  return status === 404 || status === 405 || status === 501;
}

async function requestWithFallback<T>(
  attempts: Array<() => Promise<AxiosResponse<unknown>>>,
  parser: (value: unknown) => T,
): Promise<T> {
  let lastError: unknown = null;

  for (let index = 0; index < attempts.length; index += 1) {
    try {
      const response = await attempts[index]();
      return parser(response.data);
    } catch (error) {
      lastError = error;
      if (!isMissingEndpointError(error) || index === attempts.length - 1) {
        throw error;
      }
    }
  }

  throw lastError instanceof Error ? lastError : new Error('Request failed');
}

function normalizeSchedulingConfig(value: unknown): SchedulingConfig {
  const source = unwrapData<UnknownRecord>(value) ?? {};
  return {
    credit_constraint_mode: source.credit_constraint_mode === 'REQUIRED' ? 'REQUIRED' : 'OPTIMAL',
    campus_conflict_mode:
      source.campus_conflict_mode === 'PERIOD'
        ? 'PERIOD'
        : source.campus_conflict_mode === 'DISABLED'
          ? 'DISABLED'
          : 'DAILY',
    max_solutions: Math.max(1, coerceNumber(source.max_solutions, DEFAULT_SCHEDULING_CONFIG.max_solutions)),
    time_limit: Math.max(1, coerceNumber(source.time_limit, DEFAULT_SCHEDULING_CONFIG.time_limit)),
    credit_overflow_ratio: Math.min(
      1,
      Math.max(0, coerceNumber(source.credit_overflow_ratio, DEFAULT_SCHEDULING_CONFIG.credit_overflow_ratio)),
    ),
    campus_transition_time: Math.max(
      0,
      coerceNumber(source.campus_transition_time, DEFAULT_SCHEDULING_CONFIG.campus_transition_time),
    ),
  };
}

function normalizeScheduleResult(value: unknown): ScheduleResult | null {
  const source = unwrapData<UnknownRecord>(value, ['data', 'result']) ?? null;
  if (!source) {
    return null;
  }

  const selectedCourses = extractArray<SelectedCourse>(source.selected_courses, ['selected_courses']);
  const scoreSource = isRecord(source.score) ? source.score : {};
  const conflicts = extractArray<ScheduleResult['conflicts'][number]>(source.conflicts, ['conflicts']);

  return {
    id: coerceString(source.id, `result-${Date.now()}`),
    selected_courses:
      selectedCourses.length > 0
        ? selectedCourses
        : Array.isArray(source.selected_courses)
          ? (source.selected_courses as SelectedCourse[])
          : [],
    score: {
      total_score: coerceNumber(scoreSource.total_score, 0),
      credit_match_score: coerceNumber(scoreSource.credit_match_score, 0),
      time_quality_score: coerceNumber(scoreSource.time_quality_score, 0),
    },
    conflicts,
    execution_time: coerceNumber(source.execution_time, 0),
    timestamp: coerceString(source.timestamp, new Date().toISOString()),
  };
}

function normalizeTaskStatus(value: unknown): SchedulingTaskStatus {
  const raw = coerceString(value, 'idle').toLowerCase();
  if (raw === 'pending' || raw === 'queued') {
    return 'queued';
  }
  if (raw === 'running' || raw === 'completed' || raw === 'failed' || raw === 'cancelled') {
    return raw;
  }
  if (raw === 'cancel_requested' || raw === 'cancelled_requested') {
    return 'cancelled_requested';
  }
  return 'idle';
}

function normalizeStatusResponse(value: unknown): SchedulingTaskStatusResponse {
  const source = unwrapData<UnknownRecord>(value, ['data', 'result']) ?? {};
  const result = normalizeScheduleResult(source.result);
  return {
    task_id: coerceString(source.task_id ?? source.taskId, ''),
    status: normalizeTaskStatus(source.status ?? source.state ?? 'idle'),
    message: coerceString(source.message ?? source.error_message ?? source.error, ''),
    percent: source.percent !== undefined ? coerceNumber(source.percent, 0) : undefined,
    result,
    error_message: source.error_message ? coerceString(source.error_message) : undefined,
    error: source.error ? coerceString(source.error) : undefined,
    selected_count: source.selected_count !== undefined ? coerceNumber(source.selected_count, 0) : undefined,
    course_count: source.course_count !== undefined ? coerceNumber(source.course_count, 0) : undefined,
    total_score: source.total_score !== undefined ? coerceNumber(source.total_score, 0) : undefined,
    timestamp:
      typeof source.timestamp === 'string' || typeof source.timestamp === 'number'
        ? source.timestamp
        : undefined,
  };
}

function normalizeTaskResultResponse(value: unknown): SchedulingTaskResultResponse {
  const source = unwrapData<UnknownRecord>(value, ['data', 'result']) ?? {};
  return {
    task_id: coerceString(source.task_id ?? source.taskId, ''),
    result: normalizeScheduleResult(source.result ?? source),
  };
}

function normalizeCancelResponse(value: unknown): SchedulingTaskCancelResponse {
  const source = unwrapData<UnknownRecord>(value, ['data']) ?? {};
  return {
    success: source.success !== undefined ? Boolean(source.success) : true,
    message: coerceString(source.message ?? '取消请求已提交'),
    task_id: source.task_id ? coerceString(source.task_id) : undefined,
    status: source.status ? normalizeTaskStatus(source.status) : undefined,
  };
}

function extractFilenameFromDisposition(value: string | undefined, fallback: string): string {
  if (!value) {
    return fallback;
  }

  const utf8Match = value.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    return decodeURIComponent(utf8Match[1]);
  }

  const plainMatch = value.match(/filename="?([^"]+)"?/i);
  if (plainMatch?.[1]) {
    return plainMatch[1];
  }

  return fallback;
}

function triggerBlobDownload(blob: Blob, filename: string) {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  window.URL.revokeObjectURL(url);
}

export async function healthCheck() {
  const response = await apiClient.get('/api/health');
  return response.data as { status: string; version?: string };
}

export async function loadCourses(file: File): Promise<LoadCoursesResponse> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<LoadCoursesResponse>('/api/courses/load', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  return response.data;
}

export async function getCourses(): Promise<Course[]> {
  const response = await apiClient.get('/api/courses');
  return extractArray<Course>(response.data, ['courses', 'data']);
}

export async function searchCourses(query: string): Promise<Course[]> {
  if (!query.trim()) {
    return getCourses();
  }

  const response = await apiClient.get('/api/courses/search', {
    params: { q: query.trim() },
  });

  return extractArray<Course>(response.data, ['courses', 'data']);
}

export async function getSelectedCourses(): Promise<SelectedCourse[]> {
  const response = await apiClient.get('/api/selected-courses');
  return asArray<SelectedCourse>(response.data);
}

export async function addSelectedCourse(courseCode: string, classIndex: number): Promise<SelectedCourse> {
  const formData = new FormData();
  formData.append('course_code', courseCode);
  formData.append('class_index', String(classIndex));

  const response = await apiClient.post('/api/selected-courses', formData);
  return extractObject<SelectedCourse>(response.data, ['data']) ?? (response.data as SelectedCourse);
}

export async function removeSelectedCourse(courseId: string): Promise<ApiResponse> {
  const response = await apiClient.delete('/api/selected-courses/' + courseId);
  return response.data as ApiResponse;
}

export async function clearSelectedCourses(): Promise<void> {
  await apiClient.delete('/api/selected-courses');
}

export async function addTimeSlot(courseId: string, timeSlot: TimeSlot): Promise<SelectedCourse> {
  const response = await apiClient.post(`/api/selected-courses/${courseId}/timeslots`, timeSlot);
  return extractObject<SelectedCourse>(response.data, ['data']) ?? (response.data as SelectedCourse);
}

export async function updateTimeSlot(
  courseId: string,
  timeSlotIndex: number,
  timeSlot: TimeSlot,
): Promise<SelectedCourse> {
  const response = await apiClient.put(`/api/selected-courses/${courseId}/timeslots/${timeSlotIndex}`, timeSlot);
  return extractObject<SelectedCourse>(response.data, ['data']) ?? (response.data as SelectedCourse);
}

export async function deleteTimeSlot(courseId: string, timeSlotIndex: number): Promise<SelectedCourse> {
  const response = await apiClient.delete(`/api/selected-courses/${courseId}/timeslots/${timeSlotIndex}`);
  return extractObject<SelectedCourse>(response.data, ['data']) ?? (response.data as SelectedCourse);
}

export async function updateSelectedCourseCategory(courseId: string, category: string): Promise<SelectedCourse> {
  const formData = new FormData();
  formData.append('category', category);

  const response = await apiClient.put(`/api/selected-courses/${courseId}/category`, formData);
  return extractObject<SelectedCourse>(response.data, ['data']) ?? (response.data as SelectedCourse);
}

export async function patchSelectedCourse(
  courseId: string,
  payload: Partial<Pick<SelectedCourse, 'custom_category' | 'is_category_locked'>> & {
    is_online?: boolean;
  },
): Promise<SelectedCourse> {
  const response = await apiClient.patch(`/api/selected-courses/${courseId}`, payload);
  return extractObject<SelectedCourse>(response.data, ['data']) ?? (response.data as SelectedCourse);
}

export async function importSelectedCourses(file: File): Promise<SelectedCourse[]> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post('/api/import/selected-courses', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });

  const direct = extractArray<SelectedCourse>(response.data, ['courses']);
  if (direct.length > 0) {
    return direct;
  }

  return extractArray<SelectedCourse>((response.data as UnknownRecord)?.data, ['courses']);
}

export async function getCreditStatus(): Promise<CreditRequirement[]> {
  const response = await apiClient.get('/api/credits');
  return extractArray<CreditRequirement>(response.data, ['requirements', 'data']);
}

export async function getCreditSettings(): Promise<Record<string, number>> {
  const response = await apiClient.get('/api/credits/settings');
  return (response.data as Record<string, number>) ?? {};
}

export async function updateCreditSettings(requirements: Record<string, number>): Promise<ApiResponse> {
  const response = await apiClient.post('/api/credits/settings', requirements);
  return response.data as ApiResponse;
}

export async function getSchedulingConfig(): Promise<SchedulingConfig> {
  const response = await apiClient.get('/api/scheduling/config');
  return normalizeSchedulingConfig(response.data);
}

export async function updateSchedulingConfig(config: SchedulingConfig): Promise<ApiResponse> {
  return requestWithFallback(
    [
      () => apiClient.post('/api/scheduling/config', config),
      () => apiClient.post('/api/scheduling/config', { config }),
    ],
    (value) => {
      const source = unwrapData<UnknownRecord>(value, ['data']) ?? {};
      return {
        success: source.success !== undefined ? Boolean(source.success) : true,
        message: coerceString(source.message ?? '排课配置已更新'),
        data: source.data,
      } as ApiResponse;
    },
  );
}

export async function createSchedulingTask(
  request: SchedulingTaskCreateRequest = {},
): Promise<SchedulingTaskHandle> {
  return requestWithFallback(
    [
      () => apiClient.post('/api/scheduling/execute', request),
      () => apiClient.post('/api/scheduling/tasks', request),
    ],
    (value) => {
      const source = unwrapData<UnknownRecord>(value, ['data', 'result']) ?? {};
      const result = normalizeScheduleResult(source.result ?? source);
      const taskId = coerceString(source.task_id ?? source.taskId, '');

      if (result) {
        return {
          task_id: taskId || `sync-${Date.now()}`,
          status: 'completed',
          message: coerceString(source.message ?? '排课完成'),
          percent: 100,
          result,
          mode: 'sync',
          source: 'sync',
          updated_at: coerceString(source.timestamp, new Date().toISOString()),
        };
      }

      if (source.success === false) {
        return {
          task_id: taskId || `task-${Date.now()}`,
          status: 'failed',
          message: coerceString(source.error_message ?? source.message ?? '排课失败'),
          mode: 'async',
          source: 'fallback',
          updated_at: coerceString(source.timestamp, new Date().toISOString()),
        };
      }

      return {
        task_id: taskId || `task-${Date.now()}`,
        status: normalizeTaskStatus(source.status ?? 'pending'),
        message: coerceString(source.message ?? '排课任务已创建'),
        percent: source.percent !== undefined ? coerceNumber(source.percent, 0) : undefined,
        result: source.result ? result : null,
        mode: taskId ? 'async' : 'sync',
        source: taskId ? 'fallback' : 'sync',
        updated_at: coerceString(source.timestamp, new Date().toISOString()),
      };
    },
  );
}

export async function getSchedulingTaskStatus(taskId?: string): Promise<SchedulingTaskStatusResponse> {
  if (!taskId) {
    const response = await apiClient.get('/api/scheduling/status');
    return normalizeStatusResponse(response.data);
  }

  return requestWithFallback(
    [
      () => apiClient.get(`/api/scheduling/status/${taskId}`),
      () => apiClient.get(`/api/scheduling/tasks/${taskId}`),
      () => apiClient.get('/api/scheduling/status'),
    ],
    (value) => normalizeStatusResponse(value),
  );
}

export async function getSchedulingTaskResult(taskId?: string): Promise<SchedulingTaskResultResponse> {
  if (!taskId) {
    const response = await apiClient.get('/api/scheduling/result');
    return normalizeTaskResultResponse(response.data);
  }

  return requestWithFallback(
    [
      () => apiClient.get(`/api/scheduling/result/${taskId}`),
      () => apiClient.get(`/api/scheduling/tasks/${taskId}/result`),
      () => apiClient.get('/api/scheduling/result'),
    ],
    (value) => normalizeTaskResultResponse(value),
  );
}

export async function cancelSchedulingTask(taskId?: string): Promise<SchedulingTaskCancelResponse> {
  if (!taskId) {
    const response = await apiClient.post('/api/scheduling/cancel');
    return normalizeCancelResponse(response.data);
  }

  return requestWithFallback(
    [
      () => apiClient.post(`/api/scheduling/cancel/${taskId}`),
      () => apiClient.post(`/api/scheduling/tasks/${taskId}/cancel`),
      () => apiClient.post('/api/scheduling/cancel'),
    ],
    (value) => normalizeCancelResponse(value),
  );
}

export async function downloadScheduleResultExport(): Promise<string> {
  const response = await apiClient.get('/api/export/schedule-result', {
    responseType: 'blob',
  });
  const fallback = `schedule_result_${new Date().toISOString().slice(0, 10)}.xlsx`;
  const filename = extractFilenameFromDisposition(response.headers['content-disposition'], fallback);
  triggerBlobDownload(response.data as Blob, filename);
  return filename;
}

export async function runSupplementTest(
  scheduleResultFile: File,
  courseListFile?: File,
): Promise<ApiResponse<SupplementRunData>> {
  const formData = new FormData();
  formData.append('schedule_result_file', scheduleResultFile);
  if (courseListFile) {
    formData.append('course_list_file', courseListFile);
  }

  const response = await apiClient.post<ApiResponse<SupplementRunData>>('/api/supplement/run', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
    timeout: 300000,
  });

  return response.data;
}

export function buildArtifactDownloadUrl(fileName: string): string {
  const base = apiClient.defaults.baseURL || '';
  return `${base}/api/export/download/${encodeURIComponent(fileName)}`;
}

export interface SchedulingStreamOptions {
  eventTypes?: string[];
  onMessage?: (message: SchedulingWebSocketMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
}

export interface SchedulingStreamConnection {
  socket: WebSocket;
  close: () => void;
  send: (payload: unknown) => void;
}

export function subscribeSchedulingStream(
  options: SchedulingStreamOptions = {},
): SchedulingStreamConnection | null {
  if (typeof window === 'undefined' || typeof WebSocket === 'undefined') {
    return null;
  }

  const socket = new WebSocket(SCHEDULING_WS_URL);
  const {
    eventTypes = ['scheduling.started', 'scheduling.progress', 'scheduling.completed', 'scheduling.failed'],
    onMessage,
    onOpen,
    onClose,
    onError,
  } = options;
  const subscriptions = new Set(eventTypes);

  socket.onopen = () => {
    onOpen?.();
    socket.send(
      JSON.stringify({
        action: 'subscribe',
        event_types: Array.from(subscriptions),
      }),
    );
  };

  socket.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data as string) as SchedulingWebSocketMessage;
      onMessage?.(message);
    } catch {
      // Ignore malformed payloads and keep the stream alive.
    }
  };

  socket.onerror = (error) => {
    onError?.(error);
  };

  socket.onclose = () => {
    onClose?.();
  };

  return {
    socket,
    close: () => socket.close(),
    send: (payload: unknown) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(JSON.stringify(payload));
      }
    },
  };
}
