# Área do Cliente Centralcomm — plano (2026-11-05)

Status (2026-11-05): **Fase 1 implementada**. Com "ok" do usuário, a migração
`add_area_cliente_acesso_contato.sql` foi aplicada em produção e o contato 2
(Apolo Lira, cliente 174) foi liberado. Falta: DNS de `clientes` →
72.60.141.141, `server_name` no Nginx, certificado (expandir
`centralcomm-products`), deploy do código e verificação em tela com a conta 174.

Decidido com o usuário em 2026-11-05:
- Liberação = **coluna no contato** (`tbl_contato_cliente`), como `reports_only`.
- **Cada PI é um projeto** (lista e visão 360°).
- Conta 174 sem PI: **estado vazio** na Fase 1; "ver como cliente X" para
  admins internos fica para a Fase 2.
- Conta **só-Reports** (`reports_only`) continua só no Reports, mesmo com a
  Área do Cliente liberada no CRM (o desvio para o Connect vem antes).
- 2026-11-05, revisão em tela: jornada **Briefing → Planejamento → Projeto
  (PI fechado) → Campanhas**. Novo item **Briefing** (formulário do cliente,
  grava em `cadu_briefings` como `pendente`/enviado à Centralcomm, com o
  executivo da conta; a equipe recebe em /briefings). Sai **Integrações**.
  Sidebar abre recolhida em ícones (lembra a escolha). Nome do cliente vai
  para o topo, sob o nome do usuário.
- 2026-11-05: **Planejamento vira Descobrir**, com as vitrines do Cadu
  Planner em páginas próprias da área: canais, formatos, formatos
  interativos, audiências e portais (busca, filtro, paginação e detalhe).
  Places e Radar ficam de fora (Radar é do Cadu, por marca e projeto). Sem
  preço, investimento mínimo, CPA ou valor de mercado. "Incluir no briefing"
  separa itens na sessão (até 30); eles vão no texto do próximo briefing.
  Jornada: Descobrir → Briefing → Projeto (PI fechado) → Campanhas.
- 2026-11-05: sai **Mídia e Veiculação** (Campanhas já cobre) e **Arquivos**
  vira **PIs**. Telas espelham as internas do CentralX só com o que interessa
  ao cliente: Campanhas = "Central de ritmo" (no ar, aguardando criativos,
  paradas, finalizadas; entrega x tempo; responsável da operação), sem gasto,
  previsto ou preço. PIs = etapas, valor bruto, comissão de agência, valor
  líquido (venda), nota fiscal e pagamento, marcos, resultado por campanha e
  documentos; sem custos nem "zona de lucratividade". Por decisão do usuário,
  todo usuário liberado do cliente ou da agência vê os valores do PI.
- 2026-11-05: **Ver como cliente** no menu do usuário, só para admin/superadmin
  da CENTRALCOMM (174) com a área liberada. Lista clientes e agências ativos
  com PI validado no ano corrente (fora "Em aprovação" e "Cancelado"). Toda a
  área passa a mostrar os dados do escolhido, com faixa de aviso e botão para
  voltar; envio de briefing fica desativado. Cada troca vai para a auditoria
  (`VIEW_AS`, módulo `area_cliente`).
- **Não usar `ai.centralcomm.media`**: é o CentralX (cookie interno, login só
  @centralcomm.media, `/clientes` = lista interna) e não será mexido.
- **Endereço: `https://clientes.centralcomm.media`** (host próprio, área na
  raiz: `/`, `/projetos`, `/projetos/<id_pi>`...). Config nova `CLIENTES_URL`.
  No host de clientes só respondem as rotas da área, `/login`, `/logout`,
  `/acesso-confirmado` e `/static`; o resto dá 404, então nenhuma rota interna
  fica exposta ali. Para ir ao ar: DNS, certificado e o nome no `server_name`
  do Nginx.

## 1. Objetivo

Uma área nova, em `/clientes`, onde o cliente da Centralcomm acompanha seus
projetos, campanhas, mídia, relatórios e arquivos, sem nenhum valor de custo
(mesma regra da página pública do PI). Entra com o **mesmo e-mail e senha do
Cadu**. Quem pode entrar é decidido no **CRM v3**, contato por contato.

Não é a página pública do PI (`/campanha/p/<token>`): aquela é um link sem
login, com barra superior escura. A Área do Cliente tem login, **sidebar clara
à esquerda** e topo com busca e conta.

## 2. O que já existe e será reaproveitado

