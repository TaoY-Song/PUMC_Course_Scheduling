/**
 * 课程管理API封装
 */
import { apiClient } from './client';
import type {
  LoadCoursesResponse,
  SearchCoursesResponse,
  GetCourseResponse,
  ApiResponse,
} from '../types/api';
import type {
  Course,
  SelectedCourse,
  TimeSlot,
} from '../types/models';

/**
 * 上传并加载课程Excel文件
 */
export const loadCourses = async (file: File): Promise<LoadCoursesResponse> => {
  const formData = new FormData();
  formData.append('file', file);
  
  const response = await apiClient.post<LoadCoursesResponse>(
    '/api/courses/load',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return response.data;
};

/**
 * 获取所有已加载的课程
 */
export const getCourses = async (): Promise<Course[]> => {
  const response = await apiClient.get<Course[]>('/api/courses');
  return response.data || [];
};

/**
 * 搜索课程
 */
export const searchCourses = async (query: string): Promise<Course[]> => {
  const response = await apiClient.get<SearchCoursesResponse>('/api/courses/search', {
    params: { q: query },
  });
  return response.data.courses;
};

/**
 * 获取指定课程的详细信息
 */
export const getCourse = async (courseCode: string): Promise<Course> => {
  const response = await apiClient.get<GetCourseResponse>(`/api/courses/${courseCode}`);
  return response.data.course;
};

/**
 * 获取所有已选课程
 */
export const getSelectedCourses = async (): Promise<SelectedCourse[]> => {
  const response = await apiClient.get<SelectedCourse[]>('/api/selected-courses');
  return response.data || [];
};

/**
 * 添加课程到已选列表
 */
export const addSelectedCourse = async (
  courseCode: string,
  classIndex: number = 0
): Promise<SelectedCourse> => {
  const formData = new FormData();
  formData.append('course_code', courseCode);
  formData.append('class_index', classIndex.toString());
  
  const response = await apiClient.post<SelectedCourse>(
    '/api/selected-courses',
    formData
  );
  return response.data;
};

/**
 * 从已选列表移除课程
 */
export const removeSelectedCourse = async (courseId: string): Promise<ApiResponse> => {
  const response = await apiClient.delete<ApiResponse>(`/api/selected-courses/${courseId}`);
  return response.data;
};

/**
 * 为已选课程添加时间段
 */
export const addTimeSlot = async (
  courseId: string,
  timeSlot: TimeSlot
): Promise<SelectedCourse> => {
  const response = await apiClient.post<SelectedCourse>(
    `/api/selected-courses/${courseId}/timeslots`,
    timeSlot
  );
  return response.data;
};

/**
 * 更新已选课程的类别
 */
export const updateCourseCategory = async (
  courseId: string,
  category: string
): Promise<SelectedCourse> => {
  const formData = new FormData();
  formData.append('category', category);
  
  const response = await apiClient.put<SelectedCourse>(
    `/api/selected-courses/${courseId}/category`,
    formData
  );
  return response.data;
};
