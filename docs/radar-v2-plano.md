# Radar v2: assistente, alertas automáticos e agentes

Plano de 2026-10-06. Continua `docs/planner-cobuild-radar-plan.md` (Radar R1).

## Onde estamos

| Item | Estado |
|---|---|
| Flag | `CADU_RADAR_ENABLED` ligada em produção (a tela `/radar` busca de verdade) |
| Uso real | **Nenhuma busca ainda.** `GET /radar/runs/latest` → `null`; 0 oportunidades |
| Reserva por busca | 15.207 tokens (`/radar/estimate`) |
| Pipeline | `discover` (Perplexity) ‖ `search` (Firecrawl) → `extract` → `judge` → `verify` → `save` |
| Notas | Determinísticas em `cadu_radar/scoring.py`; o modelo só preenche critérios |
| Entrada do usuário | Um campo de texto + marca/projeto da barra de contexto |
| Saída | Matriz Orgânico × Pago + cartões; única ação: "Criar planejamento" |

### O que a leitura do código já mostra (antes do teste real)

1. **Sem parâmetros.** Recência, praça, tipos de fonte, concorrentes e exclusões não existem na tela. Hoje estão fixos no código: 60 dias no prompt e `recency='month'` no Firecrawl.
2. **Sem histórico.** A tela só mostra a última busca. As buscas anteriores ficam no banco, mas ninguém as vê.
3. **Sem retorno do usuário.** Os status `salva` e `descartada` existem na tabela, mas não há botão para eles. Sem esse retorno, nenhum agente consegue aprender.
4. **Sem memória do que já foi visto.** Os sinais não têm impressão digital (URL normalizada, entidade ou fato). Cada busca reapresenta as mesmas notícias, o que inviabiliza alertas de "novo".
5. **Uma busca por cliente de cada vez.** A trava de 20 minutos é por `client_id`. Com dois alertas de marcas diferentes, um bloqueia o outro.
6. **A execução é uma thread dentro do gunicorn.** Funciona sob demanda, mas não serve para rodar no horário: reinício ou deploy matam o run. `lease_until` existe e não é usado, e um run morto fica `running` por até 20 minutos.
7. **`source_type` quase sempre é `news`.** O tipo `search_trend` existe no contrato, mas nenhuma fonte o produz.
8. **Os canais sugeridos são texto solto.** Não apontam para o catálogo, então não dá para adicioná-los ao plano.
9. **Ilustrações antigas.** `radar-scan` e `radar-empty` ainda seguem a paleta antiga (`#067647`, 3D de argila), não a do Planejar (`#1DBF73`, flat editorial).

## Visão do produto

O Radar responde à pergunta do planejador: **"o que está acontecendo agora que a minha marca deveria aproveitar, e onde?"** Ele entrega oportunidades com prazo, nota explicada, praças e canais do catálogo, prontas para virar plano.

Três modos, na ordem em que entram:

| Modo | Para quê | Quem dispara |
|---|---|---|
| **Busca** (wizard) | Pergunta pontual, com parâmetros | Usuário, sob demanda |
| **Alertas** | A mesma busca salva, rodando de 1 a 3 vezes por dia, avisando só quando há algo **novo** acima do limite | Agendador |
| **Agentes** | Um alerta que aprende o que priorizar, usa bases próprias e complementa agentes existentes da marca | Agendador + aprendizado |

Navegação (grupo **Oportunidades** em `frontend/planner/main.jsx`):

- **Radar**: busca, histórico e caixa de oportunidades.
- **Alertas** (link novo): alertas configurados e o feed do que chegou.
- **Agentes** (entra na fase 4; até lá fica oculto): agentes do Radar e o que cada um aprendeu.

## Fase 0: validar o Radar R1 em produção

O objetivo é rodar de verdade antes de construir em cima.

1. **Três buscas reais**, cerca de 45 mil tokens no total:
   - uma com marca e sem tema;
   - uma com tema e sem marca;
   - uma com marca, projeto e tema.
2. **Medir em cada busca:**
   - tokens por etapa contra a reserva (calibrar o teto de cerca de 21,5 mil, que ficou pendente);
   - tempo total;
   - quantas fontes foram lidas;
   - quantas oportunidades saíram contestadas;
   - se as URLs abrem e se as datas são recentes;
   - se as notas fazem sentido para um planejador.
3. **Corrigir o que bloqueia**, ainda no R1:
   - `lease_until` com renovação; run sem lease vira `failed`;
   - trava por `(client_id, brand_ref)` em vez de só por `client_id`;
   - reserva calibrada.
4. **Testar o Perplexity**, numa chamada avulsa barata:
   - se o OpenRouter repassa o filtro de domínio e de recência;
   - quanto o `sonar-pro` custa contra o `sonar`;
   - quantas citações caem em domínios conhecidos.
5. **Registrar** os achados neste documento, numa seção "Validação".

Critério de saída: 3 buscas concluídas, nenhuma etapa travada e ao menos 60% das oportunidades "confirmadas" ou "parciais" com fonte que abre.

## Fase 1: assistente "Configurar Radar" (wizard)

O wizard segue o mesmo esqueleto do `PlanWizard.jsx`:

- tela dividida, com a cena à esquerda;
- progresso "1 de 5";
- todos os passos opcionais, com "Pular e revisar";
- rascunho salvo em `sessionStorage`.

Ele **não substitui** a busca rápida: o campo atual continua no topo de `/radar` como atalho, e o wizard abre por "Configurar busca".

Componente novo: `frontend/planner/RadarWizard.jsx`, reaproveitando as classes `wizard__*`.

