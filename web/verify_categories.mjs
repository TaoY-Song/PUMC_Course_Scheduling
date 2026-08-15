// 校验类别工具函数：nan 绝不能成为可选项，且必须被识别为“待设置”。
// 项目没有前端测试框架，用一个可独立运行的断言脚本守住这条契约。
//
// 类型剥离交给 esbuild（Vite 自带），不手写正则：正则一旦遇到
// 泛型或联合类型就会悄悄改坏逻辑，测出来的就不是真实代码了。
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, rmSync } from 'node:fs';
import * as esbuild from 'esbuild';

const source = readFileSync(new URL('./src/lib/categories.ts', import.meta.url), 'utf-8');
const { code: compiled } = await esbuild.transform(source, {
  loader: 'ts',
  format: 'esm',
  target: 'node18',
});

const tempFile = new URL('./.verify_categories.tmp.mjs', import.meta.url);
writeFileSync(tempFile, compiled, 'utf-8');

let CREDIT_CATEGORIES;
let isCategoryUnset;
let getCategoryOptions;
let getCategoryShortLabel;
try {
  ({ CREDIT_CATEGORIES, isCategoryUnset, getCategoryOptions, getCategoryShortLabel } =
    await import(tempFile.href));
} finally {
  rmSync(tempFile, { force: true });
}

// ── isCategoryUnset ────────────────────────────────────────────────────────
for (const value of ['', '   ', 'nan', 'NaN', 'NAN', null, undefined]) {
  assert.equal(isCategoryUnset(value), true, `should be unset: ${String(value)}`);
}
for (const value of ['公共必修课 - 公共必修', '选修课 - 学位选修']) {
  assert.equal(isCategoryUnset(value), false, `should be set: ${value}`);
}

// ── getCategoryOptions：真实表标签 ─────────────────────────────────────────
// 真实一览表写的是「限制选修课」（无“性”字）。旧实现只匹配「限制性选修」，
// 于是限选课落到 else 分支，下拉里给的是学位选修/核心课。
assert.deepEqual(
  getCategoryOptions('限制选修课'),
  ['选修课 - 限制性选修'],
  '真实表的「限制选修课」必须识别为限制性选修',
);
assert.deepEqual(
  getCategoryOptions('限制性选修'),
  ['选修课 - 限制性选修'],
  '带“性”字的写法也要兼容',
);
assert.deepEqual(getCategoryOptions('通识选修课'), ['选修课 - 通识选修']);
assert.deepEqual(getCategoryOptions('公共必修课'), [
  '公共必修课 - 公共必修',
  '公共必修课 - 公共必修（二选一）',
]);
assert.deepEqual(getCategoryOptions('学位选修课'), [
  '选修课 - 学位选修',
  '学位必修课（核心课）',
]);

// ── 缺「课程类别」列的表（如附件3-2025下）────────────────────────────────
// 无法缩小范围，必须给全六项；只给学位选修/核心课的话，
// 用户根本选不到公共必修或通识选修。
for (const blank of ['', '   ', 'nan', 'NaN']) {
  assert.deepEqual(
    getCategoryOptions(blank),
    [...CREDIT_CATEGORIES],
    `无类别信息（${JSON.stringify(blank)}）时应给出全部 6 个类别`,
  );
}

// ── 绝不能把 nan / 空值当成可选项 ─────────────────────────────────────────
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

// 已有的合法自定义值要保留
const custom = getCategoryOptions('学位选修课', '某个自定义类别');
assert.ok(custom.includes('某个自定义类别'));

// ── 短标签 ─────────────────────────────────────────────────────────────────
assert.equal(getCategoryShortLabel('nan'), '待设置');
assert.equal(getCategoryShortLabel(''), '待设置');
assert.equal(getCategoryShortLabel('公共必修课 - 公共必修'), '公共必修');
assert.equal(getCategoryShortLabel('学位必修课（核心课）'), '学位必修课');

console.log('categories contract OK');
