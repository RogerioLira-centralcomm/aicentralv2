# Plano — MCP público do Cadu com OAuth 2.1

Status: proposta executável para substituir a experiência baseada em chave manual
por conexão de conta, inspirada no fluxo do Higgsfield. O objetivo não é copiar
a interface de outro produto: é entregar o mesmo resultado operacional — informar
o endereço do MCP, entrar no Cadu, revisar permissões e voltar ao agente conectado.

## 1. Resultado esperado

Um cliente do Cadu deve conseguir conectar sua conta a Codex, ChatGPT, Cursor,
VS Code, Claude e outros hosts MCP sem copiar uma chave privada.

Fluxo principal:

```text
Adicionar Cadu no agente
  → agente descobre OAuth no endpoint MCP
  → navegador abre o Cadu
  → login existente ou autenticação
  → escolha de conta, projeto inicial e permissões
  → consentimento explícito
  → retorno automático ao agente
  → tools disponíveis e créditos cobrados da conta Cadu
```

O usuário administra a conexão em **Integrações → Agentes de IA**, onde vê
aplicativo, usuário, escopos, último uso e opção de revogação.

## 2. Decisões de produto

1. OAuth 2.1 é o padrão; `cadu_mcp_*` permanece apenas como compatibilidade
   temporária para clientes sem OAuth.
2. O endereço público continua estável:
   `https://workspace.centralcomm.media/mcp/cadu/v1`.
3. O Cadu atua como authorization server e resource server. O login existente
   autentica a pessoa; o consentimento OAuth delega acesso ao agente.
4. Nenhum host escolhe `client_id`, `user_id`, tenant ou papel por argumento.
   Esses valores vêm exclusivamente do grant autorizado.
5. Access tokens são opacos, curtos e armazenados apenas como hash. Refresh
   tokens têm rotação obrigatória, hash persistido e detecção de reutilização.
6. PKCE `S256` é obrigatório. Implicit grant e password grant não existem.
7. CIMD é a primeira opção para clientes compatíveis; DCR fica disponível para
   hosts MCP que precisem registrar um cliente dinamicamente.
8. O catálogo de tools, regras de tenant, cobrança e `RequestContext` atuais
   permanecem canônicos.
9. ChatGPT web entra pela publicação de um plugin Cadu; Codex e demais clientes
   podem conectar diretamente ao MCP remoto.

## 3. Experiência por cliente

| Cliente | Entrada | Autenticação | Resultado |
|---|---|---|---|
| Codex desktop/CLI/IDE | Adicionar URL ou configuração mínima | Botão **Authenticate** abre o Cadu | Configuração compartilhada no host Codex |
| ChatGPT web | Plugin Cadu no diretório | Login e consentimento do Cadu | Tools disponíveis no ChatGPT |
| Cursor | Marketplace/deep link ou URL MCP | Navegador abre o Cadu | Servidor salvo sem API key |
| VS Code | `vscode:mcp/install` sem segredo | Navegador abre o Cadu | Servidor salvo e autenticado |
| Claude | Custom connector com URL | Navegador abre o Cadu | Connector ativo |
| MCP genérico | URL informada manualmente | OAuth 2.1 quando suportado | Fallback de chave somente se necessário |

O botão principal da tela passa de **Criar conexão** para **Conectar agente**.
A escolha do aplicativo apresenta instrução ou deep link sem colocar token na URL.
Depois da instalação, o host inicia OAuth e o Cadu assume o restante do fluxo.

## 4. Descoberta e contratos HTTP

### Protected Resource Metadata

Publicar:

```text
GET /.well-known/oauth-protected-resource
GET /.well-known/oauth-protected-resource/mcp/cadu/v1
```

Resposta mínima:

```json
{
  "resource": "https://workspace.centralcomm.media/mcp/cadu/v1",
  "authorization_servers": ["https://workspace.centralcomm.media"],
  "scopes_supported": [
    "resources:read",
    "projects:read",
    "projects:content_write",
    "projects:write",
    "brands:write",
    "artifacts:write",
    "account:read",
    "account:write",
    "credits:read",
    "google:read",
    "google:write"
  ],
  "resource_documentation": "https://workspace.centralcomm.media/workspace/app/integracoes/agents"
}
```

### Authorization Server Metadata

Publicar:

```text
GET /.well-known/oauth-authorization-server
```

Campos obrigatórios para o primeiro release:

- `issuer`;
- `authorization_endpoint`;
- `token_endpoint`;
- `registration_endpoint`;
- `revocation_endpoint`;
- `scopes_supported`;
- `response_types_supported = ["code"]`;
- `grant_types_supported = ["authorization_code", "refresh_token"]`;
- `code_challenge_methods_supported = ["S256"]`;
- `token_endpoint_auth_methods_supported` compatível com clientes públicos.

