import React, { useState, useEffect } from 'react';
import { Save, RotateCcw } from 'lucide-react';
import { Card } from '../common/Card';
import { Button } from '../common/Button';
import * as schedulingApi from '../../api/scheduling';

interface CreditSettingsProps {
  onSave?: () => void;
}

const DEFAULT_CREDIT_REQUIREMENTS: Record<string, number> = {
  '公共必修课 - 公共必修': 4.0,
  '公共必修课 - 公共必修（二选一）': 1.0,
  '选修课 - 限制性选修': 1.0,
  '选修课 - 通识选修': 1.0,
  '选修课 - 学位选修': 8.0,
  '学位必修课（核心课）': 11.0,
};

export const CreditSettings: React.FC<CreditSettingsProps> = ({ onSave }) => {
  const [requirements, setRequirements] = useState<Record<string, number>>(DEFAULT_CREDIT_REQUIREMENTS);
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    fetchSettings();
  }, []);

  const fetchSettings = async () => {
    setIsLoading(true);
    try {
      const settings = await schedulingApi.getCreditSettings();
      if (Object.keys(settings).length > 0) {
        setRequirements(settings);
      }
    } catch (error) {
      console.error('Failed to fetch credit settings:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreditChange = (category: string, value: string) => {
    const numValue = parseFloat(value) || 0;
    setRequirements((prev) => ({
      ...prev,
      [category]: Math.max(0, numValue),
    }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setMessage(null);
    try {
      await schedulingApi.updateCreditSettings(requirements);
      setMessage({ type: 'success', text: '保存成功' });
      onSave?.();
    } catch (error) {
      setMessage({ type: 'error', text: '保存失败' });
    } finally {
      setIsSaving(false);
    }
  };

  const handleReset = () => {
    setRequirements(DEFAULT_CREDIT_REQUIREMENTS);
    setMessage({ type: 'success', text: '已重置为默认值' });
  };

  const categories = Object.keys(requirements);

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-medium text-gray-900">学分要求设置</h3>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleReset}
              disabled={isSaving}
            >
              <RotateCcw className="w-4 h-4 mr-1" />
              重置
            </Button>
            <Button
              variant="primary"
              size="sm"
              onClick={handleSave}
              disabled={isSaving}
            >
              <Save className="w-4 h-4 mr-1" />
              {isSaving ? '保存中...' : '保存设置'}
            </Button>
          </div>
        </div>

        {message && (
          <div
            className={`mb-4 p-3 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-50 text-green-700'
                : 'bg-red-50 text-red-700'
            }`}
          >
            {message.text}
          </div>
        )}

        {isLoading ? (
          <div className="text-center py-8 text-gray-500">加载中...</div>
        ) : (
          <div className="space-y-4">
            {categories.map((category) => (
              <div key={category} className="flex items-center gap-4">
                <label className="flex-1 text-sm font-medium text-gray-700">
                  {category}
                </label>
                <div className="flex items-center gap-2">
                  <input
                    type="number"
                    min="0"
                    step="0.5"
                    value={requirements[category]}
                    onChange={(e) => handleCreditChange(category, e.target.value)}
                    className="w-24 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                  <span className="text-sm text-gray-500">学分</span>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="mt-6 pt-4 border-t border-gray-200">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">总要求学分:</span>
            <span className="font-medium text-gray-900">
              {Object.values(requirements || {}).reduce((sum, val) => sum + val, 0)} 学分
            </span>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default CreditSettings;