| # | Passo | Pergunta | Parâmetros (curtos) | Vem preenchido de |
|---|---|---|---|---|
| 1 | **Marca** | De quem é este radar? | Marca, projeto. Painel "O que já sabemos": setor, público, concorrentes, oportunidades de campanha, fontes do projeto. Lacunas aparecem como chips "Adicionar concorrentes" | `cadu_planner/context.py` (`brand_profile`, `cadu_ci_projetos`) |
| 2 | **Tema** | O que você quer encontrar? | Um texto livre + 1 a 3 lentes: *Sazonalidade e datas*, *Concorrência*, *Tendências e cultura*, *Regulação*, *Lançamentos do setor*, *Reputação*. Objetivo: Conteúdo, Mídia ou Os dois | Setor e oportunidades da marca viram sugestões |
| 3 | **Onde e quando** | Onde e em que janela? | Praças (chips iguais aos do Planejar), recência (24 h · 7 dias · 30 dias · 60 dias), horizonte de ação (esta semana · este mês · próximo trimestre) | Praça do projeto |
| 4 | **Fontes** | Onde o Radar deve olhar? | Tudo já vem ligado com a base curada (ver "Bases e confiabilidade"). O usuário só **desliga** grupos (Imprensa nacional · Imprensa regional das praças · Imprensa de mercado e mídia · Governo e regulação · Buscas em alta · Calendário · Concorrentes · Base do projeto) e, em "Avançado", adiciona sites para sempre olhar ou bloqueia sites | Concorrentes e sites cadastrados da marca; portais regionais das praças do passo 3 |
| 5 | **Revisão** | Pronto para procurar? | Resumo + **custo estimado em créditos** + interruptor **"Me avise quando houver novidade"**, que abre a frequência (1×, 2× ou 3× por dia) e cria o alerta | Calculado no servidor |

Regras de parâmetro:

- Cada passo cabe em uma tela sem rolagem a 1280×800. Nada de formulário longo.
- O contrato do run ganha uma coluna `params JSONB` com `{lenses, objective, places, recency, horizon, sources, include_sites, exclude_sites, competitors}`.
- `focus` continua existindo.
- O pipeline lê `params`:
  - a recência vai para o prompt e para o Firecrawl;
  - as fontes ligam ou desligam fluxos;
  - as lentes e praças entram no `judge`.

Ainda na fase 1, na tela de resultados:

- **Histórico de buscas**: lista lateral com tema, data, nota máxima e custo.
- **Ações no cartão**: Salvar · Descartar (com motivo rápido: *fora do tema*, *velho*, *fonte fraca*, *não é para a marca*) · Criar planejamento · **Adicionar a um plano existente**. Esses cliques alimentam o aprendizado da fase 4.
- **Canais do catálogo**: o `judge` recebe a lista de slugs de `cadu_canais` e escolhe dela. O cartão mostra os logos com link para a ficha.
- **"Por que esta nota?"**: um painel com os critérios, os pesos e as penalidades (que já existem em `score_breakdown`).

## Fase 2: bases de pesquisa e confiabilidade

Princípio: cada fonte vira `Signal` com `source_type` correto, e **nada sem evidência lida vira nota**. "Dose de realidade" vem de **triangulação**: o mesmo fato achado por caminhos independentes vale mais que um fato achado uma vez.

### Perplexity em dois papéis (hoje é uma chamada só, `perplexity/sonar`)

| Chamada | O que pergunta | Por quê |
|---|---|---|
| **Descoberta aberta** (já existe) | "O que aconteceu no tema, na janela e nas praças?" | Acha o que ninguém pensou em procurar |
| **Descoberta na imprensa** (nova) | A mesma pergunta, **restrita aos portais curados** (filtro de domínio e de recência do Perplexity), em lotes: nacionais, mercado e mídia, regionais das praças | Traz fatos citados por veículos conhecidos, e não por blogs ou agregadores |
| **Checagem de realidade** (nova, no `verify`) | Para cada oportunidade: "isto é verdade, é recente e quem mais publicou?" | Busca **fora** das evidências do pacote. Hoje o verificador só relê o que o próprio `judge` recebeu, e por isso não consegue achar contradição |

- **Modelo:** testar `perplexity/sonar-pro` na descoberta, porque traz mais citações por resposta e cita melhor. Manter o `sonar` na checagem, que é barata e roda uma vez por oportunidade. Decidir pelo custo e pela qualidade medidos na fase 0.
- **Verificar na fase 0** se o OpenRouter repassa o filtro de domínio e de recência para o Perplexity. Se não repassar, o plano B é pôr os domínios no texto da pergunta e descartar as citações que caírem fora da lista. O plano C é chamar a API do Perplexity direto, cobrando pelo mesmo conector de créditos.

### Fontes

| Fonte | Como | `source_type` | Custo |
|---|---|---|---|
| Notícias recentes | Firecrawl `search` com categoria de notícias e recência do wizard, com prioridade para os portais curados | `news` | Firecrawl |
| Descoberta aberta e na imprensa | Perplexity, nos dois papéis acima | `news`/`event` | Tokens |
| **Imprensa regional das praças** | Portais do Atlas da Notícia por UF e cidade (`tmp/planner-portais-atlas-candidatos.csv`, 1.000 candidatos) entram no filtro de domínio quando a praça é escolhida | `news` | Tokens |
| Buscas em alta | Perplexity com pergunta dirigida a "termos em alta no Brasil na janela X" + Firecrawl nas páginas de tendências públicas | `search_trend` | Tokens + Firecrawl |
| Governo e regulação | Firecrawl `search` restrito a `gov.br`, `in.gov.br` (DOU), agências reguladoras do setor da marca | `regulation` | Firecrawl |
| **Calendário de datas** | Tabela nova `cadu_radar_calendar` com datas comerciais, culturais e esportivas do Brasil e janelas de compra (curada; sem custo por busca) | `event` | Zero |
| Sites dos concorrentes | Firecrawl `scrape` dos sites/listas cadastrados; nos alertas, comparar com a última leitura (mudou? lançou?) | `crm`/`other` | Firecrawl |
| Base do projeto | Fontes e documentos do projeto (`project_sources`, `cadu_knowledge_documents`) como contexto da marca, nunca como "notícia" | contexto | Zero |
| Benchmarks pagos | `cadu_media_benchmarks` e `cadu_reports_gads_*` para ancorar o critério `eficiencia` da nota paga | contexto | Zero |

### Bases e confiabilidade

**O usuário não escolhe base por base.** Planejador não deve montar lista de fontes, e uma lista montada às pressas piora o resultado. A base é curada por nós e vem ligada. O usuário só desliga grupos, acrescenta os sites dele e bloqueia o que não quer (passo 4 do wizard). A tela de resultado mostra **de onde veio cada fato**.

Tabela nova `cadu_radar_sources`, mantida pela equipe e não pelo cliente:

```
domain, name, grupo ('nacional','regional','mercado_midia','governo','setorial','agregador','social'),
tier ('A','B','C','bloqueado'), uf, cidade, setores TEXT[],
canal_slug NULL,     -- liga ao portal do catálogo "Portais e veículos", quando existir
origem ('curadoria','atlas_noticia','usuario'), revisado_em
```

