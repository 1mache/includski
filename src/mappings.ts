import * as fs from 'node:fs';
import * as vscode from 'vscode';

/** Loads res/mappings.json merged with res/overrides.json (override keys win). */
export function loadMergedMap(context: vscode.ExtensionContext): Record<string, string> {
	const mappings = readJson<Record<string, string>>(context.asAbsolutePath('res/mappings.json'), {});
	const overrides = readJson<Record<string, string>>(context.asAbsolutePath('res/overrides.json'), {});
	return { ...mappings, ...overrides };
}

/** Loads res/globals.json: the closed whitelist of bare global names. */
export function loadGlobalNameWhitelist(context: vscode.ExtensionContext): ReadonlySet<string> {
	const names = readJson<string[]>(context.asAbsolutePath('res/globals.json'), []);
	return new Set(Array.isArray(names) ? names : []);
}

function readJson<T>(path: string, fallback: T): T {
	try {
		return JSON.parse(fs.readFileSync(path, 'utf8'));
	} catch {
		return fallback;
	}
}
