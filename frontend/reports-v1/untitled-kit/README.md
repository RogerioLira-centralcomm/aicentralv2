# Skin Untitled UI do Reports

Esta pasta contém só o **tema e o build de CSS** do Reports (`styles/`, `package.json`). Os componentes base (`button`, `label`, `hint-text`, `tooltip`, `input-base`, `textarea-base`, `native-select-base`, ilustração de documentos) e os utilitários vivem no kit único do design system: `frontend/cadu-design-system/untitled-kit/`.

O kit único tem duas camadas de formulário:

- **Adaptações Cadu** (`input.tsx`, `textarea.tsx`, `native-select.tsx`, `modal.tsx`, `tabs.tsx`): usadas pelo Workspace por meio dos `Cadu*`.
- **Versões completas da CLI `untitledui` v8** (`input-base.tsx`, `textarea-base.tsx`, `native-select-base.tsx`): usadas pelos adaptadores `Reports*`. O `native-select-base` tem ajustes locais para preservar `id`, rótulos acessíveis e opções desativadas.

`npm run build:reports` executa o Tailwind 4 desta pasta e gera `aicentralv2/static/cadu_connect/react/untitled.css` a partir das fontes listadas em `styles/reports-kit.css` (sem preflight), depois roda o Vite de Reports. Ao adicionar um componente ao kit, inclua o arquivo no `@source` da skin que o usa. Alterações em componentes oficiais devem vir da CLI num projeto temporário e ser revisadas no diff.

Referências: [instalação](https://www.untitledui.com/react/docs/installation), [CLI](https://www.untitledui.com/react/docs/cli), [Vite](https://www.untitledui.com/react/integrations/vite).
