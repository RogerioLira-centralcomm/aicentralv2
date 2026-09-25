"""OAuth 2.1 primitives for the public Cadu MCP.

Tokens and authorization codes are opaque. Only SHA-256 digests are stored.
The module intentionally keeps product authorization in ``auth.py``; OAuth is
only the credential delegation layer.
"""

from __future__ import annotations

import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse
from uuid import UUID, uuid4

from psycopg.types.json import Json

from ..cadu_mcp_catalog import ALL_MODULES, DEFAULT_MODULES, normalize_modules
from ..db import get_db
from .auth import CLIENT_SCOPES, DEFAULT_SCOPES, PublicMcpAuthError, accessible_client, normalize_scopes


ISSUER_PATH = ""
ACCESS_PREFIX = "cadu_oauth_at_"
REFRESH_PREFIX = "cadu_oauth_rt_"
CODE_PREFIX = "cadu_oauth_code_"
CLIENT_PREFIX = "cadu_oauth_client_"
ACCESS_TTL_SECONDS = 15 * 60
REFRESH_TTL_DAYS = 30
CODE_TTL_SECONDS = 5 * 60
DCR_PER_IP_HOURLY_LIMIT = 20
DCR_GLOBAL_DAILY_LIMIT = 1000


class OAuthError(RuntimeError):
    def __init__(self, error: str, description: str, status: int = 400):
        super().__init__(description)
        self.error = error
        self.description = description
        self.status = status


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _opaque(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(36)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _table_available(name: str) -> bool:
    try:
        with get_db().cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s) AS table_name", (f"public.{name}",))
            return bool((cursor.fetchone() or {}).get("table_name"))
    except Exception:
        return False


def _modules_column_available() -> bool:
    try:
        with get_db().cursor() as cursor:
            cursor.execute("""SELECT EXISTS (SELECT 1 FROM information_schema.columns
                               WHERE table_schema='public' AND table_name='cadu_oauth_grants'
                                 AND column_name='modules') AS available""")
            return bool((cursor.fetchone() or {}).get("available"))
    except Exception:
        return False


def available() -> bool:
    return _modules_column_available() and all(_table_available(name) for name in (
        "cadu_oauth_clients",
        "cadu_oauth_grants",
        "cadu_oauth_authorization_codes",
        "cadu_oauth_access_tokens",
        "cadu_oauth_refresh_tokens",
    ))


def validate_redirect_uri(value: str, *, allow_loopback: bool = True) -> str:
    raw = str(value or "").strip()
    parsed = urlparse(raw)
    if parsed.fragment or parsed.username or parsed.password:
        raise OAuthError("invalid_redirect_uri", "A URI de retorno é inválida.")
    if parsed.scheme == "https" and parsed.netloc:
        return raw
    if allow_loopback and parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"}:
        return raw
    raise OAuthError("invalid_redirect_uri", "A URI de retorno deve usar HTTPS ou loopback local.")


def _optional_https_url(value, field: str) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    parsed = urlparse(raw)
    if parsed.scheme != "https" or not parsed.netloc or parsed.fragment or parsed.username or parsed.password:
        raise OAuthError("invalid_client_metadata", f"{field} deve ser uma URL HTTPS.")
    return raw[:500]


def _redirect_matches(registered: str, candidate: str) -> bool:
    if secrets.compare_digest(registered, candidate):
        return True
    saved, current = urlparse(registered), urlparse(candidate)
    loopbacks = {"127.0.0.1", "::1", "localhost"}
    return (
        saved.scheme == current.scheme == "http"
        and saved.hostname == current.hostname
        and saved.hostname in loopbacks
        and saved.port is None
        and saved.path == current.path
        and saved.query == current.query
        and not saved.fragment and not current.fragment
    )


