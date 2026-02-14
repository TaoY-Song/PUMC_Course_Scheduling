import React, { useState } from 'react';
import type { TimeSlot } from '../../types/models';

interface TimeSlotEditorProps {
  initialValue?: TimeSlot;
  onSave: (timeSlot: TimeSlot) => void;
  onCancel: () => void;
}

const days = [
  { value: 1, label: '周一' },
  { value: 2, label: '周二' },
  { value: 3, label: '周三' },
  { value: 4, label: '周四' },
  { value: 5, label: '周五' },
  { value: 6, label: '周六' },
  { value: 7, label: '周日' },
];

const periods = Array.from({ length: 12 }, (_, i) => i + 1);
const weeks = Array.from({ length: 18 }, (_, i) => i + 1);

export const TimeSlotEditor: React.FC<TimeSlotEditorProps> = ({
  initialValue,
  onSave,
  onCancel,
}) => {
  const [dayOfWeek, setDayOfWeek] = useState(initialValue?.day_of_week || 1);
  const [startPeriod, setStartPeriod] = useState(initialValue?.start_period || 1);
  const [endPeriod, setEndPeriod] = useState(initialValue?.end_period || 2);
  const [selectedWeeks, setSelectedWeeks] = useState<number[]>(initialValue?.weeks || []);

  const toggleWeek = (week: number) => {
    setSelectedWeeks((prev) =>
      prev.includes(week) ? prev.filter((w) => w !== week) : [...prev, week]
    );
  };

  const selectAllWeeks = () => {
    setSelectedWeeks(weeks);
  };

  const clearAllWeeks = () => {
    setSelectedWeeks([]);
  };

  const handleSave = () => {
    if (selectedWeeks.length === 0) {
      alert('请至少选择一周');
      return;
    }
    onSave({
      day_of_week: dayOfWeek,
      start_period: startPeriod,
      end_period: endPeriod,
      weeks: selectedWeeks.sort((a, b) => a - b),
    });
  };

  return (
    <div className="p-6 space-y-6">
      <div className="grid grid-cols-3 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            星期
          </label>
          <select
            value={dayOfWeek}
            onChange={(e) => setDayOfWeek(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {days.map((day) => (
              <option key={day.value} value={day.value}>
                {day.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            开始节次
          </label>
          <select
            value={startPeriod}
            onChange={(e) => {
              const value = Number(e.target.value);
              setStartPeriod(value);
              if (value > endPeriod) {
                setEndPeriod(value);
              }
            }}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {periods.map((p) => (
              <option key={p} value={p}>
                第{p}节
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            结束节次
          </label>
          <select
            value={endPeriod}
            onChange={(e) => setEndPeriod(Number(e.target.value))}
            className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          >
            {periods
              .filter((p) => p >= startPeriod)
              .map((p) => (
                <option key={p} value={p}>
                  第{p}节
                </option>
              ))}
          </select>
        </div>
      </div>

      <div>
        <div className="flex justify-between items-center mb-3">
          <label className="block text-sm font-medium text-gray-700">
            上课周次
          </label>
          <div className="space-x-2">
            <button
              onClick={selectAllWeeks}
              className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
            >
              全选
            </button>
            <button
              onClick={clearAllWeeks}
              className="text-xs px-2 py-1 bg-gray-100 text-gray-600 rounded hover:bg-gray-200"
            >
              清空
            </button>
          </div>
        </div>

        <div className="grid grid-cols-9 gap-2">
          {weeks.map((week) => (
            <button
              key={week}
              onClick={() => toggleWeek(week)}
              className={`w-10 h-10 rounded text-sm font-medium transition-colors ${
                selectedWeeks.includes(week)
                  ? 'bg-blue-500 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              {week}
            </button>
          ))}
        </div>
      </div>

      <div className="flex justify-end space-x-3 pt-4 border-t">
        <button
          onClick={onCancel}
          className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
        >
          取消
        </button>
        <button
          onClick={handleSave}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          保存
        </button>
      </div>
    </div>
  );
};

export default TimeSlotEditor;
