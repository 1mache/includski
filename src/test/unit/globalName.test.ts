import assert from 'node:assert/strict';
import { test } from 'node:test';
import { findGlobalNameAt } from '../../globalName';

test('finds a whitelisted bare identifier under cursor', () => {
	const text = 'int x = INT_MAX;';
	const whitelist = new Set(['INT_MAX']);
	const match = findGlobalNameAt(text, 9, 9, whitelist);
	assert.equal(match?.text, 'INT_MAX');
});

test('a bare identifier not on the whitelist is ignored (e.g. the user\'s own variable)', () => {
	const text = 'int size = 5;';
	const whitelist = new Set(['INT_MAX']);
	const match = findGlobalNameAt(text, 5, 5, whitelist);
	assert.equal(match, undefined);
});

test('does not match a whitelisted name as part of a longer identifier', () => {
	const text = 'int MY_INT_MAX = 5;';
	const whitelist = new Set(['INT_MAX']);
	const match = findGlobalNameAt(text, 8, 8, whitelist);
	assert.equal(match, undefined);
});

test('cursor outside any identifier returns undefined', () => {
	const text = 'int x = INT_MAX;';
	const whitelist = new Set(['INT_MAX']);
	const match = findGlobalNameAt(text, 3, 3, whitelist);
	assert.equal(match, undefined);
});

test('matches inside comments', () => {
	const text = '// INT_MAX is the largest int';
	const whitelist = new Set(['INT_MAX']);
	const match = findGlobalNameAt(text, 5, 5, whitelist);
	assert.equal(match?.text, 'INT_MAX');
});

test('matches inside string literals', () => {
	const text = 'auto s = "INT_MAX";';
	const whitelist = new Set(['INT_MAX']);
	const match = findGlobalNameAt(text, 12, 12, whitelist);
	assert.equal(match?.text, 'INT_MAX');
});

test('a selection overlapping a whitelisted identifier resolves it', () => {
	const text = 'int x = INT_MAX;';
	const whitelist = new Set(['INT_MAX']);
	// selection covers "T_MA", starting two chars into "INT_MAX"
	const match = findGlobalNameAt(text, 10, 13, whitelist);
	assert.equal(match?.text, 'INT_MAX');
});
