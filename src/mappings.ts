import * as fs from 'node:fs';
import * as vscode from 'vscode';

/** Loads res/mappings.json merged with res/overrides.json (override keys win). */
export function loadMergedMap(context: vscode.ExtensionContext): Record<string, string> {
	const mappings = readJsonMap(context.asAbsolutePath('res/mappings.json'));
	const overrides = readJsonMap(context.asAbsolutePath('res/overrides.json'));
	return { ...mappings, ...overrides };
}

function readJsonMap(path: string): Record<string, string> {
	try {
		return JSON.parse(fs.readFileSync(path, 'utf8'));
	} catch {
		return {};
	}
}
