// 校验模糊搜索排序与匹配契约。项目没有前端测试框架，
// 用可独立运行的断言脚本守住行为（与 verify_categories.mjs 同套路）。
//
// 类型剥离交给 esbuild（Vite 自带），不手写正则：正则一旦遇到
// 泛型或联合类型就会悄悄改坏逻辑，测出来的就不是真实代码了。
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import * as esbuild from 'esbuild';

const source = readFileSync(new URL('./src/lib/fuzzySearch.ts', import.meta.url), 'utf-8');
const { code: compiled } = await esbuild.transform(source, {
  loader: 'ts',
  format: 'esm',
  target: 'node18',
});

const tempFile = new URL('./.verify_fuzzy_search.tmp.mjs', import.meta.url);
writeFileSync(tempFile, compiled, 'utf-8');

let fuzzySearch;
let splitHighlight;
try {
  ({ fuzzySearch, splitHighlight } = await import(tempFile.href));
} finally {
  rmSync(tempFile, { force: true });
}

const COURSES = [
  { code: 'BIOL03001', name: '分子生物学实验技术', teacher: '黄常志', category: '选修课 - 学位选修' },
  { code: 'BIOL03002', name: '肿瘤细胞生物学', teacher: '刘芝华', category: '选修课 - 学位选修' },
  { code: 'BIOL05017', name: '基因分子生物学实验', teacher: '付俊', category: '选修课 - 学位选修' },
  { code: 'PUBL38001', name: '中国马克思主义与当代', teacher: '张伟', category: '公共必修课 - 公共必修' },
  { code: 'STAT02001', name: '医学统计学', teacher: '李明', category: '选修课 - 限制性选修' },
];

const toFields = (c) => [
  { key: 'code', value: c.code, weight: 1.2 },
  { key: 'name', value: c.name, weight: 1.5 },
  { key: 'teacher', value: c.teacher, weight: 0.8 },
  { key: 'category', value: c.category, weight: 0.4 },
];

const search = (q, limit) => fuzzySearch(COURSES, q, toFields, limit).map((m) => m.item.code);

// 1) 空查询原样返回
assert.deepEqual(search(''), COURSES.map((c) => c.code), '空查询应原样返回');

// 2) 课名命中优先于类别命中。
//    「生物」在 3 门课名里，不该被同类别的其他课挤下去。
const bio = search('生物');
assert.deepEqual(
  bio.slice(0, 3).sort(),
  ['BIOL03001', 'BIOL03002', 'BIOL05017'],
  `课名命中应排在前三：${bio}`,
);

// 3) 编码前缀匹配
assert.ok(search('BIOL05').includes('BIOL05017'), '编码前缀应命中');
assert.equal(search('BIOL05').length, 1, '编码前缀应精确到一门');

// 4) 大小写不敏感
assert.deepEqual(search('biol05'), search('BIOL05'), '搜索应大小写不敏感');

// 5) 教师名命中
assert.deepEqual(search('黄常志'), ['BIOL03001'], '教师名应可搜');

// 6) 多关键词 AND，且可跨字段
assert.deepEqual(search('生物 付俊'), ['BIOL05017'], '多关键词应为 AND 且跨字段');
assert.deepEqual(search('生物 不存在的老师'), [], '任一关键词无命中则整条不匹配');

// 7) 离散子序列：漏字仍能搜到（原 includes 实现做不到）
assert.ok(search('分子实验').includes('BIOL03001'), '子序列匹配应命中「分子…实验」');

// 8) 匹配质量排序：完全相等 > 前缀 > 子串
const ranked = fuzzySearch(
  [
    { code: 'X', name: '统计', teacher: '', category: '' },       // 完全相等
    { code: 'Y', name: '统计学基础', teacher: '', category: '' },  // 前缀
    { code: 'Z', name: '医学统计学', teacher: '', category: '' },  // 子串
  ],
  '统计',
  toFields,
).map((m) => m.item.code);
assert.deepEqual(ranked, ['X', 'Y', 'Z'], `匹配质量排序错误：${ranked}`);

// 9) limit 生效
assert.equal(search('生物', 2).length, 2, 'limit 应截断结果');

// 10) 高亮位置正确且不丢字符
const [first] = fuzzySearch(COURSES, '统计', toFields);
const segs = splitHighlight(first.item.name, first.highlights.name);
const hit = segs.filter((s) => s.hit).map((s) => s.text).join('');
assert.equal(hit, '统计', `高亮片段应为「统计」，实际为「${hit}」`);
assert.equal(segs.map((s) => s.text).join(''), first.item.name, '高亮切分不得丢字符');

// 11) 无高亮时返回整段
assert.deepEqual(splitHighlight('abc', undefined), [{ text: 'abc', hit: false }]);
assert.deepEqual(splitHighlight('abc', []), [{ text: 'abc', hit: false }]);

console.log('fuzzy search contract OK');