def register_client(metadata: dict, *, registration_ip: str | None = None) -> dict:
    if not available():
        raise OAuthError("temporarily_unavailable", "O OAuth do Cadu ainda não está ativo.", 503)
    redirects = metadata.get("redirect_uris") or []
    if not isinstance(redirects, list) or not redirects:
        raise OAuthError("invalid_client_metadata", "Informe ao menos uma redirect_uri.")
    redirects = [validate_redirect_uri(item) for item in redirects]
    grant_types = metadata.get("grant_types") or ["authorization_code", "refresh_token"]
    response_types = metadata.get("response_types") or ["code"]
    if not isinstance(grant_types, list) or not set(grant_types) <= {"authorization_code", "refresh_token"}:
        raise OAuthError("invalid_client_metadata", "grant_types não suportado.")
    if response_types != ["code"] and set(response_types) != {"code"}:
        raise OAuthError("invalid_client_metadata", "Somente response_type code é suportado.")
    auth_method = str(metadata.get("token_endpoint_auth_method") or "none")
    if auth_method != "none":
        raise OAuthError("invalid_client_metadata", "Somente clientes públicos com PKCE são aceitos.")
    client_id = CLIENT_PREFIX + secrets.token_urlsafe(24)
    name = " ".join(str(metadata.get("client_name") or "Aplicativo MCP").split())[:120]
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            # Serialize the admission check so concurrent registrations from
            # the same origin cannot all observe a count below the limit.
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"cadu-oauth-dcr:{registration_ip or 'unknown'}",),
            )
            cursor.execute(
                """SELECT COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 hour'
                                             AND registration_ip IS NOT DISTINCT FROM %s::inet) AS ip_recent,
                          COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '1 day') AS global_recent
                     FROM cadu_oauth_clients""",
                (registration_ip,),
            )
            limits = cursor.fetchone() or {}
            if int(limits.get("ip_recent") or 0) >= DCR_PER_IP_HOURLY_LIMIT:
                raise OAuthError("too_many_requests", "Muitos aplicativos registrados por esta origem. Tente mais tarde.", 429)
            if int(limits.get("global_recent") or 0) >= DCR_GLOBAL_DAILY_LIMIT:
                raise OAuthError("temporarily_unavailable", "O registro de aplicativos atingiu o limite diário.", 503)
            cursor.execute(
                """INSERT INTO cadu_oauth_clients
                    (id, oauth_client_id, client_name, client_uri, logo_uri, redirect_uris,
                     grant_types, response_types, token_endpoint_auth_method, registration_ip, status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::inet,'active')
                RETURNING oauth_client_id, client_name, client_uri, logo_uri, redirect_uris,
                          grant_types, response_types, token_endpoint_auth_method,
                          EXTRACT(EPOCH FROM client_id_issued_at)::bigint AS client_id_issued_at""",
                (uuid4(), client_id, name, _optional_https_url(metadata.get("client_uri"), "client_uri"),
                 _optional_https_url(metadata.get("logo_uri"), "logo_uri"), Json(redirects),
                 Json(grant_types), Json(response_types), auth_method, registration_ip),
            )
            row = dict(cursor.fetchone())
        connection.commit()
        return {"client_id": row.pop("oauth_client_id"), **row}
    except OAuthError:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise


