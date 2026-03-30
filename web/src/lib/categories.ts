export const CREDIT_CATEGORIES = [
  '公共必修课 - 公共必修',
  '公共必修课 - 公共必修（二选一）',
  '选修课 - 限制性选修',
  '选修课 - 通识选修',
  '选修课 - 学位选修',
  '学位必修课（核心课）',
] as const;

export const DEFAULT_CREDIT_REQUIREMENTS: Record<string, number> = {
  '公共必修课 - 公共必修': 4,
  '公共必修课 - 公共必修（二选一）': 1,
  '选修课 - 限制性选修': 1,
  '选修课 - 通识选修': 1,
  '选修课 - 学位选修': 8,
  '学位必修课（核心课）': 11,
};

export type CreditCategory = (typeof CREDIT_CATEGORIES)[number];

export function getCategoryOptions(originalCategory: string, currentValue?: string): string[] {
  const normalized = originalCategory || '';
  let options: string[];

  if (normalized.includes('通识选修')) {
    options = ['选修课 - 通识选修'];
  } else if (normalized.includes('限制性选修')) {
    options = ['选修课 - 限制性选修'];
  } else if (normalized.includes('公共必修')) {
    options = ['公共必修课 - 公共必修', '公共必修课 - 公共必修（二选一）'];
  } else {
    options = ['选修课 - 学位选修', '学位必修课（核心课）'];
  }

  if (currentValue && currentValue.trim() && !options.includes(currentValue)) {
    return [...options, currentValue];
  }

  return options;
}

export function getCategoryShortLabel(category: string): string {
  if (!category || !category.trim() || category.trim().toLowerCase() === 'nan') {
    return '待设置';
  }

  return category
    .replace('公共必修课 - ', '')
    .replace('选修课 - ', '')
    .replace('（核心课）', '')
    .trim();
}
