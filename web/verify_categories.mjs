// 校验类别工具函数：nan 绝不能成为可选项，且必须被识别为“待设置”。
// 项目没有前端测试框架，用一个可独立运行的断言脚本守住这条契约。
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('./src/lib/categories.ts', import.meta.url), 'utf-8');

// 轻量转译：剥掉 TS 类型标注，只保留可执行逻辑。
const transpiled = source
  .replace(/export const CREDIT_CATEGORIES[\s\S]*?as const;/, '')
  .replace(/export const DEFAULT_CREDIT_REQUIREMENTS[\s\S]*?};/, '')
  .replace(/export type [^\n]+\n/g, '')
  .replace(/export function/g, 'function')
  .replace(/\(category\?: string \| null\)/g, '(category)')
  .replace(/\(originalCategory: string, currentValue\?: string\): string\[\]/, '(originalCategory, currentValue)')
  .replace(/\(category: string\): string/, '(category)')
  .replace(/: string\[\]/g, '')
  .replace(/: boolean/g, '')
  .replace(/: string/g, '');

const module = new Function(`${transpiled}\nreturn { isCategoryUnset, getCategoryOptions, getCategoryShortLabel };`)();
const { isCategoryUnset, getCategoryOptions, getCategoryShortLabel } = module;

// isCategoryUnset
for (const value of ['', '   ', 'nan', 'NaN', 'NAN', null, undefined]) {
  assert.equal(isCategoryUnset(value), true, `should be unset: ${String(value)}`);
}
for (const value of ['公共必修课 - 公共必修', '选修课 - 学位选修']) {
  assert.equal(isCategoryUnset(value), false, `should be set: ${value}`);
}

// getCategoryOptions 绝不能把 nan / 空值当成可选项
for (const current of ['nan', 'NaN', '', '   ', undefined]) {
  for (const original of ['公共必修课', '通识选修课', '限制选修课', '学位选修课', '']) {
    const options = getCategoryOptions(original, current);
    assert.ok(options.length > 0, `options empty for ${original}`);
    for (const option of options) {
      assert.equal(
        isCategoryUnset(option),
        false,
        `invalid option ${JSON.stringify(option)} for original=${original} current=${String(current)}`,
      );
    }
  }
}

// 公共必修课必须提供两个细分选项（含二选一）
const publicOptions = getCategoryOptions('公共必修课', 'nan');
assert.deepEqual(publicOptions, [
  '公共必修课 - 公共必修',
  '公共必修课 - 公共必修（二选一）',
]);

// 已有的合法自定义值要保留
const custom = getCategoryOptions('学位选修课', '某个自定义类别');
assert.ok(custom.includes('某个自定义类别'));

// 短标签
assert.equal(getCategoryShortLabel('nan'), '待设置');
assert.equal(getCategoryShortLabel(''), '待设置');
assert.equal(getCategoryShortLabel('公共必修课 - 公共必修'), '公共必修');
assert.equal(getCategoryShortLabel('学位必修课（核心课）'), '学位必修课');

console.log('categories contract OK');
