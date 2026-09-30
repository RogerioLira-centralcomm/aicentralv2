# Revisão da adequação visual — Reports

## Implementação nesta rodada

- `ReportsPanelShell` reúne cabeçalho com ícone, título, descrição, fechamento acessível, corpo rolável e rodapé opcional.
- Migração do drawer compartilhado, catálogo/paleta do Flow, inspector, montagem automática, sugestões, explorador e detalhes do monitoramento e navegação ao vivo.
- Inspector com Resumo/Configuração e navegação de abas por teclado. Aplicar proposta permanece no rodapé.
- Drawer preserva formulário ao solicitar confirmação de descarte. Fechar sem alterações mantém o comportamento direto.
- CTA padrão passa a ser botão, com submissões explícitas nas telas existentes. Selects do PageChrome usam o wrapper compartilhado. Tabs e tabelas recebem tratamento comum.
- Estados vazios usam a ilustração Documents do kit local Untitled; não foi importado template comercial não disponível.
- Correções de grupos: arestas agregadas não podem ser reconectadas; validação defensiva exige etapas reais. Mover grupo marca seus membros como editados.
- Removidos estilos do cabeçalho antigo de drawers; ajustes visuais ficam no módulo `reports-refinement.css`.

## Supervisão com a skill TypeSafe

A documentação de confiança foi consultada em https://docs.typesafe.ai/confidence. O julgamento probabilístico não substitui autorização, regra determinística ou teste. Não houve chamada ao modelo remoto nem alegação de aprovação externa. Contratos de dados, ownership e isolamento não foram alterados nesta migração visual.

## Evidências

- Regressões JavaScript de autoria, etapas e política de arestas; guardas adicionais para reconexão agregada, autoria do grupo e estrutura de painel.
- 17 testes Python de Studio, workspace v2 e schema aprovados.
- Playwright de edição e monitoramento em 1920, 1440, 1366 e 1024: seleção, exploração, pausa, comandos e ausência de overflow horizontal.
- Smoke de 11 páginas com respostas controladas: overview, customers, accounts, campaigns, reports, imports, monitor, supertag, events, links e access; desktop e 390 px. Essas capturas validam renderização inicial, não todas as submissões com dados reais.
- Build de produção executado. Persistem avisos de chunk >500 kB e diretiva use client ignorada pelo Vite.

## Limites e continuidade do plano

A base comum e os painéis prioritários foram migrados. O plano amplo ainda exige validação funcional de cada formulário com dados reais, estados de erro/permissão por rota, extração gradual das páginas de main.jsx e revisão completa dos estilos legados. As capturas de fixture não comprovam integração de importação, convites ou publicação em produção.

Sem deploy nesta rodada: o ambiente permanece sem credencial GitHub para push e sem acesso SSH configurado. Não houve alteração no banco.

## Fechamento local

- Removidas as regras antigas de padding/borda/sombra dos painéis posicionados do editor, deixando a apresentação sob responsabilidade do shell compartilhado. Mantidas regras de posicionamento e visibilidade.
- Proteção de fechamento compara valores atuais com a abertura do formulário: reverter os campos permite fechar sem alerta; continuar editando preserva o formulário montado e os valores. Confirmação recebe foco.
- Teste Playwright específico de campanha cobre abrir, editar, solicitar fechamento, continuar, conferir valor, reverter e fechar.
- A migração visual comum está aplicada às superfícies existentes. A extração completa de main.jsx continua sendo refatoração estrutural separada; não foi apresentada como concluída.
- Validação de submissões contra APIs reais e publicação permanece dependente do ambiente de homologação/produção. Os testes locais não gravam dados no servidor.
