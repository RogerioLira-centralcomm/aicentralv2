import os

from aicentralv2.contrato_tipos import normalizar_tipo_de_contrato

IMPOSTO_COMISSAO_REP = 0.1433
CODIGO_SERVICO_NF_COMISSAO = "17.06.01"

DESCRICAO_ANEXO_PLANILHA_PARCEIRO = "Planilha comercial do parceiro (Logan)"
DESCRICAO_ANEXO_PROPOSTA_PDF_PARCEIRO = "Proposta PDF do parceiro (Serasa)"


def representacao_habilitada() -> bool:
    raw = (os.getenv("REPRESENTACAO_COMERCIAL_ENABLED") or "true").strip().lower()
    return raw not in ("0", "false", "no", "off")


def eh_representacao_comercial(registro) -> bool:
    if not representacao_habilitada():
        return False
    if not registro:
        return False
    slug = normalizar_tipo_de_contrato(
        registro.get("tipo_de_contrato"), estrito=False
    )
    return slug == "representacao_comercial"
