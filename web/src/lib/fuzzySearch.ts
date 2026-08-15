/**
 * 课程模糊搜索。
 *
 * 原来只做 `includes()` 子串匹配：漏字、跨字段、拼音缩写全都搜不到，
 * 而且结果没有排序——命中课程编码和命中类别的权重一样，
 * 搜「生物」时精确匹配的课名可能排在几十条同类别课程后面。
 *
 * 这里改成带评分的匹配：
 * - 多关键词以空格分隔，每个都必须命中（AND），得分累加
 * - 每个关键词在各字段上取最高分，字段自带权重（编码/课名 > 教师/类别）
 * - 匹配质量分级：完全相等 > 前缀 > 连续子串 > 离散子序列
 * - 返回命中字符位置，供 UI 高亮
 */

export interface FuzzyField {
  /** 字段标识，UI 用它决定高亮到哪一段文本 */
  key: string;
  value: string;
  /** 字段权重，越大越优先 */
  weight: number;
}

export interface FuzzyMatch<T> {
  item: T;
  score: number;
  /** 每个字段命中的字符下标，用于高亮 */
  highlights: Record<string, number[]>;
}

const SCORE_EXACT = 1000;
const SCORE_PREFIX = 600;
const SCORE_SUBSTRING = 400;
const SCORE_SUBSEQUENCE = 150;
/** 子序列越松散扣分越多，避免「abc」把一整段长文本都算高分 */
const SPREAD_PENALTY = 8;

interface FieldScore {
  score: number;
  positions: number[];
}

/**
 * 在 haystack 中按顺序找 needle 的每个字符（允许中间跳过）。
 * 返回命中下标；找不到返回 null。
 */
function subsequencePositions(haystack: string, needle: string): number[] | null {
  const positions: number[] = [];
  let cursor = 0;

  for (const char of needle) {
    const found = haystack.indexOf(char, cursor);
    if (found === -1) {
      return null;
    }
    positions.push(found);
    cursor = found + 1;
  }

  return positions;
}

function range(start: number, length: number): number[] {
  return Array.from({ length }, (_, index) => start + index);
}

/** 单个关键词在单个字段上的得分 */
function scoreField(value: string, token: string): FieldScore | null {
  if (!value || !token) {
    return null;
  }

  const haystack = value.toLowerCase();
  const needle = token.toLowerCase();

  if (haystack === needle) {
    return { score: SCORE_EXACT, positions: range(0, needle.length) };
  }

  if (haystack.startsWith(needle)) {
    return { score: SCORE_PREFIX, positions: range(0, needle.length) };
  }

  const index = haystack.indexOf(needle);
  if (index !== -1) {
    // 越靠前越相关
    return {
      score: SCORE_SUBSTRING - index,
      positions: range(index, needle.length),
    };
  }

  const positions = subsequencePositions(haystack, needle);
  if (positions) {
    const spread = positions[positions.length - 1] - positions[0] - (positions.length - 1);
    return {
      score: Math.max(1, SCORE_SUBSEQUENCE - spread * SPREAD_PENALTY),
      positions,
    };
  }

  return null;
}

export interface ScoredFields {
  score: number;
  /** 每个字段命中的字符下标，用于高亮 */
  highlights: Record<string, number[]>;
}

/**
 * 对一条记录打分。所有关键词都必须命中至少一个字段，否则返回 null。
 */
export function scoreItem(fields: FuzzyField[], query: string): ScoredFields | null {
  const tokens = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (tokens.length === 0) {
    return { score: 0, highlights: {} };
  }

  let total = 0;
  const highlights: Record<string, number[]> = {};

  for (const token of tokens) {
    let best: { field: FuzzyField; result: FieldScore } | null = null;

    for (const field of fields) {
      const result = scoreField(field.value, token);
      if (!result) {
        continue;
      }
      const weighted = result.score * field.weight;
      if (!best || weighted > best.result.score * best.field.weight) {
        best = { field, result };
      }
    }

    if (!best) {
      return null; // 该关键词无处命中 → 整条记录不匹配
    }

    total += best.result.score * best.field.weight;
    const existing = highlights[best.field.key] ?? [];
    highlights[best.field.key] = [...new Set([...existing, ...best.result.positions])].sort(
      (a, b) => a - b,
    );
  }

  return { score: total, highlights };
}

/**
 * 搜索并按得分降序返回。query 为空时原样返回（不排序、不限量）。
 */
export function fuzzySearch<T>(
  items: T[],
  query: string,
  toFields: (item: T) => FuzzyField[],
  limit?: number,
): FuzzyMatch<T>[] {
  if (!query.trim()) {
    const all = items.map((item) => ({ item, score: 0, highlights: {} }));
    return limit ? all.slice(0, limit) : all;
  }

  const matches: FuzzyMatch<T>[] = [];
  for (const item of items) {
    const scored = scoreItem(toFields(item), query);
    if (scored) {
      matches.push({ item, score: scored.score, highlights: scored.highlights });
    }
  }

  matches.sort((left, right) => right.score - left.score);
  return limit ? matches.slice(0, limit) : matches;
}

/** 把字符串按高亮下标切成 {text, hit} 段，供渲染 */
export function splitHighlight(
  value: string,
  positions: number[] | undefined,
): Array<{ text: string; hit: boolean }> {
  if (!positions || positions.length === 0) {
    return [{ text: value, hit: false }];
  }

  const hits = new Set(positions);
  const segments: Array<{ text: string; hit: boolean }> = [];
  let buffer = '';
  let bufferHit = hits.has(0);

  for (let index = 0; index < value.length; index += 1) {
    const isHit = hits.has(index);
    if (isHit !== bufferHit && buffer) {
      segments.push({ text: buffer, hit: bufferHit });
      buffer = '';
    }
    bufferHit = isHit;
    buffer += value[index];
  }

  if (buffer) {
    segments.push({ text: buffer, hit: bufferHit });
  }

  return segments;
}