| Peça | Onde | Uso na Área do Cliente |
|---|---|---|
| Login Cadu (e-mail/senha do cliente, inclusive domínios de clientes) | `routes.py` `login()`, `auth.py` | Mesma tela e mesma sessão. Sem sistema novo. |
| Sessão Cadu compartilhada entre hosts da família | `product_domains.ProductSessionInterface` (cookie `cadu_sso_session`) | A área roda num host Cadu, então herda essa sessão. |
| Usuários do cliente | `tbl_contato_cliente` (`pk_id_tbl_cliente`, `status`, `senha`, `user_type`) | O usuário da área é o próprio contato. |
| Painel de contatos do CRM v3 | `templates/crm_v3.html` coluna "Contatos", drawer `crm_v3/_drawer_contato.html`, `static/js/crm_v3.js` / `crm_v3_drawers.js`, API `crm_v3_routes.py` | Lugar da liberação (seção 4). |
| Precedente de flag por usuário | `tbl_contato_cliente.reports_only` | Mostra o padrão; aqui proponho tabela própria (seção 4.1). |
| Payload sem custos do PI | `campanha_acompanhamento_publico.py` (`montar_payload_acompanhamento_pi`) | Telas de campanha, mídia, relatórios e arquivos. |
| Projetos do Workspace | `cadu_ci_projetos`, `cadu_ci_projeto_arquivos`, `cadu_ci_projeto_links` | Projetos e visão 360° (ver decisão D3). |
| Design system | `frontend/cadu-design-system/tokens.css` skin `workspace`, `UNTITLED-UI.md` | Mesma ponte de tokens Untitled UI v8 que `static/css/campanha_publica.css` já reproduz em CSS para Jinja. |

## 3. Endereço e host

`/clientes` **já existe** no app: é a lista interna de clientes do CentralX
(`routes.py`, endpoint `clientes`, mais `/clientes/novo`,
`/clientes/<id>/editar`, `/clientes/<id>/toggle-status`). O mesmo processo
Flask atende todos os hosts, então a área nova precisa ser **por host**:

- **CentralX** (`ai.centralcomm.media`): fora de questão. `/clientes` continua
  sendo a lista interna, sem mudança.
- **Opção A:** `https://cadu.centralcomm.media/clientes`. O nome já está no
  `server_name` do repo, mas em 2026-11-05 o host responde com a página
  estática de manutenção (`/maintenance/`, `deploy/cadu-maintenance`), fora do
  Flask. Para ir ao ar, o Nginx precisa mandar ao menos `/clientes`, `/login`,
  `/logout` e `/static` para o Flask.
- **Opção B:** host próprio, ex. `https://clientes.centralcomm.media`
  (DNS, certificado e bloco no Nginx). Endereço mais limpo para o cliente.
- Nos dois casos o host é da família Cadu: usa o cookie `cadu_sso_session` e
  o login atual do cliente, sem mudança no CentralX. O código é o mesmo; só a
  configuração do host muda.
- **Como:** mesmo padrão já usado pelo Planner (`product_domains.py`,
  `planner_host_*`): um `before_request` que, fora do host CentralX, casa
  `/clientes` e `/clientes/...` num mapa de rotas próprio e despacha para o
  blueprint `area_cliente`. Os links da área são gerados por um helper
  `area_url()`, nunca `url_for('clientes')`.
- **Local:** nova entrada `flask-clientes` em `.claude/launch.json` com
  `CADU_URL=http://cadu.localhost:5052`. Em `localhost` (host CentralX) a
  lista interna continua igual.

Login: sem sessão, `/clientes` manda para `/login?next=/clientes` no mesmo
host (o `login_url()` atual já faz isso). O `next` relativo passa pelo
`safe_product_target` e volta para a área depois do login.

## 4. Permissão no CRM v3

### 4.1 Modelo (migração `add_area_cliente_acesso_contato.sql`)

**Decidido: coluna no contato.** Fica assim:

```sql
ALTER TABLE tbl_contato_cliente
    ADD COLUMN IF NOT EXISTS area_cliente_acesso BOOLEAN NOT NULL DEFAULT FALSE;
```

Quem liberou e quando vai para `audit.registrar_acao_admin` (não precisa de
coluna). O contato só entra se a flag estiver ligada e o contato e o cliente
estiverem ativos. Papel `gestor` deixa de existir na Fase 1; se um dia
precisar, vira outra coluna.

Alternativa descartada (tabela própria, mantida só como registro):

```sql
CREATE TABLE IF NOT EXISTS area_cliente_acessos (
    id_contato_cliente INTEGER PRIMARY KEY
        REFERENCES tbl_contato_cliente(id_contato_cliente) ON DELETE CASCADE,
    id_cliente   INTEGER NOT NULL REFERENCES tbl_cliente(id_cliente),
    ativo        BOOLEAN NOT NULL DEFAULT TRUE,
    papel        VARCHAR(20) NOT NULL DEFAULT 'leitor'
                 CHECK (papel IN ('leitor', 'gestor')),
    liberado_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    liberado_em  TIMESTAMP NOT NULL DEFAULT NOW(),
    revogado_por INTEGER REFERENCES tbl_contato_cliente(id_contato_cliente),
    revogado_em  TIMESTAMP,
    atualizado_em TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_area_cliente_acessos_cliente
    ON area_cliente_acessos (id_cliente) WHERE ativo;
```

