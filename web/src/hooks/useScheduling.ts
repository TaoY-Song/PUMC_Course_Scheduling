/**
 * Scheduling Workflow Hooks
 * 封装排课工作流逻辑
 */
import { useCallback, useState } from 'react';
import { useAppStore } from '../stores/appStore';
import * as schedulingApi from '../api/scheduling';
import { useSchedulingWebSocket } from './useWebSocket';
import type { SchedulingConfig } from '../types/models';

export const useScheduling = () => {
  const {
    config,
    progress,
    lastResult,
    setConfig,
    setSchedulingStatus,
    setLastResult,
    setError,
    clearError,
  } = useAppStore();

  const [isExecuting, setIsExecuting] = useState(false);

  // 使用WebSocket监听进度
  const ws = useSchedulingWebSocket();

  // 获取排课配置
  const fetchConfig = useCallback(async () => {
    try {
      const currentConfig = await schedulingApi.getSchedulingConfig();
      setConfig(currentConfig);
      return currentConfig;
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取配置失败';
      setError(message);
      throw error;
    }
  }, [setConfig, setError]);

  // 保存排课配置
  const saveConfig = useCallback(async (newConfig: SchedulingConfig) => {
    try {
      await schedulingApi.configureScheduling(newConfig);
      setConfig(newConfig);
    } catch (error) {
      const message = error instanceof Error ? error.message : '保存配置失败';
      setError(message);
      throw error;
    }
  }, [setConfig, setError]);

  // 执行排课
  const execute = useCallback(async (courseIds: string[] = []) => {
    setIsExecuting(true);
    clearError();
    setSchedulingStatus('running', '正在启动排课...', 0);

    try {
      const response = await schedulingApi.executeScheduling(courseIds);

      if (response.success && response.result) {
        setSchedulingStatus('running', '排课进行中...', 50);
        setLastResult(response.result);
        
        // 短暂延迟后设置完成状态
        setTimeout(() => {
          setSchedulingStatus('completed', '排课完成', 100);
        }, 500);
      } else {
        setSchedulingStatus('failed', response.error_message || '排课失败');
      }

      return response;
    } catch (error) {
      const message = error instanceof Error ? error.message : '排课执行失败';
      setError(message);
      setSchedulingStatus('failed', message);
      throw error;
    } finally {
      setIsExecuting(false);
    }
  }, [clearError, setError, setSchedulingStatus, setLastResult]);

  // 取消排课
  const cancel = useCallback(async () => {
    try {
      await schedulingApi.cancelScheduling();
      setSchedulingStatus('cancelled', '已取消');
    } catch (error) {
      const message = error instanceof Error ? error.message : '取消失败';
      setError(message);
      throw error;
    }
  }, [setError, setSchedulingStatus]);

  // 获取排课结果
  const fetchResult = useCallback(async () => {
    try {
      const result = await schedulingApi.getLastResult();
      setLastResult(result);
      return result;
    } catch (error) {
      const message = error instanceof Error ? error.message : '获取结果失败';
      setError(message);
      throw error;
    }
  }, [setError, setLastResult]);

  // 获取排课状态
  const fetchStatus = useCallback(async () => {
    try {
      const status = await schedulingApi.getSchedulingStatus();
      return status;
    } catch (error) {
      console.error('Failed to fetch status:', error);
      return 'unknown';
    }
  }, []);

  return {
    config,
    progress,
    lastResult,
    isExecuting,
    ws,
    fetchConfig,
    saveConfig,
    execute,
    cancel,
    fetchResult,
    fetchStatus,
  };
};

export default useScheduling;