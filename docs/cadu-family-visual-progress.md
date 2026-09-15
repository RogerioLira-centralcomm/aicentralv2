# Aplicação do protótipo na família Python

## Entrega local — 15/09/2026

- Tokens de cor por produto, tipografia e estrutura de navegação baseados em
  `output/mockups/cadu-platform.html` e no design system da família.
- Seletor compacto com cliente, marca e projeto; fechamento por Escape e clique
  externo. Organização de acesso não é alterada pela seleção de cliente.
- Entrada `inicio` para Workspace, SmartPlanner, Studio e Connect, disponível
  também a visitantes. Rotas de módulos existentes continuam disponíveis.
- Imagens de apresentação já existentes no projeto; nenhum dado fictício do
  protótipo foi incorporado às telas de produção.
- Início do Workspace usa apenas o inventário autorizado do cliente e permite
  selecionar um projeto. Home do Connect não carrega relatórios antecipadamente.
- Studio mantém navegação horizontal e não recebe o painel central de conversas.
- Áreas pendentes continuam identificadas como em migração. Não houve ativação
  de flags, alteração no banco, redirecionamento de PHP ou deploy.

## Evidências

- Prévia Flask local com fixtures: Workspace autenticado em 1440×900,
  820×1180 e 390×844; nomes longos truncados no seletor sem overflow horizontal
  da página. Menu de contexto legível no mobile; Escape fecha e devolve foco.
- SmartPlanner visitante: painel em tela cheia no mobile, campo desabilitado,
  convite para login; Escape devolve foco ao botão Conversas.
- Troca de SmartPlanner para Studio pela navbar; Studio público revisado em
  mobile e desktop, imagens carregadas e ausência do painel central.
- Sem erros de console nas páginas inspecionadas.
- 100 execuções de testes nas suítes family, foundation, copy_ads, family_chat
  e review_fixes passaram (há testes herdados repetidos).
- `node --check` e `git diff --check` passaram.

## Ainda não validado/concluído

- Matriz completa de produtos × viewports × estados de rede/permissão.
- Login real, cookies entre domínios, banco real e integração Dify ponta a ponta.
- Paridade integral do chat PHP, telas operacionais de cada módulo e retorno
  do gerenciamento de marcas ao trabalho do Studio.
- Skills continua usando a interface existente; nenhuma alteração nesta etapa.