- Idempotente, entra em `migrations/ORDER.txt`, testada antes num Postgres
  descartável (o `.env` local aponta para produção).
- `id_cliente` é gravado na liberação e **conferido a cada request** contra o
  `pk_id_tbl_cliente` atual do contato: se o contato mudar de cliente, o
  acesso cai sozinho.
- `papel`: `leitor` na Fase 1. `gestor` fica reservado (ex.: ver Equipe,
  convidar colegas) e não muda nada até ser usado.
- Cada liberar/revogar também vai para `audit.registrar_acao_admin`.

### 4.2 Regra de acesso (`area_cliente_required`)

Entra se, e só se:
1. há sessão Cadu (`session['user_id']`);
2. o contato está ativo e o cliente dele está ativo;
3. existe `area_cliente_acessos` ativo com o mesmo `id_cliente` do contato.

Sem (3): página "Acesso ainda não liberado", com o contato do executivo da
conta (nome e WhatsApp, como na página do PI). Nada de 403 seco.

Todo dado da área é filtrado pelo `id_cliente` da sessão, nunca por id vindo da
URL. Id de projeto ou PI de outro cliente devolve 404.

### 4.3 Onde fica no CRM v3

No CRM v3 os usuários do cliente são os **Contatos** da coluna direita
(`crm-v3-col-contatos`), que já mostram o selo "Cadu: sem acesso / nunca
usou / pouco uso / muito uso".

- **Drawer do contato** (`_drawer_contato.html`): nova seção "Área do
  Cliente", logo abaixo de "Uso do Cadu", com um interruptor
  "Liberar acesso à Área do Cliente" e a linha "Liberado por X em dd/mm".
  Se o contato não tem credencial do Cadu, o interruptor continua disponível,
  mas avisa: "Este contato ainda não tem senha do Cadu. Envie o convite para
  ele conseguir entrar."
- **Card do contato** (`renderContatos`): selo "Área do Cliente" quando
  liberado.
- **API:** `PUT /crm-v3/api/contatos/<id>/area-cliente` `{ativo, papel}`,
  restrita à equipe CentralComm (`centralcomm_required_api`). O
  `list_contatos` passa a devolver `area_cliente_ativo`, `area_cliente_papel`,
  `area_cliente_liberado_por_nome` e `area_cliente_liberado_em`.
- Confirmação por modal do próprio CRM v3 e toast, nada de `confirm()`.

## 5. Telas

Shell comum (Jinja, `templates/area_cliente/`, CSS
`static/css/area_cliente.css` com os tokens da skin `workspace`, sempre
claro, Inter, fonte mínima 12px):

- **Sidebar clara à esquerda** (272px, recolhe em gaveta abaixo de 1024px):
  logo Centralcomm e nome do cliente; Início, Projetos, Campanhas,
  Planejamento, Mídia e Veiculação, Relatórios, Arquivos, Equipe,
  Integrações; bloco **Cadu** com Studio, MediaSafe, Flow e Reports (links
  para os produtos, abertos no mesmo SSO); rodapé com o executivo da conta.
- **Topo:** busca (projetos e campanhas do cliente), notificações (vazio na
  Fase 1) e menu da conta (nome, foto, sair).
- Animações de entrada só com `prefers-reduced-motion: no-preference`. Sem
  rolagem horizontal até 360px de largura.

| Rota | Tela | Fase |
|---|---|---|
| `/clientes` | **Início**: saudação; 4 KPIs (projetos ativos, campanhas no ar, entrega média vs meta em %, relatórios disponíveis); performance de mídia por campanha (meta, atingido, % — sem custo); atividades recentes; projetos em destaque | 1 |
| `/clientes/projetos` | Lista de projetos com filtro | 1 |
| `/clientes/projetos/<id>` | **Projeto 360°**: cabeçalho, resumo, campanhas ligadas, arquivos, links, equipe, linha do tempo | 1 |
| `/clientes/campanhas`, `/clientes/campanhas/<id_pi>` | Campanhas por PI, com o payload sem custos da página pública | 2 |
| `/clientes/midia` | Mídia e Veiculação: canais, plataformas, períodos, status por campanha | 2 |
| `/clientes/relatorios` | Dashboards Looker das campanhas e relatórios do Reports | 2 |
| `/clientes/arquivos` | Documentos do PI e arquivos dos projetos | 2 |
| `/clientes/equipe` | Usuários do cliente com acesso e o time Centralcomm (executivo, operação) | 3 |
| `/clientes/integracoes` | Integrações do cliente (Reports, Looker, tags) | 3 |
| `/clientes/planejamento` | **Espaço reservado**: hoje, página com os planos finais compartilhados; futuro, o guia com os itens do Cadu Planner | 4 |

