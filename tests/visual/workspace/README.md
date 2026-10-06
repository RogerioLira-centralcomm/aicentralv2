# Telas do Workspace sem login e sem banco

```bash
npx vite build --config vite.conversations.config.mjs   # gera o bundle
node tests/visual/workspace/serve.mjs                   # http://localhost:5199/
```

Cada tela vem de um fixture em `fixtures.mjs` (JSON de bootstrap). Para criar outra, copie um fixture e ajuste os campos que a tela pedir; um campo faltando aparece como erro no console.

Porta: `PORT=5204 node tests/visual/workspace/serve.mjs` (padrão 5199). O servidor lê `fixtures.mjs` só ao iniciar: reinicie depois de editar.

Telas preenchidas (auditoria de 2026-10-06): `marca-completa` (análise, paleta, fontes, ativos, fontes da auditoria), `projeto-cheio` e `projeto-cheio-<visão>` (arquivos, tarefas, entregas, links, conversas), `projetos`, `projetos-vazio`, `marcas`, `marcas-vazio`, `conta-equipe`, `conta-equipe-membro`, `conta-perfil`, `conta-agencia`, `conta-agencia-membro`. As versões `-membro` usam `admin: false`.

Os formatos seguem o que `cadu_workspace/routes.py` envia; por exemplo `brand.analysisMetadata.sources` é lista de URLs (um número derruba a tela inteira da Marca).
