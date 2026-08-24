import assert from 'node:assert/strict';
import { test } from 'node:test';
import { findIncludeInsertion } from '../../insertPosition';

function insertInclude(text: string, header: string): string {
	const { offset, text: insertText } = findIncludeInsertion(text, header);
	return text.slice(0, offset) + insertText + text.slice(offset);
}

test('empty file inserts at line 0', () => {
	assert.equal(insertInclude('', '<vector>'), '#include <vector>\n');
});

test('file with no includes, no pragma, no guard inserts at line 0', () => {
	const text = 'int main() {\n\treturn 0;\n}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#include <vector>\nint main() {\n\treturn 0;\n}\n',
	);
});

test('file with #pragma once inserts after it', () => {
	const text = '#pragma once\n\nint main() {}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#pragma once\n#include <vector>\n\nint main() {}\n',
	);
});

test('file with classic include guard inserts after the #define', () => {
	const text = '#ifndef FOO_H\n#define FOO_H\n\nint main() {}\n#endif\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#ifndef FOO_H\n#define FOO_H\n#include <vector>\n\nint main() {}\n#endif\n',
	);
});

test('guard where #define does not immediately follow #ifndef is not recognized as a guard', () => {
	const text = '#ifndef FOO_H\n\n#define FOO_H\n\nint main() {}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#include <vector>\n#ifndef FOO_H\n\n#define FOO_H\n\nint main() {}\n',
	);
});

test('guard with mismatched macro names is not recognized as a guard', () => {
	const text = '#ifndef FOO_H\n#define BAR_H\n\nint main() {}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#include <vector>\n#ifndef FOO_H\n#define BAR_H\n\nint main() {}\n',
	);
});

test('file with one existing include inserts after it', () => {
	const text = '#include <string>\n\nint main() {}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#include <string>\n#include <vector>\n\nint main() {}\n',
	);
});

test('file with multiple existing includes inserts after the last one', () => {
	const text = '#include <string>\n#include <map>\n\nint main() {}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#include <string>\n#include <map>\n#include <vector>\n\nint main() {}\n',
	);
});

test('existing include takes priority over pragma once', () => {
	const text = '#pragma once\n#include <string>\n\nint main() {}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#pragma once\n#include <string>\n#include <vector>\n\nint main() {}\n',
	);
});

test('existing include takes priority over an include guard', () => {
	const text = '#ifndef FOO_H\n#define FOO_H\n#include <string>\n\nint main() {}\n#endif\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#ifndef FOO_H\n#define FOO_H\n#include <string>\n#include <vector>\n\nint main() {}\n#endif\n',
	);
});

test('pragma once takes priority over an include guard', () => {
	const text = '#pragma once\n#ifndef FOO_H\n#define FOO_H\n\nint main() {}\n#endif\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#pragma once\n#include <vector>\n#ifndef FOO_H\n#define FOO_H\n\nint main() {}\n#endif\n',
	);
});

test('last line has no trailing newline: existing include with no EOF newline', () => {
	const text = '#include <string>';
	assert.equal(insertInclude(text, '<vector>'), '#include <string>\n#include <vector>\n');
});

test('last line has no trailing newline: no includes, guards, or pragma', () => {
	const text = 'int main() {}';
	assert.equal(insertInclude(text, '<vector>'), '#include <vector>\nint main() {}');
});

test('whitespace-tolerant pragma once detection', () => {
	const text = '#  pragma   once  \n\nint main() {}\n';
	assert.equal(
		insertInclude(text, '<vector>'),
		'#  pragma   once  \n#include <vector>\n\nint main() {}\n',
	);
});
