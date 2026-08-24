# includski

VS Code extension that offers a Quick Fix to insert the C++ standard-library `#include` for a `std::` name under the cursor. Personal tool: no clangd / compile_commands required. Mapping is a shipped JSON table, not a compiler.

This file is the locked product spec. Change the spec here before changing behaviour.

## Current repo vs this spec

The spec below is implemented: `IncludeQuickFixProvider` (`src/codeActionProvider.ts`) is registered for `{ language: 'cpp' }` with `providedCodeActionKinds: [QuickFix]`, activation is `onLanguage:cpp`, and `contributes` is empty (Hello World command removed). Lookup (`src/lookup.ts`), qualified-name matching (`src/qualifiedName.ts`), include-presence checks (`src/includeCheck.ts`), and insert-position rules (`src/insertPosition.ts`) each have unit tests under `src/test/unit`.

`scripts/generate_cppreference_mappings.py` is fixed and has produced a committed `res/mappings.json` (0 scrape errors, 29 collisions recorded in `res/scrape-collisions.json`). `res/overrides.json` exists but is still empty `{}` — the expected override examples (`move`, `forward`, `size`, `begin`, `end`) are not yet added, so those `std::` names don't resolve.

## Product

- **Documents:** `language: cpp` only.
- **Trigger:** `CodeActionProvider` returning `CodeActionKind.QuickFix` for the range under the cursor. Lightbulb / `Ctrl+.`. No command-palette command, no diagnostics, no underline, no `source.*` / on-save actions, no as-you-type rewrite.
- **Activation:** `onLanguage: cpp` (or equivalent) so opening a C++ file is enough. A command is not required for activation.
- **Name matching:** `std::` and `::std::` only. No `using namespace std`, no `using std::vector`.
- **Parser:** regex for qualified names. Hits inside comments and strings are accepted.
- **Headers:** C++ standard library only (`<vector>`, `<cstdint>`, …). Not project headers, not third-party, not `*.h` C-compat pages as scrape targets.

clangd already offers “Add include” when a compilation database exists. This extension exists for editing **without** that.

## When the Quick Fix exists

Return an action only when all of these hold:

1. The cursor (or selection) sits on a `std::` / `::std::` qualified name.
2. Lookup (below) yields a header.
3. That header is not already present as `#include <…>` (whitespace-tolerant).
4. The file does not already `#include <bits/stdc++.h>` (exact header name, spacing-tolerant; do not substring-match `bits`).

One action for the name under the cursor: include that one header. Title shape: `Include <vector>`.

## Lookup

Take the qualified-id after `std` / `::std`. Ignore template arguments (`std::vector<int>` → `vector`).

Split remaining identifiers on `::`. Walk **right-to-left**. The first identifier that exists as a key in the merged map wins.

Examples:

| Cursor name | Walk | Result if mapped that way |
|---|---|---|
| `std::vector` | `vector` | `<vector>` |
| `std::vector<int>` | `vector` | `<vector>` |
| `std::chrono::milliseconds` | `milliseconds`, then `chrono` | `<chrono>` when either key maps there |
| `std::pmr::vector` | `vector`, then `pmr` | `<vector>` if `vector` is in the map (**not** `<memory_resource>` unless `vector` is absent and `pmr` is present) |
| `std::filesystem::path` | `path`, then `filesystem` | `<filesystem>` when `path` or `filesystem` maps there |
| `::std::string` | `string` | `<string>` |

Known nested-namespace names (v1 freeze; hand-maintained, not scraped as a special list). They are ordinary map keys if present; they do **not** change walk order:

`chrono`, `filesystem`, `pmr`, `ranges`, `views`, `placeholders`, `literals`, `this_thread`, `chrono_literals`, `string_literals`, `string_view_literals`

## Insert position

Always `#include <header>` (angle brackets).

1. If the file already has any `#include`, insert after the last one.
2. Else if `#pragma once` is present, insert after that line.
3. Else if a classic include guard is present (`#ifndef` immediately followed by `#define` of the same macro), insert after that pair.
4. Else insert at line 0.

## Mapping data

Runtime reads committed files. Never crawl the network from the extension.

