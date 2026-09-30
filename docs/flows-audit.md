# Auditoria do editor de Fluxos — Reports

**Fase 0 · 29/09/2026.** Base auditada: `codex/reports-flow-editor-ux` (`7d32fd6e`). Esta fase não altera a interface, a API ou o banco. A branch `main` ainda não contém esta versão do editor; o PR desta auditoria deve ter `codex/reports-flow-editor-ux` como base.

## Decisão

Adotar um canvas baseado em `@xyflow/react` na refatoração, com adaptador explícito para o formato salvo hoje. O editor atual implementa posicionamento, zoom, arraste e conexões manualmente em `frontend/reports-v1/main.jsx`; não há React Flow, `elkjs`, `dagre` ou Zustand nas dependências. O React Flow atende à necessidade de nós compactos, handles, arestas e navegação do mapa, mas a troca de biblioteca **não** pode mudar diretamente o JSON consumido pelo coletor. Manter `draft_config` e `config` no registro de fluxo, com versão publicada imutável. Não há necessidade identificada de nova tabela para o grafo.

O JSON v2 proposto no plano é uma **meta**, não um contrato aceito pelo backend atual. Sua adoção exige leitor compatível com v1, normalizador v2, tradução para as etapas publicadas e migração verificável. A rota proposta `/connect/app/flows/:id` também não existe: a rota atual é `/connect/app/flow?flow_id=…&flow_view=edit`. A nova rota deve preservar links existentes por redirecionamento ou alias.

## Estado atual, com evidência no código

| Área | Implementação atual | Consequência para a refatoração |
|---|---|---|
| Tela | `FlowDesktop` em `frontend/reports-v1/main.jsx`, com modos `create`, `edit` e `monitor` controlados por `flow_view` na query | Separar lista/editor e manter tradução dos links antigos |
| Canvas | `div` absoluto por nó, `<svg>` com paths calculados por `flowEdgePath`, escala CSS, rolagem e drag próprios | Substituir o canvas como unidade; evitar adaptar visualmente os cards |
| Modo amplo | `focusMode` opcional aplica `reports-flow-focus-active` no `body`; CSS oculta sidebar e header | Levar esse comportamento para o layout da rota de edição, com saída acessível |
| Nós | `id`, `type`, `title`, `x`, `y`, `path`, `event_name`, `source` e metadados opcionais | Adaptador `type/title/x/y` → `kind/data.label/position`, preservando identificadores e metadados |
| Arestas | `id`, `from`, `to`, `label`, `kind` e portas opcionais | Adaptador `from/to` → `source/target`; arestas existentes não podem ser inferidas apenas da ordem visual |
| Persistência | `cadu_reports_flow_registry.draft_config` e `config` JSONB; `draft_revision` e `published_revision`; snapshots em `cadu_reports_flow_versions` | Rascunho e publicação têm papéis distintos; v2 precisa ser lido pelas consultas, publicação e coleta |
| Escrita | `PATCH /connect/api/v1/reports/flow/flows/<id>` com `expected_revision`; conflito retorna 409 | Reutilizar a revisão otimista; não criar uma segunda API de autosave |
| Publicação | `POST .../publish` copia rascunho para `config`, cria versão e sincroniza `cadu_reports_flow_steps` | Ajustar `sync_published_steps` antes de publicar um v2; ele lê `type`, `title`, `path`, `host`, `isEntry` |
| Limites | `_normalize_flow_config`: até **100 nós**, **300 arestas**, **256 KB**, posições de 0 a 10.000 | A meta do plano de 200 nós requer decisão de limites e desempenho do servidor, não apenas do canvas |
| Coleta | `config` publicado e versões são usados no matching e nas sessões; Super Tag grava eventos por site/sessão | Mapear eventos reais em nós v2 sem reinterpretar histórico publicado |

Arquivos centrais: `aicentralv2/cadu_connect/reports_flow.py`, `reports_flow_versions.py`, `reports_flow_live.py`, `reports_flow_monitor.py`, `frontend/reports-v1/main.jsx`, `frontend/reports-v1/flow-workspace.css`. Esquema: `migrations/add_reports_funnel_management_v1.sql`, `add_reports_flow_versions_v1.sql`, `add_reports_flow_site_mapping_v1.sql`, `add_reports_supertag_v1.sql`.

