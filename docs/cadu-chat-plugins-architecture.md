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
| `campaign-search` | Planned | Selected brand or project required | Brand context or project knowledge search; no cross-project search. |
| `insights` | Active (v0.3.0) | Conversation; project or brand context is optional | Firecrawl public search + Perplexity Sonar research + GPT synthesis + separate GPT factual/editorial review. Returns the insight first, with current market metrics/news, implications for marketing/communication/media, actions, and supporting source references. |
| `planner` | Catalog connected (v0.2.0) | Conversation; project for saved plan | A plan request can gather read-only channel, audience, format and Places references for a proposal. Chat does not yet persist edits to the canonical live plan. |
| `project-search` | In development (v0.1.0) | Selected project required for private project search; new work can start without project context | One experience over semantic knowledge search, resource search and artifact listings. Search is restricted to the selected project; no cross-project search. |
| `project-activities` | In development (v0.1.0) | Selected project required to read or plan its tasks | Lists activities and prepares task proposals from project context and resources. Persistent writes continue through existing confirmed actions. |
| `studio` | Planned | Conversation; brand/project/reference optional | Image creation/editing exists in Studio MCP; chat still needs cost-confirmation wiring before automatic generation. Context-free creation is generic. |
| `reports` | Early | Project plus selected/reviewed report | Imported, reviewed metrics only; live platform ingestion is not implied. |

Catalog state is product maturity, not a permission level. `active`, `early`,
and `in_development` should be rendered distinctly in the storefront.

Trello, Asana, Slack and Google are shown as planned external integrations only; no external connector is active in this phase. The chat displays a plugin attribution only after a matching MCP tool completes successfully.

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
edit cannot grant a new tool permission. Write flows should extend manifests
with input/output schemas, confirmation and cost requirements, permission
references, artifact outputs, source policy and evaluation criteria. Use
semantic versioning: PATCH for fixes, MINOR for compatible workflow additions,
MAJOR for breaking input/output or behavior changes. Publish a new version
record instead of overwriting existing versions when changing a plugin
contract. The seed uses `ON CONFLICT DO NOTHING` on version rows to preserve
published definitions.

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