| File | Role |
|---|---|
| `res/mappings.json` | Generated `{ "symbol": "<header>", ... }`. Committed. |
| `res/overrides.json` | Hand-maintained. Merged **on top** of scrape; override keys always win. Committed. |
| `res/scrape-errors.json` | Failed request URLs and reasons. Extension does not load this. |
| `res/scrape-collisions.json` | Symbols seen on more than one header; first index-order header kept in the map. Extension does not load this. |

Merged map used at runtime: `mappings.json` then `overrides.json`.

### Generator (`scripts/generate_cppreference_mappings.py`)

Maintainer tool only. Polite crawl of https://en.cppreference.com C++ header pages.

**Include in the map**

- “Primary” entities on each header page: table rows under headings such as Classes, Types, Type aliases, Macros, Constants, Enumerations, Objects.
- Skip Functions, Range access, Non-member functions, and Includes (those rows are other headers or shared algorithms like `begin` / `swap`).
- Inject the header stem as a key even if tables are odd (`<vector>` → `"vector": "<vector>"`, `<chrono>` → `"chrono": "<chrono>"`).
- C++ `c*` wrappers (`<cstdio>`, `<cstdint>`, …). Skip `*.h` C-compat pages.

**Collisions:** first header in cppreference index order wins. Record losers in `scrape-collisions.json` so overrides can be added later.

**Failures:** write whatever symbols succeeded to `mappings.json`. Write failures to `scrape-errors.json`. Exit non-zero if any request failed. Do not abort with an empty `{}` solely because one URL failed. Do not put error strings into the symbol map.

**Index URLs:** handle both `/cpp/header` and `/w/cpp/header` so the index is processed as an index, not as a header page.

**Overrides (expected examples, not exhaustive):** names that live in `<utility>` / `<iterator>` / similar and would be wrong or missing from primaries — e.g. `move`, `forward`, `size`, `begin`, `end` — belong in `overrides.json` when we care about them.

## Out of scope (v1)

- Project / third-party includes
- Language modes other than `cpp` (`c`, CUDA, Objective-C++)
- tree-sitter
- Sorting includes / clang-format / IWYU
- Treating umbrella headers other than `<bits/stdc++.h>` as “has everything”
- Offering multiple headers in the lightbulb
- Semantic correctness beyond the JSON map
- Tests as a definition of “works” (optional later)

## “Works”

Manual: F5, open a `.cpp`, cursor on `std::vector` with no includes → one Quick Fix “Include `<vector>`” → insert at the position rules above. Cursor on `std::chrono::milliseconds` → `<chrono>` when lookup hits. Cursor on `std::vector` when `<vector>` or `<bits/stdc++.h>` is already included → no action.

A successful scrape is not required to call the editor path done; a committed non-empty map is required for real std names to resolve.

## Implementation notes (when coding starts)

- Register `providedCodeActionKinds: [CodeActionKind.QuickFix]`.
- Document selector: `{ language: 'cpp' }`.
- Remove or stop shipping the Hello World command once the provider exists.
- Load merged JSON from `ExtensionContext.extensionUri` / `asAbsolutePath`, not from cwd.
- Python deps for the scraper live with the scraper (e.g. venv + requirements); they are not extension runtime deps.

# Python Expert Agent – Best Practices

This file defines the coding standards, safety rules, and workflow expectations for a Python expert AI agent. All code you write or modify MUST follow these rules unless explicitly overridden by the user.

---

## 1. Style & Formatting (PEP 8 Baseline)

- Use **4 spaces** per indentation level; **no tabs**.
- Limit lines to **88 characters** (black/ruff default); docstrings/comments to **72 characters**.
- Separate top-level definitions with **2 blank lines**; methods in a class with **1 blank line**.
- Use **`ruff`** and **`black`** (or equivalent) for formatting and linting; enforce in CI.

---

## 2. Naming Conventions

- **Modules / packages**: `lower_with_under`
- **Classes / types**: `CapWords`
- **Functions / methods / variables**: `lower_with_under`
- **Constants**: `UPPER_WITH_UNDER`
- **Private / internal helpers**: prefix with `_` (e.g. `_internal_helper`).

Avoid emoji, unicode symbols, or non-ASCII characters in identifiers.