## Inventário do banco

Consulta **somente leitura**, usando a conexão configurada localmente com `default_transaction_read_only=on` em 29/09/2026. Não foram extraídos nomes, URLs, IDs de cliente ou conteúdo dos nós.

| Registro | Estado | Revisão de rascunho | Nós | Arestas |
|---|---|---:|---:|---:|
| Fluxo 1 | Rascunho | 1 | 0 | 0 |
| Fluxo 2 | Rascunho | 7 | 4 | 0 |

Tipos presentes nos rascunhos: `page` (1), `form` (1), `event` (1), `conversion` (1). Ambos os documentos têm `nodes` e `edges`, sem `schema_version`. Não há versões publicadas (`cadu_reports_flow_versions`: 0), nem arestas salvas. Portanto, os quatro blocos da captura estão **realmente desconectados** neste banco: a UI não deve mostrar setas como se a sequência já tivesse sido salva. Os campos `config` publicados não têm dados de nós adicionais neste inventário.

Este retrato vale para o banco acessado nesta auditoria. Antes de migrar ou publicar em outro ambiente, repetir o inventário nessa base; não extrapolar que produção tenha só dois fluxos.

## Contratos existentes e diferenças frente ao plano

- `GET /connect/api/v1/reports/flow` já devolve coleção, fluxo selecionado, atividade e métricas. `POST /flow/flows` cria; `PATCH /flow/flows/<id>` salva; `POST /publish`, `GET /versions`, `POST /versions/<revision>/restore`, `POST /unpublish` e `POST /test` já cobrem parte da proposta. Não existe, hoje, `GET /flows/<id>` nem rota REST de `/journey`, `/duplicate` ou `/templates`.
- Rotas de descoberta (`/discover`, `/discoveries`, `/discovery-flows`) e seus metadados ligam páginas do site a etapas. A migração deve preservar `discoveryPageId`, `pageGroup`, `suggestedRole`, `stepId`, `campaign_id`, `host` e `isEntry`; o exemplo v2 do plano não os contempla.
- O backend aceita tipos `source`, `page`, `form`, `event`, `condition`, `delay`, `segment`, `conversion`, `webhook`, `whatsapp`, `error`, mas só mede/publica etapas `page`, `form`, `event`, `conversion`, `whatsapp`, `error`. A biblioteca visual mais ampla não cria capacidade de rastreio automaticamente.
- O normalizador v1 exige `path` começando por `/` para todos os tipos medidos. `event` e `conversion` podem exigir `event_name` válido. Um bloco v2 sem essas informações precisa ser impedido de publicar ou traduzido para um passo v1 válido.
- O normalizador preserva campos desconhecidos no objeto raiz, mas reconstrói os nós e arestas. Salvar `nodes` diretamente no formato v2 faria a validação falhar por ausência de `type/from/to`. Leitura compatível e escrita v2 precisam entrar juntas, com versão explícita; nunca converter apenas o frontend.
- `sync_published_steps` e o matching de sessões/eventos leem o v1. Uma migração preguiçosa na leitura deve manter snapshots históricos imutáveis e produzir uma projeção v1 para a coleta até que todos os consumidores entendam v2.
- O estado de autosave já usa debounce de **900 ms** e revisão otimista. O plano propõe 1,5 s: é uma escolha de UX, não um contrato novo. A UI atual preserva alterações locais em conflito, mas não oferece a resolução visual proposta.
- O índice de eventos Super Tag existente cobre `(site_id, session_id, occurred_at)` e `(site_id, page_path, occurred_at)`; **não** há índice específico `(site_id, event_name, occurred_at)`. Antes do modo Jornada, examinar consulta e cardinalidade reais; criar índice apenas com migração e medida de necessidade.

## Revisão TypeSafe: sugestões e evidência

O plano visual omite uma capacidade que já existe. `reports_flow.py` classifica páginas descobertas por regras de URL, título e formulário; `reports_typesafe.py` oferece uma **sugestão opcional** do papel da página (`entry`, `intermediate`, `form`, `conversion`, `error`, `none`) via uma pergunta `Choice`. `reports_flow_suggestions.py` guarda resultado, versão da pergunta, revisão do rascunho e hash da evidência, limita chamadas por cliente e revalida tudo quando o usuário aplica a sugestão. A escolha da página e a escrita do fluxo continuam no código e exigem ação do usuário.

