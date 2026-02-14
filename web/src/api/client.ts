/**
 * HTTP客户端配置
 * 使用axios封装API请求
 */
import axios, { AxiosInstance, AxiosError } from 'axios';

// API基础URL - 使用相对路径，适配任何部署地址
const API_BASE_URL = import.meta.env.VITE_API_URL || '';

// 创建axios实例
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
});

// 请求拦截器
apiClient.interceptors.request.use(
  (config) => {
    // 可以在这里添加认证token等
    console.log(`[API Request] ${config.method?.toUpperCase()} ${config.url}`);
    return config;
  },
  (error) => {
    console.error('[API Request Error]', error);
    return Promise.reject(error);
  }
);

// 响应拦截器
apiClient.interceptors.response.use(
  (response) => {
    console.log(`[API Response] ${response.status} ${response.config.url}`);
    return response;
  },
  (error: AxiosError) => {
    if (error.response) {
      // 服务器返回错误状态码
      console.error('[API Error]', {
        status: error.response.status,
        data: error.response.data,
        url: error.config?.url,
      });
    } else if (error.request) {
      // 请求发送但没有收到响应
      console.error('[API No Response]', error.request);
    } else {
      // 请求配置出错
      console.error('[API Config Error]', error.message);
    }
    return Promise.reject(error);
  }
);

// 健康检查
export const healthCheck = async () => {
  try {
    const response = await apiClient.get('/api/health');
    return response.data;
  } catch (error) {
    console.error('Health check failed:', error);
    throw error;
  }
};

export default apiClient;
