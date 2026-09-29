# Untitled UI React no Reports

Esta pasta contém os componentes base gerados pela CLI oficial `untitledui` v0.1.68 em 29/09/2026, com `--lib-version 8`: `button`, `input`, `select-native`, `textarea`, `tooltip`, utilitários e os arquivos de tema/tipografia necessários. O código foi gerado em um projeto temporário e copiado para o entry point de Reports. O `select-native` recebeu ajustes locais para preservar `id`, rótulos acessíveis e opções desativadas. Não contém componentes PRO.

O projeto principal usa Tailwind 3. Por isso, `npm run build:reports` executa o Tailwind 4 desta pasta para gerar `aicentralv2/static/cadu_connect/react/untitled.css` e depois executa o Vite de Reports. `styles/reports-kit.css` inclui tema e utilitários sem preflight; o template de Reports carrega esse CSS após `app.css`. Alterações em componentes base devem ser feitas via CLI no projeto temporário e revisadas no diff antes de substituir a fonte local.

Integração em uso: Button, Input, NativeSelect e TextArea nas áreas de Reports fora de Fluxos, com adaptadores em `ReportsActionButton.jsx`, `ReportsFieldInput.jsx`, `ReportsNativeSelect.jsx` e `ReportsTextArea.jsx` que preservam os eventos e valores dos formulários existentes. O cabeçalho e os filtros compartilhados usam Button oficial. Drawers e confirmações usam React Aria Dialog/Modal; as abas das áreas convertidas oferecem setas, Home e End. O canvas de Fluxos é mantido por outra frente de trabalho.

Referências: [instalação](https://www.untitledui.com/react/docs/installation), [CLI](https://www.untitledui.com/react/docs/cli), [Vite](https://www.untitledui.com/react/integrations/vite).
