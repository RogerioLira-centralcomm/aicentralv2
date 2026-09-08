"""Credenciais globais de integrações, criptografadas no PostgreSQL."""

import json
import os
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


PROVIDERS = {
    "google_calendar": {
        "label": "Google Calendar e Meet",
        "public_fields": ("client_id", "redirect_uri"),
        "secret_fields": ("client_secret",),
        "required": ("client_id", "redirect_uri", "client_secret"),
    },
    "higgsfield": {
        "label": "Higgsfield",
        "public_fields": ("workspace_id", "default_model"),
        "secret_fields": ("api_key",),
        "required": ("api_key",),
    },
}

ENV_FIELDS = {
    "google_calendar": {
        "client_id": "GOOGLE_OAUTH_CLIENT_ID",
        "redirect_uri": "GOOGLE_OAUTH_REDIRECT_URI",
        "client_secret": "GOOGLE_OAUTH_CLIENT_SECRET",
    },
    "higgsfield": {
        "workspace_id": "HIGGSFIELD_WORKSPACE_ID",
        "default_model": "HIGGSFIELD_DEFAULT_MODEL",
        "api_key": "HIGGSFIELD_API_KEY",
    },
}


class IntegrationCredentialError(ValueError):
    pass


def _setting(name):
    try:
        return current_app.config.get(name) or os.getenv(name, "")
    except RuntimeError:
        return os.getenv(name, "")


def _fernet():
    key = _setting("INTEGRATION_CREDENTIALS_KEY")
    if not key:
        raise IntegrationCredentialError(
            "Configure INTEGRATION_CREDENTIALS_KEY no servidor antes de salvar segredos."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError) as exc:
        raise IntegrationCredentialError(
            "INTEGRATION_CREDENTIALS_KEY não é uma chave Fernet válida."
        ) from exc


def encrypt_secrets(secrets):
    clean = {
        key: str(value).strip()
        for key, value in (secrets or {}).items()
        if str(value or "").strip()
    }
    if not clean:
        return None
    return _fernet().encrypt(
        json.dumps(clean, ensure_ascii=False, sort_keys=True).encode()
    ).decode()


def decrypt_secrets(encrypted):
    if not encrypted:
        return {}
    try:
        return json.loads(_fernet().decrypt(encrypted.encode()).decode())
    except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
        raise IntegrationCredentialError(
            "Não foi possível descriptografar a credencial armazenada."
        ) from exc


def _environment_configuration(provider):
    return {
        field: str(_setting(env_name) or "").strip()
        for field, env_name in ENV_FIELDS[provider].items()
    }


def get_configuration(provider, include_secrets=False):
    _schema(provider)
    record = None
    try:
        from aicentralv2 import db
        record = db.obter_credencial_integracao(provider, incluir_segredo=True)
    except Exception:
        record = None
    if record:
        config = dict(record.get("public_config") or {})
        secrets = decrypt_secrets(record.get("encrypted_secret"))
        config.update(secrets)
        source = "database"
        status = record.get("status") or "active"
    else:
        config = _environment_configuration(provider)
        source = "environment"
        status = "active"
    result = {
        "provider": provider,
        "source": source,
        "status": status,
        "configured": status == "active" and all(
            config.get(field) for field in PROVIDERS[provider]["required"]
        ),
    }
    for field in PROVIDERS[provider]["public_fields"]:
        result[field] = config.get(field, "")
    if include_secrets:
        for field in PROVIDERS[provider]["secret_fields"]:
            result[field] = config.get(field, "")
    return result


def save_configuration(provider, payload, updated_by):
    schema = _schema(provider)
    payload = payload or {}
    public = {
        field: str(payload.get(field) or "").strip()[:1000]
        for field in schema["public_fields"]
    }
    _validate_public(provider, public)
    submitted_secrets = {
        field: str(payload.get(field) or "").strip()
        for field in schema["secret_fields"]
        if str(payload.get(field) or "").strip()
    }
    encrypted = encrypt_secrets(submitted_secrets) if submitted_secrets else None
    from aicentralv2 import db
    db.salvar_credencial_integracao(
        provider,
        public,
        encrypted,
        updated_by,
        status="active" if payload.get("enabled", True) else "disabled",
    )
    return get_summary(provider)


def remove_configuration(provider):
    _schema(provider)
    from aicentralv2 import db
    return bool(db.remover_credencial_integracao(provider))


def get_summary(provider):
    config = get_configuration(provider, include_secrets=True)
    schema = PROVIDERS[provider]
    summary = {
        key: config.get(key, "")
        for key in ("provider", "source", "status", "configured")
    }
    summary["label"] = schema["label"]
    summary["public_config"] = {
        field: config.get(field, "") for field in schema["public_fields"]
    }
    summary["has_secret"] = all(
        config.get(field) for field in schema["secret_fields"]
    )
    summary["secret_mask"] = "••••••••" if summary["has_secret"] else ""
    return summary


def list_summaries():
    return [get_summary(provider) for provider in PROVIDERS]


def validate_configuration(provider):
    config = get_configuration(provider, include_secrets=True)
    missing = [
        field for field in PROVIDERS[provider]["required"] if not config.get(field)
    ]
    if missing:
        return False, "Campos obrigatórios ausentes: " + ", ".join(missing)
    _validate_public(provider, config)
    return True, (
        "Credencial Google pronta para iniciar OAuth."
        if provider == "google_calendar"
        else "Credencial Higgsfield armazenada e pronta para uso."
    )


def _validate_public(provider, config):
    if provider == "google_calendar" and config.get("redirect_uri"):
        parsed = urlparse(config["redirect_uri"])
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise IntegrationCredentialError("Redirect URI do Google inválida.")
        if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1"):
            raise IntegrationCredentialError(
                "O redirect Google deve usar HTTPS fora do ambiente local."
            )


def _schema(provider):
    if provider not in PROVIDERS:
        raise IntegrationCredentialError("Integração não suportada.")
    return PROVIDERS[provider]
