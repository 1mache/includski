import assert from 'node:assert/strict';
import { test } from 'node:test';
import { findQualifiedNameAt } from '../../qualifiedName';

test('finds std::vector under cursor', () => {
	const text = 'std::vector<int> v;';
	const match = findQualifiedNameAt(text, 5);
	assert.equal(match?.text, 'std::vector<int>');
});

test('finds ::std::string under cursor', () => {
	const text = '::std::string s;';
	const match = findQualifiedNameAt(text, 2);
	assert.equal(match?.text, '::std::string');
});

test('cursor inside template args still resolves full name', () => {
	const text = 'std::vector<int> v;';
	const match = findQualifiedNameAt(text, 15);
	assert.equal(match?.text, 'std::vector<int>');
});

test('cursor outside any qualified name returns undefined', () => {
	const text = 'int x = 5;';
	assert.equal(findQualifiedNameAt(text, 4), undefined);
});

test('matches inside comments', () => {
	const text = '// std::vector is handy';
	const match = findQualifiedNameAt(text, 6);
	assert.equal(match?.text, 'std::vector');
});

test('matches inside string literals', () => {
	const text = 'auto s = "std::vector";';
	const match = findQualifiedNameAt(text, 14);
	assert.equal(match?.text, 'std::vector');
});

test('nested namespaces resolve as one qualified name', () => {
	const text = 'std::chrono::milliseconds ms;';
	const match = findQualifiedNameAt(text, 20);
	assert.equal(match?.text, 'std::chrono::milliseconds');
});

test('cursor inside a nested qualified name in a template arg picks the inner name', () => {
	const text = 'std::map<int, std::vector<int>> m;';
	const innerOffset = text.indexOf('std::vector') + 5;
	const match = findQualifiedNameAt(text, innerOffset);
	assert.equal(match?.text, 'std::vector<int>');
});

test('a selection overlapping a qualified name resolves it', () => {
	const text = 'std::vector<int> v;';
	// selection covers "d::vector", starting one char into "std"
	const match = findQualifiedNameAt(text, 3, 12);
	assert.equal(match?.text, 'std::vector<int>');
});
