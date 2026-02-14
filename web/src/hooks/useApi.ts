import { useCallback, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import * as coursesApi from '../api/courses';
import * as schedulingApi from '../api/scheduling';
import type { TimeSlot, SchedulingConfig } from '../types/models';

/**
 * 课程数据Hook
 */
export const useCourses = () => {
  const { courses, selectedCourses, setCourses, setSelectedCourses, addSelectedCourse, removeSelectedCourse, setLoading, setError, clearError } = useAppStore();
  const [isLoading, setIsLoading] = useState(false);

  // 加载课程文件
  const loadCourses = useCallback(async (file: File) => {
    setIsLoading(true);
    setLoading(true);
    clearError();
    try {
      const response = await coursesApi.loadCourses(file);
      const loadedCourses = await coursesApi.getCourses();
      
      if (loadedCourses && loadedCourses.length > 0) {
        setCourses(loadedCourses);
      }
      
      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : '加载课程失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  }, [setCourses, setLoading, setError, clearError]);

  // 获取课程列表
  const fetchCourses = useCallback(async () => {
    setIsLoading(true);
    setLoading(true);
    try {
      const loadedCourses = await coursesApi.getCourses();
      setCourses(loadedCourses);
      return loadedCourses;
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取课程列表失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
      setLoading(false);
    }
  }, [setCourses, setLoading, setError]);

  // 搜索课程
  const searchCourses = useCallback(async (query: string) => {
    setIsLoading(true);
    try {
      return await coursesApi.searchCourses(query);
    } catch (error) {
      const message = error instanceof Error ? error.message : '搜索课程失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setError]);

  // 获取课程详情
  const fetchCourse = useCallback(async (courseCode: string) => {
    setIsLoading(true);
    try {
      return await coursesApi.getCourse(courseCode);
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取课程详情失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setError]);

  // 获取已选课程
  const fetchSelectedCourses = useCallback(async () => {
    setIsLoading(true);
    try {
      const selected = await coursesApi.getSelectedCourses();
      setSelectedCourses(selected);
      return selected;
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取已选课程失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setSelectedCourses, setError]);

  // 添加课程到已选
  const addCourse = useCallback(async (courseCode: string, classIndex: number = 0) => {
    setIsLoading(true);
    try {
      const selected = await coursesApi.addSelectedCourse(courseCode, classIndex);
      addSelectedCourse(selected);
      return selected;
    } catch (error) {
      const err = error as { response?: { data?: { detail?: string } } };
      const message = err?.response?.data?.detail || (error instanceof Error ? error.message : '添加课程失败');
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [addSelectedCourse, setError]);

  // 移除已选课程
  const removeCourse = useCallback(async (courseId: string) => {
    console.log('[removeCourse] courseId:', courseId);
    setIsLoading(true);
    try {
      await coursesApi.removeSelectedCourse(courseId);
      removeSelectedCourse(courseId);
    } catch (error) {
      const err = error as { response?: { data?: { detail?: string } } };
      const message = err?.response?.data?.detail || (error instanceof Error ? error.message : '移除课程失败');
      console.error('[removeCourse] error:', error);
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [removeSelectedCourse, setError]);

  // 添加时间段
  const addTimeSlot = useCallback(async (courseId: string, timeSlot: TimeSlot) => {
    setIsLoading(true);
    try {
      const updated = await coursesApi.addTimeSlot(courseId, timeSlot);
      // 更新已选课程列表
      const selected = await coursesApi.getSelectedCourses();
      setSelectedCourses(selected);
      return updated;
    } catch (error) {
      const message = error instanceof Error ? error.message : '添加时间段失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setSelectedCourses, setError]);

  // 更新课程类别
  const updateCategory = useCallback(async (courseId: string, category: string) => {
    setIsLoading(true);
    try {
      const updated = await coursesApi.updateCourseCategory(courseId, category);
      // 更新已选课程列表
      const selected = await coursesApi.getSelectedCourses();
      setSelectedCourses(selected);
      return updated;
    } catch (error) {
      const message = error instanceof Error ? error.message : '更新类别失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setSelectedCourses, setError]);

  return {
    courses,
    selectedCourses,
    isLoading,
    loadCourses,
    fetchCourses,
    searchCourses,
    fetchCourse,
    fetchSelectedCourses,
    addCourse,
    removeCourse,
    addTimeSlot,
    updateCategory,
  };
};

/**
 * 排课配置Hook
 */
export const useSchedulingConfig = () => {
  const { config, setConfig, updateConfig, setError } = useAppStore();
  const [isLoading, setIsLoading] = useState(false);

  // 获取配置
  const fetchConfig = useCallback(async () => {
    setIsLoading(true);
    try {
      const currentConfig = await schedulingApi.getSchedulingConfig();
      setConfig(currentConfig);
      return currentConfig;
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取配置失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setConfig, setError]);

  // 保存配置
  const saveConfig = useCallback(async (newConfig: SchedulingConfig) => {
    setIsLoading(true);
    try {
      await schedulingApi.configureScheduling(newConfig);
      setConfig(newConfig);
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存配置失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setConfig, setError]);

  // 更新单个配置项
  const updateConfigField = useCallback(async (updates: Partial<SchedulingConfig>) => {
    updateConfig(updates);
    // 立即保存到后端
    const { config: currentConfig } = useAppStore.getState();
    try {
      await schedulingApi.configureScheduling(currentConfig);
    } catch (error) {
      // 配置保存失败不回滚，因为本地已更新
      console.error('Failed to sync config to backend:', error);
    }
  }, [updateConfig]);

  return {
    config,
    isLoading,
    fetchConfig,
    saveConfig,
    updateConfig: updateConfigField,
  };
};

/**
 * 学分状态Hook
 */
export const useCredits = () => {
  const { creditRequirements, setCreditRequirements, setError } = useAppStore();
  const [isLoading, setIsLoading] = useState(false);

  // 获取学分状态
  const fetchCreditStatus = useCallback(async () => {
    setIsLoading(true);
    try {
      const requirements = await schedulingApi.getCreditStatus();
      setCreditRequirements(requirements);
      return requirements;
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取学分状态失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setCreditRequirements, setError]);

  return {
    creditRequirements,
    isLoading,
    fetchCreditStatus,
  };
};

/**
 * 排课结果Hook
 */
export const useScheduleResult = () => {
  const { lastResult, setLastResult, setError } = useAppStore();
  const [isLoading, setIsLoading] = useState(false);

  // 获取最后结果
  const fetchLastResult = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await schedulingApi.getLastResult();
      setLastResult(result);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取排课结果失败';
      setError(message);
      throw error;
    } finally {
      setIsLoading(false);
    }
  }, [setLastResult, setError]);

  return {
    lastResult,
    isLoading,
    fetchLastResult,
  };
};

/**
 * 导入导出Hook
 */
export const useImportExport = () => {
  const [isExporting, setIsExporting] = useState(false);
  const [isImporting, setIsImporting] = useState(false);
  const { setError } = useAppStore();

  // 导出已选课程
  const exportSelectedCourses = useCallback(async (filePath: string) => {
    setIsExporting(true);
    try {
      return await schedulingApi.exportSelectedCourses(filePath);
    } catch (error) {
      const message = error instanceof Error ? error.message : '导出失败';
      setError(message);
      throw error;
    } finally {
      setIsExporting(false);
    }
  }, [setError]);

  // 导出排课结果
  const exportScheduleResult = useCallback(async (filePath: string) => {
    setIsExporting(true);
    try {
      return await schedulingApi.exportScheduleResult(filePath);
    } catch (error) {
      const message = error instanceof Error ? error.message : '导出失败';
      setError(message);
      throw error;
    } finally {
      setIsExporting(false);
    }
  }, [setError]);

  // 导入已选课程
  const importSelectedCourses = useCallback(async (file: File) => {
    setIsImporting(true);
    try {
      return await schedulingApi.importSelectedCourses(file);
    } catch (error) {
      const message = error instanceof Error ? error.message : '导入失败';
      setError(message);
      throw error;
    } finally {
      setIsImporting(false);
    }
  }, [setError]);

  return {
    isExporting,
    isImporting,
    exportSelectedCourses,
    exportScheduleResult,
    importSelectedCourses,
  };
};

export default useCourses;