### Endpoints

```text
GET|POST /oauth/authorize
POST     /oauth/token
POST     /oauth/register
POST     /oauth/revoke
```

O endpoint MCP sem credencial retorna `401` com:

```text
WWW-Authenticate: Bearer resource_metadata="https://workspace.centralcomm.media/.well-known/oauth-protected-resource/mcp/cadu/v1"
```

O parâmetro `resource` deve ser preservado em autorização e troca de token. O
`audience` efetivo deve corresponder exatamente ao endpoint público do MCP.

## 5. Modelo de dados

Criar uma migration aditiva; não alterar `cadu_public_mcp_keys` na primeira fase.

### `cadu_oauth_clients`

- `id` UUID interno;
- `oauth_client_id` único;
- `client_name`, `client_uri`, `logo_uri`;
- `redirect_uris` JSONB;
- `grant_types` e `response_types` JSONB;
- `token_endpoint_auth_method`;
- `client_id_issued_at`;
- `metadata_document_uri` para CIMD, quando aplicável;
- `status`, `created_at`, `updated_at`.

Não aceitar redirect URI parcial, wildcard ou `javascript:`. Clientes nativos
podem usar loopback conforme as regras aplicáveis; clientes web exigem HTTPS e
comparação exata.

### `cadu_oauth_grants`

- `id` UUID;
- `oauth_client_id`;
- `client_id` e `user_id` do Cadu;
- `default_project_ref` opcional;
- `scopes` JSONB;
- `status`: `pending`, `active`, `revoked`;
- `consented_at`, `last_used_at`, `revoked_at`;
- metadados seguros do aplicativo para exibição na tela.

### `cadu_oauth_authorization_codes`

- hash do código, nunca o código puro;
- grant, redirect URI, resource e escopos;
- `code_challenge` e método `S256`;
- expiração máxima recomendada de 5 minutos;
- `used_at`, garantindo uso único.

### `cadu_oauth_access_tokens`

- hash do token;
- grant e família de refresh;
- resource/audience e scopes;
- emissão, expiração e revogação;
- último uso.

Access token inicial: 15 minutos. O valor poderá ser ajustado por telemetria,
sem ampliar o refresh token.

### `cadu_oauth_refresh_tokens`

- hash do token;
- grant e `family_id`;
- token anterior/substituto;
- emissão, expiração, rotação e revogação;
- `reuse_detected_at`.

Ao reutilizar um refresh token já rotacionado, revogar toda a família.

### Uso e auditoria

Alterar `cadu_public_mcp_usage` para referenciar uma identidade de credencial
abstrata, ou adicionar `grant_id` mantendo `key_id` opcional. Durante a migração,
uma chamada tem exatamente uma origem: chave legada ou grant OAuth.

## 6. Refatoração de código

### Separar identidade de credencial

Hoje `cadu_public_mcp/auth.py` combina extração do Bearer, validação da chave,
principal, escopos e contexto. Dividir em:

```text
cadu_public_mcp/
  auth.py                 fachada temporária e principal comum
  credentials.py          resolução chave legada ou access token
  oauth_metadata.py       documentos well-known
  oauth_clients.py        CIMD, DCR e validação de redirect URI
  oauth_grants.py         consentimento e revogação
  oauth_tokens.py         code, access token, refresh e rotação
  oauth_routes.py         authorize, token, register e revoke
```

Criar `PublicMcpPrincipal` independente do tipo de credencial:

```text
credential_type: api_key | oauth
credential_id
grant_id opcional
client_id do tenant
user_id
application_type
application_name
scopes
context
```

`required_scope()`, `ensure_scope()` e `_public_context()` continuam únicos.
`routes.py` recebe o principal pronto e não conhece formato de token.

### Compatibilidade

O resolvedor Bearer executa:

1. token com prefixo `cadu_mcp_` → chave legada;
2. token OAuth opaco com prefixo próprio → access token OAuth;
3. ausente/inválido → challenge OAuth, sem revelar qual parte falhou.

Não usar JWT na primeira versão. Tokens opacos facilitam revogação imediata,
reduzem exposição de dados e se encaixam no banco e no monólito atuais.

## 7. Consentimento no Cadu

A tela `/oauth/authorize` deve:

