/**
 * API请求参数类型定义
 */

import type {
  TimeSlot,
  SchedulingConfig,
  CreditSettings,
} from '../types/models';

// ==================== 课程API请求 ====================

export interface LoadCoursesRequest {
  file: File;
}

export interface SearchCoursesRequest {
  q: string;
}

export interface AddSelectedCourseRequest {
  course_code: string;
  class_index: number;
}

export interface AddTimeSlotRequest {
  time_slot: TimeSlot;
}

export interface UpdateCourseCategoryRequest {
  category: string;
}

// ==================== 排课API请求 ====================

export interface ConfigureSchedulingRequest {
  config: SchedulingConfig;
}

export interface ExecuteSchedulingRequest {
  course_ids: string[];
}

// ==================== 学分API请求 ====================

export interface UpdateCreditSettingsRequest {
  settings: CreditSettings;
}

// ==================== 导入导出API请求 ====================

export interface ExportCoursesRequest {
  file_path: string;
}

export interface ExportScheduleResultRequest {
  file_path: string;
}

export interface ImportCoursesRequest {
  file: File;
}

// ==================== WebSocket请求 ====================

export interface SubscribeRequest {
  action: 'subscribe';
  event_types: string[];
}

export interface UnsubscribeRequest {
  action: 'unsubscribe';
  event_types: string[];
}

export interface PingRequest {
  action: 'ping';
}
