/**
 * API响应类型定义
 */

import type {
  Course,
  SelectedCourse,
  ScheduleResult,
  CreditRequirement,
  SchedulingConfig,
} from './models';

// ==================== 通用响应 ====================

export interface ApiResponse<T = unknown> {
  success: boolean;
  message: string;
  data?: T;
}

// ==================== 课程API响应 ====================

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

// ==================== 排课API响应 ====================

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

// ==================== 学分API响应 ====================

export interface GetCreditStatusResponse {
  requirements: CreditRequirement[];
}

export interface UpdateCreditSettingsResponse {
  success: boolean;
  message: string;
}

// ==================== 导入导出API响应 ====================

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

// ==================== WebSocket消息 ====================

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

export interface ConfigUpdatedMessage {
  config: SchedulingConfig;
  timestamp: number;
}

export interface CoursesLoadedMessage {
  count: number;
  timestamp: number;
}

// ==================== 错误响应 ====================

export interface ApiError {
  detail: string;
  status_code: number;
}
