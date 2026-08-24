const INCLUDE_LINE_PATTERN = /^[ \t]*#[ \t]*include\b.*$/gm;
const PRAGMA_ONCE_PATTERN = /^[ \t]*#[ \t]*pragma[ \t]+once\b.*$/m;
const INCLUDE_GUARD_PATTERN = /^[ \t]*#[ \t]*ifndef[ \t]+(\w+)[ \t]*\r?\n[ \t]*#[ \t]*define[ \t]+\1\b.*$/m;

export interface IncludeInsertion {
	/** Offset into the original text where `text` should be spliced in. */
	offset: number;
	/** Text to insert at `offset`, including its own line breaks. */
	text: string;
}

/**
 * Locates where `#include header` belongs in `text` per spec:
 * after the last `#include` if any exist, else after `#pragma once`,
 * else after a classic `#ifndef`/`#define` guard pair, else at line 0.
 */
export function findIncludeInsertion(text: string, header: string): IncludeInsertion {
	const offset = findInsertOffset(text);
	const needsLeadingNewline = offset > 0 && offset === text.length && text[offset - 1] !== '\n';
	return { offset, text: (needsLeadingNewline ? '\n' : '') + `#include ${header}\n` };
}

export function insertInclude(text: string, header: string): string {
	const { offset, text: insertText } = findIncludeInsertion(text, header);
	return text.slice(0, offset) + insertText + text.slice(offset);
}

function findInsertOffset(text: string): number {
	const lastInclude = lastMatchEnd(text, INCLUDE_LINE_PATTERN);
	if (lastInclude !== undefined) {
		return lineEnd(text, lastInclude);
	}

	const pragma = PRAGMA_ONCE_PATTERN.exec(text);
	if (pragma) {
		return lineEnd(text, pragma.index + pragma[0].length);
	}

	const guard = INCLUDE_GUARD_PATTERN.exec(text);
	if (guard) {
		return lineEnd(text, guard.index + guard[0].length);
	}

	return 0;
}

function lastMatchEnd(text: string, pattern: RegExp): number | undefined {
	pattern.lastIndex = 0;
	let match: RegExpExecArray | null;
	let last: RegExpExecArray | undefined;
	while ((match = pattern.exec(text))) {
		last = match;
	}
	return last ? last.index + last[0].length : undefined;
}

function lineEnd(text: string, afterContent: number): number {
	if (text[afterContent] === '\r' && text[afterContent + 1] === '\n') {
		return afterContent + 2;
	}
	if (text[afterContent] === '\n') {
		return afterContent + 1;
	}
	return afterContent;
}
