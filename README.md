# includski

Small personal project to learn TypeScript. It's a VS Code extension that offers a Quick Fix to insert the right C++ standard-library `#include` for a `std::` name (or a known global like `INT_MAX`, `uint32_t`) under the cursor — no clangd or compile_commands needed.

## Install

```bash
git clone <this-repo-url>
cd includski
npm install
```

## Run

Open the folder in VS Code, then press `F5` (or Run → Start Debugging). This launches an Extension Development Host window with `includski` active.

In that window, open a `.cpp` file, place the cursor on a `std::` name (e.g. `std::vector`) or a global like `INT_MAX`, and trigger the Quick Fix (lightbulb, or `Ctrl+.`).

![Quick Fix demo](images/quickfix-demo.jpg)

## Other useful commands

```bash
npm run compile     # build once
npm run watch        # rebuild on file change
npm run lint         # lint src/
npm test             # run extension tests
npm run test:unit    # run unit tests only
```
