"""Regras da mesa de assinaturas e do webhook D4Sign."""

from __future__ import annotations

import logging

from ..services import integration_credentials
from ..services.d4sign_client import D4SignClient, D4SignError, public_webhook_url
from .helpers import OPEN_STATUSES, serialize_document
from .repository import AssinaturasRepository, DocumentoNaoEncontrado


logger = logging.getLogger(__name__)

MAX_UPLOAD_BYTES = 20 * 1024 * 1024

TYPE_FINISHED = "1"
TYPE_CANCELLED = "3"
TYPE_SIGNED = "4"
TYPE_REFUSED = "5"


class AssinaturaError(ValueError):
    pass


class IntegracaoPendente(AssinaturaError):
    pass


def _repo():
    return AssinaturasRepository()


def integration_ready():
    try:
        config = integration_credentials.get_configuration("d4sign", include_secrets=True)
    except Exception:
        return False
    return bool(config.get("configured") and config.get("uuid_safe"))


def get_client():
    config = integration_credentials.get_configuration("d4sign", include_secrets=True)
    if not config.get("token_api") or not config.get("crypt_key"):
        raise IntegracaoPendente("A integração D4Sign ainda não foi configurada.")
    if not config.get("uuid_safe"):
        raise IntegracaoPendente("Selecione o cofre D4Sign em Parâmetros → Integrações.")
    return D4SignClient.from_config(config), config


def webhook_url(config=None):
    config = config or {}
    return public_webhook_url(config.get("webhook_secret"))


def listar_documentos(filtros=None):
    return [serialize_document(row, row.get("signatarios")) for row in _repo().listar(filtros)]


def obter_documento(id_documento):
    return serialize_document(_repo().obter(id_documento))


def badge_count(email):
    try:
        return _repo().contar_pendencias(email)
    except Exception:
        return 0


def listar_vinculos(tipo, query=""):
    repo = _repo()
    tipo = str(tipo or "").strip()
    if tipo == "colaborador":
        return repo.listar_colaboradores(query)
    if tipo == "agencia":
        return repo.listar_clientes(query, agencia=True)
    if tipo == "pi":
        return repo.listar_pis(query)
    if tipo in {"cliente", "parceiro"}:
        return repo.listar_clientes(query)
    return []


def criar_documento(titulo, arquivo, signatarios, tipo_vinculo="interno",
                    id_vinculo=None, vinculo_nome="", workflow=0, autor_id=None):
    titulo = str(titulo or "").strip()
    if not titulo:
        raise AssinaturaError("Informe o título do documento.")
    if not arquivo or not arquivo.filename:
        raise AssinaturaError("Envie um PDF para assinatura.")
    filename = arquivo.filename
    if not filename.lower().endswith(".pdf"):
        raise AssinaturaError("Só aceitamos PDF nesta mesa.")
    payload = arquivo.read()
    if not payload:
        raise AssinaturaError("O arquivo enviado está vazio.")
    if len(payload) > MAX_UPLOAD_BYTES:
        raise AssinaturaError("O PDF não pode passar de 20 MB.")

    cleaned = _normalize_signers(signatarios)
    if not cleaned:
        raise AssinaturaError("Escolha pelo menos um signatário da CentralComm.")

    client, config = get_client()
    uploaded = client.upload_document(config["uuid_safe"], payload, filename, workflow=workflow)
    uuid_doc = uploaded["uuid"]
    remote_signers = client.create_signers(uuid_doc, cleaned)
    keys = {item["email"]: item.get("key_signer") or "" for item in remote_signers}
    for signer in cleaned:
        signer["key_signer"] = keys.get(signer["email"], "")
    client.send_to_sign(uuid_doc, skip_email=True, workflow=workflow)
    hook = webhook_url(config)
    if hook:
        try:
            client.register_webhook(uuid_doc, hook)
        except D4SignError:
            logger.exception("Não foi possível registrar o webhook D4Sign de %s", uuid_doc)

    repo = _repo()
    doc_id = repo.criar_documento({
        "titulo": titulo[:255],
        "arquivo_nome": filename[:255],
        "uuid_d4sign": uuid_doc,
        "uuid_safe": config.get("uuid_safe"),
        "status": "aguardando_assinaturas",
        "tipo_vinculo": tipo_vinculo or "interno",
        "id_vinculo": int(id_vinculo) if id_vinculo else None,
        "vinculo_nome": str(vinculo_nome or "").strip()[:255],
        "criado_por": autor_id,
    })
    repo.criar_signatarios(doc_id, cleaned)
    return obter_documento(doc_id)