def load_client(client_id: str, redirect_uri: str | None = None) -> dict:
    if not available():
        raise OAuthError("temporarily_unavailable", "O OAuth do Cadu ainda não está ativo.", 503)
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT id, oauth_client_id, client_name, client_uri, logo_uri, redirect_uris,
                      grant_types, response_types, token_endpoint_auth_method, status
                 FROM cadu_oauth_clients WHERE oauth_client_id=%s""",
            (str(client_id or ""),),
        )
        row = cursor.fetchone()
    if not row or row.get("status") != "active":
        raise OAuthError("invalid_client", "Cliente OAuth inválido.", 401)
    value = dict(row)
    if redirect_uri is not None:
        candidate = validate_redirect_uri(redirect_uri)
        if not any(_redirect_matches(registered, candidate) for registered in list(value.get("redirect_uris") or [])):
            raise OAuthError("invalid_request", "A redirect_uri não foi registrada.")
    return value


def validate_authorization_request(values) -> dict:
    client_id = str(values.get("client_id") or "")
    redirect_uri = str(values.get("redirect_uri") or "")
    client = load_client(client_id, redirect_uri)
    if values.get("response_type") != "code":
        raise OAuthError("unsupported_response_type", "Somente response_type=code é suportado.")
    challenge = str(values.get("code_challenge") or "")
    if values.get("code_challenge_method") != "S256" or len(challenge) < 43:
        raise OAuthError("invalid_request", "PKCE S256 é obrigatório.")
    resource = str(values.get("resource") or "")
    if not resource:
        raise OAuthError("invalid_target", "O resource do MCP é obrigatório.")
    raw_scope = values.get("scope")
    try:
        scopes = normalize_scopes(DEFAULT_SCOPES if raw_scope is None else str(raw_scope).split(), allow_writes=True)
    except PublicMcpAuthError as exc:
        raise OAuthError("invalid_scope", str(exc)) from exc
    if not scopes:
        raise OAuthError("invalid_scope", "Informe ao menos uma permissão.")
    return {
        "client": client,
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "resource": resource,
        "state": str(values.get("state") or ""),
        "code_challenge": challenge,
        "scopes": scopes,
    }


def create_authorization_code(*, authorization: dict, client_id: int, user_id: int,
                              scopes, default_project_ref: str | None = None, modules=None) -> str:
    try:
        allowed = normalize_scopes(scopes, allow_writes=True)
    except PublicMcpAuthError as exc:
        raise OAuthError("invalid_scope", str(exc)) from exc
    if not allowed:
        raise OAuthError("invalid_scope", "Selecione ao menos uma permissão.")
    try:
        enabled_modules = normalize_modules(modules)
    except ValueError as exc:
        raise OAuthError("invalid_scope", str(exc)) from exc
    if not enabled_modules:
        raise OAuthError("invalid_scope", "Ative ao menos um módulo.")
    requested = set(authorization["scopes"])
    if not set(allowed) <= requested:
        raise OAuthError("invalid_scope", "As permissões aprovadas excedem a solicitação.")
    raw_code = _opaque(CODE_PREFIX)
    grant_id, code_id = uuid4(), uuid4()
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """INSERT INTO cadu_oauth_grants
                    (id, oauth_client_id, client_id, user_id, default_project_ref, scopes, modules,
                     status, consented_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,'active',NOW())""",
                (grant_id, authorization["client"]["id"], int(client_id), int(user_id),
                 default_project_ref, Json(list(allowed)), Json(list(enabled_modules))),
            )
            cursor.execute(
                """INSERT INTO cadu_oauth_authorization_codes
                    (id, code_hash, grant_id, oauth_client_id, redirect_uri, resource,
                     scopes, code_challenge, code_challenge_method, expires_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'S256',%s)""",
                (code_id, _hash(raw_code), grant_id, authorization["client"]["id"],
                 authorization["redirect_uri"], authorization["resource"], Json(list(allowed)),
                 authorization["code_challenge"], _now() + timedelta(seconds=CODE_TTL_SECONDS)),
            )
        connection.commit()
        return raw_code
    except Exception:
        connection.rollback()
        raise


def _pkce_challenge(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _issue_tokens(cursor, *, grant_id, oauth_client_id, resource: str, scopes,
                  family_id=None) -> dict:
    access, refresh = _opaque(ACCESS_PREFIX), _opaque(REFRESH_PREFIX)
    access_id, refresh_id = uuid4(), uuid4()
    family_id = family_id or uuid4()
    access_expiry = _now() + timedelta(seconds=ACCESS_TTL_SECONDS)
    refresh_expiry = _now() + timedelta(days=REFRESH_TTL_DAYS)
    cursor.execute(
        """INSERT INTO cadu_oauth_access_tokens
            (id, token_hash, grant_id, oauth_client_id, resource, scopes, expires_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (access_id, _hash(access), grant_id, oauth_client_id, resource, Json(list(scopes)), access_expiry),
    )
    cursor.execute(
        """INSERT INTO cadu_oauth_refresh_tokens
            (id, token_hash, grant_id, oauth_client_id, family_id, resource, scopes, expires_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (refresh_id, _hash(refresh), grant_id, oauth_client_id, family_id, resource,
         Json(list(scopes)), refresh_expiry),
    )
    return {"access_token": access, "token_type": "Bearer", "expires_in": ACCESS_TTL_SECONDS,
            "refresh_token": refresh, "scope": " ".join(scopes)}


def exchange_code(*, code: str, client_id: str, redirect_uri: str, code_verifier: str,
                  resource: str) -> dict:
    client = load_client(client_id, redirect_uri)
    if not code_verifier:
        raise OAuthError("invalid_grant", "code_verifier ausente.")
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT code.*, grant_row.client_id AS grant_client_id,
                          grant_row.user_id AS grant_user_id, grant_row.status AS grant_status
                     FROM cadu_oauth_authorization_codes code
                     JOIN cadu_oauth_grants grant_row ON grant_row.id=code.grant_id
                    WHERE code.code_hash=%s FOR UPDATE OF code""", (_hash(code),),
            )
            row = cursor.fetchone()
            if (not row or row.get("used_at") or row["expires_at"] <= _now()
                    or row["oauth_client_id"] != client["id"]
                    or row["redirect_uri"] != redirect_uri or row["resource"] != resource
                    or row["grant_status"] != "active"
                    or not secrets.compare_digest(row["code_challenge"], _pkce_challenge(code_verifier))):
                raise OAuthError("invalid_grant", "Código de autorização inválido ou expirado.")
            if accessible_client(user_id=row["grant_user_id"], client_id=row["grant_client_id"]) is None:
                raise OAuthError("invalid_grant", "O acesso a este cliente foi revogado.")
            cursor.execute("UPDATE cadu_oauth_authorization_codes SET used_at=NOW() WHERE id=%s", (row["id"],))
            tokens = _issue_tokens(cursor, grant_id=row["grant_id"], oauth_client_id=client["id"],
                                   resource=resource, scopes=tuple(row["scopes"]))
        connection.commit()
        return tokens
    except OAuthError:
        connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise


