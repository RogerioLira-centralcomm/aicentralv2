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

    def list_campaigns(self, advertiser_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._list_advertiser_child(advertiser_id, "campaigns", "campanhas", params)

    def list_insertion_orders(self, advertiser_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._list_advertiser_child(advertiser_id, "insertionOrders", "insertion orders", params)

    def list_line_items(self, advertiser_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        return self._list_advertiser_child(advertiser_id, "lineItems", "line items", params)

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
