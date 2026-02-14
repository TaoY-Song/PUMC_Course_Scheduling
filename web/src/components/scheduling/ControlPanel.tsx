import React from 'react';
import { Play, Square, RotateCcw } from 'lucide-react';
import type { SchedulingStatus } from '../../types/models';

interface ControlPanelProps {
  status: SchedulingStatus;
  selectedCount: number;
  onStart: () => void;
  onCancel: () => void;
  onReset: () => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({
  status,
  selectedCount,
  onStart,
  onCancel,
  onReset,
}) => {
  const isRunning = status === 'running';
  const isIdle = status === 'idle' || status === 'completed' || status === 'failed';

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">执行控制</h3>

      <div className="space-y-4">
        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <span className="text-sm text-gray-600">已选课程</span>
          <span className="text-2xl font-bold text-blue-600">{selectedCount}</span>
        </div>

        <div className="flex items-center justify-between p-4 bg-gray-50 rounded-lg">
          <span className="text-sm text-gray-600">当前状态</span>
          <span
            className={`px-3 py-1 rounded-full text-sm font-medium ${
              status === 'idle'
                ? 'bg-gray-100 text-gray-700'
                : status === 'running'
                ? 'bg-yellow-100 text-yellow-700'
                : status === 'completed'
                ? 'bg-green-100 text-green-700'
                : 'bg-red-100 text-red-700'
            }`}
          >
            {status === 'idle' && '就绪'}
            {status === 'running' && '执行中'}
            {status === 'completed' && '已完成'}
            {status === 'failed' && '失败'}
            {status === 'configuring' && '配置中'}
            {status === 'cancelled' && '已取消'}
          </span>
        </div>

        <div className="flex space-x-3">
          {isIdle && (
            <button
              onClick={onStart}
              disabled={selectedCount === 0}
              className="flex-1 flex items-center justify-center px-4 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Play className="w-5 h-5 mr-2" />
              开始排课
            </button>
          )}

          {isRunning && (
            <button
              onClick={onCancel}
              className="flex-1 flex items-center justify-center px-4 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              <Square className="w-5 h-5 mr-2" />
              取消执行
            </button>
          )}

          <button
            onClick={onReset}
            className="px-4 py-3 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
          >
            <RotateCcw className="w-5 h-5" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default ControlPanel;
