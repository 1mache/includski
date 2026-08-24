# includski

VS Code extension offering a Quick Fix to insert the `#include` for a C++ standard-library name under the cursor, from a shipped JSON map (no clangd / compile_commands).

## Language

**Qualified name**:
A `std::` / `::std::` prefixed identifier (e.g. `std::vector`, `std::chrono::milliseconds`). Resolved by walking components right-to-left through the merged map.
_Avoid_: symbol, name (too generic — always say which kind)

**Global name**:
A bare (unprefixed) identifier that is valid in the global namespace because it comes from a C-compat wrapper header (`<cstdint>`, `<climits>`, `<cstddef>`, ...) — e.g. `INT_MAX`, `uint32_t`, `NULL`. Matched only against a closed, scraper-tagged whitelist, never against arbitrary bare identifiers, to avoid colliding with the user's own identically-named locals/macros.
_Avoid_: unqualified name, macro (too narrow — the whitelist also covers typedefs)

**C-compat wrapper header**:
One of the fixed set of `c*` standard headers (`cstdint`, `cstdio`, `climits`, ...) that mirror a legacy C `.h` header and whose primary symbols are guaranteed usable both as `std::x` and as bare global `x`. Source of every **global name**.
_Avoid_: C header (ambiguous with the `*.h` pages the scraper skips entirely)
