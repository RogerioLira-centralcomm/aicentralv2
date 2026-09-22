"""Small, product-neutral error responses for browser requests and APIs."""

from __future__ import annotations

from uuid import uuid4

from flask import jsonify, render_template, request
from werkzeug.exceptions import HTTPException

from .product_domains import is_centralx_request, product_url, workspace_public_url


_ERRORS = {
    400: ("REQUEST_INVALID", "Não conseguimos processar este envio.", "Confira os campos e tente novamente pelo mesmo caminho."),
    401: ("AUTHENTICATION_REQUIRED", "Faça login para continuar.", "Sua sessão pode ter expirado."),
    403: ("ACCESS_DENIED", "Você não tem permissão para acessar esta área.", "Se isso parecer incorreto, fale com o responsável pela sua conta."),
    404: ("RESOURCE_NOT_FOUND", "Esta página não faz parte do projeto.", "O endereço pode ter mudado. Use os atalhos abaixo para continuar."),
    405: ("METHOD_NOT_ALLOWED", "Esta ação não está disponível.", "Volte e tente por outro caminho."),
    413: ("REQUEST_TOO_LARGE", "O envio excede o limite permitido.", "Reduza o tamanho ou a quantidade de arquivos e tente novamente."),
    429: ("RATE_LIMITED", "Muitas tentativas em pouco tempo.", "Aguarde um instante antes de tentar novamente."),
    500: ("INTERNAL_ERROR", "O Cadu encontrou um problema.", "Use o código de suporte abaixo se precisar falar com o time."),
    503: ("DEPENDENCY_UNAVAILABLE", "Este recurso está temporariamente indisponível.", "Tente novamente em alguns minutos."),
}


def _expects_json() -> bool:
    return request.path.startswith("/api/") or (
        request.accept_mimetypes["application/json"] > request.accept_mimetypes["text/html"]
    )


def _payload(status: int, error: HTTPException | Exception | None) -> dict:
    error_class, title, guidance = _ERRORS.get(status, _ERRORS[500])
    support_id = uuid4().hex[:12].upper()
    return {
        "status": status,
        "error_class": error_class,
        "title": title,
        "guidance": guidance,
        "support_id": support_id,
    }


def register_error_pages(app) -> None:
    """Register uniform error output after legacy routes have been mounted.

    Error identifiers deliberately contain no request data or exception text.
    The full traceback remains in the server log, keyed by the same identifier.
    """

    def respond(error, status: int | None = None):
        code = status or (error.code if isinstance(error, HTTPException) else 500)
        data = _payload(code, error)
        original_exception = getattr(error, "original_exception", None)
        app.logger.error(
            "request_error class=%s status=%s support_id=%s path=%s",
            data["error_class"], code, data["support_id"], request.path,
            exc_info=bool(original_exception) or not isinstance(error, HTTPException),
        )
        if _expects_json():
            return jsonify({"success": False, "error": data["title"], **data}), code
        public_home = "/" if is_centralx_request() else workspace_public_url()
        primary_url = product_url('auth', '/login') if code == 401 and not is_centralx_request() else public_home
        primary_label = 'Entrar novamente' if code == 401 else 'Ir para o início'
        conversion_event = {
            'event': 'public_error', 'event_id': data['support_id'],
            'status_code': str(code), 'error_class': data['error_class'],
        }
        return render_template(
            "errors/page.html", home_url=public_home, primary_url=primary_url,
            primary_label=primary_label, error_robots='noindex,nofollow' if code >= 500 else 'noindex,follow',
            analytics_page_type='error', analytics_content_group='support',
            analytics_journey_stage='recovery', conversion_event=conversion_event,
            **data,
        ), code

    for status in _ERRORS:
        app.register_error_handler(status, lambda error, status=status: respond(error, status))
    app.register_error_handler(Exception, respond)
