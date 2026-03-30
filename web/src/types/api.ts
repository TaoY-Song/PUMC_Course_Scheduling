import type {
  Course,
  CreditRequirement,
  ScheduleResult,
  SchedulingConfig,
  SelectedCourse,
} from './models';

export interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data?: T;
}

export interface LoadCoursesResponse {
  success: boolean;
  message: string;
  course_count: number;
  courses: Course[];
  warnings: string[];
}

export interface GetCoursesResponse {
  courses: Course[];
}

export interface SearchCoursesResponse {
  courses: Course[];
}

export interface GetCourseResponse {
  course: Course;
}

export interface GetConfigResponse {
  config: SchedulingConfig;
}

export interface ConfigureSchedulingResponse {
  success: boolean;
  message: string;
}

export interface ExecuteSchedulingResponse {
  success: boolean;
  result?: ScheduleResult;
  error_message?: string;
}

export type SchedulingTaskStatus =
  | 'idle'
  | 'queued'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'cancelled_requested';

export type SchedulingTaskSource = 'ws' | 'poll' | 'sync' | 'fallback';

export interface SchedulingTaskHandle {
  task_id: string;
  status: SchedulingTaskStatus;
  message?: string;
  percent?: number;
  result?: ScheduleResult | null;
  mode: 'async' | 'sync';
  source: SchedulingTaskSource;
  updated_at?: string;
}

export interface SchedulingTaskCreateRequest {
  course_ids?: string[];
}

export interface SchedulingTaskStatusResponse {
  task_id?: string;
  status: SchedulingTaskStatus | string;
  message?: string;
  percent?: number;
  result?: ScheduleResult | null;
  error_message?: string;
  error?: string;
  selected_count?: number;
  course_count?: number;
  total_score?: number;
  timestamp?: string | number;
}

export interface SchedulingTaskResultResponse {
  task_id?: string;
  result?: ScheduleResult | null;
}

export interface SchedulingTaskCancelResponse {
  success: boolean;
  message: string;
  task_id?: string;
  status?: SchedulingTaskStatus | string;
}

export interface GetSchedulingStatusResponse {
  status: string;
}

export interface CancelSchedulingResponse {
  success: boolean;
  message: string;
}

export interface GetLastResultResponse {
  result: ScheduleResult | null;
}

export interface GetCreditStatusResponse {
  requirements: CreditRequirement[];
}

export interface UpdateCreditSettingsResponse {
  success: boolean;
  message: string;
}

export interface ExportResponse {
  success: boolean;
  message: string;
  file_path?: string;
}

export interface ImportResponse {
  success: boolean;
  message: string;
  courses?: SelectedCourse[];
}

export interface SupplementAddedCourse {
  code: string;
  name: string;
  credits: number;
  category: string;
  is_online: boolean;
}

export interface SupplementFailedCourse {
  code: string;
  name: string;
  reasons: string[];
}

export interface SupplementRunData {
  added_courses: SupplementAddedCourse[];
  failed_courses: SupplementFailedCourse[];
  stats: Record<string, number>;
  output_file_name?: string | null;
  log_file_name?: string | null;
  schedule_result_source?: string;
  course_list_source?: string;
  course_list_source_type?: 'session' | 'uploaded' | string;
}

export interface WebSocketMessage {
  type: string;
  data: unknown;
}

export interface SchedulingStartedMessage {
  course_count: number;
  timestamp: number;
}

export interface SchedulingProgressMessage {
  message: string;
  percent?: number;
  timestamp: number;
}

export interface SchedulingCompletedMessage {
  result: ScheduleResult;
  selected_count: number;
  total_score: number;
  timestamp: number;
}

export interface SchedulingFailedMessage {
  error: string;
  timestamp: number;
}

export interface SchedulingStartedPayload {
  task_id?: string;
  course_count?: number;
  message?: string;
  timestamp?: number | string;
}

export interface SchedulingProgressPayload {
  task_id?: string;
  message?: string;
  percent?: number;
  step?: string;
  timestamp?: number | string;
}

export interface SchedulingCompletedPayload {
  task_id?: string;
  result?: ScheduleResult;
  selected_count?: number;
  total_score?: number;
  message?: string;
  timestamp?: number | string;
}

export interface SchedulingFailedPayload {
  task_id?: string;
  error?: string;
  message?: string;
  timestamp?: number | string;
}

export interface ConfigUpdatedMessage {
  config: SchedulingConfig;
  timestamp: number;
}

export interface CoursesLoadedMessage {
  count: number;
  timestamp: number;
}

export interface SchedulingWebSocketMessage {
  type: string;
  data:
    | SchedulingStartedPayload
    | SchedulingProgressPayload
    | SchedulingCompletedPayload
    | SchedulingFailedPayload
    | ConfigUpdatedMessage
    | CoursesLoadedMessage
    | Record<string, unknown>;
}

export interface ApiError {
  detail: string;
  status_code: number;
}
