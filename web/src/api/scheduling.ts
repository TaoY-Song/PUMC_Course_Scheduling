/**
 * 排课算法API封装
 */
import { apiClient } from './client';
import type {
  GetConfigResponse,
  ConfigureSchedulingResponse,
  ExecuteSchedulingResponse,
  GetSchedulingStatusResponse,
  CancelSchedulingResponse,
  GetCreditStatusResponse,
  ApiResponse,
} from '../types/api';
import type {
  SchedulingConfig,
  ScheduleResult,
  CreditRequirement,
} from '../types/models';

/**
 * 获取当前排课配置
 */
export const getSchedulingConfig = async (): Promise<SchedulingConfig> => {
  const response = await apiClient.get<GetConfigResponse>('/api/scheduling/config');
  return response.data.config;
};

/**
 * 配置排课参数
 */
export const configureScheduling = async (
  config: SchedulingConfig
): Promise<ApiResponse> => {
  const response = await apiClient.post<ConfigureSchedulingResponse>(
    '/api/scheduling/config',
    { config }
  );
  return response.data;
};

/**
 * 执行排课算法
 */
export const executeScheduling = async (
  courseIds: string[] = []
): Promise<ExecuteSchedulingResponse> => {
  const response = await apiClient.post<ExecuteSchedulingResponse>(
    '/api/scheduling/execute',
    { course_ids: courseIds }
  );
  return response.data;
};

/**
 * 获取排课状态
 */
export const getSchedulingStatus = async (): Promise<string> => {
  const response = await apiClient.get<GetSchedulingStatusResponse>('/api/scheduling/status');
  return response.data.status;
};

/**
 * 取消排课
 */
export const cancelScheduling = async (): Promise<ApiResponse> => {
  const response = await apiClient.post<CancelSchedulingResponse>('/api/scheduling/cancel');
  return response.data;
};

/**
 * 获取最后一次排课结果
 */
export const getLastResult = async (): Promise<ScheduleResult | null> => {
  const response = await apiClient.get<{ result: ScheduleResult | null }>('/api/scheduling/result');
  return response.data.result;
};

/**
 * 获取学分完成情况
 */
export const getCreditStatus = async (): Promise<CreditRequirement[]> => {
  const response = await apiClient.get<GetCreditStatusResponse>('/api/credits');
  return response.data.requirements;
};

/**
 * 获取学分要求设置
 */
export const getCreditSettings = async (): Promise<Record<string, number>> => {
  const response = await apiClient.get<Record<string, number>>('/api/credits/settings');
  return response.data;
};

/**
 * 更新学分要求设置
 */
export const updateCreditSettings = async (
  requirements: Record<string, number>
): Promise<ApiResponse> => {
  const response = await apiClient.post<ApiResponse>(
    '/api/credits/settings',
    requirements
  );
  return response.data;
};

/**
 * 导出已选课程
 */
export const exportSelectedCourses = async (
  filePath: string
): Promise<ApiResponse> => {
  const formData = new FormData();
  formData.append('file_path', filePath);
  
  const response = await apiClient.post<ApiResponse>(
    '/api/export/selected-courses',
    formData
  );
  return response.data;
};

/**
 * 导出排课结果
 */
export const exportScheduleResult = async (
  filePath: string
): Promise<ApiResponse> => {
  const formData = new FormData();
  formData.append('file_path', filePath);
  
  const response = await apiClient.post<ApiResponse>(
    '/api/export/schedule-result',
    formData
  );
  return response.data;
};

/**
 * 导入已选课程
 */
export const importSelectedCourses = async (
  file: File
): Promise<ApiResponse<SelectedCourse[]>> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await apiClient.post<ApiResponse<SelectedCourse[]>>(
    '/api/import/selected-courses',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

// 类型定义
interface SelectedCourse {
  id: string;
  course: {
    course_code: string;
    course_name: string;
  };
}
