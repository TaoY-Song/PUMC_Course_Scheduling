/**
 * 数据模型类型定义
 * 对应后端DTO的前端类型
 */

// ==================== 枚举类型 ====================

export type CreditConstraintMode = 'REQUIRED' | 'OPTIMAL';
export type CampusConflictMode = 'DAILY' | 'PERIOD' | 'DISABLED';
export type SchedulingStatus = 'idle' | 'configuring' | 'running' | 'completed' | 'failed' | 'cancelled';

// ==================== 基础模型 ====================

export interface TimeSlot {
  day_of_week: number;
  start_period: number;
  end_period: number;
  weeks: number[];
}

export interface Course {
  course_code: string;
  course_name: string;
  department: string;
  category: string;
  credits: number;
  hours: number;
  teacher?: string;
  campus?: string;
  is_online: boolean;
  time_slots: TimeSlot[];
  class_index: number;
}

export interface SelectedCourse {
  id: string;
  course: Course;
  class_index: number;
  custom_category?: string;
  is_category_locked: boolean;
  time_slots: TimeSlot[];
}

// ==================== 配置模型 ====================

export interface SchedulingConfig {
  credit_constraint_mode: CreditConstraintMode;
  campus_conflict_mode: CampusConflictMode;
  max_solutions: number;
  time_limit: number;
  credit_overflow_ratio: number;
  campus_transition_time: number;
}

// ==================== 学分模型 ====================

export interface CreditRequirement {
  category: string;
  required_credits: number;
  completed_credits: number;
  remaining_credits: number;
  is_completed: boolean;
  courses: SelectedCourse[];
}

export interface CreditSettings {
  requirements: Record<string, number>;
}

// ==================== 排课结果模型 ====================

export interface ScheduleScore {
  total_score: number;
  credit_match_score: number;
  time_quality_score: number;
}

export interface ConflictInfo {
  course1_code: string;
  course2_code: string;
  conflict_type: string;
  description: string;
}

export interface ScheduleResult {
  id: string;
  selected_courses: SelectedCourse[];
  score: ScheduleScore;
  conflicts: ConflictInfo[];
  execution_time: number;
  timestamp: string;
}

// ==================== UI状态模型 ====================

export interface SchedulingProgress {
  status: SchedulingStatus;
  message: string;
  percent?: number;
}

export interface AppState {
  // 课程数据
  courses: Course[];
  selectedCourses: SelectedCourse[];
  
  // 排课状态
  config: SchedulingConfig;
  progress: SchedulingProgress;
  lastResult: ScheduleResult | null;
  
  // 学分
  creditRequirements: CreditRequirement[];
  
  // UI状态
  isLoading: boolean;
  error: string | null;
}
