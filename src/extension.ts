import * as vscode from 'vscode';
import { IncludeQuickFixProvider } from './codeActionProvider';
import { loadMergedMap } from './mappings';

export function activate(context: vscode.ExtensionContext) {
	const map = loadMergedMap(context);

	context.subscriptions.push(
		vscode.languages.registerCodeActionsProvider(
			{ language: 'cpp' },
			new IncludeQuickFixProvider(map),
			{ providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] },
		),
	);
}

export function deactivate() {}
