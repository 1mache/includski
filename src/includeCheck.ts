function escapeRegExp(value: string): string {
	return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function includePattern(name: string): RegExp {
	return new RegExp(`^[ \\t]*#[ \\t]*include[ \\t]*<[ \\t]*${escapeRegExp(name)}[ \\t]*>`, 'm');
}

/** Whitespace-tolerant check for `#include <header>` already present. */
export function hasHeaderIncluded(text: string, header: string): boolean {
	const name = header.replace(/^<|>$/g, '');
	return includePattern(name).test(text);
}

/** Whitespace-tolerant check for `#include <bits/stdc++.h>` (exact name, not a substring match). */
export function hasBitsStdcpp(text: string): boolean {
	return includePattern('bits/stdc++.h').test(text);
}