def refresh_tokens(*, refresh_token: str, client_id: str, resource: str) -> dict:
    client = load_client(client_id)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""SELECT token.*, grant_row.client_id AS grant_client_id,
                              grant_row.user_id AS grant_user_id, grant_row.status AS grant_status
                         FROM cadu_oauth_refresh_tokens token
                         JOIN cadu_oauth_grants grant_row ON grant_row.id=token.grant_id
                        WHERE token.token_hash=%s FOR UPDATE OF token""",
                           (_hash(refresh_token),))
            row = cursor.fetchone()
            if (not row or row["oauth_client_id"] != client["id"] or row["resource"] != resource
                    or row["grant_status"] != "active"):
                raise OAuthError("invalid_grant", "Refresh token inválido.")
            if row.get("rotated_at") or row.get("revoked_at"):
                cursor.execute(
                    """UPDATE cadu_oauth_refresh_tokens SET revoked_at=COALESCE(revoked_at,NOW()),
                              reuse_detected_at=CASE WHEN id=%s THEN NOW() ELSE reuse_detected_at END
                        WHERE family_id=%s""", (row["id"], row["family_id"]),
                )
                cursor.execute("UPDATE cadu_oauth_access_tokens SET revoked_at=COALESCE(revoked_at,NOW()) WHERE grant_id=%s",
                               (row["grant_id"],))
                connection.commit()
                raise OAuthError("invalid_grant", "A família de refresh tokens foi revogada.")
            if row["expires_at"] <= _now():
                raise OAuthError("invalid_grant", "Refresh token expirado.")
            if accessible_client(user_id=row["grant_user_id"], client_id=row["grant_client_id"]) is None:
                raise OAuthError("invalid_grant", "O acesso a este cliente foi revogado.")
            tokens = _issue_tokens(cursor, grant_id=row["grant_id"], oauth_client_id=client["id"],
                                   resource=resource, scopes=tuple(row["scopes"]), family_id=row["family_id"])
            cursor.execute("UPDATE cadu_oauth_refresh_tokens SET rotated_at=NOW() WHERE id=%s", (row["id"],))
        connection.commit()
        return tokens
    except OAuthError:
        if not connection.closed:
            connection.rollback()
        raise
    except Exception:
        connection.rollback()
        raise


def revoke_token(token: str) -> None:
    if not token or not available():
        return
    digest = _hash(token)
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            if token.startswith(REFRESH_PREFIX):
                cursor.execute("SELECT grant_id, family_id FROM cadu_oauth_refresh_tokens WHERE token_hash=%s", (digest,))
                row = cursor.fetchone()
                if row:
                    cursor.execute("UPDATE cadu_oauth_refresh_tokens SET revoked_at=COALESCE(revoked_at,NOW()) WHERE family_id=%s",
                                   (row["family_id"],))
                    cursor.execute("UPDATE cadu_oauth_access_tokens SET revoked_at=COALESCE(revoked_at,NOW()) WHERE grant_id=%s",
                                   (row["grant_id"],))
            else:
                cursor.execute("UPDATE cadu_oauth_access_tokens SET revoked_at=COALESCE(revoked_at,NOW()) WHERE token_hash=%s",
                               (digest,))
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def load_access_token(raw_token: str) -> dict:
    if not raw_token.startswith(ACCESS_PREFIX) or not available():
        raise PublicMcpAuthError("Token OAuth do MCP inválido.")
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT t.id AS credential_id, t.grant_id, t.resource, t.scopes AS token_scopes,
                      t.expires_at, t.revoked_at, g.client_id, g.user_id,
                      g.default_project_ref, g.scopes AS grant_scopes, g.modules, g.status,
                      c.client_name, c.oauth_client_id
                 FROM cadu_oauth_access_tokens t
                 JOIN cadu_oauth_grants g ON g.id=t.grant_id
                 JOIN cadu_oauth_clients c ON c.id=t.oauth_client_id
                WHERE t.token_hash=%s""", (_hash(raw_token),),
        )
        row = cursor.fetchone()
    if not row or row.get("revoked_at") or row.get("status") != "active" or row["expires_at"] <= _now():
        raise PublicMcpAuthError("Token OAuth do MCP inválido ou expirado.")
    token_scopes = set(row.get("token_scopes") or [])
    grant_scopes = set(row.get("grant_scopes") or [])
    effective_scopes = tuple(sorted(token_scopes & grant_scopes))
    if not effective_scopes:
        raise PublicMcpAuthError("Token OAuth do MCP sem permissões ativas.")
    if accessible_client(user_id=row["user_id"], client_id=row["client_id"]) is None:
        raise PublicMcpAuthError("O acesso a este cliente foi revogado.")
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE cadu_oauth_access_tokens SET last_used_at=NOW() WHERE id=%s", (row["credential_id"],))
            cursor.execute("UPDATE cadu_oauth_grants SET last_used_at=NOW() WHERE id=%s", (row["grant_id"],))
        connection.commit()
    except Exception:
        connection.rollback()
    return dict(row) | {"scopes": effective_scopes,
                        "modules": normalize_modules(row.get("modules"), default=ALL_MODULES),
                        "label": row.get("client_name") or "Aplicativo MCP",
                        "client_type": "oauth"}