Na Fase 1, as rotas das fases 2 a 4 já existem na sidebar e abrem uma página
"Em preparação" curta, com o que vai aparecer ali. Nada de link quebrado.

## 6. Fases

- **Fase 0 — plano** (este documento) e revisão com o usuário.
- **Fase 1 — fundação:** migração e permissão no CRM v3; blueprint
  `area_cliente` com despacho por host; `area_cliente_required`; shell
  (sidebar, topo, conta); Início com dados reais; Projetos e Projeto 360°;
  páginas "Em preparação"; testes unitários da regra de acesso e do despacho
  por host; verificação no navegador com a conta 174 em desktop, tablet e
  celular.
- **Fase 2 — campanhas:** Campanhas, Mídia e Veiculação, Relatórios e
  Arquivos sobre `campanha_acompanhamento_publico.py` (sem custos).
- **Fase 3 — pessoas e conexões:** Equipe, Integrações, busca completa,
  notificações, e-mail "seu acesso foi liberado" ao ligar a flag no CRM.
- **Fase 4 — Planejamento:** guia com os itens do Cadu Planner dentro da
  área (só o espaço fica previsto agora).

## 7. Testes com a conta 174 (CENTRALCOMM)

Leituras feitas em 2026-11-05 (somente leitura):

- Cliente 174 = CENTRALCOMM, ativo. 19 contatos, 18 ativos.
- **0 PIs e 0 campanhas** com `id_cliente = 174`. Os blocos de campanha e
  performance de mídia vão aparecer vazios (estado vazio desenhado), a não ser
  que a decisão D4 diga outra coisa.
- 24 projetos do Workspace (`cadu_ci_projetos`), alguns com arquivos (ex.:
  "BDMG Orienta 2026", "Netflix"). Bons para Início e Projeto 360°.
- 5 cotações.

Roteiro: liberar no CRM v3 o próprio usuário do 174 (escrita em produção, com
"ok"); entrar em `http://cadu.localhost:5052/clientes`; ver Início, Projetos
e um Projeto 360°; revogar no CRM e confirmar a tela "Acesso ainda não
liberado"; conferir que `localhost:5050/clientes` segue sendo a lista interna.

O login no navegador de teste é feito pelo próprio usuário (Claude não digita
senha real).

## 8. Decisões para revisão

Respostas do usuário: D1 em aberto (não pode ser `ai.centralcomm.media`;
escolher entre A e B da seção 3); D2 = coluna no contato; D3 = cada PI é um
projeto; D4 = estado vazio por ora.

Com D3 = PI, o Projeto 360° passa a ser o PI: campanhas, resultados (meta,
atingido, %), dashboards, combinados, documentos e contato, tudo do
`montar_payload_acompanhamento_pi`. Para o 174 (sem PI) Início, Projetos e
360° mostram estado vazio.

Texto original das opções:

- **D1 — Endereço em produção.** Recomendado `cadu.centralcomm.media/clientes`.
  Alternativa: um host próprio (ex.: `clientes.centralcomm.media`), que pede
  DNS, certificado e entrada no Nginx.
- **D2 — Onde guardar a liberação.** Recomendado: tabela
  `area_cliente_acessos` (seção 4.1). Alternativa: coluna booleana em
  `tbl_contato_cliente`, como `reports_only` (mais simples, sem histórico).
- **D3 — O que é "Projeto".** Recomendado na Fase 1: projetos do Workspace
  (`cadu_ci_projetos`), que já existem para o 174 e têm arquivos e links; as
  campanhas (PIs) entram no 360° quando houver vínculo. Alternativa: tratar
  cada PI como um projeto (o 174 não tem PI, então a tela 360° ficaria vazia
  nos testes).
- **D4 — Dados de campanha nos testes.** O 174 não tem PI. Opções: aceitar o
  estado vazio na Fase 1; ou, na Fase 2, um modo "ver como cliente X" só para
  admins internos, só leitura, com faixa de aviso no topo.

## 9. Fora do escopo agora

- Itens do Cadu Planner como guia (Fase 4, só espaço reservado).
- Qualquer valor de custo, margem, CPM pago ou fee.
- Cadastro de usuário pela própria área (a liberação é sempre pelo CRM v3).

## 10. Observação lateral

Algumas rotas internas do CentralX (ex.: `/clientes`, `/clientes/novo`)
usam só `login_required`. O cookie do CentralX é separado, mas um cliente com
sessão Cadu num host Cadu pode, em tese, abrir essas URLs nesse host. Vale
uma checagem à parte (fora desta tarefa).
