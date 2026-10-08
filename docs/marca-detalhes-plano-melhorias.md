# Marca — detalhes: auditoria de front e plano de melhorias (2026-10-08)

Escopo: tela de detalhes da marca (`WorkspaceBrand.jsx`) e vizinhas (lista de marcas, campanhas, auditorias, biblioteca, trilho lateral). Só plano; nada foi alterado.

## 1. JSON vazando (bug principal)

**Sintoma (Cemig):** título, subtítulo e "Essência da marca" mostram `[{'value': '...', 'source_url': '...', 'excerpt': '...', 'confidence': 0.93}, ...]`.

**Causa raiz, em duas camadas:**

1. **Gravação** — `aicentralv2/creative_brand_analysis.py:1673` `_text()` só trata `dict`. Quando o LLM devolve uma **lista** de `{value, source_url, excerpt, confidence}`, cai em `str(value)` e salva o `repr` do Python (aspas simples) em `brand_summary`, `tone_of_voice` e campos irmãos (linhas ~3138-3140 e demais `_text(...)`). Os dados já salvos continuam sujos.
2. **Exibição** — `WorkspaceBrand.jsx`:
   - `:617` (hero) e `:630` (lead "Essência da marca") imprimem `profile.brandSummary || profile.positioning` cru.
   - `enrichedField` (`:418`) só entende string que começa com `{` ou objeto; **não entende `[`** (lista). `FilledReading` usa essa função e os outros campos escapam por pouco; hero e lead não passam por ela.
   - `readableBrandItem` (`:429`) também só trata `{`.

**Correção proposta (nessa ordem):**
- P0 Front: criar um único `plainText(value)` que aceita string, lista, objeto, JSON ou repr Python (`[`/`{`), extrai `value`, junta itens com quebra e descarta `source_url`/`excerpt`/`confidence`. Usar no hero (truncado em ~2 linhas), no lead e no `FilledReading`. Fonte vira link discreto "Fonte" (já existe no padrão do `FilledReading`).
- P0 Back: em `_text()`, tratar `list` (juntar os `value`) e nunca chamar `str()` de estrutura. Aplicar a todos os campos de texto do perfil.
- P1 Dados: migração/comando que reprocessa marcas cujo `brand_summary`/`tone_of_voice` começam com `[{` ou `{'` (extrair `value`). Testar em Postgres local (ver memória de deploy/migrações) e listar quantas marcas afeta antes de rodar.
- P1 Teste: caso de unidade para `_text` com lista e para `plainText` com repr Python, JSON válido e texto normal.
- Guarda: se após limpar sobrar texto > ~600 caracteres, mostrar "Ler mais" em vez de parede de texto.

## 2. Hierarquia e tipografia

- Hero: nome em corpo enorme e ao lado um bloco de texto cru de 1 linha; sem resumo limpo o hero fica quebrado. Limitar resumo a 2 linhas com `line-clamp`.
- Título "Informações para orientar o trabalho" (~43px) é maior que o nome da marca e que qualquer seção: compete com o hero. Reduzir para escala de seção (≈28px) e tirar a linha grossa de 2px.
- "Essência da marca" em corpo grande e texto sem limite de largura: aplicar `max-width: 70ch` e peso normal; hoje lê como parede.
- Três títulos grandes seguidos (completude → estado da base → dossiê → direção) repetem a mesma ideia ("a marca está pronta"). Fundir "Estado da base" dentro do card de completude.
- Rótulos "COBERTURA CONSOLIDADA", "Estado da base", "Dossiê da marca" têm 3 estilos de eyebrow diferentes; padronizar um só.

## 3. CTAs

Hoje há ~10 ações espalhadas, em 3 lugares (menu esquerdo, card de completude, trilho direito), com duplicidade:

| Ação | Onde aparece hoje | Problema |
|---|---|---|
| Atualizar análise / Atualizar auditoria | completude + menu | mesmo destino, dois nomes |
| Editar dados | completude + menu | duplicada |
| Conversar sobre a marca | menu | é a ação de maior valor e está escondida, truncada ("Conversar sobre a mar…") |
| Atualizar com o Cadu | seção Direção | não é "atualizar": abre conversa. Nome engana |
| Criar imagem/vídeo no Studio | só no trilho, como link de texto | CTAs de conversão sem peso visual |
| Criar ou vincular projeto | trilho | ok, mas texto solto |
| Apagar marca | trilho, vermelho solto | perto demais das ações seguras |
| Consultar síntese da análise | card de estado | botão com borda fina, parece desabilitado |