| Nível | Quem entra | Peso na evidência |
|---|---|---|
| **A** | Fonte primária (gov.br, DOU, reguladores, IBGE, comunicado oficial da empresa, relatório de RI), grande imprensa nacional, imprensa de mercado e mídia, principal veículo de cada capital | Sozinha já sustenta um fato |
| **B** | Imprensa regional com redação (Atlas da Notícia validado), veículos setoriais | Sustenta com uma segunda fonte, ou se for fonte primária do fato local |
| **C** | Agregadores, blogs, sites desconhecidos, redes sociais | Só sinaliza: nunca sustenta sozinha; precisa de A ou B |
| **Bloqueado** | Sites de conteúdo gerado em massa, fazendas de SEO, os bloqueados pelo usuário | Descartado antes do `judge` |

Domínio que não está na tabela conta como **C** até alguém revisar.

**Selo de confiança da oportunidade.** É calculado em Python, como as notas, e aparece no cartão:

- **Alta:** há 1 fonte primária, ou 2 fontes A/B independentes, e a checagem do Perplexity não contradiz.
- **Média:** há 1 fonte A/B, ou fontes que só os dois caminhos de descoberta (Perplexity e Firecrawl) acharam em comum.
- **Baixa:** só há fontes C. Nesse caso a oportunidade vai para "ignorar" e nunca dispara alerta.

Fontes "independentes" são de grupos de mídia diferentes. Duas páginas que replicam a mesma nota de agência valem uma.

**Penalidades.** Elas usam `PENALTY_CAPS` em `scoring.py`, que já existe. `pouca_evidencia` e `baixa_confianca` passam a vir desse selo, e não da opinião do modelo.

**Curadoria inicial**, feita na fase 2:

1. Uma lista de cerca de 80 domínios A: nacionais, mercado e mídia, governo, e o principal veículo de cada capital.
2. Os 1.000 candidatos do Atlas entram como B só depois do crawl de validação de domínio, que o CSV já marca como pendente. Até lá ficam como C.
3. Os portais que também estão no catálogo "Portais e veículos" ficam ligados por `canal_slug`.

**O portal é fonte e também mídia.** Quando a oportunidade nasceu de notícias de um portal que está no catálogo, o cartão sugere esse portal como canal: "o assunto está sendo coberto aqui, e dá para anunciar aqui". Isso dá ao planejador um argumento direto para o plano.

Também nesta fase:

- **Impressão digital do sinal**, numa coluna nova `fingerprint` em `cadu_radar_signals`. É o hash de: URL canônica, ou, quando não há URL, entidade, fato e data. Com ela vêm a deduplicação dentro do run e entre runs e o selo "visto antes".
- **Oportunidade recorrente**: a mesma tese em runs diferentes vira atualização da oportunidade existente ("ganhou 2 fontes novas"), não um cartão duplicado.

## Fase 3: Alertas (link novo "Alertas")

### Modelo

`migrations/add_cadu_radar_watches.sql`:

```
cadu_radar_watches
  id UUID, client_id, owner_id, brand_ref, project_ref, name,
  params JSONB,                 -- mesmos parâmetros do wizard
  frequency SMALLINT (1..3),    -- vezes por dia
  run_hours SMALLINT[],         -- ex.: {8,13,18}, fuso America/Sao_Paulo
  min_score SMALLINT DEFAULT 70,-- só avisa acima disso
  daily_token_cap INTEGER,      -- teto diário de créditos deste alerta
  channels JSONB,               -- {"inapp": true, "email": false}
  status ('ativo','pausado','sem_credito'), next_run_at, last_run_at,
  agent_id UUID NULL            -- preenchido quando vira agente (fase 4)
cadu_radar_runs   + watch_id UUID NULL, + trigger ('manual','agendado'), + params JSONB
cadu_radar_alerts
  id, watch_id, opportunity_id, reason ('nova','subiu_nota','janela_fechando'), seen_at, created_at
```

### Execução

- **Timer systemd**, no mesmo padrão de `deploy/install_planner_site_monitor_timer.sh`: `flask --app run:app cadu_family radar-due --limit=3` a cada 5 minutos.
- O comando pega os alertas com `next_run_at <= now()` usando `FOR UPDATE SKIP LOCKED`, grava o lease e executa o mesmo `Runner`, fora do gunicorn.
- Instalador: `deploy/install_radar_watch_timer.sh`. Registrar no `deploy.sh` e no `ORDER.txt`.

### Modo econômico: o alerta só paga a parte cara quando há novidade

```
discover ‖ search (+ fontes do wizard)
        → impressão digital → descarta o que já foi visto
        → nada novo?  encerra o run aqui ("sem novidade", custo baixo)
        → há novo     extract → judge → verify (+ checagem Perplexity só das novas)
                      → save → alerta se nota ≥ min_score E selo de confiança ≠ baixa
```

Na prática, um run sem novidade custa só a descoberta, cerca de 5 a 6 mil tokens contra 15 mil. Esse número tem de ser medido na fase 0. A checagem de realidade roda só nas oportunidades novas, nunca nas que já foram checadas.

### Créditos

- Cada run agendado é cobrado do **dono do alerta**, pelo `CaduCreditConnector`.
- A cobrança usa a etiqueta global do Radar:
  - `app='Cadu Radar'`;
  - `stage='radar:auto:<etapa>'`;
  - chave idempotente `radar:<run>:<etapa>`.
- Assim o painel de créditos separa o Radar sob demanda do automático.
- Antes de cada run: `authorize` do teto. Sem saldo, o alerta vai para `sem_credito`, o usuário é avisado uma vez e o alerta para de tentar até a próxima recarga.
- A tela do alerta mostra o **custo estimado por mês** (frequência × custo médio real dos últimos runs) e o gasto do mês até agora.

### Avisos

- **No app:** `cadu_planner_user_notifications` no sino do Planner, com link para a oportunidade.
- **Resumo por e-mail (opcional):** um e-mail por dia, com as oportunidades novas.
- **"Janela fechando":** quando faltam 48 h para a janela de uma oportunidade salva, o usuário recebe um aviso.

### Tela `/radar/alertas`

- **Lista de alertas.** Cada linha mostra:
  - nome, marca e frequência;
  - última execução, com o resultado;
  - novidades;
  - gasto do mês;
  - ações pausar e editar.
- **Feed de novidades**, filtrável por alerta, marca e quadrante.
- **Criar alerta.** O alerta abre o mesmo wizard, com o passo 5 em modo alerta.