def viewer_payload(id_documento, user_email, user_name=""):
    document = obter_documento(id_documento)
    client, _config = get_client()
    email = str(user_email or "").strip().lower()
    signer = next(
        (item for item in document["signatarios"] if item["email"] == email),
        None,
    )
    embed_url = ""
    if document.get("uuid_d4sign") and email:
        embed_url = client.embed_url(
            document["uuid_d4sign"],
            email,
            (signer or {}).get("key_signer") or "",
        )
    return {
        "documento": document,
        "embed_url": embed_url,
        "pode_assinar": bool(
            signer
            and signer.get("status") == "pendente"
            and document["status"] in OPEN_STATUSES
        ),
        "sou_signatario": bool(signer),
        "usuario": {"email": email, "nome": user_name},
    }


def cancelar(id_documento):
    document = _repo().obter(id_documento)
    if document["status"] in {"finalizado", "cancelado"}:
        raise AssinaturaError("Este documento já foi encerrado.")
    client, _config = get_client()
    if document.get("uuid_d4sign"):
        client.cancel_document(document["uuid_d4sign"])
    _repo().atualizar_status(id_documento, "cancelado")
    return obter_documento(id_documento)


def processar_webhook(payload, secret=""):
    config = integration_credentials.get_configuration("d4sign", include_secrets=True)
    expected = str(config.get("webhook_secret") or "").strip()
    if expected and str(secret or "").strip() != expected:
        raise AssinaturaError("Webhook D4Sign sem autorização.")
    uuid_doc = str(payload.get("uuid") or payload.get("uuid_document") or "").strip()
    if not uuid_doc:
        raise AssinaturaError("Webhook sem UUID do documento.")
    repo = _repo()
    document = repo.obter_por_uuid(uuid_doc)
    if not document:
        logger.info("Webhook D4Sign ignorado: documento %s não está no CentralX.", uuid_doc)
        return {"ignored": True}
    type_post = str(payload.get("type_post") or "").strip()
    repo.registrar_evento(document["id"], type_post, payload)
    email = _webhook_email(payload)
    if type_post == TYPE_SIGNED and email:
        repo.marcar_signatario(document["id"], email, "assinado")
        repo.atualizar_status(document["id"], _status_apos_assinatura(document["id"]))
    elif type_post == TYPE_REFUSED and email:
        repo.marcar_signatario(document["id"], email, "recusado")
        repo.atualizar_status(document["id"], "recusado")
    elif type_post == TYPE_FINISHED:
        _finalizar(document)
    elif type_post == TYPE_CANCELLED:
        repo.atualizar_status(document["id"], "cancelado")
    return {"ok": True, "id": document["id"], "type_post": type_post}


def _finalizar(document):
    repo = _repo()
    for signer in repo.listar_signatarios(document["id"]):
        if signer.get("status") == "pendente":
            repo.marcar_signatario(document["id"], signer["email"], "assinado")
    repo.atualizar_status(document["id"], "finalizado")
    if document.get("tipo_vinculo") == "pi" and document.get("id_vinculo"):
        _concluir_checklist_pi(document["id_vinculo"])


def _concluir_checklist_pi(id_pi):
    try:
        from ..pi_operacao_repository import PiOperacaoRepository

        PiOperacaoRepository().concluir_itens_automaticos(
            int(id_pi),
            [{
                "codigo": "assinatura_d4sign",
                "evidencia": "Documento finalizado na mesa D4Sign",
            }],
        )
        from ..pi_fechamento_repository import PiFechamentoRepository

        PiFechamentoRepository().upsert_status(int(id_pi), "pronto_nf")
    except Exception:
        logger.exception("Não foi possível concluir o checklist D4Sign do PI %s", id_pi)


def _status_apos_assinatura(id_documento):
    signers = _repo().listar_signatarios(id_documento)
    if signers and all(item.get("status") == "assinado" for item in signers):
        return "finalizado"
    return "parcialmente_assinado"


def _webhook_email(payload):
    signer = payload.get("signer") or {}
    if isinstance(signer, dict) and signer.get("email"):
        return str(signer["email"]).strip().lower()
    for item in payload.get("signers") or []:
        if isinstance(item, dict) and item.get("email"):
            return str(item["email"]).strip().lower()
    return str(payload.get("email") or payload.get("email_user") or "").strip().lower()


def _normalize_signers(signatarios):
    cleaned = []
    seen = set()
    for index, item in enumerate(signatarios or []):
        email = str(item.get("email") or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        cleaned.append({
            "id_contato": item.get("id_contato") or item.get("id"),
            "email": email,
            "nome": str(item.get("nome") or item.get("label") or email).strip(),
            "ordem": item.get("ordem", index),
        })
    return cleaned
