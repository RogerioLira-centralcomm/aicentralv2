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
