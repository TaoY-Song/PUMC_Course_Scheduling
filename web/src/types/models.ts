export type CreditConstraintMode = 'REQUIRED' | 'OPTIMAL';
export type CampusConflictMode = 'DAILY' | 'PERIOD' | 'DISABLED';
export type SchedulingStatus =
  | 'idle'
  | 'configuring'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled';

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
  is_online: boolean;
  time_slots: TimeSlot[];
}

export interface SchedulingConfig {
  credit_constraint_mode: CreditConstraintMode;
  campus_conflict_mode: CampusConflictMode;
  max_solutions: number;
  time_limit: number;
  credit_overflow: number;
}

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

export interface SchedulingProgress {
  status: SchedulingStatus;
  message: string;
  percent?: number;
}

export interface AppState {
  courses: Course[];
  selectedCourses: SelectedCourse[];
  config: SchedulingConfig;
  progress: SchedulingProgress;
  lastResult: ScheduleResult | null;
  creditRequirements: CreditRequirement[];
  isLoading: boolean;
  error: string | null;
}
