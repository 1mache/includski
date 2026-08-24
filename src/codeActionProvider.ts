import * as vscode from 'vscode';
import { hasBitsStdcpp, hasHeaderIncluded } from './includeCheck';
import { resolveHeader } from './lookup';
import { findQualifiedNameAt } from './qualifiedName';

export const PRINT_INCLUDE_COMMAND = 'includski.printInclude';

export class IncludeQuickFixProvider implements vscode.CodeActionProvider {
	constructor(private readonly map: Record<string, string>) {}

	provideCodeActions(
		document: vscode.TextDocument,
		range: vscode.Range,
	): vscode.CodeAction[] {
		const text = document.getText();
		const match = findQualifiedNameAt(
			text,
			document.offsetAt(range.start),
			document.offsetAt(range.end),
		);
		if (!match) {
			return [];
		}

		const header = resolveHeader(match.text, this.map);
		if (!header) {
			return [];
		}

		if (hasBitsStdcpp(text) || hasHeaderIncluded(text, header)) {
			return [];
		}

		const action = new vscode.CodeAction(`Include ${header}`, vscode.CodeActionKind.QuickFix);
		action.command = {
			command: PRINT_INCLUDE_COMMAND,
			title: `Include ${header}`,
			arguments: [header],
		};

		return [action];
	}
}
