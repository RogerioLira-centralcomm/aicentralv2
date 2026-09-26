# Cadu chat plugins and MCP composition

## Product model

A plugin is a named, versioned workflow the customer can invoke in chat. The
agent may also select it automatically when the request clearly matches. A
plugin is not a second tool server: it composes authorized internal MCP tools,
context rules, and a response/artifact contract. The shared MCP registry stays
the only execution and authorization layer for internal tools.

External MCPs are connector dependencies of a plugin. They must be explicitly
configured and authorized for the client before a workflow can call them. An
empty `external_connectors` list means the plugin currently uses Cadu data or
public research only; it does not imply a third-party connection.

## Turn lifecycle

1. Route the customer's request to a product intent.
2. Select the matching plugin from that intent and the request language. Do not
   ask the customer to choose a plugin when intent is clear.
3. Resolve scope: conversation, brand, project, selected artifact/report, or an
   external connector. Ask one focused question when a private scope is missing
   or ambiguous; never search a private source by guessing. Public Insights
   queries use an allowlisted topic extracted from the request; project, client,
   brand, campaign, brief, and file details are not forwarded to public search.
4. Run the plugin's minimal MCP chain through the shared registry. Each tool
   retains its own authorization, schema, idempotency, confirmation, and audit
   behavior.
5. Return the result in chat with source and confidence distinctions. Open or
   update an artifact when the workflow calls for a durable deliverable. Never
   claim a write, generation, or external action without a completed tool result.
6. Record plugin ID/version and source-tool versions with durable outputs as
   artifact provenance is added to the artifact contract.

## Initial plugin catalog

| ID | State | Context | Current composition / known boundary |
|---|---|---|---|
| `market-intelligence` | Active (v1.1.0) | Conversation; selected brand/project may enrich synthesis | Quick, deep or configured research in a resumable worker. Firecrawl and OpenRouter are provider dependencies behind Cadu; neither is dynamically loaded as a customer MCP. |
| `market-radar` | Active (v1.2.0) | Selected brand required to research brand/competitor movements | Searches current public sources and requires read evidence tied to claims; it does not promise continuous monitoring. |
| `campaign-search` | Planned | Selected brand or project required | Searches brand context or unified project content using the smallest relevant chain; remains limited to the selected scope and does not search across projects. |
| `insights` | Active (v1.2.0) | Conversation; project or brand context is optional | Firecrawl public search + Perplexity Sonar research + GPT synthesis + separate GPT factual/editorial review. Returns the insight first, with current market metrics/news, implications for marketing/communication/media, actions, and supporting source references. |
| `planner` | Catalog connected (v0.3.0) | Conversation; project for saved plan | A plan request can gather project direction plus read-only channel, audience, format and Places references for a proposal. Chat does not yet persist edits to the canonical live plan. |
| `project-search` | In development (v0.2.0) | Selected project required for private project search; new work can start without project context | One experience over unified project-content retrieval, hybrid indexed knowledge search, source-chunk reading, resource search and artifact listings. Automatic selection may use a smaller subset; the agent should read additional source chunks only when needed and ground claims in returned evidence. Search is restricted to the selected project; no cross-project search. |
| `project-activities` | In development (v0.1.0) | Selected project required to read or plan its tasks | Lists activities and prepares task proposals from project context and resources. Persistent writes continue through existing confirmed actions. |
| `audience-map` | Active (v1.2.0) | Channel scope from the request; project/brand may enrich | Combines approved channel/audience catalogs and read public evidence. Segments without verified data remain labeled as hypotheses. |
| `investment-simulator` | Active (v1.3.0) | Investment assumptions supplied by the user or scenario request | Uses deterministic allocation calculations; outputs are illustrative and are not forecasts or quotes. |
| `media-plan-audit` | Active (v1.1.0) | Selected plan or supplied plan content | Reviews calculations, objective, channels and measurement; does not write changes to the canonical plan. |
| `campaign-tracker` | Active (v1.3.0) | Report attachment or metrics supplied in the conversation | Analyzes provided metrics; does not query Reports or live media platforms. |
| `creative-concept` / `channel-copy` | Active (v1.2.0) | Conversation; project/brand context when selected | Produces creative routes or channel-scoped copy; factual claims must remain supported by supplied brand evidence. |
| `page-review` | Active (v1.2.0) | URL or page content | Reviews readable content; extracted text alone cannot establish visual layout, interactions, speed or accessibility. |
| `meeting-copilot` | Active (v1.2.0) | Notes/transcript for summaries; request context for agendas | Meet metadata is not meeting content. Without notes/transcript it can prepare a pauta, but must not invent decisions. |
| `client-delivery` | Active (v1.2.0) | Selected project or supplied status details | Summarizes tasks and resources; completed tasks do not prove delivery or client acceptance. |
| `studio` | Planned (v0.2.0) | Conversation; brand/project/reference optional | Chat can inspect creation capabilities; paid generation/editing remains in the persisted approval flow and is not directly callable by the model. Context-free creation is generic. |
| `reports` | Early | Project plus selected/reviewed report | Imported, reviewed metrics only; live platform ingestion is not implied. The separate `campaign-tracker` workflow analyzes an attached report or metrics supplied in the conversation and does not call Reports. |

