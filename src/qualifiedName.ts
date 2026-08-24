export interface QualifiedNameMatch {
	text: string;
	start: number;
	end: number;
}

const QUALIFIED_NAME_PATTERN = /(?:::)?\bstd(?:::[A-Za-z_]\w*)+/g;

/**
 * Find the `std::` / `::std::` qualified name (including any trailing
 * template args) overlapping [rangeStart, rangeEnd] (a cursor when both are
 * equal, a selection otherwise), per spec. When a template arg contains a
 * nested qualified name, the tightest (innermost) overlapping match wins.
 * Scans raw text, so hits inside comments and strings are accepted.
 */
export function findQualifiedNameAt(
	text: string,
	rangeStart: number,
	rangeEnd: number = rangeStart,
): QualifiedNameMatch | undefined {
	QUALIFIED_NAME_PATTERN.lastIndex = 0;
	let match: RegExpExecArray | null;
	let best: QualifiedNameMatch | undefined;

	while ((match = QUALIFIED_NAME_PATTERN.exec(text))) {
		const start = match.index;
		let end = start + match[0].length;

		if (text[end] === '<') {
			const templateEnd = findMatchingAngleBracketEnd(text, end);
			if (templateEnd !== undefined) {
				end = templateEnd;
			}
		}

		const overlaps = start <= rangeEnd && end >= rangeStart;
		if (overlaps && (!best || end - start < best.end - best.start)) {
			best = { text: text.slice(start, end), start, end };
		}
	}

	return best;
}

function findMatchingAngleBracketEnd(text: string, openIndex: number): number | undefined {
	let depth = 0;

	for (let i = openIndex; i < text.length; i++) {
		const char = text[i];

		if (char === '<') {
			depth++;
		} else if (char === '>') {
			depth--;
			if (depth === 0) {
				return i + 1;
			}
		} else if (char === ';' || char === '\n') {
			return undefined;
		}
	}

	return undefined;
}
