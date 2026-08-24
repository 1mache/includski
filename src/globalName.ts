export interface GlobalNameMatch {
	text: string;
	start: number;
	end: number;
}

const IDENTIFIER_PATTERN = /\b[A-Za-z_]\w*\b/g;

/**
 * Find a bare identifier overlapping [rangeStart, rangeEnd] (a cursor when
 * both are equal, a selection otherwise) that is a member of `whitelist`,
 * per the spec's "Global name lookup": closed whitelist only, never
 * arbitrary bare-identifier matching. Scans raw text, so hits inside
 * comments and strings are accepted.
 */
export function findGlobalNameAt(
	text: string,
	rangeStart: number,
	rangeEnd: number = rangeStart,
	whitelist: ReadonlySet<string>,
): GlobalNameMatch | undefined {
	IDENTIFIER_PATTERN.lastIndex = 0;
	let match: RegExpExecArray | null;

	while ((match = IDENTIFIER_PATTERN.exec(text))) {
		const start = match.index;
		const end = start + match[0].length;
		const overlaps = start <= rangeEnd && end >= rangeStart;

		if (overlaps && whitelist.has(match[0])) {
			return { text: match[0], start, end };
		}
	}

	return undefined;
}
