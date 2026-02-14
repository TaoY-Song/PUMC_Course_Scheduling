import React from 'react';
import type { SchedulingConfig } from '../../types/models';

interface ConfigPanelProps {
  config?: SchedulingConfig;
  onChange: (config: SchedulingConfig) => void;
}

const DEFAULT_CONFIG: SchedulingConfig = {
  credit_constraint_mode: 'OPTIMAL',
  campus_conflict_mode: 'DAILY',
  max_solutions: 10,
  time_limit: 30,
  credit_overflow_ratio: 0.2,
  campus_transition_time: 2,
};

export const ConfigPanel: React.FC<ConfigPanelProps> = ({
  config = DEFAULT_CONFIG,
  onChange,
}) => {
  const handleChange = (key: keyof SchedulingConfig, value: unknown) => {
    onChange({ ...config, [key]: value });
  };

  return (
    <div className="bg-white rounded-lg shadow p-6 space-y-6">
      <h3 className="text-lg font-medium text-gray-900">排课配置</h3>

      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            学分约束模式
          </label>
          <div className="space-y-2">
            <label className="flex items-center">
              <input
                type="radio"
                checked={config.credit_constraint_mode === 'REQUIRED'}
                onChange={() => handleChange('credit_constraint_mode', 'REQUIRED')}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">
                必需模式 - 严格满足学分要求
              </span>
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                checked={config.credit_constraint_mode === 'OPTIMAL'}
                onChange={() => handleChange('credit_constraint_mode', 'OPTIMAL')}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">
                优化模式 - 尽量满足学分要求
              </span>
            </label>
          </div>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            校区冲突模式
          </label>
          <div className="space-y-2">
            <label className="flex items-center">
              <input
                type="radio"
                checked={config.campus_conflict_mode === 'DAILY'}
                onChange={() => handleChange('campus_conflict_mode', 'DAILY')}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">
                日内模式 - 同一天不跨校区
              </span>
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                checked={config.campus_conflict_mode === 'PERIOD'}
                onChange={() => handleChange('campus_conflict_mode', 'PERIOD')}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">
                时段模式 - 相邻时段不跨校区
              </span>
            </label>
            <label className="flex items-center">
              <input
                type="radio"
                checked={config.campus_conflict_mode === 'DISABLED'}
                onChange={() => handleChange('campus_conflict_mode', 'DISABLED')}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500"
              />
              <span className="ml-2 text-sm text-gray-700">
                禁用模式 - 允许跨校区
              </span>
            </label>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              时间限制 (秒)
            </label>
            <input
              type="number"
              min={10}
              max={300}
              value={config.time_limit}
              onChange={(e) => handleChange('time_limit', Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              最大解数量
            </label>
            <input
              type="number"
              min={1}
              max={10}
              value={config.max_solutions}
              onChange={(e) => handleChange('max_solutions', Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              学分溢出比例
            </label>
            <input
              type="number"
              min={0}
              max={0.5}
              step={0.1}
              value={config.credit_overflow_ratio}
              onChange={(e) => handleChange('credit_overflow_ratio', Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              校区转换时间 (分钟)
            </label>
            <input
              type="number"
              min={0}
              max={120}
              value={config.campus_transition_time}
              onChange={(e) => handleChange('campus_transition_time', Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfigPanel;
