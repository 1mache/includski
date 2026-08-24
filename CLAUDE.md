# includski

VS Code extension that offers a Quick Fix to insert the C++ standard-library `#include` for a `std::` name under the cursor. Personal tool: no clangd / compile_commands required. Mapping is a shipped JSON table, not a compiler.

This file is the locked product spec. Change the spec here before changing behaviour.

## Current repo vs this spec

The workspace is still a Yo Code Hello World stub (`includski.helloWorld`), empty `res/mappings.json` (`{}`), and a Crawlee scraper in `scripts/generate_cppreference_mappings.py` that is meant to fill the map from cppreference and has not produced a usable file (hard-fail on any request error; index path may miss `/w/cpp/header`).

Until the spec below is implemented, the extension does not add includes.

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