## Fase 4: Agentes do Radar (depois de validar os alertas)

Um **agente** é um alerta com memória e preferências. Ele só aparece quando o alerta tem ao menos cerca de 10 oportunidades com retorno do usuário. Antes disso, aprender seria chute.

### O que o agente aprende (explícito, visível e reversível)

`cadu_radar_agents`:

```
id, client_id, brand_ref, project_ref, name,
instructions TEXT,             -- instruções do usuário + herdadas (abaixo)
preferences JSONB              -- o que aprendeu:
  {"weights": {"editorial": {"timing": 1.2, ...}, "paid": {...}},   # multiplicadores 0,7–1,3
   "topics": {"boost": [...], "mute": [...]},
   "sources": {"trusted": [...], "muted": [...]},
   "min_score": 72}
knowledge JSONB                -- bases extras: URLs, sites, documentos, listas de concorrentes
learned_at, version
```

Como ele aprende:

1. Os sinais de retorno vêm da fase 1 (salvar, descartar com motivo, virar plano, adicionar a plano, ignorar o alerta).
2. Uma rotina diária determinística recalcula as preferências:
   - critérios que separam oportunidades aceitas de recusadas ganham ou perdem peso, sempre dentro de 0,7 a 1,3;
   - os motivos de descarte viram "mute" de tema ou de fonte;
   - o limite de nota sobe ou desce conforme a taxa de aceite.
3. O modelo **não** altera pesos sozinho, para que a nota continue explicável. Ele só resume em português "o que mudou e por quê".
4. A tela "O que o agente aprendeu" lista cada preferência. Cada uma tem dois botões: **Manter** e **Desfazer**. Toda mudança gera nova `version`, para que dê para voltar.

### Marca, projeto e agentes que já existem

Ao criar um agente para uma marca ou projeto, o Radar procura o que já existe e oferece complementar:

| Já existe | Onde está | O que o agente do Radar faz |
|---|---|---|
| Perfil da marca | `cx_clients.brand_profile` | Usa como contexto; aponta lacunas (concorrentes, público) |
| Projeto e fontes | `cadu_ci_projetos`, `project_sources`, `cadu_knowledge_documents` | Usa como base de consulta |
| Skill personalizada do cliente | `cadu_skill_customizations` (Cadu Skills) | Importa as instruções como ponto de partida, com origem marcada |
| Plugin "Radar de mercado" do workspace | `agent_v2/daily_workflows.py` (`market-radar`) | Compartilha a mesma lista de concorrentes e as regras de fonte lida; o agente do Radar passa a ser a versão contínua dele |
| Planos da marca | `cadu_planner_plans` | Canais e praças dos planos recentes reforçam o critério `canais` e as praças |

O usuário vê a origem de cada instrução ("herdada da skill X") e pode desligá-la. Bases novas que ele adiciona ao agente (sites, listas, documentos) ficam só no agente e não alteram a marca.

## Recursos que mais valem para planejadores

1. **Janela com prazo**: mostra a contagem regressiva e põe as oportunidades num calendário ("o que abre e fecha este mês").
2. **Oportunidade → plano novo ou existente**: com o briefing, as praças e os canais do catálogo já preenchidos.
3. **Calendário de datas por setor**, cruzado com as praças da marca.
4. **Movimento de concorrentes**: o que mudou no site e o que saiu na imprensa, por concorrente.
5. **Resumo semanal da marca**, compartilhável. Sem preço, como todo o Planner.
6. **"Por que esta nota"** e veredito do verificador sempre visíveis, para o planejador conseguir defender a oportunidade para o cliente.

## Ordem, tamanho e dependências

| Fase | Entrega | Depende de | Tamanho |
|---|---|---|---|
| 0 | Validação real + lease + trava por marca + calibrar reserva | Aval para gastar ~45 mil tokens | P |
| 1 | Wizard, `params`, histórico, ações no cartão, canais do catálogo | 0 | M |
| 2 | Perplexity na imprensa e na checagem, `cadu_radar_sources` com níveis A/B/C, selo de confiança, portais regionais do Atlas, calendário, impressão digital | 1 | G |
| 3 | Alertas: tabela, timer, modo econômico, créditos, avisos, link "Alertas" | 2 (dedupe é obrigatório) | G |
| 4 | Agentes: preferências, aprendizado, herança de skills/plugin, bases extras | 3 validado em uso | G |

Migrações novas devem ser testadas no Postgres local antes, conforme `migrations/ORDER.txt`. O `.env` local aponta para o banco remoto: **nunca rodar migração nele sem pedir**.

## Lab do Radar: medir antes de mudar (2026-10-06)

Regra da casa: nada muda no pipeline de produção sem ganho medido no Lab.

| Peça | Onde |
|---|---|
| Prompts v1.0 (os 3 do R1 + imprensa, buscas em alta, checagem de realidade, revisor) | `aicentralv2/cadu_radar/prompts.py` |
| Base de fontes v1 (níveis A/B/C, regra de governo, selo de confiança) | `aicentralv2/cadu_radar/sources.py`, `data/sources_v1.json` |
| Fluxos, medição e relatório | `aicentralv2/cadu_radar/lab.py` |
| Linha de comando e cenários (Cemig, Nike, Bomfim) | `scripts/radar_lab.py`, `scripts/radar_lab_scenarios.json` |

### Fluxos

| Fluxo | Descoberta | Leitura | Juiz | Checagem |
|---|---|---|---|---|
| **F1 Perplexity + imprensa** | `sonar-pro` aberto ‖ `sonar` só na imprensa curada ‖ `sonar` buscas em alta | Firecrawl, com o leitor Python como reserva | `openai/gpt-5.4-mini` (OpenRouter, igual ao R1) | `sonar` busca fora do pacote |
| **F2 OpenAI nativo** | `openai/gpt-5-mini` com busca nativa (plugin `web`, `engine: native`) aberto ‖ imprensa | — (a OpenAI lê) | `gpt-5-mini` na OpenAI direta | `gpt-5-mini` com busca nativa |
| **F3 Evidência primeiro** | Google Notícias RSS (grátis) ‖ Firecrawl só nos domínios curados | Firecrawl + leitor Python | `google/gemini-2.5-flash` | `deepseek/deepseek-v3.2` relê o pacote |
| **Revisor final** | `anthropic/claude-haiku-4.5` via OpenRouter, com nota cega (A/B/C embaralhados) de 1 a 5 em veracidade, recência, aderência, ação e novidade, e escolha do vencedor |

