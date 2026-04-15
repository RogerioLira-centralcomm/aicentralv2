"""
Cliente Display & Video 360 (API v4 + OAuth refresh token).

Variáveis de ambiente (.env), alinhadas ao hub PHP:
  DV360_CLIENT_ID, DV360_CLIENT_SECRET, DV360_REFRESH_TOKEN,
  DV360_PARTNER_ID, DV360_API_BASE_URL (opcional, default v4),
  DV360_TIMEOUT (opcional, segundos).

Teste no terminal (exit 0 = OK): ``python scripts/verify_dv360.py``
ou ``flask --app run.py dv360-verify`` (na raiz do repo).
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any, Mapping, Optional

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

logger = logging.getLogger(__name__)

DV360_SCOPES = ("https://www.googleapis.com/auth/display-video",)

DV360_ENDPOINTS = (
    "googleAudiences",
    "firstPartyAndPartnerAudiences",
    "combinedAudiences",
    "customLists",
)

# Filtro para bulkList em line items: geo + cidade + postal + país + listas + proximidade + POI + cadeias.
# Sem cidade/postal/país, muitas contas devolviam praça vazia apesar de targeting local nos LIs.
_DV360_LINE_ITEM_LOCATION_FILTER = (
    'targetingType="TARGETING_TYPE_GEO_REGION" OR '
    'targetingType="TARGETING_TYPE_CITY" OR '
    'targetingType="TARGETING_TYPE_POSTAL_CODE" OR '
    'targetingType="TARGETING_TYPE_COUNTRY" OR '
    'targetingType="TARGETING_TYPE_REGIONAL_LOCATION_LIST" OR '
    'targetingType="TARGETING_TYPE_PROXIMITY_LOCATION_LIST" OR '
    'targetingType="TARGETING_TYPE_POI" OR '
    'targetingType="TARGETING_TYPE_BUSINESS_CHAIN"'
)
# Fallback se a API v4 rejeitar algum tipo do filtro alargado (HTTP 400).
_DV360_LINE_ITEM_LOCATION_FILTER_LEGACY = (
    'targetingType="TARGETING_TYPE_GEO_REGION" OR '
    'targetingType="TARGETING_TYPE_REGIONAL_LOCATION_LIST" OR '
    'targetingType="TARGETING_TYPE_PROXIMITY_LOCATION_LIST" OR '
    'targetingType="TARGETING_TYPE_POI"'
)


class DV360API:
    """Port Python da classe PHP DV360API (refresh OAuth + REST)."""

    def __init__(self, config: Mapping[str, Any]):
        self.client_id = (config.get("DV360_CLIENT_ID") or "").strip()
        self.client_secret = (config.get("DV360_CLIENT_SECRET") or "").strip()
        self.refresh_token = (config.get("DV360_REFRESH_TOKEN") or "").strip()
        self.partner_id = (config.get("DV360_PARTNER_ID") or "").strip()
        self.api_base = (config.get("DV360_API_BASE_URL") or "https://displayvideo.googleapis.com/v4").rstrip("/")
        self.timeout = int(config.get("DV360_TIMEOUT") or 30)
        self._oauth_creds: Optional[Credentials] = None

    def is_configured(self) -> bool:
        return bool(
            self.client_secret
            and self.client_secret != "COLE_SEU_NOVO_CLIENT_SECRET_AQUI"
            and self.refresh_token
            and self.refresh_token != "COLE_SEU_REFRESH_TOKEN_AQUI"
        )

    def get_access_token(self) -> Optional[str]:
        if not self.is_configured():
            return None
        try:
            if self._oauth_creds is None:
                self._oauth_creds = Credentials(
                    token=None,
                    refresh_token=self.refresh_token,
                    token_uri="https://oauth2.googleapis.com/token",
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    scopes=DV360_SCOPES,
                )
            if not self._oauth_creds.valid:
                self._oauth_creds.refresh(Request())
            return self._oauth_creds.token or None
        except Exception as e:
            logger.error("DV360 OAuth refresh failed: %s", e)
            return None

    def verify_installation(self, *, list_advertisers: bool = True) -> dict[str, Any]:
        """
        Verificação ponta-a-ponta para CLI/CI (sem imprimir segredos).

        Retorno: ``ok`` (bool), ``messages`` (linhas legíveis), ``step_failed``,
        ``details`` (resumos de connection/advertisers).
        """
        out: dict[str, Any] = {
            "ok": False,
            "messages": [],
            "step_failed": None,
            "details": {},
        }
        if not self.client_id:
            out["step_failed"] = "configure"
            out["messages"].append("configure: FALTA DV360_CLIENT_ID")
            return out
        if not self.is_configured():
            out["step_failed"] = "configure"
            out["messages"].append(
                "configure: FALTA client_secret/refresh_token válidos (ou ainda placeholders no .env)"
            )
            return out
        out["messages"].append("configure: OK (credenciais OAuth presentes)")
        if not self.partner_id and list_advertisers:
            out["step_failed"] = "configure"
            out["messages"].append("configure: FALTA DV360_PARTNER_ID (necessário para list_advertisers)")
            return out

        conn = self.test_connection()
        out["details"]["connection"] = {
            k: conn.get(k) for k in ("success", "error", "message", "token_preview") if k in conn
        }
        if not conn.get("success"):
            out["step_failed"] = "oauth"
            out["messages"].append(f"oauth: FALHA — {conn.get('error', 'desconhecido')}")
            return out
        out["messages"].append("oauth: OK (access token obtido junto ao Google)")

        if not list_advertisers:
            out["ok"] = True
            out["messages"].append("api: ignorado (--oauth-only)")
            return out

        adv = self.list_advertisers([], test_all=False)
        out["details"]["advertisers"] = {
            "success": adv.get("success"),
            "http_code": adv.get("http_code"),
            "url_used": adv.get("url_used"),
        }
        if not adv.get("success"):
            out["step_failed"] = "advertisers"
            err = adv.get("error", "desconhecido")
            out["messages"].append(f"advertisers: FALHA — {err}")
            return out
        data = adv.get("data") or {}
        n = len(data.get("advertisers") or [])
        out["messages"].append(f"advertisers: OK ({n} anunciantes no partner {self.partner_id})")
        out["ok"] = True
        return out

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get_json(self, url: str, token: str) -> dict[str, Any]:
        try:
            r = requests.get(url, headers=self._headers(token), timeout=self.timeout)
        except requests.RequestException as e:
            return {
                "http_code": 0,
                "request_error": str(e),
                "text": "",
                "data": None,
            }
        text = r.text or ""
        parsed = None
        try:
            parsed = r.json()
        except ValueError:
            pass
        return {
            "http_code": r.status_code,
            "request_error": None,
            "text": text,
            "data": parsed,
        }

    def _patch_json(self, url: str, token: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            r = requests.patch(
                url,
                headers=self._headers(token),
                json=body,
                timeout=self.timeout,
            )
        except requests.RequestException as e:
            return {
                "http_code": 0,
                "request_error": str(e),
                "text": "",
                "data": None,
            }
        text = r.text or ""
        parsed = None
        try:
            parsed = r.json()
        except ValueError:
            pass
        return {
            "http_code": r.status_code,
            "request_error": None,
            "text": text,
            "data": parsed,
        }

    def get_audience_data(self, audience_id: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "error": (
                    "Falha ao obter Access Token. Verifique se seu Client Secret e "
                    "Refresh Token estão corretos e válidos."
                ),
                "http_code": 0,
            }
        for endpoint in DV360_ENDPOINTS:
            url = f"{self.api_base}/{endpoint}/{audience_id}"
            res = self._get_json(url, token)
            code = res["http_code"]
            if code == 200 and res["data"] is not None:
                return {
                    "success": True,
                    "data": res["data"],
                    "endpoint": endpoint,
                    "http_code": 200,
                }
            if code == 404:
                continue
            if code != 200:
                return {
                    "success": False,
                    "error": (
                        f"Erro ao chamar a API para o endpoint '{endpoint}'. Verifique se a "
                        "'Display & Video 360 API' está ativa em seu projeto no Google Cloud e se sua conta tem permissão."
                    ),
                    "error_details": res["data"],
                    "http_code": code,
                    "endpoint": endpoint,
                }
        return {
            "success": False,
            "error": (
                f"O ID de audiência '{audience_id}' não foi encontrado em nenhum dos tipos de audiência testados "
                "(Google, First/Third Party, Combinada, Customizada). Verifique o ID e se ele pertence ao anunciante correto."
            ),
            "http_code": 404,
        }

    def list_audiences(
        self,
        endpoint_type: str,
        advertiser_id: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
        test_all: bool = False,
    ) -> dict[str, Any]:
        params = dict(params or {})
        token = self.get_access_token()
        debug_info: dict[str, Any] = {
            "endpoint_type": endpoint_type,
            "advertiser_id_received": advertiser_id,
            "advertiser_id_type": type(advertiser_id).__name__,
            "advertiser_id_empty": not advertiser_id,
            "advertiser_id_trimmed": str(advertiser_id).strip() if advertiser_id else None,
        }
        if not token:
            return {
                "success": False,
                "error": (
                    "Falha ao obter Access Token. Verifique se seu Client Secret e "
                    "Refresh Token estão corretos e válidos."
                ),
                "http_code": 0,
                "debug": debug_info,
            }
        if not self.partner_id:
            return {
                "success": False,
                "error": "DV360_PARTNER_ID não configurado.",
                "http_code": 0,
                "debug": debug_info,
            }
        partner_id = self.partner_id
        endpoint_v4 = endpoint_type
        endpoint_v1_v2 = (
            "firstAndThirdPartyAudiences"
            if endpoint_type == "firstPartyAndPartnerAudiences"
            else endpoint_type
        )
        urls_to_test: dict[str, str] = {}
        if endpoint_type in (
            "googleAudiences",
            "firstPartyAndPartnerAudiences",
            "combinedAudiences",
        ):
            if test_all:
                urls_to_test = {
                    "v4_global": f"https://displayvideo.googleapis.com/v4/{endpoint_v4}",
                    "v2_global": f"https://displayvideo.googleapis.com/v2/{endpoint_v1_v2}",
                    "v1_global": f"https://displayvideo.googleapis.com/v1/{endpoint_v1_v2}",
                }
            else:
                urls_to_test = {"v4_global": f"https://displayvideo.googleapis.com/v4/{endpoint_v4}"}
        elif advertiser_id:
            aid = str(advertiser_id).strip()
            debug_info["advertiser_id_str"] = aid
            debug_info["advertiser_id_length"] = len(aid)
            if test_all:
                urls_to_test = {
                    "v4_path": f"https://displayvideo.googleapis.com/v4/advertisers/{aid}/{endpoint_v4}",
                    "v2_path": f"https://displayvideo.googleapis.com/v2/advertisers/{aid}/{endpoint_v1_v2}",
                    "v1_path": f"https://displayvideo.googleapis.com/v1/advertisers/{aid}/{endpoint_v1_v2}",
                }
            else:
                urls_to_test = {
                    "v4_path": f"https://displayvideo.googleapis.com/v4/advertisers/{aid}/{endpoint_v4}",
                }
        else:
            endpoint_v2 = (
                "firstAndThirdPartyAudiences"
                if endpoint_type == "firstPartyAndPartnerAudiences"
                else endpoint_type
            )
            if test_all:
                urls_to_test = {
                    "v4_direct": f"https://displayvideo.googleapis.com/v4/{endpoint_v4}",
                    "v2_direct": f"https://displayvideo.googleapis.com/v2/{endpoint_v2}",
                }
            else:
                urls_to_test = {
                    "v4_direct": f"https://displayvideo.googleapis.com/v4/{endpoint_v4}",
                }

        safe_qp: list[str] = [f"partnerId={partner_id}"]
        for key, value in params.items():
            lk = str(key).lower()
            if key == "partnerId" or key == "partner_id" or "partner" in lk:
                continue
            from urllib.parse import quote

            safe_qp.append(f"{quote(str(key), safe='')}={quote(str(value), safe='')}")

        query = "&".join(safe_qp)
        test_results: list[dict[str, Any]] = []
        first_success: Optional[dict[str, Any]] = None

        for test_name, base_url in urls_to_test.items():
            api_url = f"{base_url}?{query}"
            res = self._get_json(api_url, token)
            code = res["http_code"]
            text = res["text"] or ""
            req_err = res["request_error"]
            is_html = "<!DOCTYPE html>" in text or "<html" in text.lower()
            preview = text[:500]
            row: dict[str, Any] = {
                "test_name": test_name,
                "url": api_url,
                "http_code": code,
                "curl_error": req_err,
                "is_html": is_html,
                "content_type": None,
                "response_length": len(text),
                "response_preview": preview,
                "success": bool(code == 200 and not req_err and not is_html),
            }
            if code == 200 and not req_err and not is_html and isinstance(res["data"], dict):
                data = res["data"]
                row["data"] = data
                n = 0
                for k in (
                    "googleAudiences",
                    "firstPartyAndPartnerAudiences",
                    "firstAndThirdPartyAudiences",
                    "combinedAudiences",
                    "customLists",
                ):
                    if k in data and isinstance(data[k], list):
                        n = len(data[k])
                        break
                if n == 0 and isinstance(data, list) and data and isinstance(data[0], dict):
                    n = len(data)
                row["audiences_count"] = n
                if first_success is None:
                    first_success = row
            elif code != 0:
                row["error_details"] = res["data"]
                if isinstance(res["data"], dict):
                    err = res["data"].get("error") or {}
                    if isinstance(err, dict) and err.get("message"):
                        row["error_message"] = err["message"]
            test_results.append(row)

        if test_all:
            ok = first_success is not None
            return {
                "success": ok,
                "test_mode": True,
                "test_results": test_results,
                "total_tests": len(test_results),
                "successful_tests": sum(1 for r in test_results if r.get("success")),
                "best_result": first_success,
                "endpoint": endpoint_type,
                "advertiser_id": advertiser_id,
                "partner_id_used": partner_id,
            }

        if first_success and isinstance(first_success.get("data"), dict):
            data = first_success["data"]
            audiences: list[Any] = []
            for k in (
                "googleAudiences",
                "firstPartyAndPartnerAudiences",
                "firstAndThirdPartyAudiences",
                "combinedAudiences",
                "customLists",
            ):
                if k in data and isinstance(data[k], list):
                    audiences = data[k]
                    break
            return {
                "success": True,
                "data": data,
                "audiences": audiences,
                "http_code": 200,
                "endpoint": endpoint_type,
                "url_used": first_success["url"],
                "urls_tested": [
                    {"url": r["url"], "http_code": r["http_code"], "success": r["success"]}
                    for r in test_results
                ],
                "debug": debug_info,
            }

        if not advertiser_id:
            return {
                "success": False,
                "error": (
                    f"Este endpoint requer um advertiserId. O tipo '{endpoint_type}' precisa do ID do anunciante no caminho da URL."
                ),
                "http_code": 400,
                "endpoint": endpoint_type,
                "test_results": test_results,
                "debug": debug_info,
            }
        return {
            "success": False,
            "error": f"Não foi possível listar audiências do tipo '{endpoint_type}'. Nenhuma URL funcionou.",
            "http_code": 404,
            "endpoint": endpoint_type,
            "advertiserId_used": advertiser_id,
            "test_results": test_results,
            "debug": debug_info,
        }

    def _process_audience_data(self, data: Any, endpoint_type: str) -> Any:
        if not data or not isinstance(data, dict):
            return []
        type_keys = {
            "googleAudiences": "googleAudiences",
            "firstPartyAndPartnerAudiences": "firstPartyAndPartnerAudiences",
            "firstAndThirdPartyAudiences": "firstAndThirdPartyAudiences",
            "combinedAudiences": "combinedAudiences",
            "customLists": "customLists",
        }
        audiences_list: list[Any] = []
        if endpoint_type in type_keys and type_keys[endpoint_type] in data:
            v = data[type_keys[endpoint_type]]
            audiences_list = v if isinstance(v, list) else []
        if not audiences_list and isinstance(data.get("audiences"), list):
            audiences_list = data["audiences"]
        if not audiences_list and isinstance(data, list):
            audiences_list = data  # type: ignore[assignment]
        if not audiences_list:
            for _k, value in data.items():
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    audiences_list = value
                    break
        if not audiences_list:
            return data
        return {"audiences": audiences_list, "count": len(audiences_list), "raw_data": data}

    def list_all_audiences(self, advertiser_id: Optional[str] = None) -> dict[str, Any]:
        if not self.get_access_token():
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        all_audiences: dict[str, Any] = {}
        errors: dict[str, Any] = {}
        for endpoint in DV360_ENDPOINTS:
            if not advertiser_id:
                result = self.list_audiences(endpoint, None)
                if not result["success"]:
                    err_msg = result.get("error") or ""
                    err_details = result.get("error_details") or {}
                    needs_adv = False
                    if isinstance(err_details, dict):
                        inner = err_details.get("error") or {}
                        if isinstance(inner, dict) and inner.get("message"):
                            em = str(inner["message"]).lower()
                            if "advertiser" in em or "required" in em or result.get("http_code") == 400:
                                needs_adv = True
                    if needs_adv:
                        errors[endpoint] = "Este tipo requer um advertiserId. Use o filtro de anunciante."
                    else:
                        errors[endpoint] = err_msg
                else:
                    all_audiences[endpoint] = result["data"]
            else:
                result = self.list_audiences(endpoint, advertiser_id)
                if result["success"]:
                    processed = self._process_audience_data(result.get("data"), endpoint)
                    all_audiences[endpoint] = processed
                    if result.get("url_used"):
                        all_audiences[f"{endpoint}_debug"] = {
                            "url_used": result["url_used"],
                            "endpoint": endpoint,
                        }
                else:
                    errors[endpoint] = result.get("error")
                    if result.get("error_details"):
                        errors[f"{endpoint}_details"] = result["error_details"]
                    if result.get("url_tried"):
                        errors[f"{endpoint}_url"] = result["url_tried"]
                    if result.get("debug"):
                        errors[f"{endpoint}_debug"] = result["debug"]
        return {
            "success": bool(all_audiences),
            "audiences": all_audiences,
            "errors": errors,
            "total_types": len(DV360_ENDPOINTS),
            "successful_types": len(all_audiences),
            "advertiser_id": advertiser_id,
        }

    def list_partners(self, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        params = dict(params or {})
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        if "pageSize" not in params:
            params["pageSize"] = 100
        urls_to_try = [
            "https://displayvideo.googleapis.com/v4/partners",
            "https://displayvideo.googleapis.com/v2/partners",
            f"{self.api_base}/partners",
        ]
        from urllib.parse import urlencode

        for base_url in urls_to_try:
            api_url = base_url + (("?" + urlencode(params)) if params else "")
            res = self._get_json(api_url, token)
            if res["request_error"]:
                continue
            code = res["http_code"]
            if code == 200 and isinstance(res["data"], dict):
                return {"success": True, "data": res["data"], "http_code": 200, "url_used": api_url}
            if code != 404:
                return {
                    "success": False,
                    "error": f"Erro HTTP {code} ao listar partners",
                    "error_details": res["data"],
                    "http_code": code,
                    "url_tried": api_url,
                }
        return {
            "success": False,
            "error": (
                "Não foi possível listar partners. Todos os endpoints retornaram 404. Isso pode indicar que: "
                "1) Sua conta não tem acesso a partners, 2) Suas permissões não incluem acesso a partners, "
                "ou 3) O endpoint não está disponível para sua conta."
            ),
            "error_details": {"urls_tried": urls_to_try, "suggestion": "Você pode tentar listar anunciantes diretamente sem usar partners"},
            "http_code": 404,
        }

    def list_advertisers(
        self,
        params: Optional[dict[str, Any]] = None,
        test_all: bool = False,
    ) -> dict[str, Any]:
        params = dict(params or {})
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        if not self.partner_id:
            return {"success": False, "error": "DV360_PARTNER_ID não configurado.", "http_code": 0}
        partner_id = self.partner_id
        safe_params: dict[str, Any] = {}
        if params.get("pageSize") and int(params["pageSize"]) > 0:
            safe_params["pageSize"] = int(params["pageSize"])
        else:
            safe_params["pageSize"] = 100
        if params.get("pageToken"):
            safe_params["pageToken"] = params["pageToken"]
        urls_to_test = {
            "v4_direct": {
                "base": "https://displayvideo.googleapis.com/v4/advertisers",
                "params": {"partnerId": partner_id, "pageSize": safe_params["pageSize"]},
            },
            "v4_filter": {
                "base": "https://displayvideo.googleapis.com/v4/advertisers",
                "params": {"filter": f'partnerId="{partner_id}"', "pageSize": safe_params["pageSize"]},
            },
            "v4_partners_path": {
                "base": f"https://displayvideo.googleapis.com/v4/partners/{partner_id}/advertisers",
                "params": {"pageSize": safe_params["pageSize"]},
            },
            "v2_direct": {
                "base": "https://displayvideo.googleapis.com/v2/advertisers",
                "params": {"partnerId": partner_id, "pageSize": safe_params["pageSize"]},
            },
            "v2_filter": {
                "base": "https://displayvideo.googleapis.com/v2/advertisers",
                "params": {"filter": f'partnerId="{partner_id}"', "pageSize": safe_params["pageSize"]},
            },
            "v1_direct": {
                "base": "https://displayvideo.googleapis.com/v1/advertisers",
                "params": {"partnerId": partner_id, "pageSize": safe_params["pageSize"]},
            },
        }
        from urllib.parse import urlencode

        test_results: list[dict[str, Any]] = []
        first_success: Optional[dict[str, Any]] = None
        for test_name, cfg in urls_to_test.items():
            qp = dict(cfg["params"])
            if "pageToken" in safe_params:
                qp["pageToken"] = safe_params["pageToken"]
            api_url = cfg["base"] + "?" + urlencode(qp)
            res = self._get_json(api_url, token)
            text = res["text"] or ""
            code = res["http_code"]
            req_err = res["request_error"]
            is_html = "<!DOCTYPE html>" in text or "<html" in text.lower()
            row: dict[str, Any] = {
                "test_name": test_name,
                "url": api_url,
                "http_code": code,
                "curl_error": req_err,
                "is_html": is_html,
                "response_length": len(text),
                "response_preview": text[:500],
                "success": bool(code == 200 and not req_err and not is_html),
            }
            if code == 200 and not req_err and not is_html and isinstance(res["data"], dict):
                data = res["data"]
                row["data"] = data
                row["advertisers_count"] = len(data.get("advertisers") or [])
                if first_success is None:
                    first_success = row
            elif code != 0:
                row["error_details"] = res["data"]
                if isinstance(res["data"], dict):
                    err = res["data"].get("error") or {}
                    if isinstance(err, dict) and err.get("message"):
                        row["error_message"] = err["message"]
            test_results.append(row)

        if test_all:
            return {
                "success": first_success is not None,
                "test_mode": True,
                "test_results": test_results,
                "total_tests": len(test_results),
                "successful_tests": sum(1 for r in test_results if r.get("success")),
                "best_result": first_success,
                "partner_id_used": partner_id,
            }
        if first_success:
            return {
                "success": True,
                "data": first_success["data"],
                "http_code": 200,
                "url_used": first_success["url"],
                "partner_id_used": partner_id,
            }
        return {
            "success": False,
            "error": "Nenhuma URL funcionou. Verifique os resultados dos testes.",
            "http_code": 404,
            "test_results": test_results,
            "partner_id_used": partner_id,
        }

    def test_connection(self) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "success": False,
                "error": "Configuração incompleta. Por favor, preencha CLIENT_SECRET e REFRESH_TOKEN (variáveis de ambiente DV360_*).",
            }
        token = self.get_access_token()
        if not token:
            return {
                "success": False,
                "error": "Falha ao obter Access Token. Verifique suas credenciais.",
            }
        return {
            "success": True,
            "message": "Conexão estabelecida com sucesso! Access Token obtido.",
            "token_preview": token[:20] + "...",
        }

    @staticmethod
    def infer_campaign_lifecycle_pt(campaign: Optional[dict[str, Any]]) -> dict[str, Any]:
        """
        Situação legível: combina `entityStatus` (API) com datas do voo em `campaignFlight.plannedDates`.

        Isto explica casos como campanha ainda ACTIVE na API mas com voo já em 2022 — mostramos "Finalizada".
        """
        today = date.today()
        out: dict[str, Any] = {
            "code": "UNKNOWN",
            "label_pt": "Estado desconhecido",
            "entity_status": None,
            "flight_start": None,
            "flight_end": None,
            "hint_pt": None,
        }
        if not campaign or not isinstance(campaign, dict):
            return out

        es = campaign.get("entityStatus") if campaign.get("entityStatus") is not None else campaign.get("entity_status")
        es_s = str(es).strip() if es is not None else ""
        out["entity_status"] = es_s or None

        def _parse_date(d: Any) -> Optional[date]:
            if not isinstance(d, dict):
                return None
            try:
                return date(int(d["year"]), int(d["month"]), int(d["day"]))
            except (KeyError, TypeError, ValueError):
                return None

        start_d: Optional[date] = None
        end_d: Optional[date] = None
        cf = campaign.get("campaignFlight")
        if isinstance(cf, dict):
            pd = cf.get("plannedDates")
            if isinstance(pd, dict):
                start_d = _parse_date(pd.get("startDate"))
                end_d = _parse_date(pd.get("endDate"))
        if start_d:
            out["flight_start"] = start_d.isoformat()
        if end_d:
            out["flight_end"] = end_d.isoformat()

        if es_s == "ENTITY_STATUS_ARCHIVED":
            out["code"] = "ARCHIVED"
            out["label_pt"] = "Arquivada"
            return out
        if es_s == "ENTITY_STATUS_SCHEDULED_FOR_DELETION":
            out["code"] = "SCHEDULED_DELETION"
            out["label_pt"] = "Agendada para eliminação"
            return out
        if es_s == "ENTITY_STATUS_DRAFT":
            out["code"] = "DRAFT"
            out["label_pt"] = "Rascunho"
            return out
        if es_s == "ENTITY_STATUS_SCHEDULED_FOR_ACTIVE":
            out["code"] = "SCHEDULED_FOR_ACTIVE"
            out["label_pt"] = "Agendada para ativação"
            return out
        if es_s == "ENTITY_STATUS_PAUSED":
            out["code"] = "PAUSED"
            if end_d and end_d < today:
                out["label_pt"] = "Pausada (o período planejado do voo já terminou)"
            else:
                out["label_pt"] = "Pausada"
            return out

        # ACTIVE ou UNSPECIFIED: usar datas do voo quando existirem
        if end_d and end_d < today:
            out["code"] = "FINISHED_FLIGHT"
            if es_s == "ENTITY_STATUS_ACTIVE":
                out["label_pt"] = "Finalizada (voo já terminou)"
                out["hint_pt"] = (
                    "A API ainda pode marcar entityStatus ACTIVE; no DV360 pode arquivar ou pausar se quiser refletir o fim."
                )
            else:
                out["label_pt"] = "Finalizada (voo já terminou)"
            return out

        if start_d and start_d > today:
            out["code"] = "SCHEDULED_FLIGHT"
            out["label_pt"] = "Agendada (voo ainda não começou)"
            return out

        if start_d and end_d and start_d <= today <= end_d:
            out["code"] = "IN_FLIGHT"
            if es_s == "ENTITY_STATUS_ACTIVE":
                out["label_pt"] = "Ativa (dentro do período do voo)"
            else:
                out["label_pt"] = f"No período do voo ({es_s or 'estado API indefinido'})"
            return out

        if es_s == "ENTITY_STATUS_ACTIVE":
            out["code"] = "ACTIVE_NO_FLIGHT_WINDOW"
            out["label_pt"] = "Ativa na API (sem datas de voo no recurso para calcular fim/início)"
            return out

        out["code"] = "OTHER"
        out["label_pt"] = es_s or "Indefinido"
        return out

    def list_campaigns(self, advertiser_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Lista campanhas. Corrige `entityStatus` em falta ou UNSPECIFIED com GET da campanha
        (a listagem por vezes não devolve o mesmo estado que o recurso completo).
        """
        out = self._list_advertiser_child(advertiser_id, "campaigns", "campanhas", params)
        if not out.get("success"):
            return out
        data = out.get("data")
        if not isinstance(data, dict):
            return out
        camps = data.get("campaigns")
        if not isinstance(camps, list):
            return out
        aid = str(advertiser_id).strip()
        fixed = 0
        max_fix = 50
        for camp in camps:
            if fixed >= max_fix:
                break
            if not isinstance(camp, dict):
                continue
            if camp.get("entityStatus") is None and camp.get("entity_status"):
                camp["entityStatus"] = camp.get("entity_status")
            es = camp.get("entityStatus")
            if es is not None and str(es).strip() not in ("", "ENTITY_STATUS_UNSPECIFIED"):
                continue
            cid = str(camp.get("campaignId") or "").strip()
            if not cid:
                continue
            got = self.get_campaign(aid, cid)
            if not got.get("success"):
                continue
            full = got.get("data") or {}
            full_es = full.get("entityStatus")
            if full_es is not None and str(full_es).strip():
                camp["entityStatus"] = full_es
                fixed += 1
        for camp in camps:
            if isinstance(camp, dict):
                camp["lifecycle"] = DV360API.infer_campaign_lifecycle_pt(camp)
        return out

    def get_campaign(self, advertiser_id: str, campaign_id: str) -> dict[str, Any]:
        """GET um recurso Campaign (v4 advertisers.campaigns.get)."""
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        aid = str(advertiser_id).strip()
        cid = str(campaign_id).strip()
        if not aid or not cid:
            return {
                "success": False,
                "error": "advertiser_id e campaign_id são obrigatórios.",
                "http_code": 400,
            }
        api_url = f"{self.api_base}/advertisers/{aid}/campaigns/{cid}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro HTTP: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            return {"success": True, "data": res["data"], "http_code": 200, "url_used": api_url}
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao obter campanha",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def list_campaign_geo_assigned_options(
        self,
        advertiser_id: str,
        campaign_id: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Lista opções de targeting geo (praça / região) atribuídas à campanha.
        GET .../targetingTypes/TARGETING_TYPE_GEO_REGION/assignedTargetingOptions
        """
        params = dict(params or {})
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        aid = str(advertiser_id).strip()
        cid = str(campaign_id).strip()
        if not aid or not cid:
            return {
                "success": False,
                "error": "advertiser_id e campaign_id são obrigatórios.",
                "http_code": 400,
            }
        if "pageSize" not in params:
            params["pageSize"] = 200
        from urllib.parse import urlencode

        ttype = "TARGETING_TYPE_GEO_REGION"
        base = f"{self.api_base}/advertisers/{aid}/campaigns/{cid}/targetingTypes/{ttype}/assignedTargetingOptions"
        api_url = base + ("?" + urlencode(params) if params else "")
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro HTTP: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            return {"success": True, "data": res["data"], "http_code": 200, "url_used": api_url}
        # Sem geo ao nível da campanha o DV360 costuma responder 404; tratar como lista vazia
        # para seguir com fallback (insertion orders / line items).
        if code == 404:
            return {
                "success": True,
                "data": {"assignedTargetingOptions": []},
                "http_code": 404,
                "url_used": api_url,
                "treated_as_empty": True,
            }
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao listar geo da campanha",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def list_insertion_order_geo_assigned_options(
        self,
        advertiser_id: str,
        insertion_order_id: str,
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Geo atribuída ao insertion order (muitas campanhas só têm targeting de região no IO).
        GET .../insertionOrders/{ioId}/targetingTypes/TARGETING_TYPE_GEO_REGION/assignedTargetingOptions
        """
        params = dict(params or {})
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        aid = str(advertiser_id).strip()
        ioid = str(insertion_order_id).strip()
        if not aid or not ioid:
            return {
                "success": False,
                "error": "advertiser_id e insertion_order_id são obrigatórios.",
                "http_code": 400,
            }
        if "pageSize" not in params:
            params["pageSize"] = 200
        from urllib.parse import urlencode

        ttype = "TARGETING_TYPE_GEO_REGION"
        base = (
            f"{self.api_base}/advertisers/{aid}/insertionOrders/{ioid}"
            f"/targetingTypes/{ttype}/assignedTargetingOptions"
        )
        api_url = base + ("?" + urlencode(params) if params else "")
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro HTTP: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            return {"success": True, "data": res["data"], "http_code": 200, "url_used": api_url}
        if code == 404:
            return {
                "success": True,
                "data": {"assignedTargetingOptions": []},
                "http_code": 404,
                "url_used": api_url,
                "treated_as_empty": True,
            }
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao listar geo do insertion order",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    @staticmethod
    def _geo_region_details_from_option(o: dict[str, Any]) -> Optional[dict[str, Any]]:
        """REST pode expor geoRegionDetails no topo ou dentro de `details` (oneof)."""
        det = o.get("geoRegionDetails")
        if isinstance(det, dict):
            return det
        details = o.get("details")
        if isinstance(details, dict):
            inner = details.get("geoRegionDetails")
            if isinstance(inner, dict):
                return inner
        return None

    @staticmethod
    def _details_union_dict(o: dict[str, Any], key: str) -> Optional[dict[str, Any]]:
        inner = o.get(key)
        if isinstance(inner, dict):
            return inner
        details = o.get("details")
        if isinstance(details, dict):
            inner2 = details.get(key)
            if isinstance(inner2, dict):
                return inner2
        return None

    @staticmethod
    def _location_label_from_assigned_option(o: dict[str, Any]) -> Optional[str]:
        """Texto legível de praça/local a partir de um AssignedTargetingOption (vários targetingType)."""
        det = DV360API._geo_region_details_from_option(o)
        if isinstance(det, dict):
            label = (
                det.get("displayName")
                or det.get("geoRegionDisplayName")
                or det.get("regionName")
                or det.get("geoRegionId")
                or det.get("regionId")
            )
            if not label and isinstance(det.get("geoRegion"), dict):
                gr = det["geoRegion"]
                label = gr.get("displayName") or gr.get("name") or gr.get("geoRegionId")
            if label is not None and str(label).strip():
                return str(label).strip()
        poi = o.get("poiDetails") or DV360API._details_union_dict(o, "poiDetails")
        if isinstance(poi, dict) and poi.get("displayName"):
            return str(poi["displayName"]).strip()
        city = o.get("cityDetails") or DV360API._details_union_dict(o, "cityDetails")
        if isinstance(city, dict):
            label = city.get("displayName") or city.get("name") or city.get("cityId")
            if label is not None and str(label).strip():
                return str(label).strip()
        postal = o.get("postalCodeDetails") or DV360API._details_union_dict(o, "postalCodeDetails")
        if isinstance(postal, dict):
            label = postal.get("displayName") or postal.get("postalCode")
            if label is not None and str(label).strip():
                return str(label).strip()
        country = o.get("countryDetails") or DV360API._details_union_dict(o, "countryDetails")
        if isinstance(country, dict):
            label = country.get("displayName") or country.get("countryCode")
            if label is not None and str(label).strip():
                return str(label).strip()
        chain = o.get("businessChainDetails") or DV360API._details_union_dict(o, "businessChainDetails")
        if isinstance(chain, dict):
            label = chain.get("displayName") or chain.get("businessChainId")
            if label is not None and str(label).strip():
                return str(label).strip()
        rll = o.get("regionalLocationListDetails") or DV360API._details_union_dict(
            o, "regionalLocationListDetails"
        )
        if isinstance(rll, dict) and rll.get("regionalLocationListId") is not None:
            lid = str(rll["regionalLocationListId"]).strip()
            neg = bool(rll.get("negative"))
            prefix = "Excluir lista regional " if neg else "Lista regional "
            return f"{prefix}#{lid}"
        pll = o.get("proximityLocationListDetails") or DV360API._details_union_dict(
            o, "proximityLocationListDetails"
        )
        if isinstance(pll, dict) and pll.get("proximityLocationListId") is not None:
            lid = str(pll["proximityLocationListId"]).strip()
            rad = pll.get("proximityRadius")
            unit = str(pll.get("proximityRadiusUnit") or "").replace("PROXIMITY_RADIUS_UNIT_", "")
            if rad is not None:
                return f"Proximidade (lista #{lid}, raio {rad} {unit})".strip()
            return f"Proximidade (lista #{lid})"
        toid = o.get("targetingOptionId")
        if toid is not None and str(toid).strip():
            return f"Targeting option {toid}"
        return None

    @staticmethod
    def summarize_location_assigned_options(data: Optional[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        """
        Praça / local a partir de:
        - resposta `assignedTargetingOptions` ou
        - `bulkListAssignedTargetingOptions` (`lineItemAssignedTargetingOptions`).
        """
        if not data or not isinstance(data, dict):
            return "—", []
        opts: list[dict[str, Any]] = []
        raw = data.get("assignedTargetingOptions")
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, dict):
                    opts.append(x)
        liato = data.get("lineItemAssignedTargetingOptions")
        if isinstance(liato, list):
            for wrap in liato:
                if not isinstance(wrap, dict):
                    continue
                inner = wrap.get("assignedTargetingOption")
                if isinstance(inner, dict):
                    merged = dict(inner)
                    if wrap.get("targetingType") and not merged.get("targetingType"):
                        merged["targetingType"] = wrap["targetingType"]
                    if wrap.get("targetingOptionId") and not merged.get("targetingOptionId"):
                        merged["targetingOptionId"] = wrap["targetingOptionId"]
                    opts.append(merged)
        if not opts:
            return "—", []
        names: list[str] = []
        regions: list[dict[str, Any]] = []
        seen: set[str] = set()
        for o in opts:
            label = DV360API._location_label_from_assigned_option(o)
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(label)
            regions.append(
                {
                    "displayName": label,
                    "assignedTargetingOptionId": o.get("assignedTargetingOptionId"),
                    "targetingType": o.get("targetingType"),
                }
            )
        summary = ", ".join(names) if names else "—"
        return summary, regions

    @staticmethod
    def summarize_geo_assigned_options(data: Optional[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
        """Compat: mesmo que summarize_location_assigned_options."""
        return DV360API.summarize_location_assigned_options(data)

    @staticmethod
    def _infer_targeting_type_from_assigned_option(o: dict[str, Any]) -> str:
        """Quando `targetingType` vem vazio no assigned option, deduz pelo oneof `details`."""
        if DV360API._geo_region_details_from_option(o):
            return "TARGETING_TYPE_GEO_REGION"
        if o.get("cityDetails") or DV360API._details_union_dict(o, "cityDetails"):
            return "TARGETING_TYPE_CITY"
        if o.get("postalCodeDetails") or DV360API._details_union_dict(o, "postalCodeDetails"):
            return "TARGETING_TYPE_POSTAL_CODE"
        if o.get("countryDetails") or DV360API._details_union_dict(o, "countryDetails"):
            return "TARGETING_TYPE_COUNTRY"
        if o.get("poiDetails") or DV360API._details_union_dict(o, "poiDetails"):
            return "TARGETING_TYPE_POI"
        if o.get("businessChainDetails") or DV360API._details_union_dict(o, "businessChainDetails"):
            return "TARGETING_TYPE_BUSINESS_CHAIN"
        pll = o.get("proximityLocationListDetails") or DV360API._details_union_dict(
            o, "proximityLocationListDetails"
        )
        if isinstance(pll, dict) and pll.get("proximityLocationListId") is not None:
            return "TARGETING_TYPE_PROXIMITY_LOCATION_LIST"
        rll = o.get("regionalLocationListDetails") or DV360API._details_union_dict(
            o, "regionalLocationListDetails"
        )
        if isinstance(rll, dict) and rll.get("regionalLocationListId") is not None:
            return "TARGETING_TYPE_REGIONAL_LOCATION_LIST"
        return ""

    @staticmethod
    def _label_from_targeting_option_payload(payload: dict[str, Any]) -> Optional[str]:
        """Nome amigável do recurso global `TargetingOption` (GET targetingOptions)."""
        dn = payload.get("displayName")
        if dn is not None and str(dn).strip():
            return str(dn).strip()
        return DV360API._location_label_from_assigned_option(payload)

    @staticmethod
    def _assigned_option_needs_targeting_option_resolve(base: Optional[str], targeting_option_id: str) -> bool:
        if not str(targeting_option_id).strip():
            return False
        if base is None:
            return True
        b = str(base).strip()
        if b.startswith("Targeting option "):
            return True
        if b == str(targeting_option_id).strip():
            return True
        if b.isdigit():
            return True
        return False

    def get_targeting_option(
        self, advertiser_id: str, targeting_type: str, targeting_option_id: str
    ) -> dict[str, Any]:
        """
        GET .../targetingTypes/{targetingType}/targetingOptions/{targetingOptionId}?advertiserId=
        Usado para obter o nome da região quando o assigned option só traz IDs.
        """
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        aid = str(advertiser_id).strip()
        tt = str(targeting_type).strip()
        toid = str(targeting_option_id).strip()
        if not aid or not tt or not toid:
            return {
                "success": False,
                "error": "advertiser_id, targeting_type e targeting_option_id são obrigatórios.",
                "http_code": 400,
            }
        from urllib.parse import quote, urlencode

        seg_tt = quote(tt, safe="")
        seg_id = quote(toid, safe="")
        q = urlencode({"advertiserId": aid})
        api_url = f"{self.api_base}/targetingTypes/{seg_tt}/targetingOptions/{seg_id}?{q}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro HTTP: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            return {"success": True, "data": res["data"], "http_code": 200, "url_used": api_url}
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao obter targetingOption",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def _label_for_assigned_option_resolved(
        self,
        advertiser_id: str,
        o: dict[str, Any],
        resolve_cache: dict[tuple[str, str], Optional[str]],
        resolutions_used: list[int],
        max_resolutions: int,
    ) -> Optional[str]:
        toid_raw = o.get("targetingOptionId")
        toid = str(toid_raw).strip() if toid_raw is not None else ""
        tt = str(o.get("targetingType") or "").strip() or DV360API._infer_targeting_type_from_assigned_option(o)
        base = DV360API._location_label_from_assigned_option(o)
        if not toid or not tt:
            return base
        if not DV360API._assigned_option_needs_targeting_option_resolve(base, toid):
            return base
        key = (tt, toid)
        if key in resolve_cache:
            return resolve_cache[key] or base
        if resolutions_used[0] >= max_resolutions:
            return base
        resolutions_used[0] += 1
        got = self.get_targeting_option(advertiser_id, tt, toid)
        if got.get("success") and isinstance(got.get("data"), dict):
            resolved = DV360API._label_from_targeting_option_payload(got["data"])
            resolve_cache[key] = resolved
            return resolved or base
        resolve_cache[key] = None
        return base

    def summarize_location_assigned_options_resolved(
        self,
        advertiser_id: str,
        data: Optional[dict[str, Any]],
        resolve_cache: dict[tuple[str, str], Optional[str]],
        resolutions_used: list[int],
        max_resolutions: int = 120,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Como `summarize_location_assigned_options`, mas resolve nomes via `targetingOptions.get`."""
        if not data or not isinstance(data, dict):
            return "—", []
        opts: list[dict[str, Any]] = []
        raw = data.get("assignedTargetingOptions")
        if isinstance(raw, list):
            for x in raw:
                if isinstance(x, dict):
                    opts.append(x)
        liato = data.get("lineItemAssignedTargetingOptions")
        if isinstance(liato, list):
            for wrap in liato:
                if not isinstance(wrap, dict):
                    continue
                inner = wrap.get("assignedTargetingOption")
                if isinstance(inner, dict):
                    merged = dict(inner)
                    if wrap.get("targetingType") and not merged.get("targetingType"):
                        merged["targetingType"] = wrap["targetingType"]
                    if wrap.get("targetingOptionId") and not merged.get("targetingOptionId"):
                        merged["targetingOptionId"] = wrap["targetingOptionId"]
                    opts.append(merged)
        if not opts:
            return "—", []
        names: list[str] = []
        regions: list[dict[str, Any]] = []
        seen: set[str] = set()
        aid = str(advertiser_id).strip()
        for o in opts:
            label = self._label_for_assigned_option_resolved(
                aid, o, resolve_cache, resolutions_used, max_resolutions
            )
            if not label:
                continue
            key = label.lower()
            if key in seen:
                continue
            seen.add(key)
            names.append(label)
            regions.append(
                {
                    "displayName": label,
                    "assignedTargetingOptionId": o.get("assignedTargetingOptionId"),
                    "targetingType": o.get("targetingType") or DV360API._infer_targeting_type_from_assigned_option(o),
                }
            )
        summary = ", ".join(names) if names else "—"
        return summary, regions

    def summarize_geo_assigned_options_resolved(
        self,
        advertiser_id: str,
        data: Optional[dict[str, Any]],
        resolve_cache: dict[tuple[str, str], Optional[str]],
        resolutions_used: list[int],
        max_resolutions: int = 120,
    ) -> tuple[str, list[dict[str, Any]]]:
        return self.summarize_location_assigned_options_resolved(
            advertiser_id, data, resolve_cache, resolutions_used, max_resolutions
        )

    @staticmethod
    def _dv360_micros_to_float(value: Any) -> Optional[float]:
        """Valores monetários / metas na API vêm em micros (ex.: 500000000 → 500 unidades)."""
        try:
            return int(str(value)) / 1_000_000.0
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _dv360_format_date(d: Any) -> str:
        if not isinstance(d, dict):
            return ""
        y, m, day = d.get("year"), d.get("month"), d.get("day")
        if y is None or m is None or day is None:
            return ""
        try:
            return f"{int(y):04d}-{int(m):02d}-{int(day):02d}"
        except (TypeError, ValueError):
            return ""

    @staticmethod
    def summarize_campaign_commercial_snapshot(
        campaign: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Metas CPM/CPA/CPC, voo planejado, orçamentos e cap de frequência a partir do GET Campaign.
        Impressões e custo **entregues** não constam deste endpoint — ver `delivery_note_pt`.
        """
        _cg_pt: dict[str, str] = {
            "CAMPAIGN_GOAL_TYPE_UNSPECIFIED": "Objetivo não especificado",
            "CAMPAIGN_GOAL_TYPE_BRAND_AWARENESS": "Notoriedade da marca",
            "CAMPAIGN_GOAL_TYPE_BRAND_CONSIDERATION": "Consideração da marca",
            "CAMPAIGN_GOAL_TYPE_PERFORMANCE": "Performance",
            "CAMPAIGN_GOAL_TYPE_APP_INSTALL": "Instalação de app",
            "CAMPAIGN_GOAL_TYPE_ONLINE_ACTION": "Ação online",
            "CAMPAIGN_GOAL_TYPE_OFFLINE_ACTION": "Ação offline",
            "CAMPAIGN_GOAL_TYPE_NON_COMMERCIAL": "Não comercial",
        }
        _pg_pt: dict[str, str] = {
            "PERFORMANCE_GOAL_TYPE_UNSPECIFIED": "Meta de performance não especificada",
            "PERFORMANCE_GOAL_TYPE_CPM": "CPM (custo por mil impressões)",
            "PERFORMANCE_GOAL_TYPE_CPC": "CPC (custo por clique)",
            "PERFORMANCE_GOAL_TYPE_CPA": "CPA (custo por aquisição)",
            "PERFORMANCE_GOAL_TYPE_CPIAVC": "CPIAVC (custo por impressão audível e visível)",
            "PERFORMANCE_GOAL_TYPE_VCPM": "vCPM (custo por mil impressões visíveis)",
            "PERFORMANCE_GOAL_TYPE_VIEWABILITY": "Viewability (visibilidade)",
            "PERFORMANCE_GOAL_TYPE_CTR": "CTR (taxa de cliques)",
            "PERFORMANCE_GOAL_TYPE_CLICK_CVR": "CVR de cliques",
            "PERFORMANCE_GOAL_TYPE_IMPRESSION_CVR": "CVR de impressões",
            "PERFORMANCE_GOAL_TYPE_VIDEO_COMPLETION_RATE": "Taxa de conclusão de vídeo",
        }
        _bu_pt: dict[str, str] = {
            "BUDGET_UNIT_UNSPECIFIED": "Unidade não especificada",
            "BUDGET_UNIT_CURRENCY": "Moeda",
            "BUDGET_UNIT_IMPRESSIONS": "Impressões",
        }
        _tu_pt: dict[str, str] = {
            "TIME_UNIT_UNSPECIFIED": "período",
            "TIME_UNIT_LIFETIME": "vida útil",
            "TIME_UNIT_MONTHS": "mês(es)",
            "TIME_UNIT_WEEKS": "semana(s)",
            "TIME_UNIT_DAYS": "dia(s)",
            "TIME_UNIT_HOURS": "hora(s)",
            "TIME_UNIT_MINUTES": "minuto(s)",
        }
        delivery_note_pt = (
            "Impressões entregues e custo real consolidado não vêm neste detalhe da API (só configuração). "
            "No DV360 use relatórios, Query Tool ou exportações agendadas para métricas de desempenho."
        )
        snap: dict[str, Any] = {
            "campaign_goal_type": None,
            "campaign_goal_label_pt": "",
            "performance_goal_type": None,
            "performance_goal_label_pt": "",
            "performance_target_text": "",
            "planned_spend_text": "",
            "planned_dates_text": "",
            "frequency_cap_text": "",
            "budgets_text": [],
            "delivery_note_pt": delivery_note_pt,
        }
        if not campaign or not isinstance(campaign, dict):
            return snap

        cg = campaign.get("campaignGoal")
        if isinstance(cg, dict):
            gt = cg.get("campaignGoalType")
            if gt is not None:
                gts = str(gt)
                snap["campaign_goal_type"] = gts
                snap["campaign_goal_label_pt"] = _cg_pt.get(
                    gts, gts.replace("CAMPAIGN_GOAL_TYPE_", "").replace("_", " ").title()
                )
            pg = cg.get("performanceGoal")
            if isinstance(pg, dict):
                pt = pg.get("performanceGoalType")
                if pt is not None:
                    pts = str(pt)
                    snap["performance_goal_type"] = pts
                    snap["performance_goal_label_pt"] = _pg_pt.get(
                        pts, pts.replace("PERFORMANCE_GOAL_TYPE_", "").replace("_", " ").title()
                    )
                if pg.get("performanceGoalString"):
                    snap["performance_target_text"] = str(pg["performanceGoalString"]).strip()
                elif pg.get("performanceGoalPercentageMicros") is not None:
                    pv = DV360API._dv360_micros_to_float(pg.get("performanceGoalPercentageMicros"))
                    if pv is not None:
                        snap["performance_target_text"] = f"{pv:.4f}%".rstrip("0").rstrip(".").rstrip("%") + "%"
                elif pg.get("performanceGoalAmountMicros") is not None:
                    amt = DV360API._dv360_micros_to_float(pg.get("performanceGoalAmountMicros"))
                    if amt is not None:
                        snap["performance_target_text"] = (
                            f"{amt:,.4f}".rstrip("0").rstrip(".").rstrip(",") + " (moeda do anunciante)"
                        )

        cf = campaign.get("campaignFlight")
        if isinstance(cf, dict):
            if cf.get("plannedSpendAmountMicros") is not None:
                ps = DV360API._dv360_micros_to_float(cf.get("plannedSpendAmountMicros"))
                if ps is not None:
                    snap["planned_spend_text"] = (
                        f"{ps:,.4f}".rstrip("0").rstrip(".").rstrip(",") + " (gasto planejado no voo)"
                    )
            pd = cf.get("plannedDates")
            if isinstance(pd, dict):
                sd = DV360API._dv360_format_date(pd.get("startDate"))
                ed = DV360API._dv360_format_date(pd.get("endDate"))
                if sd and ed:
                    snap["planned_dates_text"] = f"{sd} até {ed}"
                elif sd:
                    snap["planned_dates_text"] = f"Início {sd}" + (" (sem data de fim)" if not ed else "")

        fc = campaign.get("frequencyCap")
        if isinstance(fc, dict):
            if fc.get("unlimited") is True:
                snap["frequency_cap_text"] = "Cap de frequência: ilimitado nesta campanha."
            else:
                tu = str(fc.get("timeUnit") or "")
                tuc = fc.get("timeUnitCount")
                mi = fc.get("maxImpressions")
                mv = fc.get("maxViews")
                bits: list[str] = []
                if mi is not None:
                    bits.append(f"até {mi} impressões")
                if mv is not None:
                    bits.append(f"até {mv} visualizações")
                if bits:
                    period = _tu_pt.get(tu, tu or "período")
                    cnt = ""
                    if tuc is not None:
                        try:
                            cnt = f"{int(tuc)} "
                        except (TypeError, ValueError):
                            cnt = f"{tuc} "
                    snap["frequency_cap_text"] = (
                        "Cap de frequência: " + ", ".join(bits) + f" por {cnt}{period}."
                    )

        budgets_raw = campaign.get("campaignBudgets")
        if isinstance(budgets_raw, list):
            for b in budgets_raw:
                if not isinstance(b, dict):
                    continue
                nm = (b.get("displayName") or b.get("budgetId") or "Orçamento").strip()
                unit = str(b.get("budgetUnit") or "")
                unit_pt = _bu_pt.get(unit, unit)
                micros = b.get("budgetAmountMicros")
                amt = DV360API._dv360_micros_to_float(micros) if micros is not None else None
                if amt is not None:
                    if unit == "BUDGET_UNIT_IMPRESSIONS":
                        line = f"{nm}: {amt:,.0f} (orçamento em impressões, escala micros da API)"
                    else:
                        line = (
                            f"{nm}: {amt:,.4f}".rstrip("0").rstrip(".").rstrip(",")
                            + f" ({unit_pt}, moeda do anunciante)"
                        )
                else:
                    line = f"{nm}: ({unit_pt})"
                dr = b.get("dateRange")
                if isinstance(dr, dict):
                    d0 = DV360API._dv360_format_date(dr.get("startDate"))
                    d1 = DV360API._dv360_format_date(dr.get("endDate"))
                    if d0 or d1:
                        line += f" — {d0 or '?'} → {d1 or '?'}"
                snap["budgets_text"].append(line)

        return snap

    def get_geo_summary_for_campaign(
        self, advertiser_id: str, campaign_id: str, max_insertion_orders: int = 20
    ) -> dict[str, Any]:
        """
        Resumo de praça: campanha (GEO_REGION); insertion orders da campanha; por fim line items
        (bulkList — onde o targeting de local costuma estar).
        """
        aid = str(advertiser_id).strip()
        cid = str(campaign_id).strip()
        resolve_cache: dict[tuple[str, str], Optional[str]] = {}
        resolutions_used = [0]
        max_geo_resolutions = 120

        geo = self.list_campaign_geo_assigned_options(aid, cid, {})
        summary, regions = "—", []
        if geo.get("success"):
            summary, regions = self.summarize_geo_assigned_options_resolved(
                aid, geo.get("data"), resolve_cache, resolutions_used, max_geo_resolutions
            )
        campaign_geo_error = None if geo.get("success") else geo.get("error")

        if summary != "—":
            return {
                "success": True,
                "summary": summary,
                "regions": regions,
                "geo_source": "campaign",
                "campaign_geo_error": campaign_geo_error,
            }

        io_res = self.list_insertion_orders(
            aid, {"filter": f'campaignId="{cid}"', "pageSize": 50}
        )
        insertion_orders_error = None if io_res.get("success") else io_res.get("error")
        if not io_res.get("success"):
            return {
                "success": True,
                "summary": "—",
                "regions": [],
                "geo_source": None,
                "campaign_geo_error": campaign_geo_error,
                "insertion_orders_error": insertion_orders_error,
            }

        raw = io_res.get("data") or {}
        orders = raw.get("insertionOrders") or []
        if not isinstance(orders, list):
            orders = []

        merged_names: list[str] = []
        merged_regions: list[dict[str, Any]] = []
        seen_labels: set[str] = set()
        seen_option_keys: set[str] = set()

        cap = max(1, min(int(max_insertion_orders), 20))
        for ord_ in orders[:cap]:
            if not isinstance(ord_, dict):
                continue
            ioid = str(ord_.get("insertionOrderId") or "").strip()
            if not ioid:
                continue
            gio = self.list_insertion_order_geo_assigned_options(aid, ioid, {})
            if not gio.get("success"):
                continue
            s, r = self.summarize_geo_assigned_options_resolved(
                aid, gio.get("data"), resolve_cache, resolutions_used, max_geo_resolutions
            )
            if s == "—":
                continue
            for part in s.split(", "):
                p = part.strip()
                if p and p not in seen_labels:
                    seen_labels.add(p)
                    merged_names.append(p)
            for reg in r:
                if not isinstance(reg, dict):
                    continue
                oid = reg.get("assignedTargetingOptionId")
                key = str(oid) if oid is not None else str(reg.get("displayName") or "")
                if key and key not in seen_option_keys:
                    seen_option_keys.add(key)
                    merged_regions.append(reg)

        def _merge_location_summary(s: str, rlist: list[dict[str, Any]]) -> None:
            if s == "—":
                return
            for part in s.split(", "):
                p = part.strip()
                if p and p not in seen_labels:
                    seen_labels.add(p)
                    merged_names.append(p)
            for reg in rlist:
                if not isinstance(reg, dict):
                    continue
                oid = reg.get("assignedTargetingOptionId")
                key = str(oid) if oid is not None else str(reg.get("displayName") or "")
                if key and key not in seen_option_keys:
                    seen_option_keys.add(key)
                    merged_regions.append(reg)

        if merged_names:
            return {
                "success": True,
                "summary": ", ".join(merged_names),
                "regions": merged_regions,
                "geo_source": "insertion_order",
                "campaign_geo_error": None,
                "insertion_orders_error": insertion_orders_error,
            }

        # Geo muitas vezes só existe nos line items (nem campanha nem IO).
        line_items_error: Optional[str] = None
        li_res = self.list_line_items(
            aid, {"filter": f'campaignId="{cid}"', "pageSize": 200}
        )
        lids: list[str] = []
        if li_res.get("success"):
            ldata = li_res.get("data") or {}
            for li in ldata.get("lineItems") or []:
                if isinstance(li, dict) and li.get("lineItemId") is not None:
                    lids.append(str(li["lineItemId"]).strip())
            npt = ldata.get("nextPageToken")
            if npt and len(lids) < 120:
                li_res2 = self.list_line_items(
                    aid,
                    {
                        "filter": f'campaignId="{cid}"',
                        "pageSize": 200,
                        "pageToken": npt,
                    },
                )
                if li_res2.get("success"):
                    ldata2 = li_res2.get("data") or {}
                    for li in ldata2.get("lineItems") or []:
                        if isinstance(li, dict) and li.get("lineItemId") is not None:
                            lids.append(str(li["lineItemId"]).strip())
        else:
            line_items_error = li_res.get("error")

        chunk_size = 25
        for i in range(0, min(len(lids), 120), chunk_size):
            chunk = lids[i : i + chunk_size]
            if not chunk:
                break
            bulk = self.bulk_list_line_items_assigned_geo_like(aid, chunk, {})
            if not bulk.get("success"):
                line_items_error = bulk.get("error")
                continue
            s_li, r_li = self.summarize_location_assigned_options_resolved(
                aid, bulk.get("data"), resolve_cache, resolutions_used, max_geo_resolutions
            )
            _merge_location_summary(s_li, r_li)
            bt = (bulk.get("data") or {}).get("nextPageToken")
            if bt:
                bulk2 = self.bulk_list_line_items_assigned_geo_like(
                    aid, chunk, {"pageToken": bt}
                )
                if bulk2.get("success"):
                    s2, r2 = self.summarize_location_assigned_options_resolved(
                        aid, bulk2.get("data"), resolve_cache, resolutions_used, max_geo_resolutions
                    )
                    _merge_location_summary(s2, r2)

        if merged_names:
            return {
                "success": True,
                "summary": ", ".join(merged_names),
                "regions": merged_regions,
                "geo_source": "line_item",
                "campaign_geo_error": None,
                "insertion_orders_error": insertion_orders_error,
                "line_items_error": line_items_error,
            }

        return {
            "success": True,
            "summary": "—",
            "regions": [],
            "geo_source": None,
            "campaign_geo_error": campaign_geo_error,
            "insertion_orders_error": insertion_orders_error,
            "line_items_error": line_items_error,
        }

    def patch_campaign_entity_status(
        self,
        advertiser_id: str,
        campaign_id: str,
        entity_status: str,
    ) -> dict[str, Any]:
        """Atualiza entityStatus da campanha (ex.: ENTITY_STATUS_PAUSED)."""
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        aid = str(advertiser_id).strip()
        cid = str(campaign_id).strip()
        if not aid or not cid:
            return {
                "success": False,
                "error": "advertiser_id e campaign_id são obrigatórios.",
                "http_code": 400,
            }
        from urllib.parse import urlencode

        api_url = (
            f"{self.api_base}/advertisers/{aid}/campaigns/{cid}"
            f"?{urlencode({'updateMask': 'entityStatus'})}"
        )
        res = self._patch_json(api_url, token, {"entityStatus": entity_status})
        if res["request_error"]:
            return {
                "success": False,
                "error": "Erro HTTP: " + res["request_error"],
                "http_code": 0,
            }
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            return {
                "success": True,
                "data": res["data"],
                "http_code": 200,
                "url_used": api_url,
            }
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao atualizar campanha",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def list_insertion_orders(self, advertiser_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._list_advertiser_child(advertiser_id, "insertionOrders", "insertion orders", params)

    def list_line_items(self, advertiser_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._list_advertiser_child(advertiser_id, "lineItems", "line items", params)

    def bulk_list_line_items_assigned_geo_like(
        self,
        advertiser_id: str,
        line_item_ids: list[str],
        params: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        GET .../lineItems:bulkListAssignedTargetingOptions
        (geo, listas regionais, proximidade, POI — onde a praça costuma estar na prática).
        """
        params = dict(params or {})
        ids = [str(x).strip() for x in line_item_ids if str(x).strip()]
        if not ids:
            return {"success": False, "error": "line_item_ids vazio", "http_code": 400}
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        aid = str(advertiser_id).strip()
        if not aid:
            return {"success": False, "error": "advertiser_id obrigatório", "http_code": 400}
        from urllib.parse import urlencode

        q: list[tuple[str, str]] = [("filter", params.get("filter") or _DV360_LINE_ITEM_LOCATION_FILTER)]
        page_size = params.get("pageSize", 5000)
        q.append(("pageSize", str(int(page_size))))
        if params.get("pageToken"):
            q.append(("pageToken", str(params["pageToken"])))
        for lid in ids:
            q.append(("lineItemIds", lid))
        api_url = f"{self.api_base}/advertisers/{aid}/lineItems:bulkListAssignedTargetingOptions?{urlencode(q)}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro HTTP: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 400 and not params.get("filter") and q[0][1] == _DV360_LINE_ITEM_LOCATION_FILTER:
            q2: list[tuple[str, str]] = [("filter", _DV360_LINE_ITEM_LOCATION_FILTER_LEGACY)]
            q2.append(("pageSize", str(int(page_size))))
            if params.get("pageToken"):
                q2.append(("pageToken", str(params["pageToken"])))
            for lid in ids:
                q2.append(("lineItemIds", lid))
            api_url = f"{self.api_base}/advertisers/{aid}/lineItems:bulkListAssignedTargetingOptions?{urlencode(q2)}"
            res = self._get_json(api_url, token)
            if res["request_error"]:
                return {"success": False, "error": "Erro HTTP: " + res["request_error"], "http_code": 0}
            code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            return {"success": True, "data": res["data"], "http_code": 200, "url_used": api_url}
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao listar targeting (line items)",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def list_creatives(self, advertiser_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._list_advertiser_child(advertiser_id, "creatives", "criativos", params)

    def _list_advertiser_child(
        self,
        advertiser_id: str,
        segment: str,
        label_pt: str,
        params: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        params = dict(params or {})
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token.", "http_code": 0}
        if "pageSize" not in params:
            params["pageSize"] = 100
        from urllib.parse import urlencode

        api_url = f"{self.api_base}/advertisers/{advertiser_id}/{segment}"
        if params:
            api_url += "?" + urlencode(params)
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro HTTP: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            return {"success": True, "data": res["data"], "http_code": 200, "url_used": api_url}
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao listar {label_pt}",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def list_google_audiences(self, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        params = dict(params or {})
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token", "http_code": 0}
        if not self.partner_id:
            return {"success": False, "error": "DV360_PARTNER_ID não configurado.", "http_code": 0}
        q = {"partnerId": self.partner_id, "pageSize": 100, **params}
        from urllib.parse import urlencode

        api_url = f"{self.api_base}/googleAudiences?{urlencode(q)}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro: " + res["request_error"], "http_code": 0, "url_tried": api_url}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            data = res["data"]
            audiences = data.get("googleAudiences") or []
            return {
                "success": True,
                "data": data,
                "audiences": audiences,
                "total": len(audiences),
                "nextPageToken": data.get("nextPageToken"),
                "http_code": 200,
                "url_used": api_url,
            }
        err = res["data"] if isinstance(res["data"], dict) else {}
        inner = err.get("error") if isinstance(err.get("error"), dict) else {}
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao listar Google Audiences",
            "error_message": inner.get("message", "Erro desconhecido") if isinstance(inner, dict) else "Erro desconhecido",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def get_google_audience(self, google_audience_id: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token", "http_code": 0}
        if not self.partner_id:
            return {"success": False, "error": "DV360_PARTNER_ID não configurado.", "http_code": 0}
        from urllib.parse import urlencode

        api_url = f"{self.api_base}/googleAudiences/{google_audience_id}?{urlencode({'partnerId': self.partner_id})}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {
                "success": False,
                "error": "Erro: " + res["request_error"],
                "http_code": 0,
                "url_tried": api_url,
                "partner_id_used": self.partner_id,
            }
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            aud = res["data"]
            return {
                "success": True,
                "audience": aud,
                "data": aud,
                "http_code": 200,
                "url_used": api_url,
                "partner_id_used": self.partner_id,
            }
        err = res["data"] if isinstance(res["data"], dict) else {}
        inner = err.get("error") if isinstance(err.get("error"), dict) else {}
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao buscar Google Audience",
            "error_message": inner.get("message", "Erro desconhecido") if isinstance(inner, dict) else "Erro desconhecido",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
            "partner_id_used": self.partner_id,
        }

    def get_first_party_audience(self, advertiser_id: str, audience_id: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Falha ao obter Access Token", "http_code": 0}
        api_url = f"{self.api_base}/advertisers/{advertiser_id}/firstPartyAndPartnerAudiences/{audience_id}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro: " + res["request_error"], "http_code": 0, "url_tried": api_url}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            aud = res["data"]
            return {
                "success": True,
                "audience": aud,
                "data": aud,
                "http_code": 200,
                "url_used": api_url,
                "advertiser_id": advertiser_id,
            }
        err = res["data"] if isinstance(res["data"], dict) else {}
        inner = err.get("error") if isinstance(err.get("error"), dict) else {}
        return {
            "success": False,
            "error": f"Erro HTTP {code}",
            "error_message": inner.get("message", "Erro desconhecido") if isinstance(inner, dict) else "Erro desconhecido",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
            "advertiser_id": advertiser_id,
        }

    def get_first_party_and_partner_audience(self, audience_id: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Não foi possível obter o token de acesso", "http_code": 0}
        if not self.partner_id:
            return {"success": False, "error": "DV360_PARTNER_ID não configurado.", "http_code": 0}
        from urllib.parse import urlencode

        api_url = f"{self.api_base}/firstPartyAndPartnerAudiences/{audience_id}?{urlencode({'partnerId': self.partner_id})}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            data = res["data"]
            return {
                "success": True,
                "data": data,
                "audience": data,
                "http_code": 200,
                "url_used": api_url,
                "partner_id_used": self.partner_id,
            }
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao buscar First-Party Audience",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def get_combined_audience(self, audience_id: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Não foi possível obter o token de acesso", "http_code": 0}
        if not self.partner_id:
            return {"success": False, "error": "DV360_PARTNER_ID não configurado.", "http_code": 0}
        from urllib.parse import urlencode

        api_url = f"{self.api_base}/combinedAudiences/{audience_id}?{urlencode({'partnerId': self.partner_id})}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            data = res["data"]
            return {
                "success": True,
                "data": data,
                "audience": data,
                "http_code": 200,
                "url_used": api_url,
                "partner_id_used": self.partner_id,
            }
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao buscar Combined Audience",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }

    def get_custom_list(self, advertiser_id: str, custom_list_id: str) -> dict[str, Any]:
        token = self.get_access_token()
        if not token:
            return {"success": False, "error": "Não foi possível obter o token de acesso", "http_code": 0}
        api_url = f"{self.api_base}/advertisers/{advertiser_id}/customLists/{custom_list_id}"
        res = self._get_json(api_url, token)
        if res["request_error"]:
            return {"success": False, "error": "Erro: " + res["request_error"], "http_code": 0}
        code = res["http_code"]
        if code == 200 and isinstance(res["data"], dict):
            data = res["data"]
            return {
                "success": True,
                "data": data,
                "audience": data,
                "http_code": 200,
                "url_used": api_url,
                "advertiser_id_used": advertiser_id,
            }
        return {
            "success": False,
            "error": f"Erro HTTP {code} ao buscar Custom List",
            "error_details": res["data"],
            "http_code": code,
            "url_tried": api_url,
        }


def get_dv360_client() -> DV360API:
    from flask import current_app

    return DV360API(current_app.config)
