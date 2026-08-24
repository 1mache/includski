import * as vscode from 'vscode';
import { findGlobalNameAt } from './globalName';
import { hasBitsStdcpp, hasHeaderIncluded } from './includeCheck';
import { findIncludeInsertion } from './insertPosition';
import { resolveHeader } from './lookup';
import { findQualifiedNameAt } from './qualifiedName';

export class IncludeQuickFixProvider implements vscode.CodeActionProvider {
	constructor(
		private readonly map: Record<string, string>,
		private readonly globalNameWhitelist: ReadonlySet<string> = new Set(),
	) {}

	provideCodeActions(
		document: vscode.TextDocument,
		range: vscode.Range,
	): vscode.CodeAction[] {
		const text = document.getText();
		const start = document.offsetAt(range.start);
		const end = document.offsetAt(range.end);

		const qualifiedMatch = findQualifiedNameAt(text, start, end);
		const header = qualifiedMatch
			? resolveHeader(qualifiedMatch.text, this.map)
			: this.resolveGlobalHeader(text, start, end);
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

	private resolveGlobalHeader(text: string, start: number, end: number): string | undefined {
		const globalMatch = findGlobalNameAt(text, start, end, this.globalNameWhitelist);
		return globalMatch ? this.map[globalMatch.text] : undefined;
	}
}
