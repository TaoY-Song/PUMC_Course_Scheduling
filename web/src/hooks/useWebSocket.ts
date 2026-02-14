/**
 * WebSocket Hooks
 * 封装WebSocket连接和事件处理
 */
import { useEffect, useRef, useCallback, useState } from 'react';
import { useAppStore } from '../stores/appStore';

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws';

export type WebSocketStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

interface WebSocketMessage {
  type: string;
  data: unknown;
}

interface UseWebSocketOptions {
  autoConnect?: boolean;
  eventTypes?: string[];
  onMessage?: (type: string, data: unknown) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
}

/**
 * WebSocket连接Hook
 */
export const useWebSocket = (options: UseWebSocketOptions = {}) => {
  const {
    autoConnect = false,
    eventTypes = [],
    onMessage,
    onConnect,
    onDisconnect,
    onError,
  } = options;

  const [status, setStatus] = useState<WebSocketStatus>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const subscribedEventsRef = useRef<Set<string>>(new Set(eventTypes));

  const { setSchedulingStatus, setLastResult } = useAppStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus('connecting');
    console.log('[WebSocket] Connecting to', WS_URL);

    try {
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        setStatus('connected');
        console.log('[WebSocket] Connected');
        onConnect?.();

        // 重新订阅之前订阅过的事件
        if (subscribedEventsRef.current.size > 0) {
          ws.send(JSON.stringify({
            action: 'subscribe',
            event_types: Array.from(subscribedEventsRef.current),
          }));
        }
      };

      ws.onmessage = (event) => {
        console.log('[WebSocket] Received:', event.data);
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          const { type, data } = message;
          console.log('[WebSocket] Message type:', type, 'data:', data);

          // 处理特定事件类型
          switch (type) {
            case 'scheduling.started':
              setSchedulingStatus('running', '开始智能排课...', 0);
              break;
            case 'scheduling.progress':
              if (typeof data === 'object' && data !== null) {
                const progressData = data as { message?: string; percent?: number };
                setSchedulingStatus('running', progressData.message || '排课进行中...', progressData.percent);
              }
              break;
            case 'scheduling.completed':
              setSchedulingStatus('completed', '排课完成', 100);
              // 如果有结果数据，更新结果
              if (typeof data === 'object' && data !== null) {
                const resultData = data as { result?: unknown };
                if (resultData.result) {
                  setLastResult(resultData.result as never);
                }
              }
              break;
            case 'scheduling.failed':
              setSchedulingStatus('failed', '排课失败');
              break;
            case 'courses.loaded':
              // 课程加载完成，可以触发刷新
              break;
            case 'config.updated':
              // 配置更新
              break;
          }

          // 调用自定义消息处理
          onMessage?.(type, data);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setStatus('error');
        onError?.(error);
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setStatus('disconnected');
        onDisconnect?.();

        // 不自动重连，因为不依赖WebSocket获取排课结果
      };

      wsRef.current = ws;
    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      setStatus('error');
    }
  }, [autoConnect, onConnect, onDisconnect, onError, onMessage, setLastResult, setSchedulingStatus]);

  const disconnect = useCallback(() => {
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setStatus('disconnected');
  }, []);

  const subscribe = useCallback((eventTypes: string[]) => {
    subscribedEventsRef.current = new Set([
      ...Array.from(subscribedEventsRef.current),
      ...eventTypes,
    ]);

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe',
        event_types: eventTypes,
      }));
    }
  }, []);

  const unsubscribe = useCallback((eventTypes: string[]) => {
    eventTypes.forEach((type) => {
      subscribedEventsRef.current.delete(type);
    });

    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'unsubscribe',
        event_types: eventTypes,
      }));
    }
  }, []);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  // 自动连接
  useEffect(() => {
    if (autoConnect) {
      connect();
    }

    return () => {
      disconnect();
    };
  }, [autoConnect, connect, disconnect]);

  return {
    status,
    isConnected: status === 'connected',
    connect,
    disconnect,
    subscribe,
    unsubscribe,
    send,
  };
};

/**
 * 排课进度WebSocket Hook
 * 专门用于监听排课进度
 */
export const useSchedulingWebSocket = () => {
  const { setSchedulingStatus, setProgress, setLastResult } = useAppStore();

  const handleMessage = useCallback((type: string, data: unknown) => {
    const messageData = data as { message?: string; percent?: number; result?: unknown } | null;

    switch (type) {
      case 'scheduling.started':
        setSchedulingStatus('running', messageData?.message || '开始智能排课...', 0);
        setProgress({ status: 'running', message: messageData?.message || '开始智能排课...' });
        break;

      case 'scheduling.progress':
        setSchedulingStatus('running', messageData?.message || '排课进行中...', messageData?.percent);
        setProgress({
          status: 'running',
          message: messageData?.message || '排课进行中...',
          percent: messageData?.percent,
        });
        break;

      case 'scheduling.completed':
        setSchedulingStatus('completed', '排课完成', 100);
        setProgress({ status: 'completed', message: '排课完成' });
        if (messageData?.result) {
          setLastResult(messageData.result as never);
        }
        break;

      case 'scheduling.failed':
        setSchedulingStatus('failed', messageData?.message || '排课失败');
        setProgress({ status: 'failed', message: messageData?.message || '排课失败' });
        break;
    }
  }, [setLastResult, setProgress, setSchedulingStatus]);

  return useWebSocket({
    autoConnect: false,
    eventTypes: ['scheduling.started', 'scheduling.progress', 'scheduling.completed', 'scheduling.failed'],
    onMessage: handleMessage,
    onConnect: () => console.log('[WebSocket] Subscribing to events'),
  });
};

export default useWebSocket;