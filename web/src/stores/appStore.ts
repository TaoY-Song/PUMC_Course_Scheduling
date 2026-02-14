/**
 * Zustand状态管理
 * 全局应用状态管理
 */
import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import type {
  Course,
  SelectedCourse,
  SchedulingConfig,
  ScheduleResult,
  CreditRequirement,
  SchedulingProgress,
  SchedulingStatus,
} from '../types/models';

// ==================== 状态接口 ====================

interface AppState {
  // ===== 课程数据 =====
  courses: Course[];
  selectedCourses: SelectedCourse[];
  
  // ===== 排课状态 =====
  config: SchedulingConfig;
  progress: SchedulingProgress;
  lastResult: ScheduleResult | null;
  
  // ===== 学分 =====
  creditRequirements: CreditRequirement[];
  
  // ===== UI状态 =====
  isLoading: boolean;
  error: string | null;
  
  // ===== Actions =====
  // 课程管理
  setCourses: (courses: Course[]) => void;
  setSelectedCourses: (courses: SelectedCourse[]) => void;
  addSelectedCourse: (course: SelectedCourse) => void;
  removeSelectedCourse: (courseId: string) => void;
  updateSelectedCourse: (courseId: string, updates: Partial<SelectedCourse>) => void;
  
  // 排课配置
  setConfig: (config: SchedulingConfig) => void;
  updateConfig: (updates: Partial<SchedulingConfig>) => void;
  
  // 排课进度
  setProgress: (progress: SchedulingProgress) => void;
  setSchedulingStatus: (status: SchedulingStatus, message?: string, percent?: number) => void;
  
  // 排课结果
  setLastResult: (result: ScheduleResult | null) => void;
  
  // 学分
  setCreditRequirements: (requirements: CreditRequirement[]) => void;
  
  // UI状态
  setLoading: (isLoading: boolean) => void;
  setError: (error: string | null) => void;
  clearError: () => void;
  
  // 重置
  reset: () => void;
}

// ==================== 初始状态 ====================

const initialConfig: SchedulingConfig = {
  credit_constraint_mode: 'OPTIMAL',
  campus_conflict_mode: 'DAILY',
  max_solutions: 1,
  time_limit: 60,
  credit_overflow_ratio: 0.1,
  campus_transition_time: 30,
};

const initialProgress: SchedulingProgress = {
  status: 'idle',
  message: '就绪',
};

const initialState = {
  courses: [],
  selectedCourses: [],
  config: initialConfig,
  progress: initialProgress,
  lastResult: null,
  creditRequirements: [],
  isLoading: false,
  error: null,
};

// ==================== Store创建 ====================

export const useAppStore = create<AppState>()(
  devtools(
    (set, get) => ({
      ...initialState,
      
      // ===== 课程管理Actions =====
      setCourses: (courses) => set({ courses }),
      
      setSelectedCourses: (selectedCourses) => set({ selectedCourses }),
      
      addSelectedCourse: (course) => {
        const { selectedCourses } = get();
        const courses = selectedCourses || [];
        const exists = courses.some(
          (c) => c.course.course_code === course.course.course_code &&
                 c.class_index === course.class_index
        );
        if (!exists) {
          set({ selectedCourses: [...courses, course] });
        }
      },
      
      removeSelectedCourse: (courseId) => {
        const { selectedCourses } = get();
        const courses = selectedCourses || [];
        set({
          selectedCourses: courses.filter((c) => c.id !== courseId),
        });
      },
      
      updateSelectedCourse: (courseId, updates) => {
        const { selectedCourses } = get();
        set({
          selectedCourses: selectedCourses.map((c) =>
            c.id === courseId ? { ...c, ...updates } : c
          ),
        });
      },
      
      // ===== 排课配置Actions =====
      setConfig: (config) => set({ config }),
      
      updateConfig: (updates) => {
        const { config } = get();
        set({ config: { ...config, ...updates } });
      },
      
      // ===== 排课进度Actions =====
      setProgress: (progress) => set({ progress }),
      
      setSchedulingStatus: (status, message, percent) => {
        const { progress } = get();
        set({
          progress: {
            ...progress,
            status,
            message: message || progress.message,
            percent,
          },
        });
      },
      
      // ===== 排课结果Actions =====
      setLastResult: (lastResult) => set({ lastResult }),
      
      // ===== 学分Actions =====
      setCreditRequirements: (creditRequirements) => set({ creditRequirements }),
      
      // ===== UI状态Actions =====
      setLoading: (isLoading) => set({ isLoading }),
      
      setError: (error) => set({ error }),
      
      clearError: () => set({ error: null }),
      
      // ===== 重置 =====
      reset: () => set(initialState),
    }),
    {
      name: 'pumc-app-store',
    }
  )
);

// ==================== 选择器Hooks ====================

export const useCourses = () => useAppStore((state) => state.courses);
export const useSelectedCourses = () => useAppStore((state) => state.selectedCourses);
export const useConfig = () => useAppStore((state) => state.config);
export const useProgress = () => useAppStore((state) => state.progress);
export const useLastResult = () => useAppStore((state) => state.lastResult);
export const useCreditRequirements = () => useAppStore((state) => state.creditRequirements);
export const useIsLoading = () => useAppStore((state) => state.isLoading);
export const useError = () => useAppStore((state) => state.error);
