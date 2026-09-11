"""Cliente HTTP da API D4Sign usado pela mesa de assinaturas."""

from __future__ import annotations

import logging
from urllib.parse import urlencode

import requests


logger = logging.getLogger(__name__)

PRODUCTION_API = "https://secure.d4sign.com.br/api/v1"
SANDBOX_API = "https://sandbox.d4sign.com.br/api/v1"
PRODUCTION_EMBED = "https://secure.d4sign.com.br/embed/viewblob"
SANDBOX_EMBED = "https://sandbox.d4sign.com.br/embed/viewblob"


class D4SignError(RuntimeError):
    pass


class D4SignClient:
    def __init__(self, token_api, crypt_key, ambiente="producao", timeout=30):
        self.token_api = str(token_api or "").strip()
        self.crypt_key = str(crypt_key or "").strip()
        self.ambiente = "sandbox" if str(ambiente or "").lower() == "sandbox" else "producao"
        self.timeout = timeout
        if not self.token_api or not self.crypt_key:
            raise D4SignError("Informe tokenAPI e cryptKey da D4Sign.")

    @classmethod
    def from_config(cls, config):
        return cls(
            config.get("token_api"),
            config.get("crypt_key"),
            config.get("ambiente") or "producao",
        )

    @property
    def base_url(self):
        return SANDBOX_API if self.ambiente == "sandbox" else PRODUCTION_API

    @property
    def embed_host(self):
        return SANDBOX_EMBED if self.ambiente == "sandbox" else PRODUCTION_EMBED

    def _url(self, path, extra=None):
        query = {"tokenAPI": self.token_api, "cryptKey": self.crypt_key}
        if extra:
            query.update(extra)
        return f"{self.base_url}{path}?{urlencode(query)}"

    def _raise(self, response, fallback):
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        message = (
            payload.get("message")
            or payload.get("error")
            or payload.get("msg")
            or response.text
            or fallback
        )
        if isinstance(message, list):
            message = "; ".join(str(item) for item in message)
        raise D4SignError(str(message)[:400])

    def _request(self, method, path, **kwargs):
        url = self._url(path)
        try:
            response = requests.request(method, url, timeout=self.timeout, **kwargs)
        except requests.RequestException as exc:
            raise D4SignError("Não foi possível falar com a D4Sign.") from exc
        if response.status_code in (401, 403):
            raise D4SignError("A D4Sign recusou a credencial.")
        if response.status_code >= 400:
            self._raise(response, "A D4Sign recusou a requisição.")
        if not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    def list_safes(self):
        payload = self._request("GET", "/safes")
        rows = payload if isinstance(payload, list) else payload.get("safes") or []
        safes = []
        for item in rows or []:
            if not isinstance(item, dict):
                continue
            uuid = str(
                item.get("uuid_safe")
                or item.get("uuid-safe")
                or item.get("uuid")
                or ""
            ).strip()
            name = str(
                item.get("name-safe")
                or item.get("name_safe")
                or item.get("name")
                or item.get("nome")
                or uuid
            ).strip()
            if uuid:
                safes.append({"uuid": uuid, "name": name})
        return safes

    def upload_document(self, safe_uuid, pdf_bytes, filename, workflow=0):
        files = {"file": (filename, pdf_bytes, "application/pdf")}
        data = {"workflow": "1" if int(workflow or 0) else "0"}
        payload = self._request(
            "POST",
            f"/documents/{safe_uuid}/upload",
            files=files,
            data=data,
        )
        uuid = _first(payload, "uuid", "uuid_document", "uuidDoc")
        if not uuid:
            raise D4SignError("A D4Sign não devolveu o UUID do documento.")
        return {"uuid": uuid, "raw": payload}

    def create_signers(self, document_uuid, signers):
        body = {
            "signers": [
                {
                    "email": signer["email"],
                    "act": "1",
                    "foreign": "0",
                    "certificadoicpbr": "0",
                    "assinatura_presencial": "0",
                    "embed_methodauth": "email",
                    "skipemail": "1",
                }
                for signer in signers
            ]
        }
        payload = self._request("POST", f"/documents/{document_uuid}/createlist", json=body)
        return _parse_signers(payload)

    def send_to_sign(self, document_uuid, skip_email=True, workflow=0, message=""):
        body = {
            "skip_email": "1" if skip_email else "0",
            "workflow": "1" if int(workflow or 0) else "0",
            "message": message or "",
        }
        return self._request("POST", f"/documents/{document_uuid}/sendtosigner", json=body)

    def register_webhook(self, document_uuid, url):
        return self._request(
            "POST",
            f"/documents/{document_uuid}/webhooks",
            json={"url": url},
        )

    def get_document(self, document_uuid):
        return self._request("GET", f"/documents/{document_uuid}")

    def cancel_document(self, document_uuid):
        return self._request("POST", f"/documents/{document_uuid}/cancel")

    def embed_url(self, document_uuid, signer_email, key_signer=""):
        query = {
            "email": signer_email or "",
            "disable_preview": "0",
        }
        if key_signer:
            query["key_signer"] = key_signer
        return f"{self.embed_host}/{document_uuid}?{urlencode(query)}"


def _first(payload, *keys):
    if not isinstance(payload, dict):
        return ""
    for key in keys:
        value = payload.get(key)
        if value:
            return str(value).strip()
    return ""


def _parse_signers(payload):
    rows = payload
    if isinstance(payload, dict):
        rows = payload.get("signers") or payload.get("list") or [payload]
    parsed = []
    for item in rows or []:
        if not isinstance(item, dict):
            continue
        email = str(item.get("email") or "").strip().lower()
        if not email:
            continue
        parsed.append({
            "email": email,
            "key_signer": str(item.get("key_signer") or item.get("key") or "").strip(),
            "status": str(item.get("status") or "").strip(),
        })
    return parsed
