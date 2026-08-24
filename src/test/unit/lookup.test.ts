import assert from 'node:assert/strict';
import { test } from 'node:test';
import { resolveHeader } from '../../lookup';

const map: Record<string, string> = {
	vector: '<vector>',
	milliseconds: '<chrono>',
	chrono: '<chrono>',
	path: '<filesystem>',
	filesystem: '<filesystem>',
	string: '<string>',
	pmr: '<memory_resource>',
};

test('std::vector maps to <vector>', () => {
	assert.equal(resolveHeader('std::vector', map), '<vector>');
});

test('std::vector<int> ignores template args', () => {
	assert.equal(resolveHeader('std::vector<int>', map), '<vector>');
});

test('std::chrono::milliseconds walks right-to-left to milliseconds', () => {
	assert.equal(resolveHeader('std::chrono::milliseconds', map), '<chrono>');
});

test('std::pmr::vector prefers vector over pmr', () => {
	assert.equal(resolveHeader('std::pmr::vector', map), '<vector>');
});

test('std::pmr::vector falls back to pmr when vector is absent', () => {
	const withoutVector: Record<string, string> = { pmr: '<memory_resource>' };
	assert.equal(resolveHeader('std::pmr::vector', withoutVector), '<memory_resource>');
});

test('std::filesystem::path maps to <filesystem>', () => {
	assert.equal(resolveHeader('std::filesystem::path', map), '<filesystem>');
});

test('::std::string maps to <string>', () => {
	assert.equal(resolveHeader('::std::string', map), '<string>');
});

test('unknown name returns undefined', () => {
	assert.equal(resolveHeader('std::frobnicate', map), undefined);
});

test('non-std name returns undefined', () => {
	assert.equal(resolveHeader('boost::vector', map), undefined);
});

test('bare std with no member returns undefined', () => {
	assert.equal(resolveHeader('std', map), undefined);
});