Os modelos são trocados por linha de comando (`--model F3.judge=...`).

**Tudo passa pelo roteador global de créditos:**

- `CaduAIConnector` para os modelos;
- `web_search.search` e `web_search.read` para o Firecrawl;
- débito com `app='Cadu Radar'` e `stage='radar-lab:<fluxo>:<etapa>'`.

As tabelas do Radar não são tocadas. `--dry-run` simula sem chamar provedor e sem debitar nada.

**O que o relatório compara**, por fluxo:

- quantas oportunidades saíram;
- a nota do revisor;
- a porcentagem de fontes A/B;
- a porcentagem de URLs que abrem (o teste é real);
- a porcentagem de fontes na janela;
- o selo de confiança;
- tokens simulados contra debitados;
- US$ do provedor;
- tempo.

O relatório traz também uma tabela por chamada, com rota e regime de cobrança.

### Achado do dry-run: dois regimes de cobrança

O roteador cobra de dois jeitos:

- **OpenRouter:** pelo custo em USD informado pelo provedor.
- **OpenAI direta:** que não informa USD, cobra **1 token Cadu por token do modelo**, seja qual for o preço do modelo.

No dry-run, o mesmo juiz `gpt-5-mini` sai por cerca de 1,2 mil tokens Cadu pelo OpenRouter e 6,7 mil pela OpenAI direta (cerca de 5,5×).

### Rodada real 1: Cemig (2026-10-06, cliente 174)

Cenário: conta de luz, bandeira tarifária, calor e consumo consciente. Praças: MG e BH. Janela de 30 dias.

| Fluxo | Oport. | Revisor (1–5) | Fontes A/B | URLs abrem | Selo alta/média/baixa | Tokens debitados | US$ provedor | Tempo |
|---|---|---|---|---|---|---|---|---|
| **F1 Perplexity + imprensa** | 5 | **4,56** | 67% | 87% | 5/0/0 | **417** | 0,067 | 75 s |
| F2 OpenAI nativo | 4 | 2,60 | 50% | 50% | 3/0/1 | 6.109 | 0,070 | 51 s |
| F3 Evidência primeiro | 3 | 2,67 | 27% | 100% | 0/3/0 | 100 | 0,016 | 48 s |

O revisor escolheu o F1. As 5 oportunidades foram confirmadas pela checagem de realidade, com G1, ANEEL, InfoMoney e o site da Cemig como fonte, e todas são acionáveis na semana.

O F2 trouxe URLs do site da Cemig que não abrem, ou seja, links inventados. Também teve a checagem sem resposta legível e, pela regra de tokens 1:1 da OpenAI direta, custou cerca de 15 vezes mais.

O F3 é barato e rápido, mas só tem manchetes de agregadores e portais pequenos (nível C). Isso não sustenta nota alta.

**Bugs corrigidos depois da rodada:**

- o `gov.br` raiz era classificado como C;
- o selo de confiança considerava links quebrados.

**Decisão: o F1 é o fluxo do Radar.** Ele vira a versão 1.5 do pipeline, com três ajustes:

1. O RSS do Google Notícias, que veio do F3 e é gratuito, entra como fonte extra de imprensa regional. Ele só abre pistas: o juiz ainda exige a fonte A/B.
2. O juiz continua `openai/gpt-5.4-mini` via OpenRouter, cobrado pelo custo.
3. A checagem de realidade com `sonar` passa a ser obrigatória.

Antes de mexer no pipeline de produção, falta rodar os cenários Nike e Bomfim só com o F1. Cada rodada custa cerca de 400 tokens.

### Lab ampliado: 7 fluxos com busca online e revisão em loop (2026-10-06)

**Fluxos.** Cada um tem um tipo: `perplexity`, `web` (o próprio modelo busca na web pelo plugin `web` nativo do OpenRouter) ou `evidence`.

| Fluxo | Tipo | Descoberta | Juiz | Checagem |
|---|---|---|---|---|
| F1 | perplexity | `sonar-pro` + `sonar` (imprensa, buscas em alta) | `gpt-5.4-mini` | `sonar` |
| F2 | web | `gpt-5-mini` com busca da OpenAI | `gpt-5-mini` (OpenAI direta, regime de tokens) | `gpt-5-mini` com busca |
| F3 | evidence | Google Notícias RSS + Firecrawl (na web aberta, se a imprensa curada voltar vazia) | `gemini-2.5-flash` | `deepseek-v3.2` relê o pacote |
| F4 | web | `gemini-3-flash-preview` com busca do Google | o mesmo | o mesmo, com busca |
| F5 | web | `grok-4.3` com busca na web e no X | o mesmo | o mesmo, com busca |
| F6 | web | `claude-sonnet-5` com busca da Anthropic | o mesmo | o mesmo, com busca |
| F7 | perplexity + RSS | igual ao F1, mais as pistas do Google Notícias | `claude-sonnet-5` | `sonar` |

**Loop 1: revisão das oportunidades.** O revisor Haiku dá notas cegas a todos os fluxos.

- O fluxo abaixo da meta (padrão 4,2) reescreve a própria lista com o prompt `revise`.
- A reescrita usa o mesmo pacote de evidências e as notas e comentários do revisor por oportunidade.
- Depois da reescrita, a lista passa de novo pela checagem e pela nota cega.
- São até N voltas (padrão 2), e fica a melhor versão de cada fluxo.
- A cada passada, os fluxos que não revisaram também recebem nota de novo. A variação deles mede o **ruído do revisor**, que entra no relatório.

**Loop 2: revisão dos prompts.**

- O **médico de prompts** (`claude-sonnet-5`) lê o diagnóstico da melhor versão. O diagnóstico traz:
  - as piores oportunidades, com os comentários do revisor;
  - fontes C, links quebrados, oportunidades sem fonte e oportunidades não verificadas, por fluxo.
- Com isso, ele propõe até 3 mudanças nos prompts editáveis: `judge`, `revise`, `reality_check` e `verify`.
- `prompts.apply_changes` recusa a mudança que:
  - altera os campos `{…}`;
  - quebra as chaves dobradas do JSON;
  - cresce mais de 60%.
- A versão candidata (v1.1, v1.2…) roda sobre as **mesmas evidências**, porque a descoberta não é reexecutada. Assim, a comparação mede só o prompt.
- A candidata só vira a melhor versão se a média dos fluxos subir. O resultado sai em `prompts_best.json`.

