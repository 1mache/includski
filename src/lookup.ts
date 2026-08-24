const STD_PREFIX_PATTERN = /^(?:::)?std::/;

/**
 * Resolve a `std::` / `::std::` qualified name to a header, per the spec's
 * right-to-left walk: strip template args, split on `::`, and return the
 * header for the first (rightmost) identifier found in the map.
 */
export function resolveHeader(
	qualifiedName: string,
	map: Record<string, string>,
): string | undefined {
	if (!STD_PREFIX_PATTERN.test(qualifiedName)) {
		return undefined;
	}

	const withoutTemplateArgs = qualifiedName.split('<')[0];
	const rest = withoutTemplateArgs.replace(STD_PREFIX_PATTERN, '');
	const segments = rest.split('::').filter((segment) => segment.length > 0);

	for (let i = segments.length - 1; i >= 0; i--) {
		const header = map[segments[i]];
		if (header) {
			return header;
		}
	}

	return undefined;
}