Catalog state is product maturity, not a permission level. `active`, `early`,
and `in_development` should be rendered distinctly in the storefront.

Google Workspace is implemented as a Cadu-managed connector invoked through the internal MCP registry; it is not a dynamically loaded third-party MCP server. Trello, Asana, and Slack remain planned. No arbitrary external MCP server is dynamically loaded by chat plugins in this phase. The chat displays a plugin attribution only after a matching MCP tool completes successfully.

## Planner behavior

The Planner is a living, user-owned plan, not a one-shot response. A chat
proposal may use channel, audience, format, placement, and demographic catalogs
and recommend a quick or deep planning pass. The user can edit copy, include or
remove items, and change allocations. Until canonical chat-edit tools are
implemented, the agent must not claim these edits were saved in the Planner;
it can still prepare a proposal or an explicitly requested draft artifact.

Plan proposals use catalog data as references, label estimates and do not imply
availability, quotes, or guaranteed performance. Plan changes must use expected-version concurrency, preserve untouched fields,
and create a revision record. A chat turn should summarize the changed sections
and provide an affordance to open the live plan.

## Database catalog and manifest contract

`migrations/add_cadu_chat_plugin_catalog.sql` creates the catalog tables and
seeds the first version of the Cadu workflows and planned external integrations.
`cadu_chat_plugins` stores stable identity, kind, category, logo, ordering and
visibility. `cadu_chat_plugin_versions` stores immutable version records,
maturity, description, JSONB manifest, changelog and the current-version marker.
Each plugin can keep its prior versions for audit and rollback. The storefront
and capability endpoint read the current version from these tables.

The JSONB manifest documents triggers, internal tools, context, external
connectors, known gaps, inputs, and outputs. It is descriptive metadata: the
runtime still uses its backend allowlist for executable tools, and a database
edit cannot grant a new tool permission. Keep the manifest's tool list aligned
with the effective runtime allowlist. `tool_contract_matches_manifest` in the
capability metadata exposes this comparison for review; it is a diagnostic,
not an authorization check. `provider_dependencies` documents providers used
behind a Cadu workflow; it does not assert that a provider is currently
connected or available. Firecrawl and OpenRouter are implementation
dependencies of Market Intelligence, while Google Workspace is accessed
through Cadu's internal Google connector. Write flows should extend manifests
with input/output schemas, confirmation and cost requirements, permission
references, artifact outputs, source policy and evaluation criteria. Use
semantic versioning: PATCH for fixes, MINOR for compatible workflow additions,
MAJOR for breaking input/output or behavior changes. Publish a new version
record instead of overwriting existing versions when changing a plugin
contract. The seed uses `ON CONFLICT DO NOTHING` on version rows to preserve
published definitions.

