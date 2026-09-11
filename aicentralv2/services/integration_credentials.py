"""Credenciais globais de integrações, criptografadas no PostgreSQL."""

import json
import os
import secrets
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
    "openrouter": {
        "label": "OpenRouter",
        "public_fields": ("default_model", "image_model"),
        "secret_fields": ("api_key",),
        "required": ("api_key",),
    },
    "d4sign": {
        "label": "D4Sign",
        "public_fields": ("uuid_safe", "ambiente"),
        "secret_fields": ("token_api", "crypt_key", "webhook_secret"),
        "required": ("token_api", "crypt_key"),
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
    "openrouter": {
        "default_model": "AGENT_OPENROUTER_MODEL",
        "image_model": "CREATIVE_IMAGE_MODEL",
        "api_key": "OPENROUTER_API_KEY",
    },
    "d4sign": {},
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
    unreadable = False
    if record:
        config = dict(record.get("public_config") or {})
        try:
            secrets = decrypt_secrets(record.get("encrypted_secret"))
            config.update(secrets)
        except IntegrationCredentialError:
            unreadable = bool(record.get("encrypted_secret"))
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
        "unreadable_secret": unreadable,
        "configured": (
            not unreadable
            and status == "active"
            and all(config.get(field) for field in PROVIDERS[provider]["required"])
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
    existing_secrets = {}
    try:
        existing = get_configuration(provider, include_secrets=True)
        existing_secrets = {
            field: existing.get(field, "")
            for field in schema["secret_fields"]
            if existing.get(field)
        }
    except Exception:
        existing_secrets = {}
    if provider == "openrouter" and not public.get("image_model"):
        public["image_model"] = "openai/gpt-image-2"
    if provider == "d4sign" and not public.get("ambiente"):
        public["ambiente"] = "producao"
    if provider == "d4sign" and not submitted_secrets.get("webhook_secret") and not existing_secrets.get("webhook_secret"):
        submitted_secrets["webhook_secret"] = secrets.token_urlsafe(24)
    if submitted_secrets:
        merged = dict(existing_secrets)
        merged.update(submitted_secrets)
        encrypted = encrypt_secrets(merged)
    else:
        encrypted = None
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
    summary["unreadable_secret"] = bool(config.get("unreadable_secret"))
    summary["label"] = schema["label"]
    summary["public_config"] = {
        field: config.get(field, "") for field in schema["public_fields"]
    }
    required_secrets = [
        field for field in schema["secret_fields"] if field in schema["required"]
    ] or list(schema["secret_fields"])
    summary["has_secret"] = all(
        config.get(field) for field in required_secrets
    )
    summary["secret_mask"] = "••••••••" if summary["has_secret"] else ""
    if provider == "d4sign":
        from .d4sign_client import public_webhook_url
        summary["webhook_url"] = public_webhook_url(config.get("webhook_secret"))
    return summary


def list_summaries():
    items = []
    for provider in PROVIDERS:
        try:
            items.append(get_summary(provider))
        except IntegrationCredentialError:
            schema = PROVIDERS[provider]
            items.append({
                "provider": provider,
                "source": "database",
                "status": "error",
                "configured": False,
                "unreadable_secret": True,
                "label": schema["label"],
                "public_config": {field: "" for field in schema["public_fields"]},
                "has_secret": False,
                "secret_mask": "",
            })
    return items


def validate_configuration(provider):
    config = get_configuration(provider, include_secrets=True)
    missing = [
        field for field in PROVIDERS[provider]["required"] if not config.get(field)
    ]
    if missing:
        return False, "Campos obrigatórios ausentes: " + ", ".join(missing), {}
    _validate_public(provider, config)
    if provider == "openrouter":
        valid, message = _validate_openrouter(config)
        return valid, message, {}
    if provider == "d4sign":
        return _validate_d4sign(config)
    return True, (
        "Credencial Google pronta para iniciar OAuth."
        if provider == "google_calendar"
        else "Credencial Higgsfield armazenada e pronta para uso."
    ), {}


def _validate_openrouter(config):
    import requests

    key = str(config.get("api_key") or "").strip()
    try:
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers={
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://centralcomm.media",
                "X-OpenRouter-Title": "CentralX",
            },
            timeout=15,
        )
    except requests.RequestException:
        return False, "Não foi possível validar a chave no OpenRouter."
    if response.status_code in (401, 403):
        return False, "A credencial OpenRouter não foi aceita."
    if response.status_code == 402:
        return False, "O saldo da conta OpenRouter é insuficiente."
    if response.status_code >= 400:
        return False, "O OpenRouter recusou a validação da chave."
    return True, "Credencial OpenRouter aceita pelo provedor."


def _validate_d4sign(config):
    from .d4sign_client import D4SignClient, D4SignError

    try:
        safes = D4SignClient.from_config(config).list_safes()
    except D4SignError as exc:
        return False, str(exc), {"safes": []}
    except Exception:
        return False, "Não foi possível validar a credencial na D4Sign.", {"safes": []}
    if not safes:
        return False, "A API respondeu, mas nenhum cofre foi encontrado.", {"safes": []}
    suggested = safes[0]["uuid"]
    uuid_safe = str(config.get("uuid_safe") or "").strip()
    ids = {item["uuid"] for item in safes}
    if uuid_safe and uuid_safe not in ids:
        return False, "O UUID do cofre não está entre os cofres desta conta.", {
            "safes": safes,
        }
    if not uuid_safe:
        try:
            from aicentralv2 import db
            record = db.obter_credencial_integracao("d4sign", incluir_segredo=False)
            if record:
                public = dict(record.get("public_config") or {})
                public["uuid_safe"] = suggested
                public.setdefault("ambiente", config.get("ambiente") or "producao")
                db.salvar_credencial_integracao(
                    "d4sign", public, None, record.get("updated_by"), status="active"
                )
        except Exception:
            pass
        hook_message = _register_d4sign_vault_webhook(config, suggested)
        return True, (
            f"Credencial D4Sign aceita. Cofre preenchido: {safes[0]['name']}.{hook_message}"
        ), {"safes": safes, "suggested_safe": suggested}
    name = next((item["name"] for item in safes if item["uuid"] == uuid_safe), uuid_safe)
    hook_message = _register_d4sign_vault_webhook(config, uuid_safe)
    return True, f"Credencial D4Sign aceita. Cofre: {name}.{hook_message}", {
        "safes": safes,
    }


def _register_d4sign_vault_webhook(config, uuid_safe):
    from .d4sign_client import D4SignClient, D4SignError, public_webhook_url

    hook = public_webhook_url(config.get("webhook_secret"))
    if not uuid_safe or not hook:
        return ""
    try:
        D4SignClient.from_config(config).register_vault_webhook(uuid_safe, hook)
    except D4SignError:
        return (
            " O POSTBack de cada documento já aponta para o CentralX. "
            "Para o webhook do cofre inteiro, ative Webhook 2.0 em D4Sign → Dev API."
        )
    except Exception:
        return " O POSTBack de cada documento já aponta para o CentralX."
    return " POSTBack do cofre registrado em ai.centralcomm.media."


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
