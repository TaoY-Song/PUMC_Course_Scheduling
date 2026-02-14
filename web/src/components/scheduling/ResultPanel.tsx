import React from 'react';
import { CheckCircle, AlertTriangle } from 'lucide-react';
import type { ScheduleResult } from '../../types/models';

interface ResultPanelProps {
  result: ScheduleResult | null | undefined;
}

export const ResultPanel: React.FC<ResultPanelProps> = ({
  result,
}) => {
  if (!result) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">排课结果</h3>
        <div className="text-center py-8 text-gray-500">
          暂无排课结果
        </div>
      </div>
    );
  }

  const { selected_courses = [], score = { total_score: 0, credit_match_score: 0, time_quality_score: 0 }, conflicts = [], execution_time = 0 } = result || {};

  return (
    <div className="bg-white rounded-lg shadow p-6">
      <h3 className="text-lg font-medium text-gray-900 mb-4">排课结果</h3>

      <div className="space-y-6">
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-blue-50 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-blue-600">
              {selected_courses.length}
            </div>
            <div className="text-sm text-blue-700">选中课程</div>
          </div>

          <div className="bg-green-50 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-green-600">
              {score.total_score.toFixed(1)}
            </div>
            <div className="text-sm text-green-700">综合评分</div>
          </div>

          <div className="bg-purple-50 p-4 rounded-lg text-center">
            <div className="text-2xl font-bold text-purple-600">
              {execution_time.toFixed(2)}s
            </div>
            <div className="text-sm text-purple-700">执行时间</div>
          </div>
        </div>

        <div>
          <h4 className="font-medium text-gray-900 mb-2">评分详情</h4>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">学分匹配度</span>
              <div className="flex items-center">
                <div className="w-32 bg-gray-200 rounded-full h-2 mr-2">
                  <div
                    className="bg-green-500 h-2 rounded-full"
                    style={{ width: `${score.credit_match_score}%` }}
                  />
                </div>
                <span className="text-sm font-medium">
                  {score.credit_match_score.toFixed(1)}
                </span>
              </div>
            </div>

            <div className="flex justify-between items-center">
              <span className="text-sm text-gray-600">时间质量</span>
              <div className="flex items-center">
                <div className="w-32 bg-gray-200 rounded-full h-2 mr-2">
                  <div
                    className="bg-blue-500 h-2 rounded-full"
                    style={{ width: `${score.time_quality_score}%` }}
                  />
                </div>
                <span className="text-sm font-medium">
                  {score.time_quality_score.toFixed(1)}
                </span>
              </div>
            </div>
          </div>
        </div>

        {conflicts.length > 0 && (
          <div>
            <h4 className="font-medium text-gray-900 mb-2 flex items-center">
              <AlertTriangle className="w-5 h-5 text-yellow-500 mr-2" />
              冲突信息 ({conflicts.length})
            </h4>
            <div className="space-y-2 max-h-40 overflow-y-auto">
              {conflicts.map((conflict, index) => (
                <div
                  key={index}
                  className="p-3 bg-yellow-50 border border-yellow-200 rounded-lg text-sm"
                >
                  <div className="font-medium text-yellow-800">
                    {conflict.conflict_type}
                  </div>
                  <div className="text-yellow-700">
                    {conflict.course1_code} vs {conflict.course2_code}
                  </div>
                  <div className="text-yellow-600 text-xs mt-1">
                    {conflict.description}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {conflicts.length === 0 && (
          <div className="flex items-center p-4 bg-green-50 rounded-lg">
            <CheckCircle className="w-5 h-5 text-green-500 mr-2" />
            <span className="text-green-700">无冲突，排课成功！</span>
          </div>
        )}

        <div>
          <h4 className="font-medium text-gray-900 mb-2">已选课程列表</h4>
          <div className="max-h-60 overflow-y-auto border rounded-lg">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    课程
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    教师
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                    学分
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {selected_courses.map((course) => (
                  <tr key={course.id}>
                    <td className="px-4 py-2 text-sm">
                      {course.course.course_name}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {course.course.teacher || '-'}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {course.course.credits}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ResultPanel;