The runtime catalog exposes the manifest/runtime comparison as two lists:
tools declared but unavailable, and allowed tools not documented in the
manifest. A mismatch is an operational documentation defect; it never expands
the allowlist. `runtime_tools` is the full capability boundary, while the tool
chain selected for a turn is narrower and depends on the user's selected
project, brand, attachment, and request. Optional project/brand reads appear in
the capability boundary but must not run when that context is absent or
irrelevant.

Project search and activity management are separate workflows. Project search
is selected only for requests to find or summarize existing project knowledge;
it must not silently attach ordinary new work to the active project. The user
can create a new artifact in the conversation first, then explicitly save or
associate it with a project. Project Activities owns task-list reading and task
proposals; writes continue through the existing confirmation and action
journal. Plugins should return editable draft artifacts when a durable document
is useful and use the normal artifact revision path when editing an existing
item.

The customer may invoke a plugin by naming it in the chat, or the router may
select it from intent. While the workflow runs, show its name with the small
Cadu MCP mark; only retain the “used” attribution on the final answer when a
matching internal tool completed successfully. Explicit file requests create
an editable artifact from the referenced latest assistant response. As a
fallback for unrequested responses above roughly 520 words or 3,600 characters,
store the complete Markdown-derived document in a session artifact and leave a
short summary and open action in the chat. Saving that session artifact into a
project remains a separate user-directed step.

Skills are intentionally not a customer-facing dependency in this phase.

## Model, reviewer, and retrieval boundaries

Model/provider policy is currently explicit for the composite Insights and
Market Intelligence workflows; the smaller daily workflows use the shared
chat model with deterministic MCP helpers where available. Insights performs
separate research, synthesis, and review stages. Market Intelligence runs a
resumable multi-stage worker. Other plugins do not currently have a general
independent reviewer contract. Keep deterministic calculations in tools and
reserve an additional model pass for claims or decisions whose evidence/risk
justifies its latency and cost.

Project-source retrieval currently combines lexical and dense top-12 candidate
lists with reciprocal-rank fusion, then returns a bounded number of excerpts.
It does not yet run a learned cross-encoder/model reranker. Before adding one,
measure candidate recall and top-k relevance on an approved, project-scoped
evaluation set: reranking can reorder retrieved passages but cannot recover a
relevant passage missing from both initial lists. Record retrieval mode,
pipeline version, source and chunk IDs, and whether indexing was complete. A
lexical fallback or unavailable index must remain visible as a degraded result,
not be presented as proof that no project evidence exists.

The TypeSafe review principles used for this design are intent/complexity
routing, typed evidence relevance checks, and independent citation support
checks. They guide evaluation and workflow structure only; TypeSafe is not a
runtime dependency of the customer environment.

## Insights market workflow

`insights.research_market` is an internal composite MCP tool selected by the
chat agent when the user asks for a concrete market insight. The user can ask
for an insight in a conversation without selecting a project, brand, or report;
the selected context may enrich the answer later but does not replace public
market evidence. A generic request such as “buscar insights” asks for one topic
before spending credits.

The market lookup is deferred until the admitted turn has opened its SSE stream,
so the interface can show a real `tool.started` activity while research runs.
The current workflow queries Firecrawl and Perplexity, then passes the combined evidence to a synthesis model and a
separate reviewer model. The reviewed conclusion and its evidence-backed cards
are returned directly in chat; there is no fourth model call to paraphrase it.
AI calls run through `CaduAIConnector`, with one
idempotent credit entry per stage. Firecrawl uses the existing
`web_search.search` credit authorization and charging. Model names are
environment-configurable (`CADU_INSIGHTS_RESEARCH_MODEL`,
`CADU_INSIGHTS_SYNTHESIS_MODEL`, and `CADU_INSIGHTS_REVIEW_MODEL`). Defaults
are Perplexity Sonar and GPT-5.4 mini for synthesis and review.

Publication policy prioritizes evidence from the previous 183 days and accepts
dated sources from the current calendar year as a fallback. Each factual metric
and news item must retain at least one dated, eligible source ID after review;
undated or out-of-window claims are excluded from the modeled insight. The
answer begins with the main market insight, then explains its metric/news basis,
marketing, communication or media relevance, and recommended actions. Sources
remain available as supporting references rather than taking over the opening.