**Comando:**

```
.venv/bin/python scripts/radar_lab.py --client-id 174 --user-id 2 --scenario cemig --flows all --revise-rounds 2 --prompt-loops 1
```

Dry-run de uma versão com os 7 fluxos: cerca de 31 mil tokens Cadu, ou US$ 0,88. Desses, 25,7 mil são do F2, por causa da cobrança por token da OpenAI direta.

Testes: `tests/test_cadu_radar_lab.py` cobre:

- o loop para ao bater a meta;
- o loop guarda a melhor versão;
- uma revisão que piora a nota é descartada;
- as regras do médico de prompts;
- o JSON mode só para quem aceita.

### Rodada ampliada: Cemig, 7 fluxos, 2 voltas de revisão, 1 volta de prompt (2026-10-06)

**Custo e tempo:** 49,7 mil tokens Cadu (US$ 2,45) em 14 minutos.

A primeira tentativa falhou e foi corrigida:

- o juiz parou no limite de 3.200 tokens, então F2, F6 e F7 ficaram sem nenhuma oportunidade;
- a busca nativa da Anthropic gastou US$ 1,25 numa chamada só;
- o médico de prompts não devolveu JSON.

| Fluxo | Boas / total | Média do revisor | Fontes A/B | Tokens debitados | US$ provedor | Leitura |
|---|---|---|---|---|---|---|
| **F1 Perplexity + imprensa** | **3/4** | 4,45 | 83% | **509** | 0,08 | Melhor custo-benefício de novo |
| F2 OpenAI nativo | 3/3 | 4,27 | 100% | 35.938 | 0,25 | Qualidade boa, mas o regime de tokens 1:1 o torna 70 vezes mais caro em créditos que o F1 |
| F5 Grok + web e X | 1/1 | 4,40 | 50% | 1.702 | 0,27 | Bom, mas entrega pouco |
| F7 Híbrido, juiz Sonnet | 1/1 | 4,60 | 100% | 3.662 | 0,59 | O Sonnet corta demais e sai caro |
| F3 Evidência primeiro | 0/2 | 4,60 | 38% | 265 | 0,04 | Média alta, mas só com fonte C (selo baixa) |
| F4 Gemini + Google | 0/3 | 2,47 | 57% | 3.748 | 0,60 | Datas de 2024 e links quebrados |
| F6 Claude + busca | 0/3 | 1,60 | 0% | 2.673 | 0,43 | Descartado |

"Boa" quer dizer nota do revisor ≥ 4 e selo de confiança diferente de "baixa".

**O que a rodada ensinou:**

1. **O loop de revisão tinha um viés, já corrigido.** A média subia quando o fluxo cortava oportunidades (o F7 e o F5 terminaram com 1 item). O objetivo agora é **pontos**: a soma das notas das oportunidades boas. Cortar um item bom perde pontos. A revisão só para com pelo menos 3 boas e a média na meta. Os testes cobrem os dois casos.
2. **O ruído do revisor fica entre 0,21 e 0,29 ponto** na média de um fluxo que não mudou. Diferença menor que isso não é ganho.
3. **Prompts v1.1.** O médico aceitou uma mudança no `revise` (trocar o que está fora da janela ou é sustentado só por fonte C) e teve duas recusadas por crescerem demais. A média subiu de 3,69 para 3,77, uma diferença de 0,08, **dentro do ruído**. A v1.1 não é promovida.
4. **Decisão mantida: o F1 é a base do Radar.** O F2 vira segunda opinião só depois que a cobrança passar a ser pelo custo em US$. O F5 (Grok) é candidato a fonte de conversa social (X) dentro do F1. F3, F4 e F6 saem.

**Próxima rodada sugerida:**

- fluxos: F1, F2 e F5;
- 3 cenários: Cemig, Nike e Bomfim;
- 2 voltas de revisão e 2 de prompt;
- objetivo: medir a v1.1 e a v1.2 com o critério de pontos;
- custo estimado: 15 a 20 mil tokens por cenário, quase tudo do F2.

### Rodada final e fluxo padrão (2026-10-06)

Os fluxos F1, F2 e F5 rodaram nos cenários Cemig, Nike e Bomfim, com 2 voltas de revisão e 2 de prompt.

- **Custo e tempo:** 51 mil tokens Cadu e US$ 1,44, cerca de 3 minutos por cenário, rodando em paralelo.
- **Comparação justa:** a tabela usa a primeira passada do revisor, a única em que os três fluxos são julgados juntos e nas mesmas condições.

| Fluxo | Pontos (3 cenários) | Boas / total | Tokens Cadu por busca | US$ por busca | Vitórias no revisor |
|---|---|---|---|---|---|
| **F1 Perplexity + imprensa** | **39,8** | **9/12** | **551** | 0,088 | 2 de 3 |
| F2 OpenAI nativo | 29,8 | 7/12 | 14.673 | 0,109 | 1 de 3 |
| F5 Grok + web e X | 4,2 | 1/8 | 1.516 | 0,243 | 0 de 3 |

Somando com as duas rodadas anteriores no cenário Cemig, o F1 venceu ou empatou em todas as comparações. Ele também tem o menor custo por oportunidade boa.

**Fluxo padrão do Radar: F1.**

1. **Descoberta em paralelo, toda com Perplexity via OpenRouter:**
   - `sonar-pro` na busca aberta;
   - `sonar` só na imprensa curada (`sources.press_domains`, com os regionais das praças);
   - `sonar` nas buscas em alta.
2. **Leitura das páginas citadas** pelo Firecrawl, com o leitor Python gratuito como reserva.
3. **Juiz `openai/gpt-5.4-mini`** via OpenRouter, que é cobrado pelo custo. Prompt `judge` v1.0.
4. **Checagem de realidade obrigatória com `sonar`**, buscando fora do pacote. Prompt `reality_check` v1.0.
5. **Nível das fontes e selo de confiança** (`sources.py`). Selo baixo não vira alerta.

**O que não vai para produção agora:**

- **Loop de revisão das oportunidades.** O revisor Haiku oscila demais entre passadas: a mesma lista do F1 no Cemig foi de 18,0 para 12,8 pontos sem mudar nada, e o ruído chegou a 1,07 ponto no Bomfim. Com tanta variação, o loop ora melhora (F2 Nike: de 8,0 para 13,4), ora destrói (F1 Nike: de 12,8 para 0, e a guarda manteve a original). Volta a ser avaliado com dois revisores ou com média de passadas.
- **Loop de prompts.** O médico de prompts (`gpt-5.4`) não rodou porque o **saldo do OpenRouter acabou** (US$ 0,12 de US$ 465). Os prompts v1.0 seguem como padrão.