---

## 3. Imports & File Structure

- Imports at the top of the file, grouped and sorted:
  1. Standard library
  2. Third-party packages
  3. Local project imports
- Avoid wildcard imports (`from x import *`).
- Use explicit relative imports inside packages.
- Each `.py` file should have a clear, single responsibility.

---

## 4. Type Hints (Modern Python)

- Annotate **all public functions and methods** (parameters and return types).
- Use modern syntax:
  - `list[str]`, `dict[str, int]`, `tuple[int, ...]`
  - `X | Y` instead of `Union[X, Y]`
  - `T | None` instead of `Optional[T]`
- Use `from __future__ import annotations` in libraries targeting multiple Python 3.x versions.
- Use `dataclass`, `enum`, and `Protocol` for structured data and interfaces.
- Prefer Pydantic models for validated, structured I/O (APIs, configs, agent outputs).

---

## 5. Docstrings & Comments (PEP 257)

- Write docstrings for **all public modules, classes, functions, and methods**.
- Use triple double-quotes: `"""..."""`.
- One-line docstrings: keep on a single line.
- Multi-line docstrings:
  - First line: concise summary.
  - Blank line.
  - Details: behavior, arguments (with types), return value, and raised exceptions.
- Use `#` for inline comments; explain **why**, not **what**.
- Avoid tautological comments (e.g., “increment i by 1” above `i += 1`).

---

## 6. Error Handling & Robustness

- Use specific exception types; avoid bare `except:`.
- Avoid magic numbers; use named constants.
- Use context managers (`with`) for resources (files, sockets, DB connections).
- Prefer f-strings for formatting.
- Validate inputs (types, ranges) at API boundaries; use `pydantic` or similar for structured validation.
- Fail fast: raise early on invalid state instead of hiding errors.

---

## 7. Testing & Quality

- Write tests for all public behavior (unit tests; integration tests where relevant).
- Run linters (`ruff`, `pylint`) and type checkers (`mypy`, `pyright`) in CI.
- Keep functions small and single-purpose; refactor large functions.
- Prefer pure functions where possible; minimize hidden global state.

---

## 8. Agent-Specific Safety & Control

These rules are critical when the agent is writing, modifying, or executing Python code:

- **Cap agent loops**: always respect `max_iterations` / `max_steps` (e.g., 5–25) to prevent infinite tool-calling.
- **Validate tool arguments** with schemas (e.g., Pydantic) before execution.
- **Least privilege**: tools should be read-only by default; require explicit approval for destructive actions.
- **Sandbox code execution**: run untrusted code in isolated containers with resource limits.
- **Log every tool call**: name, args, result, latency; keep an audit trail.
- **Structured outputs**: use Pydantic models or JSON schemas for agent responses; retry on validation failure.
- **Grounding for RAG**: use retrieved context only; return “I don’t know” when retrieval is empty or insufficient.

---

## 9. Project Structure & Maintainability

- Use a clear layout, e.g.:

  ```text
  project_root/
    src/
      your_package/
    tests/
    docs/
    pyproject.toml
  ```

- Pin dependencies in `pyproject.toml` or `requirements.txt`; avoid implicit global state.
- Separate concerns:
  - Ingestion vs. query paths
  - Config vs. logic
  - Core vs. adapters (DB, external APIs, agents)
- Prefer small, composable modules over monolithic files.

---

## 10. Workflow Expectations for the Agent

When asked to write or modify Python code:

1. **Plan briefly** (in comments or a short explanation) before implementing.
2. **Follow all rules above** by default.
3. **Prefer clarity and correctness over cleverness**; optimize only when necessary and justified.
4. **Use type hints and docstrings** in all new public code.
5. **Ask for clarification** if requirements are ambiguous or conflict with these standards.
6. **When in doubt**, choose the more explicit, readable, and testable option.

---

## 11. Tooling Commands (Reference)

Use these as the canonical commands for style and quality checks (adjust paths as needed):

```bash
# Formatting
ruff format .

# Linting
ruff check .

# Type checking
mypy src/

# Tests
pytest tests/
```

The agent should assume these tools are available and write code that passes them without additional configuration.