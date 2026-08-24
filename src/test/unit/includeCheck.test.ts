import assert from 'node:assert/strict';
import { test } from 'node:test';
import { hasBitsStdcpp, hasHeaderIncluded } from '../../includeCheck';

test('detects an existing include', () => {
	assert.equal(hasHeaderIncluded('#include <vector>\n', '<vector>'), true);
});

test('is whitespace tolerant', () => {
	assert.equal(hasHeaderIncluded('#  include   <  vector  >\n', '<vector>'), true);
});

test('does not match a different header', () => {
	assert.equal(hasHeaderIncluded('#include <string>\n', '<vector>'), false);
});

test('detects bits/stdc++.h', () => {
	assert.equal(hasBitsStdcpp('#include <bits/stdc++.h>\n'), true);
});

test('does not substring-match "bits"', () => {
	assert.equal(hasBitsStdcpp('#include <bitset>\n'), false);
});
