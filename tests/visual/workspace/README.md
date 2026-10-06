# Telas do Workspace sem login e sem banco

```bash
npx vite build --config vite.conversations.config.mjs   # gera o bundle
node tests/visual/workspace/serve.mjs                   # http://localhost:5199/
```

Cada tela vem de um fixture em `fixtures.mjs` (JSON de bootstrap). Para criar outra, copie um fixture e ajuste os campos que a tela pedir; um campo faltando aparece como erro no console.
