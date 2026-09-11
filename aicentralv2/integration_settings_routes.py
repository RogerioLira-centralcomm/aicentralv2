"""Central administrativa de credenciais globais."""

from flask import current_app, jsonify, render_template, request, session

from . import db
from .auth import admin_required, admin_required_api
from .services import integration_credentials


def _ok(data=None, **extra):
    body = {"success": True}
    if data is not None:
        body["data"] = data
    body.update(extra)
    return jsonify(body)


def _error(message, status=400):
    return jsonify({"success": False, "error": message}), status


def register_integration_settings_routes(blueprint):
    @blueprint.route("/integracoes")
    @admin_required
    def integracoes():
        return render_template("parametros/integracoes.html")

    @blueprint.route("/api/integrations")
    @admin_required_api
    def api_integrations():
        try:
            return _ok(integration_credentials.list_summaries())
        except integration_credentials.IntegrationCredentialError as exc:
            return _error(str(exc))

    @blueprint.route("/api/integrations/<provider>", methods=["PUT"])
    @admin_required_api
    def api_update_integration(provider):
        try:
            summary = integration_credentials.save_configuration(
                provider,
                request.get_json(silent=True) or {},
                session.get("user_id"),
            )
            return _ok(summary)
        except integration_credentials.IntegrationCredentialError as exc:
            return _error(str(exc))
        except Exception:
            current_app.logger.exception(
                "Falha ao salvar credencial da integração %s", provider
            )
            return _error("Não foi possível salvar a credencial.", 500)

    @blueprint.route("/api/integrations/<provider>", methods=["DELETE"])
    @admin_required_api
    def api_delete_integration(provider):
        try:
            integration_credentials.remove_configuration(provider)
            return _ok({"provider": provider, "removed": True})
        except integration_credentials.IntegrationCredentialError as exc:
            return _error(str(exc))
        except Exception:
            return _error("Não foi possível remover a credencial.", 500)

    @blueprint.route("/api/integrations/<provider>/validate", methods=["POST"])
    @admin_required_api
    def api_validate_integration(provider):
        try:
            result = integration_credentials.validate_configuration(provider)
            valid, message = result[0], result[1]
            extra = result[2] if len(result) > 2 else {}
            try:
                db.atualizar_validacao_credencial_integracao(
                    provider, "valid" if valid else "invalid", message
                )
            except Exception:
                pass
            payload = {
                "provider": provider,
                "valid": valid,
                "message": message,
            }
            payload.update(extra or {})
            return _ok(payload)
        except integration_credentials.IntegrationCredentialError as exc:
            return _error(str(exc))
