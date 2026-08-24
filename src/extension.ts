import * as vscode from 'vscode';
import { IncludeQuickFixProvider, PRINT_INCLUDE_COMMAND } from './codeActionProvider';
import { loadMergedMap } from './mappings';

export function activate(context: vscode.ExtensionContext) {
	const map = loadMergedMap(context);

	context.subscriptions.push(
		vscode.commands.registerCommand(PRINT_INCLUDE_COMMAND, (header: string) => {
			console.log(`[includski] Include ${header}`);
		}),
		vscode.languages.registerCodeActionsProvider(
			{ language: 'cpp' },
			new IncludeQuickFixProvider(map),
			{ providedCodeActionKinds: [vscode.CodeActionKind.QuickFix] },
		),
	);
}

export function deactivate() {}
