# Untitled UI React integration

This directory adopts Untitled UI React as its component source. The source of record is the official Untitled UI CLI output for library v8 and the official integration documentation:

- https://www.untitledui.com/react/docs/installation
- https://www.untitledui.com/react/integrations/vite
- https://www.untitledui.com/react/docs/theming

## Workspace normalization boundary

The Workspace entry currently shares React 18, Vite 6, and one compiled stylesheet with Conversations. The official library v8 Vite starter currently uses Tailwind CSS 4 and React Aria Components. The existing application pipelines compile Tailwind CSS 3.4. Do not import the kit's global stylesheet into the shared entry until the isolated Tailwind 4 build decision is complete; a Tailwind preflight or broad selectors can change the dark Conversations surface.

`tokens.css` contains the CADU-to-Untitled semantic token bridge. The official v8 Button and Modal are vendored in `untitled-kit` and used through `CaduButton` and `CaduModal`. Input, NativeSelect, Textarea and Tabs are adapted from the official React kit for this application's React 18 runtime and used through `CaduInput`, `CaduSelect`, `CaduTextarea` and `CaduViewTabs`. Their Tailwind 4 stylesheet is compiled separately by `untitled-kit/package.json` without Tailwind preflight. Only the six React Workspace templates load that stylesheet; Conversations remains dark and does not load it.

## Source and license handling

Use `npx untitledui@latest add <component> --type base --lib-version 8` from a disposable or correctly configured probe first. The CLI must be run with `--dir` pointing to the intended project. Never run `init` against the CentralX repository root. Keep the generated source with its upstream header and the CLI/library version recorded here. Do not copy PRO components unless the project has the appropriate license entitlement.

## Current stage

- Inventory completed for the shared Workspace/Conversations React entry and current Tailwind pipelines.
- Dedicated Tailwind 4 build boundary implemented in `untitled-kit`, with no preflight or change to the application's Tailwind 3 build.
- Untitled UI React v8 Button, Modal, TextField, NativeSelect, Textarea and Tabs primitives integrated through CADU wrappers; catalog creation, detail dialogs, account forms, credit purchase and the project library use them.
- The Workspace Dock account control now displays its menu when the caller supplies one; keyboard arrows, Escape and focus return are covered by browser verification. Conversation Dock still uses its direct account link.
- Brand scale maps to the Workspace teal tokens. Browser verification covers catalog and creation actions at desktop, tablet and phone widths.
- Remaining migration: rich menus, account tables and secondary Workspace forms and actions. Existing controls must remain usable while each surface is converted.

## Kit único (Workspace e Reports)

Todos os componentes Untitled vivem em `untitled-kit/`. O Reports deixou de ter cópia própria: seus adaptadores importam `button`, `input-base`, `textarea-base`, `native-select-base` e `illustrations/documents` daqui, e mantém em `frontend/reports-v1/untitled-kit/` apenas a skin de CSS. Cada produto compila o próprio CSS (`workspace-kit.input.css` e `reports-kit.css`) com os temas dele, listando em `@source` apenas os arquivos que usa. A convergência de `input`, `textarea` e `native-select` adaptados com as versões `*-base` fica para uma fase própria, com verificação visual do Workspace.
