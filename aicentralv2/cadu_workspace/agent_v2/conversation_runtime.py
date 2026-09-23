"""Canonical identity and rollout policy for a Conversations V2 turn.

The transport may remain SSE and providers may change, but every turn enters
through this boundary so temporary run identifiers never become conversation
identifiers by accident.
"""

from dataclasses import dataclass
from uuid import UUID, uuid4

from flask import abort, current_app


def _identifiers(name: str) -> set[str]:
    value = current_app.config.get(name, "")
    if isinstance(value, (list, tuple, set)):
        return {str(item).strip() for item in value if str(item).strip()}
    return {item.strip() for item in str(value or "").split(",") if item.strip()}


def _flag(name: str, *, client_id=None, user_id=None, is_internal=False, default="all") -> bool:
    value = current_app.config.get(name, default)
    if not isinstance(value, str):
        return bool(value)
    stage = value.strip().lower()
    if stage in {"1", "true", "on", "yes", "all"}:
        return True
    if stage in {"0", "false", "off", "no", "none"}:
        return False
    allowed = (
        str(client_id or "") in _identifiers("CADU_CONVERSATION_ROLLOUT_CLIENTS")
        or str(user_id or "") in _identifiers("CADU_CONVERSATION_ROLLOUT_USERS")
    )
    if stage == "internal":
        return bool(is_internal)
    if stage == "allowlist":
        return allowed
    if stage == "staged":
        return bool(is_internal) or allowed
    return False


def _global_capability(name: str, *, default="all") -> bool:
    """Enable baseline capabilities for every tenant unless explicitly disabled."""
    value = current_app.config.get(name, default)
    if not isinstance(value, str):
        return bool(value)
    return value.strip().lower() not in {"0", "false", "off", "no", "none"}


@dataclass(frozen=True)
class TurnIdentity:
    conversation_id: str
    run_id: str
    conversation_supplied: bool

    @classmethod
    def from_payload(cls, data: dict):
        try:
            run_id = str(UUID(str(data.get("request_id"))))
        except (TypeError, ValueError):
            abort(400, description="Identificador de envio inválido.")
        supplied = bool(data.get("conversation_id"))
        if supplied:
            try:
                conversation_id = str(UUID(str(data["conversation_id"])))
            except (TypeError, ValueError):
                abort(400, description="Identificador de conversa inválido.")
        else:
            conversation_id = str(uuid4())
        if conversation_id == run_id:
            abort(400, description="A conversa e o envio precisam de identificadores distintos.")
        return cls(conversation_id, run_id, supplied)


@dataclass(frozen=True)
class RuntimeRollout:
    runtime_v2: bool
    memory_v2: bool
    shell_v2: bool

    @classmethod
    def current(cls, *, client_id=None, user_id=None, is_internal=False):
        return cls(
            runtime_v2=_global_capability("CADU_CONVERSATION_RUNTIME_V2"),
            memory_v2=_global_capability("CADU_CONVERSATION_MEMORY_V2"),
            shell_v2=_flag("CADU_CHAT_SHELL_V2", client_id=client_id, user_id=user_id, is_internal=is_internal),
        )

    def public_metadata(self) -> dict:
        return {
            "runtime_v2": self.runtime_v2,
            "memory_v2": self.memory_v2,
            "shell_v2": self.shell_v2,
        }
