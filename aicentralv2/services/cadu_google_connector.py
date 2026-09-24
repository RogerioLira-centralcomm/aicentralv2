"""Cadu connector for client-scoped Google Workspace data.

The connector is deliberately stateless: authorization remains owned by
``google_workspace`` and request identity remains owned by ``RequestContext``.
Each token belongs to the authorizing user within a Cadu ``client_id``. This
layer composes that identity with project boundaries for Workspace and MCP.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from ..cadu_family import repository
from ..cadu_workspace.agent_v2.contracts import RequestContext
from . import google_workspace


class CaduGoogleConnectorError(RuntimeError):
    """A safe, user-facing connector error."""


@dataclass(frozen=True)
class CaduGoogleConnector:
    """Google capability surface scoped to the Cadu client and current authorizer."""

    name: str = "cadu_google"
    provider: str = "google_workspace"

    @staticmethod
    def _bind_context(context: RequestContext) -> None:
        google_workspace.bind_client_user_scope(context.client_id, context.user_id)

    def _project_id(self, context: RequestContext) -> str:
        project_ref = str(context.project_ref or "")
        if not project_ref.startswith("ci:"):
            raise CaduGoogleConnectorError("Selecione um projeto do Cadu para usar os recursos Google.")
        project_id = project_ref[3:]
        rows = repository.rows(
            """SELECT id FROM cadu_ci_projetos
                WHERE id=%s AND id_cliente=%s AND status <> 'deletado'""",
            (project_id, context.client_id),
        )
        if not rows:
            raise CaduGoogleConnectorError("Projeto indisponível para esta conta.")
        return project_id

    @staticmethod
    def _connection_summary(connection: dict | None) -> dict[str, Any]:
        if not connection:
            return {"status": "disconnected", "account": None}
        return {
            "status": str(connection.get("status") or "unknown"),
            "account": {
                "email": connection.get("google_email"),
                "domain": connection.get("google_domain"),
                "granted_scopes": len(str(connection.get("granted_scopes") or "").split()),
                "last_sync_at": connection.get("last_sync_at"),
            },
        }

    def status(self, context: RequestContext) -> dict[str, Any]:
        """Return safe connector state for the current user/project context."""
        self._bind_context(context)
        matrix = google_workspace.service_matrix(context.client_id)
        connection = google_workspace.get_connection(context.client_id)
        connected = bool(connection and connection.get("status") == "connected")
        project_selected = bool(context.project_ref)
        return {
            "connector": self.name,
            "provider": self.provider,
            "scope": "client_user",
            "connection": self._connection_summary(connection),
            "services": matrix["services"],
            "service_summary": matrix["summary"],
            "configuration": {
                "configured": bool(matrix["configuration"].get("configured")),
                "missing": list(matrix["configuration"].get("missing") or []),
                "redirect_uri": matrix["configuration"].get("redirect_uri") or "",
            },
            "context": {
                "organization_id": context.organization_id,
                "client_id": context.client_id,
                "user_id": context.user_id,
                "surface": context.surface,
                "project_ref": context.project_ref,
                "brand_ref": context.brand_ref,
                "conversation_id": context.conversation_id,
            },
            "permissions": {
                "user_can_use": connected,
                "user_can_link_project_resources": connected and project_selected,
                "project_selected": project_selected,
            },
            "next_step": (
                "authorize_google_workspace"
                if not connected
                else "select_project" if not project_selected else "ready"
            ),
        }

    def list_project_resources(self, context: RequestContext, *, limit: int = 100) -> dict[str, Any]:
        self._bind_context(context)
        self._project_id(context)
        resources = google_workspace.list_resources(
            context.client_id,
            project_ref=context.project_ref,
            limit=min(max(int(limit), 1), 200),
        )
        return {
            "connector": self.name,
            "project_ref": context.project_ref,
            "user_id": context.user_id,
            "resources": resources,
            "total": len(resources),
        }

    def list_calendar_events(self, context: RequestContext, *, limit: int = 50) -> dict[str, Any]:
        self._bind_context(context)
        return {
            "connector": self.name,
            "organization_id": context.organization_id,
            "events": google_workspace.list_calendar_events(context.client_id, limit=limit),
        }

    def create_project_meeting(self, context: RequestContext, **meeting) -> dict[str, Any]:
        self._bind_context(context)
        project_id = self._project_id(context)
        members = repository.project_access(context.client_id, context.project_ref)
        attendees = [row.get("email") for row in members
                     if row.get("status") is True and row.get("email")]
        if not attendees:
            raise CaduGoogleConnectorError("A equipe do projeto não tem e-mails ativos para receber o convite.")
        result = google_workspace.create_calendar_event(
            context.client_id, attendees=attendees, **meeting,
        )
        return {"connector": self.name, "project_id": project_id, **result}

    def list_meet_records(self, context: RequestContext, *, limit: int = 50) -> dict[str, Any]:
        self._bind_context(context)
        return {
            "connector": self.name,
            "organization_id": context.organization_id,
            "conference_records": google_workspace.list_meet_conference_records(
                context.client_id, limit=limit,
            ),
        }

    def list_meet_artifacts(self, context: RequestContext, *, limit: int = 25) -> dict[str, Any]:
        self._bind_context(context)
        return {
            "connector": self.name,
            "organization_id": context.organization_id,
            **google_workspace.discover_meet_artifacts(context.client_id, limit=limit),
        }

    def link_resource(
        self,
        context: RequestContext,
        *,
        resource_id: str,
        purpose: str = "project_knowledge",
    ) -> dict[str, Any]:
        self._bind_context(context)
        self._project_id(context)
        if purpose not in {"project_knowledge", "project_attachment", "reference"}:
            raise CaduGoogleConnectorError("Finalidade de vínculo Google inválida.")
        return google_workspace.link_resource(
            client_id=context.client_id,
            resource_id=resource_id,
            project_ref=str(context.project_ref),
            user_id=context.user_id,
            purpose=purpose,
        ) | {"connector": self.name, "linked_by": context.user_id}

    def sync(
        self,
        context: RequestContext,
        *,
        drive_limit: int = 200,
        ads_limit: int = 100,
        calendar_limit: int = 100,
        meet_limit: int = 25,
    ) -> dict[str, Any]:
        """Synchronize this user's Google account for the current client."""
        self._bind_context(context)
        results: list[dict[str, Any]] = []
        errors: list[dict[str, str]] = []
        operations: tuple[tuple[str, Callable[[], dict]], ...] = (
            ("drive", lambda: google_workspace.sync_drive(
                context.client_id, limit=min(max(int(drive_limit), 1), 1000)
            )),
            ("ads", lambda: google_workspace.sync_ads(
                context.client_id, limit=min(max(int(ads_limit), 1), 200)
            )),
            ("calendar", lambda: google_workspace.sync_calendar_events(
                context.client_id, limit=min(max(int(calendar_limit), 1), 2500)
            )),
            ("meet", lambda: google_workspace.discover_meet_artifacts(
                context.client_id, limit=min(max(int(meet_limit), 1), 50)
            )),
        )
        for service, operation in operations:
            try:
                results.append({"service": service, **operation()})
            except google_workspace.GoogleWorkspaceError as exc:
                errors.append({"service": service, "message": str(exc)})
        return {
            "connector": self.name,
            "status": "partial" if results and errors else "completed" if results else "failed",
            "results": results,
            "errors": errors,
            "user_id": context.user_id,
        }


connector = CaduGoogleConnector()
