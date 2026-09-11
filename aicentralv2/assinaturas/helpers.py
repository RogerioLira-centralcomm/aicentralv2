"""Constantes e serialização da mesa de assinaturas."""

from datetime import date, datetime

STATUS_LABELS = {
    "rascunho": "Rascunho",
    "aguardando_assinaturas": "Aguardando assinaturas",
    "parcialmente_assinado": "Parcialmente assinado",
    "finalizado": "Finalizado",
    "cancelado": "Cancelado",
    "recusado": "Recusado",
}

VINCULO_LABELS = {
    "cliente": "Cliente",
    "agencia": "Agência",
    "parceiro": "Parceiro",
    "colaborador": "Colaborador",
    "interno": "Interno",
    "pi": "PI",
}

OPEN_STATUSES = ("aguardando_assinaturas", "parcialmente_assinado")


def label_status(status):
    return STATUS_LABELS.get(status, status or "")


def label_vinculo(tipo):
    return VINCULO_LABELS.get(tipo, tipo or "")


def iso(value):
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    if isinstance(value, date):
        return value.isoformat()
    return value


def serialize_signer(row):
    row = row or {}
    return {
        "id": row.get("id"),
        "id_contato": row.get("id_contato"),
        "email": row.get("email") or "",
        "nome": row.get("nome") or row.get("email") or "",
        "key_signer": row.get("key_signer") or "",
        "ordem": row.get("ordem") or 0,
        "status": row.get("status") or "pendente",
        "assinado_em": iso(row.get("assinado_em")),
    }


def serialize_document(row, signers=None):
    row = row or {}
    tipo = row.get("tipo_vinculo") or "interno"
    return {
        "id": row.get("id"),
        "titulo": row.get("titulo") or "",
        "arquivo_nome": row.get("arquivo_nome") or "",
        "uuid_d4sign": row.get("uuid_d4sign") or "",
        "uuid_safe": row.get("uuid_safe") or "",
        "status": row.get("status") or "rascunho",
        "status_label": label_status(row.get("status")),
        "tipo_vinculo": tipo,
        "tipo_vinculo_label": label_vinculo(tipo),
        "id_vinculo": row.get("id_vinculo"),
        "vinculo_nome": row.get("vinculo_nome") or "",
        "criado_por": row.get("criado_por"),
        "criado_por_nome": row.get("criado_por_nome") or "",
        "created_at": iso(row.get("created_at")),
        "updated_at": iso(row.get("updated_at")),
        "signatarios": [serialize_signer(item) for item in (signers or row.get("signatarios") or [])],
        "pendentes": sum(
            1
            for item in (signers or row.get("signatarios") or [])
            if (item.get("status") or "pendente") == "pendente"
        ),
    }
