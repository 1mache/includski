import * as vscode from 'vscode';
import { hasBitsStdcpp, hasHeaderIncluded } from './includeCheck';
import { findIncludeInsertion } from './insertPosition';
import { resolveHeader } from './lookup';
import { findQualifiedNameAt } from './qualifiedName';

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
		const insertion = findIncludeInsertion(text, header);
		action.edit = new vscode.WorkspaceEdit();
		action.edit.insert(document.uri, document.positionAt(insertion.offset), insertion.text);

		return [action];
	}
}