- exigir sessão válida ou encaminhar ao login preservando a transação;
- mostrar nome e logo verificados do aplicativo;
- mostrar conta Cadu e usuário que serão vinculados;
- permitir projeto inicial opcional;
- agrupar permissões em linguagem de produto;
- deixar permissões administrativas desmarcadas por padrão;
- informar que tools usam créditos compartilhados;
- exibir **Autorizar** e **Cancelar**;
- nunca mostrar client secret, access token ou refresh token.

Mapeamento sugerido:

| Grupo exibido | Scopes |
|---|---|
| Consultar projetos e materiais | `resources:read`, `projects:read` |
| Adicionar conteúdo aos projetos | `projects:content_write` |
| Consultar conta e créditos | `account:read`, `credits:read` |
| Consultar conexões Google | `google:read` |
| Administrar projetos | `projects:write` |
| Administrar marcas e documentos | `brands:write`, `artifacts:write` |
| Alterar conta e equipe | `account:write` |
| Vincular dados do Google | `google:write` |

Escopos solicitados pelo cliente são teto, não concessão automática. O grant
recebe apenas a interseção entre solicitado, permitido pelo papel e aprovado.

## 8. Administração da conexão

Refatorar `/workspace/app/integracoes/agents` para mostrar **Aplicativos
conectados** em vez de apenas chaves:

- nome e logo do host;
- usuário que autorizou;
- projeto inicial;
- permissões concedidas;
- data e último uso;
- estado `active`, `expired`, `reauth_required` ou `revoked`;
- ação para revisar permissões;
- revogação com invalidação de access e refresh tokens.

Chaves legadas aparecem em uma seção separada, com aviso de migração e data de
desativação definida somente depois de adoção suficiente.

## 9. Segurança obrigatória

- PKCE `S256`, `state` e autorização code de uso único;
- redirect URI exata;
- `resource` e audience exatos;
- tokens opacos com entropia criptográfica e hash SHA-256 no banco;
- rotação de refresh token e reuse detection;
- revogação transitiva da família;
- rate limit por IP, cliente, grant, usuário e tenant nos endpoints OAuth;
- CSRF na decisão de consentimento;
- clickjacking bloqueado na tela de autorização;
- `Cache-Control: no-store` em OAuth e MCP autenticado;
- logs sem códigos, tokens, conteúdo de documentos ou prompts;
- auditoria de criação, consentimento, troca, refresh, falha e revogação;
- mensagens públicas que não permitam enumerar usuários ou clientes;
- aprovação administrativa para scopes de alto risco quando a política exigir.

## 10. Observabilidade

Eventos mínimos:

```text
oauth.client_registered
oauth.authorization_started
oauth.authorization_approved
oauth.authorization_denied
oauth.code_exchanged
oauth.token_refreshed
oauth.refresh_reuse_detected
oauth.grant_revoked
mcp.authentication_failed
mcp.tool_called
```

Métricas:

- taxa de início → consentimento → primeira chamada bem-sucedida;
- tempo de conexão por host;
- falhas por etapa e cliente;
- refresh success rate;
- grants ativos e revogados;
- chamadas e créditos por aplicação;
- uso de chave legada versus OAuth.

## 11. Plano de entrega

### Fase 0 — contrato e testes de conformidade

- congelar resource identifier, issuer e scopes;
- criar fixtures para Codex, ChatGPT, Cursor, VS Code e Claude;
- definir política de redirect URI e duração dos tokens;
- adicionar testes negativos antes da implementação.

Saída: ADR aprovado e suíte de contrato falhando pelos motivos esperados.

### Fase 1 — descoberta e challenge

- publicar os dois documentos well-known;
- retornar `WWW-Authenticate` correto no MCP;
- atualizar `/.well-known/cadu-mcp-public` para `oauth.status = ready` somente
  quando todas as dependências estiverem ativas;
- preservar autenticação por chave.

Saída: hosts descobrem o authorization server sem regressão para chaves.

### Fase 2 — authorization code + PKCE

- migrations OAuth;
- `/oauth/authorize`, login e consentimento;
- `/oauth/token` para `authorization_code`;
- access token opaco e autenticação MCP;
- revogação de grant.

Saída: Codex conecta, autentica e executa `tools/list` e uma tool de leitura.

### Fase 3 — refresh, DCR e CIMD

- rotação de refresh token;
- reuse detection;
- `/oauth/register` com limites e validações;
- validação/fetch seguro de CIMD, com proteção contra SSRF;
- interoperabilidade com os demais hosts.

Saída: sessões persistem sem chave manual e podem ser revogadas imediatamente.

### Fase 4 — experiência de instalação

