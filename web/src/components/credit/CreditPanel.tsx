import React from 'react';
import { CheckCircle, XCircle } from 'lucide-react';
import type { CreditRequirement } from '../../types/models';

interface CreditPanelProps {
  requirements: CreditRequirement[];
}

export const CreditPanel: React.FC<CreditPanelProps> = ({
  requirements = [],
}) => {
  const totalRequired = requirements.reduce((sum, r) => sum + r.required_credits, 0);
  const totalCompleted = requirements.reduce((sum, r) => sum + r.completed_credits, 0);

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">学分总览</h3>
        <div className="grid grid-cols-3 gap-4">
          <div className="text-center p-4 bg-blue-50 rounded-lg">
            <div className="text-3xl font-bold text-blue-600">{totalRequired}</div>
            <div className="text-sm text-blue-700">总要求学分</div>
          </div>
          <div className="text-center p-4 bg-green-50 rounded-lg">
            <div className="text-3xl font-bold text-green-600">{totalCompleted}</div>
            <div className="text-sm text-green-700">已完成学分</div>
          </div>
          <div className="text-center p-4 bg-yellow-50 rounded-lg">
            <div className="text-3xl font-bold text-yellow-600">
              {Math.max(0, totalRequired - totalCompleted)}
            </div>
            <div className="text-sm text-yellow-700">剩余学分</div>
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">各类别详情</h3>
        </div>
        <div className="divide-y divide-gray-200">
          {requirements.map((req) => (
            <div key={req.category} className="p-6">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center">
                  {req.is_completed ? (
                    <CheckCircle className="w-5 h-5 text-green-500 mr-2" />
                  ) : (
                    <XCircle className="w-5 h-5 text-gray-400 mr-2" />
                  )}
                  <span className="font-medium text-gray-900">{req.category}</span>
                </div>
                <span
                  className={`px-2 py-1 text-xs font-medium rounded ${
                    req.is_completed
                      ? 'bg-green-100 text-green-800'
                      : 'bg-yellow-100 text-yellow-800'
                  }`}
                >
                  {req.is_completed ? '已完成' : '未完成'}
                </span>
              </div>

              <div className="mt-2">
                <div className="flex justify-between text-sm text-gray-600 mb-1">
                  <span>
                    {req.completed_credits} / {req.required_credits} 学分
                  </span>
                  <span>{Math.round((req.completed_credits / req.required_credits) * 100)}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full transition-all ${
                      req.is_completed ? 'bg-green-500' : 'bg-blue-500'
                    }`}
                    style={{
                      width: `${Math.min(
                        100,
                        (req.completed_credits / req.required_credits) * 100
                      )}%`,
                    }}
                  />
                </div>
              </div>

              {req.courses && req.courses.length > 0 && (
                <div className="mt-3 text-sm text-gray-600">
                  <span className="font-medium">已选课程:</span>{' '}
                  {req.courses.length} 门
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CreditPanel;