Proposta:
- **Barra de ações do hero** (só aprovada): primário `Criar no Studio` (menu: imagem/vídeo), secundário `Conversar sobre a marca`, terciário `Editar dados`. Depois do hero, nenhum outro "Editar dados".
- **Completude**: manter só `Atualizar análise` (primário) quando score < 100%; quando alto, vira link discreto "Reanalisar".
- Renomear "Atualizar com o Cadu" → "Refinar com o Cadu" ou "Conversar sobre a direção".
- Menu esquerdo: tirar ações (fica só navegação por seção); mover ações para hero/menu "⋯". Evita truncamento.
- "Apagar marca" para menu "⋯" do hero ou rodapé "Zona de risco", com confirmação (já existe `DeleteBrandDialog`).
- Botões do tipo `cadu-ds-entity-rail__studio` ganham estilo de botão (hoje link verde pequeno).
- Estados: `Aprovar análise` (quando pendente) deve ser o CTA primário do hero, nunca só no menu.

## 4. Detalhes de interface

- **Placeholders vazados**: textos de fallback como "Dado registrado", "Detalhe disponível", "Registro público" aparecem sem contexto no trilho; preferir esconder o item quando não há valor real.
- **Presença pública** repete "E-mail público"/"Telefone público" 7 vezes; agrupar por tipo (E-mails, Telefones, Endereço) e usar o valor como título. Cada linha tem ícone de link externo + seta ↗ (duas pistas); manter uma. E-mail/telefone devem ser `mailto:`/`tel:`, não link externo para a "fonte".
- **Fontes da auditoria**: títulos como "Como Solicitar Os Principais Serviços" (slug capitalizado) e detalhe truncado. Mostrar domínio + caminho legível, com "Ver todos" que abre drawer.
- **Trilho direito**: Paleta, Tipografia, Base da marca, CTAs, Presença, Fontes numa coluna única longa (~1200px). Dividir: kit (paleta/tipografia) fixo no topo, resto recolhível.
- **Paleta**: hex + papel em duas colunas ok, mas sem feedback ao copiar. Adicionar toast "Copiado". Hoje `navigator.clipboard` sem tratamento de erro.
- **Tipografia**: "Roboto / interface" e "Helvetica Neue / interface" duplicam o papel; deduplicar e linkar fonte.
- **Logo** do hero é miniatura cinza num quadrado grande; usar fundo neutro e `object-fit: contain` com padding.
- **Status** "Pronta para uso" e "Identidade aprovada" aparecem no hero, no trilho e no estado da base: três vezes o mesmo selo.
- **Menu esquerdo**: contadores só em alguns itens; "Cobertura da marca" e "Atualizar auditoria" usam o mesmo ícone de pulso.
- **Acessibilidade**: botões de cor sem `aria-label` com nome; `aria-live` ausente ao copiar; contraste do cinza das legendas (~#6b7280 sobre #fafafa) perto do limite em 11px.
- **Mobile**: o trilho vira bloco duplicado ao fim (`cadu-ds-brand-responsive-management`) e repete Paleta/CTAs; conferir se o JSON também aparece no `WorkspaceMobileChrome` (usa só `brand.name`, ok).
- `window.localStorage.getItem` em `:525` sem try/catch (o `EntityNavigator` já usa); em modo privado quebra a tela inteira.
- `window.location.reload()` após auditoria (`:546`) perde scroll e estado; trocar por refetch.

## 5. Telas vizinhas (a verificar no mesmo padrão)

- `WorkspaceBrands.jsx` (lista): checar cards que usam `brandSummary`/`tone` crus; mesmo `plainText` deve ser usado.
- `CampaignSection`, `AuditHistory`, `AuditAtlas/ListBlock` (`:455`): o `ListBlock` já limpa item a item, mas depende de `readableBrandItem`, que falha em listas aninhadas (`[`). Reaproveitar `plainText`.
- Biblioteca (`AssetSection`): sem busca/filtro por tipo; CTA de upload só em estado vazio.
- `WorkspaceProject.jsx`: ver se exibe resumo da marca vinculada (mesmo risco de JSON).
- Varredura no repo por qualquer outro `profile.*` impresso sem passar pelo helper (`grep -n "profile\.\(brandSummary\|toneOfVoice\|positioning\)"`).

## 6. Ordem de execução

1. `plainText` no front + usar em hero/lead/FilledReading (resolve o visível hoje).
2. `_text()` no back + testes (para de gerar lixo novo).
3. Script de reparo dos dados existentes (contagem primeiro, depois rodar).
4. Reorganização de CTAs (barra do hero, remover duplicatas, "Apagar" para zona de risco).
5. Ajustes tipográficos e do trilho (itens 2 e 4).
6. Varredura das telas vizinhas e acessibilidade.

Verificação: marca Cemig em tela (desktop e 375px), marca sem auditoria, em processamento, com falha, e com resumo longo; ver console sem erros. Build do bundle precisa ser regerado (os `static/.../react/app.js` são artefatos, ver memória de módulos ES/import map).

---

# 7. Radares na página da marca e fim das "Campanhas" estáticas (2026-10-08)

## Diagnóstico

- A seção "Campanhas que viram projetos" ([WorkspaceBrand.jsx:369](../frontend/cadu-design-system/components/WorkspaceBrand.jsx)) lista `profile.campaigns`, gerado **uma vez** pela auditoria (`_campaigns()` em `creative_brand_analysis.py:1848`, a partir de `campaigns`/`campaign_opportunities` do LLM). São hipóteses do modelo sobre o site, sem data, fonte, prazo ou nota. Não são fatos do mundo. Daí a sensação de "não faz sentido".
- O sinal de oportunidade de verdade já existe no Radar: `cadu_radar_opportunities` (nota editorial/paga, quadrante, `geo_scores`, `signal_ids`, status `nova/salva/em_plano/descartada`), `cadu_radar_signals` (manchete, fonte, URL, data) e `cadu_radar_watches` (alertas por marca). Tudo já tem `brand_ref = 'studio:<cx_clients.id>'`, o mesmo id da marca da tela. O módulo `cadu_radar/radars.py` já agrega execuções, novidades e estado de leitura; `repository.list_opportunities(client_id, brand_ref=...)` já filtra por marca.
- A página da marca está no Workspace e o Radar no Planner: hoje não se conversam. Só o Radar lê a marca (`brand_profile.py`); a marca não lê o Radar.

## Proposta: substituir "Campanhas" por "Radar da marca"

Seção nova (mesmo `id`, para não quebrar a âncora e o menu; renomear item para **Radar**), alimentada por oportunidades e sinais reais:

1. **Cabeçalho**: "Radar de {marca}" + estado (último run, próximo run, nº de alertas ativos, novidades não vistas) + CTA primário **Rodar radar** (abre o wizard do Planner já com a marca) e **Configurar alerta**.
2. **Oportunidades abertas**: cartões ordenados por nota, só `nova`/`salva`, com título, tese, quadrante (Conteúdo · Mídia · Integrada), **janela/prazo**, selo de confiança, 1–2 fontes (veículo + data) e a nota explicada ("por que?"). Ações: **Criar projeto** (ou plano no Planner), **Salvar**, **Descartar** (com motivo). Os botões gravam em `cadu_radar_opportunities.status`, o mesmo retorno que alimenta o aprendizado de agentes da fase 4 do Radar.
3. **Sinais recentes**: lista curta de manchetes (fonte, data, tipo) ligadas à marca e aos concorrentes cadastrados; "Ver todos" leva ao feed do Radar filtrado por marca.
4. **Concorrentes em movimento**: usa `profile.competitors` como entrada; mostra o que saiu sobre cada um. Cria o laço com "Concorrentes e alternativas" de Todos os dados (que hoje mostra `Description:` em inglês, cru).
5. **Estados vazios com ação**: sem nenhum run → "Ainda não há radar para esta marca" + CTA **Criar primeiro radar** (custo estimado em créditos). Sem créditos/alerta pausado → aviso claro. Em execução → progresso. Falha → "Tentar de novo".
6. **O que sobra de `profile.campaigns`**: deixa de ser seção. Vira **semente**: ao criar o primeiro radar, as `campaign_opportunities` da auditoria viram sugestões de tema/lente no passo 2 do wizard ("Tema sugerido: Institucional"). Os projetos já criados a partir delas (`status = project_created`) continuam acessíveis em **Projetos** (trilho) sem perder o vínculo.

## Integrações (desenho)

| Elo | Como | Onde |
|---|---|---|
| Marca → Radar | Bootstrap da marca ganha `radar`: `{enabled, runs, watches, openOpportunities[], recentSignals[], unread, urls:{run, wizard, feed, alerts}}`, montado no backend a partir de `repository.list_opportunities(client_id, brand_ref=f'studio:{brand.id}')`, `radars.list_radars` e `feed.list_feed` filtrados por marca. Limitar a ~6 oportunidades e ~8 sinais. | view do Workspace que monta `bootstrap.brand` |
| Radar → Marca | Wizard recebe `?marca=studio:ID` (já aceita marca na barra de contexto); ao concluir, volta para a marca (`#radar`). | `RadarWizard.jsx`, `Radar.jsx` |
| Oportunidade → Projeto | "Criar projeto" reaproveita `CreateBrandProjectDialog` (já existe) com título/tese/fonte da oportunidade, e grava `status='em_plano'` + vínculo (`cadu_planner_plans.signal_id`/`opportunity`). Mantém "plano" do Planner como destino alternativo. | `repository.create_plan`, `CreateBrandProjectDialog` |
| Oportunidade → Studio/Chat | Ação secundária "Criar peça no Studio" com a tese como briefing e o contexto da marca aprovado; "Conversar sobre isso" abre o Cadu com a oportunidade anexada. | `urls.createImage/createVideo`, conversa |
| Marca → Radar (contexto) | Concorrentes, público e setor da marca alimentam o wizard (`brand_profile.load_brand`, `gaps`, `propose`). Lacunas viram chips "Adicionar concorrentes". Já existe; só precisa do link vindo da marca. | `cadu_radar/brand_profile.py` |
| Alertas → Marca | Novidade de alerta mostra badge no item **Radar** do menu e no cartão da marca na lista; aviso no sino já previsto na fase 3. | menu `brandNav`, `WorkspaceBrands.jsx` |
| Auditoria → Radar | Reauditar a marca atualiza concorrentes/setor usados pelos alertas ativos (hoje congelados no `params` do alerta). Decidir: o alerta lê da marca a cada run (recomendado) em vez de copiar. | `watches.py`, `pipeline.py` |
| Créditos | Rodar radar na página da marca mostra estimativa (`/radar/estimate`) e usa o mesmo `CaduCreditConnector` ("Cadu Radar"). | `AuditDialog` mostra `creditAvailable`: reaproveitar o padrão |
| Permissões | Ver radar = qualquer papel que vê a marca; rodar/configurar/descartar = `canManageBrand`. Respeitar a flag `CADU_RADAR_ENABLED`: desligada, a seção some. | bootstrap |

Cuidados de modelagem (verificar antes de codar):
- `client_id` do Radar é `crm_client_id` e `brand_ref` é `studio:<cx_clients.id>`; a marca da tela usa `cx_clients`. Confirmar que `brand.id` é esse mesmo id (em `brand_profile._brand_id`).
- Oportunidades antigas guardam `brand_ref` por texto; marcas apagadas/renomeadas não quebram, mas "Apagar marca" deve avisar quantos alertas ativos serão pausados.
- Hoje **não há nenhuma busca real em produção** (ver `radar-v2-plano.md`). A seção precisa nascer bonita no estado vazio e em dados de amostra, e só depois ganhar volume. Não prometer "resultados" antes da fase 0 do Radar.
- Sem preço/tarifa nas oportunidades (decisão do Planner); mostrar custo só em créditos.

## Ordem de execução (adendo)

1. Back: função `brand_radar_context(client_id, brand_id)` + campo `radar` no bootstrap da marca (somente leitura, com testes e flag).
2. Front: componente `BrandRadar` no lugar de `CampaignSection`; estados vazio/em execução/falha/sem créditos; item de menu renomeado e com badge.
3. Ações: Salvar/Descartar (já existe em `repository.set_pauta`/status) e **Criar projeto** a partir da oportunidade.
4. Ligações: `?marca=` no wizard e retorno para a marca; sementes vindas de `campaign_opportunities`.
5. Alertas na marca (criar/pausar) e badge de novidades.
6. Limpeza: remover `CampaignSection`, o campo `campaigns` da exibição e as classes `cadu-ds-brand-campaigns`; manter o dado em `brand_profile` por compatibilidade com o Planner.
7. Verificar em tela (marca com e sem radar, 375px) e rebuildar os bundles.

## Pontos para você decidir

1. As oportunidades aparecem **só na marca** ou também no **projeto** vinculado? (recomendo marca, com o projeto herdando as da marca.)
2. "Criar projeto" a partir da oportunidade vai para **Workspace (projeto)** ou **Planner (plano)**? (recomendo projeto no Workspace, com "Montar plano no Planner" como segunda ação.)
3. Mostrar o radar já com dados de amostra enquanto não há buscas reais, ou só o estado vazio com CTA? (recomendo só o vazio honesto, e rodar a Fase 0 do Radar na Cemig.)

---

# 8. Página do Projeto: resumo cross-produto, "Mais ações" e Biblioteca/Arquivos/Indexação (2026-10-08)

Código: `frontend/cadu-design-system/components/WorkspaceProject.jsx` (menu em `:935-950`, "Mais ações" em `:988-992`), `aicentralv2/templates/cadu_workspace/project_detail_react.html` (`projectLinks`), `aicentralv2/cadu_workspace/project_reports_service.py`, `project_portfolio_service.py`.

## 8.1 Diagnóstico

1. **Reports já se liga ao projeto, mas só numa aba escondida.** `project_reports_service.LINKABLE` vincula campanhas, sites e fluxos (`REPORT_KINDS` em `:729`) e lista os relatórios. Não há resumo na Visão geral, nem Monitoramento nem Tags (o pedido cita "monitoramento, tag").
2. **"Mais ações" manda o contexto errado ou incompleto.** Criar plano/imagem/vídeo é só link com `project_id` (+ `brand_id`). O projeto da página de **Projeto** não chega "selecionado e pronto" nos ambientes:
   - **Planner** lê o contexto por `project_ref = 'ci:<id>'` (`contextBar`, `PlansPages.jsx:178`); o link manda `project_id=<uuid>` sem o prefixo. **Verificar** se `/novo` converte; se não, o plano nasce sem projeto.
   - **Studio** lê `bootstrap.projectId` e tenta casar por `external_project_id`/`ci:` (`StudioHomeApp.jsx:44`); se não casar, pega `list[0]` (um projeto qualquer). Isso é um risco real: a peça pode cair no projeto errado.
   - Nenhum dos dois mostra "criando para o projeto X, marca Y, com N fontes" antes de começar.
3. **Planos do Planner não aparecem no projeto.** `cadu_planner_plans.project_ref` existe e `project_portfolio_service` até conta `media_plans`, mas a página do projeto não lista planos. Também não aparecem as peças do Studio (`studio_images`).
4. **Biblioteca mistura três coisas**: (a) fontes/arquivos/links/notas do projeto, (b) itens de **Direção** (Nome do projeto, Público, Posicionamento, Cor de referência: gravados como memória de direção, com "Revisão 1") e (c) relatórios/saídas (`FILE` "Relatório"). Os itens de Direção são do sistema de contexto do Cadu, não "biblioteca do usuário". O que é do Studio (peças, referências visuais) deveria ter casa própria.
5. **Arquivos × Biblioteca × Indexação** se sobrepõem: os três listam os mesmos arquivos com ângulos diferentes (lista crua, visão rica, estado de processamento). O mesmo `media-hacks-imersao-deck-v9.pptx` aparece 3 vezes (duas na Biblioteca, uma na Indexação) e ainda como "Conectado ao projeto" no trilho.
6. Trilho: "Trocar marca" é botão grande sem hierarquia; "Auditar" é link solto; "Definir identidade" idem; "A marca que orienta este trabalho · Parcial" sem dizer o que falta; título "[CENTRAL] [D:C…" truncado em "Conectado ao projeto".

## 8.2 Proposta de informação

### Menu do projeto (de 11 para 7 itens)

| Atual | Proposto | Observação |
|---|---|---|
| Visão geral | **Visão geral** | ganha o resumo cross-produto (8.3) |
| Direção | **Direção** | mantém; itens de direção saem da Biblioteca |
| Tarefas | **Tarefas** | |
| Arquivos + Biblioteca + Indexação | **Fontes** | uma só aba: arquivos, links, notas, com a coluna "estado de indexação" e filtros. Indexação vira filtro/painel dentro dela |
| Conversas | **Conversas** | |
| Artefatos e entregas | **Entregas** | passa a reunir peças do Studio, planos do Planner e relatórios do Reports (com filtro por produto) |
| Relatórios + Visualizações | **Reports** | monitoramento, campanhas, sites, fluxos, tags; resumo no topo |

"Visualizações" hoje é uma tela vazia com ilustração; fundir em Reports até haver conteúdo.

### Decisão sobre Arquivos/Biblioteca/Indexação (você pediu para pensar)

- **Arquivos**: o arquivo físico (upload, tamanho, quem enviou).
- **Biblioteca**: hoje é a mesma lista com cartões. Não tem função própria.
- **Indexação**: é *estado* do arquivo/link (pronto, processando, requer atenção), não um lugar.
Recomendação: **uma aba "Fontes"** com a lista unificada, cada linha com origem (arquivo/link/nota), papel (referência, relatório, direção), estado da indexação e ações (reindexar, remover, abrir). Os 4 contadores de Indexação viram chips de filtro no topo. Se houver erro de indexação, o badge vermelho aparece no item do menu (já existe a contagem). Não perde funcionalidade.
- **Direção do projeto** (nome, público, posicionamento, cor) volta para a aba Direção, não para a Biblioteca.
- **Studio fica no Studio**: peças e referências visuais geradas lá aparecem em **Entregas** como "Studio", com link para abrir no editor, e *não* duplicam na biblioteca de fontes do Cadu. A biblioteca do projeto fica "exclusiva do ecossistema do Cadu" (fontes de contexto), como você pediu.

## 8.3 Resumo cross-produto na Visão geral (aba/cartão "Hoje no projeto")

Um painel único, lido de `project_portfolio_service` (já agrega contagens) estendido com itens recentes:

| Bloco | Conteúdo | Fonte | CTA |
|---|---|---|---|
| **Planos** | nº de planos, último plano e status (rascunho/pronto) | `cadu_planner_plans WHERE project_ref='ci:<id>'` | Criar plano · Abrir |
| **Peças (Studio)** | nº de imagens/vídeos, 3 miniaturas recentes | `cx_studio_projects`/items (via `external_project_id`) | Criar imagem · Criar vídeo |
| **Reports** | campanhas, sites e fluxos vinculados, com saúde/último dado | `project_reports_service.list_project_reports` | Vincular · Abrir no Reports |
| **Monitoramento e tags** | status dos sites monitorados, alertas abertos, tags do projeto | Reports (monitoramento) + tags do projeto | Ver alertas |
| **Radar** | oportunidades abertas da marca/projeto (ver seção 7) | `cadu_radar_opportunities` | Rodar radar |
| **Fontes** | `1 de 1 indexadas`, requer atenção | `project.files` | Adicionar fonte |

Regras: cada bloco some se o produto não está habilitado; estado vazio sempre com CTA; um clique abre o produto **já com o projeto selecionado** (8.4); contagens vêm numa única chamada (`/projetos/<id>/resumo`) para não gerar 6 requisições.

Alternativa pedida ("mostrar resumo em uma aba"): colocar esse painel numa aba **Resumo** logo após Visão geral. Recomendo cartões na Visão geral (a primeira tela) e deixar a aba "Reports" para o detalhe, porque uma aba extra esconde de novo o que se quer mostrar.

## 8.4 "Mais ações" → "Criar no projeto" com contexto garantido

- Mover **Criar plano de mídia / imagem / vídeo** de "Mais ações" para o grupo **Ações** (são ações principais, hoje escondidas junto com Excluir). "Mais ações" fica só com administrativas: Gerenciar acesso, Arquivar, Mesclar, Excluir (esta separada e com confirmação).
- **Contrato único de contexto** para todos os destinos: `project_ref=ci:<uuid>` e `brand_ref=studio:<id>` (não `project_id` cru). Montar no backend (`projectLinks`) e ler em:
  - Planner `/novo`: preencher `contextBar` (marca + projeto) e já abrir no passo certo; plano grava `project_ref`.
  - Studio `criar`/`video`: selecionar o projeto **exato** e falhar de forma visível (aviso) se não achar, em vez de cair em `list[0]` (`StudioHomeApp.jsx:44-45`).
- **Tela de partida ("pronto para começar")** nos dois destinos: faixa "Criando para **Media Hacks** · marca **Centralcomm** · 1 fonte pronta · tom e cores aplicados", com "Trocar". Se a marca está "Parcial", avisar o que falta (ex.: "sem logo/tipografia") com atalho para completar.
- **Volta**: ao salvar plano/peça, voltar ao projeto na aba Entregas com o item novo destacado.
- Alinhar com o Radar: oportunidade → "Criar plano"/"Criar peça" usa o mesmo contrato.

## 8.5 Ajustes menores no trilho do projeto
- Substituir "Trocar marca" (botão grande) por link de edição junto ao nome da marca; "Auditar" e "Definir identidade" viram um menu "Marca ▾".
- "Parcial" vira "Faltam: logo, tipografia" (usar `brand.readiness.missing`).
- "Conectado ao projeto": mostrar nome completo em duas linhas, tipo em chip, e ordenar por tipo; reduzir duplicidade com Fontes.
- Remover o ícone de lupa duplicado em Relatórios e Visualizações; ícones diferentes por seção.

## 8.6 Ordem de execução
1. **Contrato de contexto** (`project_ref`/`brand_ref`) em `projectLinks` + leitura no Planner e no Studio, com teste de que nunca cai em outro projeto. É a correção mais valiosa e pequena.
2. Mover as 3 ações de criação para "Ações" e criar a faixa de partida nos destinos.
3. Endpoint `resumo` do projeto + cartões "Hoje no projeto" (planos, peças, reports).
4. Unificar Arquivos+Biblioteca+Indexação em **Fontes**; tirar itens de Direção da biblioteca; fundir Visualizações em Reports.
5. Reports: monitoramento e tags no projeto (depende de como o Reports expõe monitoramento e tag por projeto: **verificar** antes; hoje só há campanha/site/fluxo).
6. Entregas unificadas (Studio + Planner + Reports) com filtro por produto.
7. Trilho e polimento; verificar em tela (desktop/375px).

## 8.7 Perguntas para você
1. Confirma a fusão **Arquivos + Biblioteca + Indexação → Fontes**? (Mantemos "Arquivos" como visão em grade dentro dela, se preferir.)
2. "Tag" e "monitoramento": são recursos do Reports (tags de campanha, monitor de site)? Preciso saber qual tabela/serviço usar; não achei vínculo por projeto além de campanha/site/fluxo.
3. Peças do Studio devem **também** ir para as Fontes do projeto (para o Cadu usar como contexto), ou só Entregas? Recomendo só Entregas.

---

# 9. Decisões do usuário (2026-10-08) e ajustes nas seções 7 e 8

**Substituem o que estiver em conflito acima.**

## 9.1 Oportunidade vira plano, não projeto
- Na página da marca, o CTA da oportunidade é **`Criar plano`** (Planner), não "Criar projeto". Em `7. Proposta`, os itens 2 e "Oportunidade → Projeto" mudam: o destino é `cadu_planner_plans`, criado por `repository.create_plan(client_id, actor_id, opportunity_id, context)`, que já grava `brand_ref`, `project_ref` e o vínculo da oportunidade (`status='em_plano'`, `cadu_planner_plans.signal_id`).
- **`project_ref` é opcional.** Um plano pode existir só para a marca (`brand_ref` preenchido, `project_ref` nulo). Se a marca tiver um único projeto ativo, oferecer "Vincular ao projeto X" como padrão desmarcável; nunca obrigar.
- **Plano aparece no projeto depois**, quando associado: o cartão "Planos" do resumo do projeto (8.3) lista `cadu_planner_plans WHERE project_ref='ci:<id>'`. A aba **Entregas** também. Associar depois = ação `Vincular a projeto` no plano (atualiza `project_ref`), sem recriar.
- Oportunidades continuam **só na marca**; o projeto não herda cartões de oportunidade, apenas vê os **planos** que nasceram delas (via `project_ref`). Isso fecha a pergunta 1 da seção 7.
- A ação secundária é "Montar plano com contexto" (abre o Planner no wizard com marca, tema e fontes da oportunidade preenchidos). `Salvar` e `Descartar` ficam como estão.

## 9.2 Estado vazio honesto, sem dados de amostra
- Sem runs → estado vazio com ação, sem cartões inventados. Rodar a **Fase 0 do Radar na Cemig** (3 buscas reais, ~45 mil tokens: antes de gastar, pedir seu aval) para validar o que a seção mostra.
- **Ilustrações melhores:** as do Radar (`radar-scan`, `radar-empty`) estão na paleta antiga (`#067647`, 3D de argila). Refazer no estilo do Planejar (`#1DBF73`, flat editorial) via `frontend/planner/Illustration.jsx`, e criar uma ilustração própria para a marca sem radar ("antena sobre a marca"), uma para "radar em execução" e uma para "sem novidades". Reaproveitar no Workspace (copiar para `static/images/cadu/...`), sem importar o bundle do Planner. Estados da página de **Projeto** (Biblioteca/Indexação vazias) também usam `ProjectStateIllustration`: revisar na mesma leva para manter coerência.

## 9.3 CTAs revisados (regra geral para marca e projeto)
- **Um CTA primário por tela/seção**, verbo + objeto, nunca "Atualizar com o Cadu":
  - Marca/Radar: `Rodar radar` (primário), `Criar plano` por oportunidade, `Configurar alerta` (secundário).
  - Projeto: `Criar plano de mídia`, `Criar imagem`, `Criar vídeo` ficam em **Ações** (fora de "Mais ações"); `Adicionar fonte` é o primário da aba Fontes.
- **Hierarquia visual:** primário preenchido (verde), secundário contorno, terciário link. Hoje `Transformar em projeto`, `Consultar síntese da análise` e `Editar direção` têm o mesmo peso fino e parecem desabilitados.
- **Sem duplicatas:** cada ação existe em um só lugar por tela (ver auditoria de CTAs na seção 3).
- **Rótulos com resultado:** "Criar plano a partir desta oportunidade", "Vincular a projeto", "Ver fontes (3)".
- **Estados:** desabilitado com motivo ("Sem créditos: recarregue para rodar"), carregando, sucesso com próxima ação ("Plano criado · Abrir · Vincular a projeto").

## 9.4 "Fontes ruins" (qualidade das fontes exibidas)
Problemas vistos nos prints e no código:
1. **Rótulos de URL feios:** `sourceLabel` ([WorkspaceBrand.jsx:572](../frontend/cadu-design-system/components/WorkspaceBrand.jsx)) transforma o último trecho do caminho em título ("Como Solicitar Os Principais Serviços"), com "Site informado pela marca"/"Fonte usada na auditoria" repetido em toda linha.
2. **Fontes sem valor** misturadas: páginas de login, cookies, PDFs genéricos, redes sociais, mesma página com `?utm`. `uniqueSources` só deduplica por `host+path`.
3. **Sem hierarquia de confiança:** a página oficial vale o mesmo que um blog. O Radar já tem níveis A/B/C (`cadu_radar/sources.py`, `data/sources_v1.json`).
4. **Notícias/sinais do Radar** vão precisar de selo de fonte (veículo + data), por isso resolver agora evita retrabalho.

Ajustes:
- **Rótulo = título real da página** (`<title>`/`og:title` coletado na auditoria, campo `title` de `sourceRecords`), com fallback para o domínio e o caminho legível; nunca capitalizar slug.
- **Agrupar por domínio** ("cemig.com.br · 7 páginas"), expandir ao clicar; favicon do domínio; ocultar parâmetros de rastreio na exibição.
- **Selo de tipo e confiança** ("Oficial", "Imprensa", "Rede social", "Terceiros") reutilizando a classificação A/B/C; ordenar oficial → imprensa → resto.
- **Filtrar ruído** na auditoria (login, cookies, política genérica, páginas 404) antes de salvar em `analysisMetadata.sources`; reparo dos já salvos via o mesmo script da seção 1 (P1).
- **Contagem e escopo claros:** "10 fontes · 6 oficiais" + "Ver todas" em drawer com busca, em vez de lista longa no trilho.
- No **projeto**, a aba Fontes usa o mesmo componente (nome, origem, tipo, estado de indexação), para a mesma qualidade de rótulo.

## 9.5 Perguntas ainda em aberto (da seção 8.7)
1. Fusão **Arquivos + Biblioteca + Indexação → Fontes**: confirma?
2. **Tag** e **monitoramento**: quais recursos do Reports são esses (tabela/serviço)? Só encontrei campanha, site e fluxo vinculáveis ao projeto.
3. Peças do Studio só em **Entregas** (recomendado) ou também em Fontes?
