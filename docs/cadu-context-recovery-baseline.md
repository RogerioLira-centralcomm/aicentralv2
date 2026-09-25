# Cadu context recovery baseline — client 174

Read-only inspection of the application database on 2026-09-25. Counts are a snapshot, not an ongoing metric.

## What exists

| Measure | Count |
| --- | ---: |
| Conversations | 845 |
| Conversations with a project in `cadu_conversations.projeto_id` | 157 |
| Canonical conversation bindings | 155 |
| Bindings with `project_ref` | 128 |
| Active projects | 10 |
| Project files marked `knowledge_source` and indexed | 5 |
| Project files marked `project_attachment` and paused | 5 |
| Indexed chunks with embeddings | 5 |
| Resource registry records | 1 |
| Resource reconciliation jobs queued for more than 10 minutes | 47 |
| Memory checkpoint jobs unfinished for more than 10 minutes | 34 |

The five paused attachments are intentionally metadata-only until reviewed as knowledge sources. Do not count them as readable evidence. The 47 resource jobs and 34 memory jobs are older than ten minutes; the oldest resource job dates to September 20, and the oldest memory job to September 23.

## Observed failures

- Some project-bound turns asking what the assistant knows about the project were routed to `answer` with no project tool call. One observed wording was “O que você tem sobre esse projeto?”. The router now covers that wording.
- Only five files have indexed text, so an inventory entry alone cannot support a claim that the assistant read a file.
- Conversation memory has 16 ready state records, all with `covers_message_count = 0`. The checkpoint implementation only creates historical segments after 20 messages, so this number alone does not prove memory retrieval failed. The 34 unfinished jobs do show that the durable projection is not keeping up.
- Project search and memory diagnostics were present in backend events but not visible enough in the observability detail to locate where evidence disappeared.

## Verification cases for the next deliveries

1. A new conversation bound to a project answers “O que você tem sobre esse projeto?” using structured project data and indexed sources, with provenance.
2. A project with paused attachments reports that they exist but have not been indexed.
3. A conversation can refer to an earlier decision after its checkpoint job completes.
4. A turn's observability detail shows resolved scope, retrieval counts, index gaps, and unavailable scopes.
5. The project resource and memory queues drain under supervised workers; a stalled queue raises an alert.

These cases test information flow and coverage. They should be expanded with source-specific expected answers before changing the retrieval ranker or migrating plugins.

## Historical project conversations

The project search now retrieves a bounded set of original user messages from earlier conversations with the same organization, client, project, and user. Each result includes the conversation and message IDs. These are statements from prior dialogue, not confirmed project decisions. The assistant should use them to locate context and distinguish them from saved direction, indexed sources, and reviewed working memory. Conversations without a canonical project binding are not included.

The working-memory tables were missing in production because their migration runner was omitted from `deploy.sh`. The runner now executes during deployment; future project decisions can be proposed for review. Existing conversations have not been backfilled into confirmed working memory.

## Queue reset and prevention

After the snapshot, 47 queued resource jobs and 34 unclaimed memory jobs for client 174 were deleted in one transaction. Canonical conversations, messages, files, indexed chunks, and completed memory states were not changed. A read-only check immediately afterward found zero pending jobs in both queues.

The resource enqueue path now coalesces pending events for the same client and project under a transaction advisory lock. Chat resource reads consult source tables even when the registry has some records, so a partial registry cannot hide newer sources. Continuous resource and memory consumers must be enabled in production for future jobs to complete; queue-age alerts report a missing or stalled worker.
