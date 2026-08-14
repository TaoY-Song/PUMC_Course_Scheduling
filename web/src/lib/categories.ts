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

/**
 * 类别是否仍待用户设置。
 *
 * 后端对公共必修课等无法自动判定的课程会把 custom_category 规范化为
 * "nan"，强制用户手选具体类别。排课引擎按 custom_category 归集学分，
 * 所以 "nan" 的课程不计入任何学分要求，会被静默丢弃 —— 必须在 UI 上
 * 显式拦下来，而不是让用户排完才发现课程少了。
 */
export function isCategoryUnset(category?: string | null): boolean {
  const value = (category ?? '').trim().toLowerCase();
  return value === '' || value === 'nan';
}

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

  // 保留用户已有的自定义值，但绝不把 "nan"/空值当成可选项。
  // 之前会把 currentValue 无条件追加，于是下拉里出现一个 "nan" 选项，
  // 用户能主动把课程改回“排课会忽略”的状态。
  if (currentValue && !isCategoryUnset(currentValue) && !options.includes(currentValue)) {
    return [...options, currentValue];
  }

  return options;
}

export function getCategoryShortLabel(category: string): string {
  if (isCategoryUnset(category)) {
    return '待设置';
  }

  return category
    .replace('公共必修课 - ', '')
    .replace('选修课 - ', '')
    .replace('（核心课）', '')
    .trim();
}
