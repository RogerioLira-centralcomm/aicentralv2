# Cadu para ChatGPT — pacote de submissão

Status: preparação técnica; ainda não submetido nem publicado.

## Produto

- Nome: Cadu
- Categoria proposta: Marketing e produtividade
- Descrição curta: Acesse projetos, marcas, biblioteca e materiais de marketing do Cadu com autorização da sua conta.
- URL MCP: `https://workspace.centralcomm.media/mcp/cadu/v1`
- Logo: `aicentralv2/static/images/cadu/products/cadu-mcp-icon.svg`
- Distribuição: plugin público ligado ao servidor MCP remoto existente; sem novo backend.
- Autenticação: OAuth 2.1 Authorization Code com PKCE S256, refresh token, escopo por ferramenta e consentimento Cadu.

## Pendências antes do envio

- Confirmar identidade individual ou empresarial verificada e permissão `api.apps.write` na organização correta.
- Informar URLs públicas oficiais de site, suporte, privacidade e termos; verificar o domínio no portal.
- Executar o runner de migração `migrations/run_add_cadu_public_mcp_modules.py` no ambiente de destino antes de conectar clientes.
- Confirmar que as rotas de OAuth e o MCP público estão disponíveis fora da rede interna.
- Fazer Scan Tools e revisar nome, descrição, schemas, escopos, custos, `readOnlyHint`, `openWorldHint` e `destructiveHint` de cada ferramenta.
- Fornecer credenciais de demonstração revisáveis pela equipe da OpenAI, sem MFA, com dados fictícios e permissões suficientes para cobrir leitura e escrita.
- Confirmar elegibilidade e disponibilidade do plugin para os planos/regiões pretendidos; a publicação não remove as limitações de produto do ChatGPT.

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