**Para levar o F1 ao pipeline de produção** (`cadu_radar/pipeline.py`):

- trocar o `discover` pelas três buscas do F1;
- usar os prompts de `prompts.py`;
- incluir a checagem com `sonar` e o selo de `sources.py`;
- **recalcular a reserva de créditos pelo custo**.

Hoje a reserva é fixa em 15.207 tokens. Para o cliente 174, o débito real do F1 é de cerca de 550 tokens.

### Primeiro uso real: perfil da marca, e-mail e animação (2026-10-06)

Ajustes pedidos depois de o usuário abrir o wizard em produção.

- **Escolher a marca avança sozinho** para o passo do conceito. O projeto e a situação do perfil passaram para o passo 2.
- **Completar o perfil da marca é um fluxo separado.** Quando faltam concorrentes, posicionamento ou público, o passo 2 mostra o aviso com "Completar perfil" (ou "Atualizar perfil", se estiver completo). O botão abre um fluxo próprio:
  1. O Radar pesquisa na web (Perplexity, uns 40 tokens) e **propõe**. Nada é gravado.
  2. O usuário revisa: concorrentes novos já vêm marcados, os que a marca já tem aparecem bloqueados, e o texto proposto é editável.
  3. Ao salvar, a proposta é **somada** ao perfil: a lista de concorrentes não repete nem reescreve o que existe, e texto já preenchido só é trocado se o usuário marcar "Trocar o texto atual".
  4. Cada atualização fica registrada no próprio perfil (`radar_enrichment.history`, até 10 entradas, e `field_provenance`), com as fontes usadas.
  - Quem grava é o gravador oficial do perfil, que mescla só as chaves enviadas e nunca mexe em `design_system_ads`. A marca é validada contra o cliente antes.
- **Ao clicar em buscar, a animação entra na hora**, sem esperar a resposta do servidor. Se falhar, o wizard volta com o rascunho e o motivo.
- **E-mail ao terminar a busca** (decisão do usuário: melhor ao terminar do que ao começar). O e-mail traz:
  - os **ângulos**, com o gancho, o "por que agora" e os formatos e canais;
  - o **buzz** que os sustenta, com veículo, data e link;
  - o **tempo economizado**, com a conta aberta: 30 min pesquisando o que está em alta, 5 min por fonte conferida e 15 min por ângulo escrito. Para 4 fontes e 4 ângulos dá cerca de 2 h. É uma estimativa com tempos de referência do trabalho manual, no mesmo molde do tempo poupado do plano;
  - o custo em tokens da busca e o link para ver os ângulos e criar o planejamento.
  - Busca **sem ângulos** recebe um e-mail honesto, sem tempo poupado, sugerindo uma janela maior ou um conceito mais conhecido.
  - O **radar ativo** (agendado) só manda e-mail quando encontra ângulos; sem novidade fica quieto.
  - O e-mail sai depois de a busca estar salva e concluída, e uma falha de envio nunca derruba a busca.
  - O tempo poupado também aparece, discreto, no cabeçalho dos ângulos na tela.

**O 403 ao buscar em produção não era do Radar.** O Planner bloqueia toda gravação sem `CADU_FAMILY_WRITES_ENABLED=1` (`routes.py`, trava `protect`), e a trava foi apontada na auditoria `docs/auditoria-planner-reports.md`. Provas em produção:

- `POST /familia/api/context` responde 200;
- `radar/runs` e `radar/watches` respondem 403;
- uma escrita contra um plano que não existe também responde 403.

A flag precisa ser ligada no servidor. Havia ainda um segundo problema: o tratador global de 403 devolve uma página HTML e escondia o motivo. Agora as rotas da API devolvem o motivo em JSON, e a tela mostra a mensagem real.

### Simplificação: buzz e ângulos (2026-10-06, depois do primeiro uso real)

O primeiro uso real mostrou que o Radar estava complicado demais para o que ele precisa fazer. O produto é simples: **ver o que está em buzz agora e os ângulos para falar de um conceito.** Esta seção **substitui** a descrição do pipeline e do wizard em "Radar v2 entregue em duas páginas", logo abaixo. As partes sobre as duas páginas, os radares ativos, o agendador e a migração continuam valendo.

**O que saiu:** as 3 buscas em paralelo, a leitura de páginas pelo Firecrawl, as notas editorial e paga, o quadrante, a conferência extra com o Perplexity e o selo de confiança. A **base de fontes não guia mais a busca**: o Perplexity procura na web aberta, e a base só diz, depois, se a fonte achada é forte (A), regional (B) ou a conferir (C).

**Pipeline v1.5** (`prompts.V1_5`, 4 etapas, 2 chamadas de IA):

1. **Buzz:** uma busca do Perplexity `sonar-pro` pede os assuntos em alta sobre o conceito, com data, veículo e link.
2. **Conferir:** só fica o que tem data dentro da janela (7, 30 ou 60 dias) e link que abre. Sem data, sem link, antigo, do futuro ou repetido sai.
3. **Ângulos:** um modelo (`gpt-5.4-mini`) transforma o buzz em 3 a 5 ângulos. Cada um tem título, gancho, por que agora, formatos e canais, janela e o buzz que o sustenta. Ângulo que não se apoia em nenhum buzz da lista é descartado.
4. **Salvar:** o buzz vira sinal e o ângulo vira oportunidade, e o ângulo abre um planejamento com o gancho e o buzz no briefing.

**Data de hoje.** O modelo trazia material de anos atrás porque respondia pelo que conhecia. Agora a data de hoje e o início da janela entram no prompt, e o código **descarta** qualquer item sem data ou fora da janela, em vez de confiar na resposta do modelo.

**Wizard em 4 passos:** Marca → Conceito (com seis ideias para começar) → Onde e quando → Revisão. Saíram as lentes, o objetivo e a escolha de fontes. A cena `radar-4-fontes` ficou sem uso.

**Teste real em produção** (Cemig, "consumo consciente de energia no fim do ano", MG, 30 dias):

| | Antes (F1 de 5 etapas) | Agora |
|---|---|---|
| Tempo | 41 s | 20 s |
| Tokens da conta 174 | 369 | 125 a 163 |
| Resultado | 4 oportunidades com notas | 3 a 5 itens de buzz e 4 ângulos, todos de setembro e outubro de 2026 |