def list_grants(*, client_id: int, user_id: int) -> list[dict]:
    if not available():
        return []
    with get_db().cursor() as cursor:
        cursor.execute(
            """SELECT g.id, g.default_project_ref, g.scopes, g.modules, g.status, g.consented_at,
                      g.last_used_at, g.revoked_at, c.client_name, c.logo_uri
                 FROM cadu_oauth_grants g JOIN cadu_oauth_clients c ON c.id=g.oauth_client_id
                WHERE g.client_id=%s AND g.user_id=%s ORDER BY g.created_at DESC""",
            (int(client_id), int(user_id)),
        )
        return [dict(row) | {"id": str(row["id"])} for row in cursor.fetchall()]


def update_grant_modules(*, grant_id: str, client_id: int, user_id: int, modules) -> bool:
    try:
        parsed = UUID(str(grant_id))
        enabled_modules = normalize_modules(modules)
    except (TypeError, ValueError) as exc:
        raise OAuthError("invalid_request", "Seleção de módulos inválida.") from exc
    if not enabled_modules:
        raise OAuthError("invalid_scope", "Ative ao menos um módulo.")
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_oauth_grants SET modules=%s, updated_at=NOW()
                    WHERE id=%s AND client_id=%s AND user_id=%s AND status='active'""",
                (Json(list(enabled_modules)), parsed, int(client_id), int(user_id)),
            )
            changed = cursor.rowcount == 1
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    return changed


def revoke_grant(*, grant_id: str, client_id: int, user_id: int) -> bool:
    try:
        parsed = UUID(str(grant_id))
    except (TypeError, ValueError) as exc:
        raise OAuthError("invalid_request", "Conexão OAuth inválida.") from exc
    connection = get_db()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE cadu_oauth_grants SET status='revoked', revoked_at=NOW()
                    WHERE id=%s AND client_id=%s AND user_id=%s AND status='active' RETURNING id""",
                (parsed, int(client_id), int(user_id)),
            )
            changed = bool(cursor.fetchone())
            if changed:
                cursor.execute("UPDATE cadu_oauth_access_tokens SET revoked_at=COALESCE(revoked_at,NOW()) WHERE grant_id=%s", (parsed,))
                cursor.execute("UPDATE cadu_oauth_refresh_tokens SET revoked_at=COALESCE(revoked_at,NOW()) WHERE grant_id=%s", (parsed,))
        connection.commit()
        return changed
    except Exception:
        connection.rollback()
        raise
