# Cadu para ChatGPT — pacote de submissão

Status: pacote do plugin pronto em `plugins/cadu/` (manifesto com campos de listagem, 5 casos positivos e 3 negativos, 4 skills); ainda não submetido nem publicado. Faltam os itens de conta, a gravação de demonstração e a conta de demonstração, listados abaixo.

## Produto

- Nome: Cadu
- Categoria proposta: Marketing e produtividade
- Descrição curta: Acesse projetos, marcas, biblioteca e materiais de marketing do Cadu com autorização da sua conta.
- URL MCP: `https://workspace.centralcomm.media/mcp/cadu/v1`
- Logo: `aicentralv2/static/images/cadu/products/cadu-mcp-icon.svg`
- Distribuição: plugin público ligado ao servidor MCP remoto existente; sem novo backend.
- Autenticação: OAuth 2.1 Authorization Code com PKCE S256, refresh token, escopo por ferramenta e consentimento Cadu.

## Já verificado em produção (2026-10-06)

- `https://workspace.centralcomm.media/privacidade`, `/termos` e `/workspace/contato` respondem 200.
- Metadados OAuth (`/.well-known/oauth-authorization-server` e `oauth-protected-resource/mcp/cadu/v1`) respondem 200, com PKCE S256, refresh token e registro dinâmico de cliente em `auth.centralcomm.media`.
- O endpoint MCP sem token responde 401 com `WWW-Authenticate` e `resource_metadata`.

## Pendências antes do envio

Só a Central Comm pode fazer:
- Confirmar identidade verificada (individual ou empresarial) e a permissão `api.apps.write` na organização correta; verificar o domínio no portal.
- Gravar a demonstração e preencher `extensions.com.openai.review.demo_recording_url` no manifesto (campo obrigatório; ainda ausente).
- Criar a conta de demonstração: sem MFA, dados fictícios, com marca, projeto, Planner e créditos, e permissões de leitura e escrita.
- Confirmar os redirects HTTPS oficiais do ChatGPT no cliente OAuth.
- Subir esta versão ao servidor (o `git pull` estava travado pelo bundle `static/cadu_planner/react/app.js`) e reiniciar o serviço; refazer a conexão OAuth para ganhar `brands:write` e `artifacts:write`.
- Decidir `commerce: true` no manifesto: está declarado porque `credits.purchase_package` existe (pedido de compra por administrador, sem pagamento na conversa).
- Fazer Scan Tools e revisar nome, descrição, schemas, escopos, custos e as dicas `readOnlyHint`, `openWorldHint`, `destructiveHint`.
- Confirmar elegibilidade do plugin para os planos e regiões pretendidos (campo `publication.countries`).

## Roteiro da gravação de demonstração (3 a 4 minutos)

1. Instalar o plugin e conectar: tela de consentimento do Cadu com as permissões, e aprovar.
2. "Quero começar com um cliente novo no Cadu": o agente segue a skill de primeiros passos.
3. Cadastrar a marca Bomfim Cargas e enviar o logo; mostrar `brands.get_context`.
4. Pedir a auditoria completa: o agente mostra o custo estimado e o tempo e pede confirmação; confirmar e abrir o link da marca no Cadu.
5. "Quais audiências de executivos existem no Planner?": cards com imagem, logo da plataforma e link; aprofundar um item.
6. Abrir uma sessão do Studio para um anúncio 4:5 e mostrar o link.
7. Mostrar a revogação da conexão em Integrações.

## Prompts iniciais propostos

1. “Resuma o objetivo, o público e as decisões deste projeto. Cite as fontes do Cadu usadas.”
2. “Pesquise os materiais do projeto e prepare um briefing de campanha com o que já está definido e o que falta decidir.”
3. “Consulte a identidade da marca e proponha três ângulos de comunicação para esta campanha.”
4. “Compare o relatório mais recente com o plano de mídia e destaque os desvios que precisam de atenção.”
5. “Transforme estas notas em um rascunho editável no projeto selecionado e me mostre o que será salvo antes de concluir.”

## Casos de revisão

### Positivos

- Pesquisar um projeto com evidência: usar busca de conteúdo e citar fonte e trecho retornados.
- Preparar briefing: consultar projeto e fontes, separar fatos, lacunas e hipóteses, sem duplicar chamadas de busca.
- Criar material: produzir rascunho e preservar o original até pedido de finalização.
- Usar a marca: recuperar identidade e ativos do projeto correto antes de propor conteúdo.
- Revogar uma conexão: invalidar os tokens ativos e confirmar que uma chamada seguinte recebe não autorizado.

### Negativos

- Projeto sem acesso: negar a consulta sem revelar nomes ou conteúdo de outra conta.
- Escrita sem escopo aprovado: não executar; indicar a permissão necessária sem tentar outra rota para contornar o bloqueio.
- Módulo desativado: não chamar ferramenta omitida do catálogo; orientar ativação em Integrações → Agentes.
- Pedido de compra por membro sem papel de administrador: negar a solicitação e não criar ordem pendente.
- Fonte ou escopo indisponível: declarar a lacuna, sem inventar resultado ou alegar que o conteúdo foi pesquisado.

## Notas de manutenção

- Reenviar o MCP para revisão após alterações incompatíveis na lista ou schema de ferramentas.
- Acompanhar mudanças de ferramenta e manter o contrato compatível com os snapshots aprovados pelos workspaces.
- O diretório público é uma forma de instalação e descoberta; o endpoint, a autorização, os limites por escopo e as regras de acesso permanecem no Cadu.
