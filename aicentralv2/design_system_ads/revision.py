"""Revisão do documento. Distinta de `version` (contador de passes)."""

from __future__ import annotations

BRAND_CONFLICT = "A marca mudou. Recarregue."
CAMPAIGN_CONFLICT = "A campanha mudou. Recarregue."
DISCARDED_EDIT = "Edição pendente descartada. A marca mudou."
DISCARDED_STALE_LOCAL = (
    "O ajuste anterior foi gravado. Este pedido usava o estado antigo e não foi reenviado."
)
REVISION_REQUIRED = "Informe a revisão da marca."
CAMPAIGN_REVISION_REQUIRED = "Informe a revisão da campanha."


def read_revision(value):
    if value is None:
        raw = 0
    elif isinstance(value, dict):
        raw = value.get("revision")
    elif hasattr(value, "revision") and not isinstance(value, (int, float, str, bool)):
        raw = getattr(value, "revision", 0)
    else:
        raw = value
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def next_revision(value):
    current = read_revision(value)
    return 1 if current < 1 else current + 1


def pin_expected_revision(stored, expected_revision=None):
    """Fixa o número do CAS antes de qualquer chamada externa.

    `client` é o snapshot que o operador viu. `stored_at_start` é a
    transição explícita de compatibilidade: usa a revisão no começo do
    request, nunca uma leitura recente no momento de gravar.
    """
    if expected_revision is None:
        return read_revision(stored), "stored_at_start"
    return read_revision(expected_revision), "client"


def resolve_write_revision(stored, expected_revision):
    if expected_revision is None:
        raise ValueError(REVISION_REQUIRED)
    expected = read_revision(expected_revision)
    return expected, expected == read_revision(stored)


def should_discard_queued_write(job_revision, current_revision, job_epoch, epoch):
    """Ação enfileirada sobre snapshot antigo não ganha a revisão atual."""
    return queued_write_reason(job_revision, current_revision, job_epoch, epoch) is not None


def queued_write_reason(
    job_revision, current_revision, job_epoch, epoch, *, local_success=False
):
    """Conflito de outra aba vs. pedido velho depois do sucesso local."""
    if job_epoch != epoch:
        return "conflict"
    if read_revision(job_revision) != read_revision(current_revision):
        return "stale_after_local" if local_success else "stale"
    return None


def queued_write_message(reason):
    if reason == "stale_after_local":
        return DISCARDED_STALE_LOCAL
    if reason in {"conflict", "stale"}:
        return DISCARDED_EDIT
    return ""


def projection_is_stale(existing, incoming):
    """Projeção mais nova que o incoming não regride."""
    return read_revision(existing) > read_revision(incoming)


ORPHAN_PROJECTION = "Este Ads veio da projeção. Grave na marca para ficar canônico."


def storage_report(source):
    if source == "projection":
        return {
            "canonical": "projection",
            "orphan": True,
            "label": ORPHAN_PROJECTION,
        }
    if source == "profile":
        return {"canonical": "brand_profile", "orphan": False, "label": ""}
    return {"canonical": "", "orphan": False, "label": ""}


def stamp_revision(system, revision):
    from .schema import dump_system, parse_system

    data = dump_system(system)
    data["revision"] = read_revision(revision)
    return parse_system(data)
