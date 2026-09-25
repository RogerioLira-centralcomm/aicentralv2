"""Credenciais globais de integrações, criptografadas no PostgreSQL."""

import base64
import hashlib
import json
import os
import secrets
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from flask import current_app


PROVIDERS = {
    "google_login_centralx": {
        "label": "Google Login — CentralX interno",
        "public_fields": ("client_id", "redirect_uri", "allowed_domain"),
        "secret_fields": ("client_secret",),
        "required": ("client_id", "redirect_uri", "client_secret", "allowed_domain"),
    },
    "google_login_cadu": {
        "label": "Google Login — Cadu e família",
        "public_fields": ("client_id", "redirect_uri"),
        "secret_fields": ("client_secret",),
        "required": ("client_id", "redirect_uri", "client_secret"),
    },
    "google_workspace": {
        "label": "Google Workspace — Dados e arquivos do cliente",
        "public_fields": ("client_id", "redirect_uri"),
        "secret_fields": ("client_secret", "token_encryption_key"),
        "required": (
            "client_id",
            "redirect_uri",
            "client_secret",
            "token_encryption_key",
        ),
    },
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
    "openai": {
        "label": "OpenAI",
        "public_fields": ("default_model", "image_model"),
        "secret_fields": ("api_key",),
        "required": ("api_key",),
    },
    "typesafe": {
        "label": "TypeSafe AI",
        "public_fields": ("default_model",),
        "secret_fields": ("api_key",),
        "required": ("api_key",),
    },
    "firecrawl": {
        "label": "Firecrawl",
        "public_fields": (),
        "secret_fields": ("api_key",),
        "required": ("api_key",),
    },
    "dify": {
        "label": "Dify — Integração global (legado)",
        "public_fields": ("base_url",),
        "secret_fields": ("api_key",),
        "required": ("api_key",),
    },
    "dify_cadu_chat": {
        "label": "Dify — Cadu Chat exclusivo",
        "public_fields": ("base_url",),
        "secret_fields": ("api_key",),
        "required": ("api_key",),
    },
    "brevo": {
        "label": "Brevo",
        "public_fields": (),
        "secret_fields": ("api_key", "webhook_token"),
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
    "google_login_centralx": {
        "client_id": "GOOGLE_CENTRALX_CLIENT_ID",
        "redirect_uri": "GOOGLE_CENTRALX_REDIRECT_URI",
        "allowed_domain": "GOOGLE_CENTRALX_DOMAIN",
        "client_secret": "GOOGLE_CENTRALX_CLIENT_SECRET",
    },
    "google_login_cadu": {
        "client_id": "GOOGLE_CADU_CLIENT_ID",
        "redirect_uri": "GOOGLE_CADU_REDIRECT_URI",
        "client_secret": "GOOGLE_CADU_CLIENT_SECRET",
    },
    "google_workspace": {
        "client_id": "GOOGLE_WORKSPACE_CLIENT_ID",
        "redirect_uri": "GOOGLE_WORKSPACE_REDIRECT_URI",
        "client_secret": "GOOGLE_WORKSPACE_CLIENT_SECRET",
    },
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
    "openai": {
        "default_model": "OPENAI_DEFAULT_MODEL",
        "image_model": "OPENAI_IMAGE_MODEL",
        "api_key": "OPENAI_API_KEY",
    },
    "typesafe": {
        "default_model": "TYPESAFE_DEFAULT_MODEL",
        "api_key": "TYPESAFE_API_KEY",
    },
    "firecrawl": {
        "api_key": "FIRECRAWL_API_KEY",
    },
    "dify": {
        "base_url": "CADU_DIFY_BASE_URL",
        "api_key": "CADU_DIFY_API_KEY",
    },
    "dify_cadu_chat": {
        "base_url": "CADU_CONVERSATIONS_V2_DIFY_URL",
        "api_key": "CADU_CONVERSATIONS_V2_DIFY_KEY",
    },
    "brevo": {
        "api_key": "BREVO_API_KEY",
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
    if key:
        try:
            return Fernet(key.encode())
        except (ValueError, TypeError) as exc:
            raise IntegrationCredentialError(
                "INTEGRATION_CREDENTIALS_KEY não é uma chave Fernet válida."
            ) from exc

    # The dedicated credential key is preferred, but its absence must not make
    # the integrations console unusable.  Derive a separate Fernet key from
    # CentralX's already-required application secret; nothing is persisted or
    # exposed, and the domain separator prevents reusing SECRET_KEY directly.
    app_secret = str(_setting("SECRET_KEY") or "").strip()
    if not app_secret:
        raise IntegrationCredentialError(
            "Configure SECRET_KEY no servidor antes de salvar segredos."
        )
    derived_key = base64.urlsafe_b64encode(
        hashlib.sha256(
            b"centralx:integration-credentials:v1:" + app_secret.encode("utf-8")
        ).digest()
    )
    return Fernet(derived_key)


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
        # A rotated database encryption key must not make a working deployment
        # look unconfigured. When the server still has a complete provider
        # configuration in its protected environment, it is the live fallback
        # used by the runtime and should be reported as such in the console.
        if unreadable:
            environment = _environment_configuration(provider)
            required = PROVIDERS[provider]["required"]
            if all(environment.get(field) for field in required):
                config = environment
                source = "environment"
                unreadable = False
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
    if provider == "openai" and not public.get("default_model"):
        public["default_model"] = "gpt-5-mini"
    if provider == "openai" and not public.get("image_model"):
        public["image_model"] = "gpt-image-2"
    if provider in {"dify", "dify_cadu_chat"} and not public.get("base_url"):
        public["base_url"] = "https://api.dify.ai/v1"
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
    if provider == "openai":
        valid, message = _validate_openai(config)
        return valid, message, {}
    if provider == "typesafe":
        return _validate_typesafe(config)
    if provider == "firecrawl":
        valid, message = _validate_firecrawl(config)
        return valid, message, {}
    if provider in {"dify", "dify_cadu_chat"}:
        valid, message = _validate_dify(config)
        return valid, message, {}
    if provider == "brevo":
        valid, message = _validate_brevo(config)
        return valid, message, {}
    if provider == "d4sign":
        return _validate_d4sign(config)
    return True, (
        "Credencial Google pronta para iniciar OAuth."
        if provider.startswith("google_")
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


def _validate_openai(config):
    import requests

    key = str(config.get("api_key") or "").strip()
    try:
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
    except requests.RequestException:
        return False, "Não foi possível validar a chave na OpenAI."
    if response.status_code in (401, 403):
        return False, "A credencial OpenAI não foi aceita."
    if response.status_code == 429:
        return False, "A OpenAI limitou a validação. Aguarde e tente de novo."
    if response.status_code >= 400:
        return False, "A OpenAI recusou a validação da chave."
    return True, "Credencial OpenAI aceita. Modelos GPT passam a sair direto de api.openai.com."


def _validate_typesafe(config):
    """Validate authentication with one minimal, real System One evaluation."""
    import requests

    model = str(config.get("default_model") or "jev-latest").strip()
    payload = {
        "state": "CentralX TypeSafe API credential validation.",
        "model": model,
        "questions": {
            "connection_check": {
                "type": "noul",
                "instructions": "Does this text describe an API credential validation?",
            }
        },
    }
    try:
        response = requests.post(
            "https://api.typesafe.ai/v1/systemone",
            headers={
                "Authorization": f"Bearer {str(config.get('api_key') or '').strip()}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=20,
        )
    except requests.RequestException:
        return False, "Não foi possível validar a chave na TypeSafe.", {}
    if response.status_code in (401, 403):
        return False, "A credencial TypeSafe não foi aceita.", {}
    if response.status_code == 429:
        return False, "A TypeSafe limitou a validação. Aguarde e tente de novo.", {}
    if response.status_code == 529:
        return False, "A TypeSafe está temporariamente sobrecarregada. Tente novamente.", {}
    if response.status_code >= 400:
        return False, "A TypeSafe recusou a avaliação de validação.", {}
    try:
        result = response.json()
    except ValueError:
        return False, "A TypeSafe retornou uma resposta inválida.", {}
    if not isinstance(result, dict) or not isinstance(result.get("answers"), dict) or "connection_check" not in result["answers"]:
        return False, "A TypeSafe aceitou a chave, mas não retornou a avaliação esperada.", {}
    usage = result.get("usage") if isinstance(result.get("usage"), dict) else {}

    def _usage_count(key):
        try:
            return max(0, int(usage.get(key) or 0))
        except (TypeError, ValueError):
            return 0

    return True, "Chave TypeSafe aceita; avaliação de conexão concluída.", {
        "model": result.get("model") or model,
        "usage": {
            "input_tokens": _usage_count("input_tokens"),
            "output_tokens": _usage_count("output_tokens"),
        },
    }


def resolve_typesafe_api_key() -> str:
    """Return the configured TypeSafe key for server-side API calls."""
    try:
        config = get_configuration("typesafe", include_secrets=True)
        if config.get("status") == "disabled":
            return ""
        key = str(config.get("api_key") or "").strip()
        if key:
            return key
    except Exception:
        pass
    return str(_setting("TYPESAFE_API_KEY") or "").strip()


def resolve_firecrawl_api_key() -> str:
    try:
        config = get_configuration("firecrawl", include_secrets=True)
        if config.get("status") == "disabled":
            return ""
        key = str(config.get("api_key") or "").strip()
        if key:
            return key
    except Exception:
        pass
    return str(_setting("FIRECRAWL_API_KEY") or "").strip()


def resolve_dify_configuration():
    """Resolve Dify no cofre, mantendo o .env como reserva operacional."""
    default_url = "https://api.dify.ai/v1"
    try:
        config = get_configuration("dify", include_secrets=True)
        if config.get("status") == "disabled":
            return "", ""
        key = str(config.get("api_key") or "").strip()
        if key:
            return str(config.get("base_url") or default_url).strip(), key
    except Exception:
        pass
    return (
        str(_setting("CADU_DIFY_BASE_URL") or default_url).strip(),
        str(_setting("CADU_DIFY_API_KEY") or "").strip(),
    )


def resolve_cadu_chat_dify_configuration():
    """Resolve o runtime exclusivo de Conversas sem reutilizar o agente global."""
    default_url = "https://api.dify.ai/v1"
    try:
        config = get_configuration("dify_cadu_chat", include_secrets=True)
        if config.get("status") == "disabled":
            return "", ""
        key = str(config.get("api_key") or "").strip()
        if key:
            return str(config.get("base_url") or default_url).strip(), key
    except Exception:
        pass
    return (
        str(_setting("CADU_CONVERSATIONS_V2_DIFY_URL") or default_url).strip(),
        str(_setting("CADU_CONVERSATIONS_V2_DIFY_KEY") or "").strip(),
    )


def _validate_dify(config):
    import requests

    base_url = str(config.get("base_url") or "https://api.dify.ai/v1").rstrip("/")
    key = str(config.get("api_key") or "").strip()
    try:
        response = requests.get(
            base_url + "/parameters",
            params={"user": "centralx-validation"},
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
            allow_redirects=False,
        )
    except requests.RequestException:
        return False, "Não foi possível validar a chave no Dify."
    if response.status_code in (401, 403):
        return False, "A credencial Dify não foi aceita."
    if response.status_code >= 400:
        return False, "O Dify recusou a validação da credencial."
    return True, "Credencial Dify aceita. Conversas Cadu estão prontas para uso."


def _validate_firecrawl(config):
    import requests

    key = str(config.get("api_key") or "").strip()
    try:
        response = requests.get(
            "https://api.firecrawl.dev/v2/team/credit-usage",
            headers={"Authorization": f"Bearer {key}"},
            timeout=15,
        )
    except requests.RequestException:
        return False, "Não foi possível validar a chave no Firecrawl."
    if response.status_code in (401, 403):
        return False, "A credencial Firecrawl não foi aceita."
    if response.status_code == 402:
        return False, "O saldo da conta Firecrawl é insuficiente."
    if response.status_code >= 400:
        return False, "O Firecrawl recusou a validação da chave."
    remaining = None
    try:
        remaining = (response.json() or {}).get("data", {}).get("remainingCredits")
    except ValueError:
        remaining = None
    if remaining is None:
        return True, "Credencial Firecrawl aceita. Places, Planner e CRM já podem buscar referências."
    return True, (
        f"Credencial Firecrawl aceita. Créditos restantes: {remaining}."
    )


def resolve_brevo_api_key() -> str:
    """Retorna a chave Brevo ativa, priorizando o cofre criptografado."""
    try:
        config = get_configuration("brevo", include_secrets=True)
        if config.get("status") == "disabled":
            return ""
        key = str(config.get("api_key") or "").strip()
        if key:
            return key
    except Exception:
        pass
    return str(_setting("BREVO_API_KEY") or "").strip()


def resolve_brevo_webhook_token() -> str:
    """Token exclusivo usado para autenticar eventos recebidos da Brevo."""
    try:
        config = get_configuration("brevo", include_secrets=True)
        if config.get("status") == "disabled":
            return ""
        token = str(config.get("webhook_token") or "").strip()
        if token:
            return token
    except Exception:
        pass
    return str(_setting("BREVO_WEBHOOK_TOKEN") or "").strip()


def _validate_brevo(config):
    import requests

    key = str(config.get("api_key") or "").strip()
    try:
        response = requests.get(
            "https://api.brevo.com/v3/account",
            headers={"accept": "application/json", "api-key": key},
            timeout=15,
        )
    except requests.RequestException:
        return False, "Não foi possível validar a chave na Brevo."
    if response.status_code in (401, 403):
        return False, "A credencial Brevo não foi aceita."
    if response.status_code == 429:
        return False, "A Brevo limitou a validação. Aguarde e tente de novo."
    if response.status_code >= 400:
        return False, "A Brevo recusou a validação da chave."
    return True, "Credencial Brevo aceita. Os envios transacionais estão prontos."


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
    if provider.startswith("google_") and config.get("redirect_uri"):
        parsed = urlparse(config["redirect_uri"])
        if parsed.scheme not in ("https", "http") or not parsed.netloc:
            raise IntegrationCredentialError("Redirect URI do Google inválida.")
        if parsed.scheme != "https" and parsed.hostname not in ("localhost", "127.0.0.1"):
            raise IntegrationCredentialError(
                "O redirect Google deve usar HTTPS fora do ambiente local."
            )
        if provider == "google_workspace":
            auth_url = urlparse(str(current_app.config.get("AUTH_URL") or ""))
            auth_host = (auth_url.hostname or "").lower()
            if (parsed.path != "/auth/google/workspace/callback" or parsed.query or parsed.fragment):
                raise IntegrationCredentialError(
                    "Use a rota /auth/google/workspace/callback como URL de retorno do Google Workspace."
                )
            if auth_host:
                try:
                    parsed_port = parsed.port or (443 if parsed.scheme == "https" else 80)
                    auth_port = auth_url.port or (443 if auth_url.scheme == "https" else 80)
                except ValueError as exc:
                    raise IntegrationCredentialError("A porta da URL de retorno Google é inválida.") from exc
                if (parsed.hostname or "").lower() != auth_host or parsed_port != auth_port:
                    raise IntegrationCredentialError(
                        "A URL de retorno Google Workspace precisa usar o domínio Auth configurado."
                    )
    if provider == "dify" and config.get("base_url"):
        parsed = urlparse(config["base_url"])
        if parsed.scheme != "https" or not parsed.hostname:
            raise IntegrationCredentialError("O endereço Dify deve usar HTTPS.")


def _schema(provider):
    if provider not in PROVIDERS:
        raise IntegrationCredentialError("Integração não suportada.")
    return PROVIDERS[provider]
