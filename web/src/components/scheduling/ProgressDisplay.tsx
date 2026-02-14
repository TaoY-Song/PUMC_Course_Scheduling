import React from 'react';
import { Loader2 } from 'lucide-react';
import type { SchedulingProgress } from '../../types/models';

interface ProgressDisplayProps {
  progress?: SchedulingProgress;
}

const DEFAULT_PROGRESS: SchedulingProgress = {
  status: 'idle',
  message: '就绪',
  percent: 0,
};

export const ProgressDisplay: React.FC<ProgressDisplayProps> = ({
  progress = DEFAULT_PROGRESS,
}) => {
  const { status, message, percent } = progress;

  const isRunning = status === 'running';

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">执行进度</h3>

      <div className="space-y-4">
        {isRunning && (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-12 h-12 text-blue-600 animate-spin" />
          </div>
        )}

        <div className="text-center">
          <p className="text-lg font-medium text-gray-900">{message}</p>
        </div>

        {percent !== undefined && (
          <div>
            <div className="flex justify-between text-sm text-gray-600 mb-1">
              <span>进度</span>
              <span>{percent}%</span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${percent}%` }}
              />
            </div>
          </div>
        )}

        {!isRunning && !percent && (
          <div className="py-8 text-center text-gray-500">
            等待开始排课...
          </div>
        )}
      </div>
    </div>
  );
};

export default ProgressDisplay;
