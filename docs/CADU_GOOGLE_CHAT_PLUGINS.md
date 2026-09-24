# Google Workspace plugins in Cadu conversations

The Google connector is an individual OAuth authorization within one Cadu
`client_id`. The same client may have several authorizers. A person can manage
only their own connection. Drive search exposes metadata discovered through
that person's authorization. Project references belong to the client; Google
still enforces access to original files.

## Customer flow

1. The Plugins page shows Conectar Google first, then Drive, Calendar and Meet.
2. Opening one of these plugins shows the current person's connection state in
   the conversation. An unconnected person can start OAuth there.
3. The OAuth `next` target returns to the same conversation. The unsent prompt
   is kept in session storage for review; returning never executes a write.
4. A connected person can refresh Drive metadata independently of Calendar,
   Meet and Ads. Large Drives are indexed one page per request; the panel
   offers a continuation until the initial snapshot is complete. Drive results
   identify original Google files and folders.
5. The user can continue in the composer. Explicit instructions also select a
   matching Google workflow automatically. Tool execution remains authorized
   by the shared MCP registry.

## Contracts

- `GET /workspace/api/v2/google/connection`: safe current-person connection,
  service readiness, recent original resources and OAuth start URL.
- `POST /workspace/api/v2/google/drive/sync`: current-person Drive metadata
  refresh, protected by the chat CSRF contract.
- `GET /workspace/api/v2/google/drive/resources`: searchable, paginated
  original files and folders from the current person's Drive grant, with one
  visible record per Google item. A current Drive scope is required.
- `POST /workspace/api/v2/google/resources/<id>/link`: explicitly associate
  an original Google resource with a selected native Cadu project.
- `google.search_drive_resources`: metadata search within the current person's
  authorization and client, deduplicated by provider and Google external ID.
  Search does not grant Google file permissions.
- Project association stores the Google external identity and URL in Cadu's
  resource registry. Reconciliation reads active Google links so the registry
  cannot archive them merely because it refreshed the project. It does not
  create a Drive file copy. When an authorizer disconnects or switches accounts,
  links move to another active authorization for the same original item, or
  the registry marks them unavailable.

The migration `activate_cadu_google_chat_plugins.sql` versions these four
workflows and hides the historical planned Google integration card. The
database manifest is descriptive; the executable tool allowlist remains in
`agent_v2/plugins.py` and the MCP registry.

## Operational checks before rollout

- Apply the Google connection migrations and the plugin catalog migrations in
  `deploy.sh` before serving the new chat UI.
- Configure the Workspace OAuth client, redirect URI and token encryption key.
- Exercise the OAuth return with a real Google account on each configured host.
- Confirm two people in one client do not overwrite one another and the same
  person in two clients gets separate connections.
- Confirm a shared Drive file appears once in search and remains a reference
  after project association.
