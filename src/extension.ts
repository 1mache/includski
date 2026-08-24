import * as vscode from 'vscode';
import { IncludeQuickFixProvider } from './codeActionProvider';
import { loadGlobalNameWhitelist, loadMergedMap } from './mappings';

export function activate(context: vscode.ExtensionContext) {
	const map = loadMergedMap(context);
	const globalNameWhitelist = loadGlobalNameWhitelist(context);

	context.subscriptions.push(
		vscode.languages.registerCodeActionsProvider(
			{ language: 'cpp' },
			new IncludeQuickFixProvider(map, globalNameWhitelist),
			{ providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] },
		),
	);
}

export function deactivate() {}