**Custo da reserva:** US$ 0,10 por busca, o que dá 624 tokens para a conta 174.

**Ainda aberto:** o número de itens de buzz varia entre buscas (3 e 5 nas duas rodadas), porque o Perplexity às vezes não traz data. Se isso incomodar, o próximo passo é pedir uma segunda busca quando vier menos de 3.

### Radar v2 entregue em duas páginas (2026-10-06)

O Radar passou a ter duas páginas, para separar quem cria de quem acompanha, poupar recursos e facilitar a manutenção:

| Página | O que faz |
|---|---|
| **Novo radar** (`/radar`) | Wizard de 5 passos, no mesmo padrão do Planejar. Depois de enviar, a mesma URL (`?run=<id>`) mostra a busca ao vivo e os resultados. |
| **Meus radares** (`/radares`) | Radares ativos (pausar, retomar, apagar) e as consultas realizadas, com resultado e custo. Só lê e gerencia. |

**Wizard.** Cinco passos, todos opcionais, com as cenas novas à esquerda e o rascunho salvo na sessão:

1. **Marca:** escolher a marca e o projeto. O Radar mostra o que já sabe do perfil e o que falta (concorrentes, público, posicionamento).
2. **Tema:** campo de tema com seis ideias de busca prontas, até três lentes e o objetivo (conteúdo, mídia ou os dois).
3. **Onde e quando:** praça e janela de 7, 30 ou 60 dias.
4. **Fontes:** imprensa conhecida e buscas em alta podem ser desligadas. A busca aberta e a conferência na web ficam sempre ligadas.
5. **Revisão:** resumo, custo reservado e a opção "Me avise quando houver novidade", com frequência de 1, 2 ou 3 vezes por dia.

**Pipeline de produção = F1.**

- Três buscas do Perplexity em paralelo, uma delas só nos veículos da base curada, com os regionais da praça.
- Leitura das páginas pelo Firecrawl, com o leitor Python como reserva.
- Juiz `gpt-5.4-mini` e conferência na web com o `sonar`.
- Selo de confiança calculado pela base de fontes, com o teste real de cada link.
- Tudo via OpenRouter, cobrado pelo custo em US$. A reserva também é em US$ (0,15), e não mais 15.207 tokens fixos.
- O cartão da oportunidade mostra o selo e as fontes, com o nível de cada uma e o aviso "link não abre".

**Radares ativos.**

- A tabela `cadu_radar_watches` guarda os radares.
- O comando `flask cadu_family radar-due` pega, a cada 5 minutos, os radares no horário, com `FOR UPDATE SKIP LOCKED`, e roda cada um na própria linha de comando, fora do servidor web.
- Os horários são 8h (1 vez), 8h e 17h (2 vezes) e 8h, 13h e 18h (3 vezes), no fuso de Brasília.
- Cada rodada é cobrada do dono do radar.
- Sem saldo, o radar vai para "Sem créditos" e para de tentar até alguém retomá-lo.
- O limite é de 10 radares por cliente.

**Outras correções do pipeline.**

- Um run cuja execução morreu (deploy ou reinício) perde o lease e vira falha em 5 minutos, em vez de travar a marca.
- A trava de busca simultânea passou a ser por marca, e não por cliente.

**Para ligar em produção.** Nada disso está em produção ainda:

1. Aplicar `migrations/add_cadu_radar_v2.sql`. Já está no `ORDER.txt`. Foi testada num Postgres local, aplicada duas vezes sem erro, e as consultas reais foram exercitadas ali. Não foi rodada no banco remoto.
2. Fazer o deploy. O `deploy.sh` instala o timer `cadu-radar-watch`, que não faz nada sem `CADU_RADAR_ENABLED` ou sem a migração.
3. Recarregar o saldo do OpenRouter. Estava em US$ 0,12.

**O que ainda não existe, e a tela não promete:**

- avisar só do que é **novo**: hoje cada rodada do radar é uma busca completa, sem a impressão digital dos sinais da fase 2;
- aviso no sino ou por e-mail, e o limite de nota para alertar (`min_score` já está na tabela);
- o agente que aprende o que priorizar (fase 4).

### Ajuda ao usuário na tela do Radar (2026-10-06)

- **Ideias de busca:**
  - O que é: seis chips que preenchem um pedido completo já com a marca escolhida.
  - Lentes: Datas e sazonalidade, Concorrentes, Tendências e buscas em alta, Regulação e governo, Reputação e imprensa, Notícias da praça.
- **"Como pedir uma boa busca":**
  - O que é: um quadro com 5 regras curtas.
  - Regras: tema + recorte, escolher a marca, dizer a praça, uma pergunta por busca, janela de 30 a 60 dias.
  - Fica aberto até a primeira busca.
- **Aviso sem marca:** quando não há marca nem projeto escolhido, a tela pede para escolher.
- **Resultado vazio:** passa a sugerir como recortar melhor, com a ilustração `radar-empty`.

**Decisão proposta:** um regime só.

- Debitar sempre pelo **custo real em USD**. Quando o provedor não informa o valor, ele é calculado pela tabela de preços.
- Converter com o preço comercial do token.
- Deixar a **margem num lugar só**: no preço de venda do crédito ou num multiplicador global.

É o mesmo princípio já adotado para imagem no Studio. A mudança é no `cadu_tool_billing.charge_from_provider` e vale para todos os produtos, por isso fica atrás de chave e com teste.

## Perguntas em aberto

1. **"Tag global" de créditos.** O plano assume que se refere à etiqueta de cobrança `app='Cadu Radar'` no livro de créditos. Se for outra coisa (por exemplo, a SuperTag), o desenho da cobrança muda.
2. **Quem paga o alerta:** o usuário que criou ou a conta do cliente? O plano assume o dono.
3. **E-mail no resumo diário:** já na fase 3 ou só no app primeiro?
4. **Curadoria da lista A.** Quem da equipe revisa os cerca de 80 domínios iniciais e os candidatos do Atlas? Eu preparo a primeira lista para revisão.
5. **Custo maior por busca.** As duas chamadas novas do Perplexity (imprensa e checagem) devem somar cerca de 3 a 5 mil tokens por busca. O número real sai da fase 0.
6. **Teto mensal padrão por alerta**, por exemplo 500 mil tokens. Ele protege contra surpresas na fatura.