Há duas medidas diferentes chamadas de “confiança”: `_classify_discovered_page` atribui números fixos como `.91` a heurísticas; o TypeSafe retorna `probabilities` e `confidence` calculada da distribuição da resposta. **Não são intercambiáveis nem prova de que uma conversão aconteceu.** A nova biblioteca/inspetor deve mostrar origem e evidência da sugestão, manter a opção “não sei” e permitir correção manual. Não usar a classificação para criar arestas, publicar ou afirmar rastreio automaticamente. Uma página sugerida como “obrigado” continua sendo uma hipótese sobre a função da página; visitas e conversões exigem eventos observados.

Para a Fase 2, preservar `discoveryPageId` e a referência à evidência ao converter nós. Uma sugestão recebida após mudança de página, evidência ou revisão deve ser descartada. Se novos blocos pedirem julgamento semântico (por exemplo, identificar função de uma página de produto), formular uma decisão fechada e estreita sobre dados observáveis; regras exatas de URL, identidade, conexão, permissões e métricas continuam determinísticas. Não acrescentar chamada TypeSafe ao pan, ao zoom, ao salvamento ou à migração do JSON. Avaliar sugestões em páginas rotuladas antes de definir limiares de automação; a `confidence` de `Choice` expressa concentração entre opções, não correção garantida.

Base desta revisão: [modelo de construção](https://docs.typesafe.ai/concepts/how-to-build-with-system-one), [Choice](https://docs.typesafe.ai/primitives/choice) e [confiança](https://docs.typesafe.ai/confidence), consultados em 29/09/2026. Ver também `docs/reviews/reports-flow-typesafe-review-2026-09-29.md` para os achados e correções anteriores.

## Migração segura proposta

1. Definir `schema_version` ausente como v1. Criar adaptador puro v1→v2 que preserve IDs, posições, caminhos, hosts, nomes de eventos, referências de descoberta e arestas **existentes**. Não inventar conexões para os quatro nós desconectados.
2. Definir `blockRegistry` com `kind` visual separado de `trackingKind`/projeção de publicação. Mapear tipos v1 conhecidos (`page`, `form`, `event`, `conversion`, `error`, `whatsapp`) e também os tipos aceitos pelo backend (`source`, `condition`, `delay`, `segment`, `webhook`). Para subtipos de página ou conversão, manter os campos originais necessários ao matching.
3. Carregar v1 sem gravar automaticamente. Na primeira edição/salvamento, persistir v2 com `expected_revision`. Se a gravação falhar ou conflitar, manter o documento local e oferecer recarga/comparação. Cópia de segurança e script de inventário com `dry-run` antes de qualquer migração em lote.
4. Antes de permitir publicação v2, atualizar validador, `sync_published_steps`, leitor de versões, matching, simulação, descoberta e monitoramento. Confirmar que a publicação projeta os mesmos passos medidos. Versões antigas continuam sendo lidas por `schema_version` ausente.
5. Fazer rollout em fases: rota de editor e canvas podem consumir v1 por adaptador na Fase 1; gravação v2 e novos nós entram somente quando a camada de compatibilidade da Fase 2 estiver pronta. Não mudar o schema SQL nesta etapa.

## Pendências para revisão antes da Fase 1

1. Confirmar se o editor v2 deve preservar **exatamente** os quatro nós sem arestas do banco atual e oferecer uma ação explícita para conectá-los. Esta é a opção recomendada para evitar criar uma jornada fictícia.
2. Confirmar a regra de publicação para blocos conceituais sem evento ou URL rastreável (`CRM`, comunicação, origem): eles podem aparecer no desenho, mas não devem ser apresentados como eventos medidos até haver integração específica.
3. Definir a base do próximo PR: esta branch de auditoria deve ser revisada/mesclada sobre `codex/reports-flow-editor-ux`; a Fase 1 deve partir dessa base, mantendo um PR por fase conforme o plano anexado.

**Critério para avançar:** revisão deste diagnóstico e das três decisões acima. O plano anexado exige essa revisão antes de alterar a UI.