- trocar o formulário de criação de chave por seleção de aplicativo;
- gerar deep links sem segredo para VS Code e Cursor;
- instrução mínima para Codex e clientes genéricos;
- tela de aplicativos conectados e permissões;
- teste de conexão usando o grant do próprio fluxo.

Saída: experiência de instalação equivalente ao resultado do Higgsfield.

### Fase 5 — plugin Cadu para ChatGPT

- empacotar MCP, metadados, logo, política e suporte;
- testar conexão OAuth no builder;
- cumprir requisitos de revisão e privacidade;
- publicar primeiro de forma privada/beta e depois no diretório.

Saída: instalação nativa pelo diretório de plugins do ChatGPT.

### Fase 6 — migração das chaves

- convidar usuários ativos a reconectar por OAuth;
- medir adoção e falhas por cliente;
- bloquear criação de novas chaves onde OAuth funciona;
- definir janela de encerramento separada para chaves existentes;
- remover fallback apenas após clientes críticos migrarem.

Saída: OAuth como único caminho nos hosts compatíveis, sem interrupção abrupta.

## 12. Testes mínimos

### Protocolo OAuth

- metadata válida e consistente;
- PKCE ausente, `plain` ou incorreto é recusado;
- code expira e não pode ser reutilizado;
- redirect URI diferente é recusada;
- `resource`/audience diferente é recusado;
- refresh rotaciona; reutilização revoga a família;
- revogação invalida access e refresh tokens;
- DCR rejeita schemes e redirects inseguros;
- CIMD não permite SSRF, redirect ou conteúdo fora do contrato.

### Segurança de produto

- grant nunca acessa outro tenant;
- projeto padrão pertence ao tenant;
- papel do usuário limita scopes administrativos;
- revogar usuário ou acesso ao projeto reduz/invalida o grant;
- tool sem scope não é listada nem executada;
- cobrança continua atribuída ao tenant e usuário autorizadores;
- token, code e refresh nunca aparecem em logs, templates ou respostas MCP.

### Interoperabilidade

- Codex desktop, CLI e IDE;
- ChatGPT plugin em ambiente de teste;
- Cursor;
- VS Code;
- Claude custom connector;
- MCP Inspector como cliente de referência.

### Regressão

- chaves existentes continuam funcionando durante a migração;
- uploads multipart e assets autenticados aceitam principal OAuth;
- idempotência e registros de uso preservam a origem da credencial;
- `initialize`, `tools/list` e `tools/call` mantêm o contrato atual.

## 13. Critérios de liberação

OAuth só vira padrão quando:

- a suíte de segurança e interoperabilidade estiver verde;
- Codex concluir login e refresh sem intervenção manual;
- revogação bloquear nova chamada em até 60 segundos;
- nenhuma URL de instalação contiver segredo;
- auditoria identificar aplicativo, grant, usuário e tenant;
- dashboard mostrar falhas por etapa;
- runbook de incidente e rotação estiver publicado;
- política de privacidade explicar o uso de agentes externos;
- a equipe conseguir desativar DCR ou um cliente individual sem derrubar o MCP.

## 14. Fora do primeiro release

- social login próprio do agente;
- JWT autossuficiente;
- device authorization grant;
- service accounts sem usuário;
- consentimento permanente para novos scopes;
- remoção imediata das chaves legadas;
- marketplace próprio para todos os hosts.

## 15. Ordem recomendada dos pull requests

1. `oauth-metadata-and-challenge`;
2. `oauth-schema-and-token-primitives`;
3. `oauth-authorize-consent-pkce`;
4. `oauth-token-refresh-revocation`;
5. `mcp-oauth-principal-and-usage`;
6. `oauth-dcr-cimd-hardening`;
7. `agents-connected-apps-ui`;
8. `client-installers-without-secrets`;
9. `chatgpt-plugin-beta`;
10. `legacy-key-migration`.

Cada PR deve ser implantável de forma aditiva, protegido por feature flag e
reversível sem apagar grants ou chaves existentes.

## Referências

- OpenAI — autenticação de plugins e MCP:
  https://developers.openai.com/plugins/build/auth
- OpenAI — MCP no Codex:
  https://developers.openai.com/codex/mcp
- MCP Authorization Specification:
  https://modelcontextprotocol.io/specification/2025-11-25/basic/authorization
- OAuth 2.0 Protected Resource Metadata — RFC 9728:
  https://www.rfc-editor.org/rfc/rfc9728
- OAuth 2.0 for Native Apps — RFC 8252:
  https://www.rfc-editor.org/rfc/rfc8252
- Fluxo público de referência do Higgsfield:
  https://higgsfield.ai/creator-hub/help-center/integrations/how-do-i-connect-higgsfield-to-ai-agent
