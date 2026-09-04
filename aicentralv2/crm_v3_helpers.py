"""Helpers para o protótipo /crm-v3 (sem dependência do CRM real)."""

import re
from typing import Any, Dict, List, Optional


def pluralizar_contatos(n: int) -> str:
    n = int(n or 0)
    if n == 0:
        return "0 contatos"
    if n == 1:
        return "1 contato"
    return f"{n} contatos"


def normalizar_telefone(telefone: Optional[str], ddi: str = "55") -> str:
    if not telefone:
        return ""
    digits = re.sub(r"\D", "", str(telefone))
    if not digits:
        return ""
    if digits.startswith(ddi) and len(digits) > 11:
        return digits
    if len(digits) >= 10 and not digits.startswith(ddi):
        return f"{ddi}{digits}"
    return digits


def avatar_iniciais(nome: Optional[str]) -> str:
    nome = (nome or "?").strip()
    if not nome:
        return "?"
    parts = nome.split()
    if len(parts) >= 2:
        return (parts[0][0] + parts[1][0]).upper()
    return nome[:2].upper()


def avatar_tone(nome: Optional[str]) -> str:
    """primary ou muted — determinístico por hash do nome."""
    nome = (nome or "").strip()
    if not nome:
        return "muted"
    return "primary" if sum(ord(c) for c in nome) % 2 == 0 else "muted"


def parse_texto_contatos(texto: str) -> List[Dict[str, Any]]:
    """Parse linhas Nome;email;telefone ou separadores , |"""
    if not texto or not str(texto).strip():
        return []
    out: List[Dict[str, Any]] = []
    for linha in str(texto).splitlines():
        linha = linha.strip()
        if not linha:
            continue
        parts = [p.strip() for p in re.split(r"[;|,]", linha)]
        if len(parts) < 2:
            continue
        nome, email = parts[0], parts[1]
        telefone = parts[2] if len(parts) > 2 else ""
        if not nome or not email or "@" not in email:
            continue
        out.append(
            {
                "nome": nome,
                "email": email,
                "telefone": telefone,
                "cargo": parts[3] if len(parts) > 3 else "",
                "principal": False,
            }
        )
    return out


def badge_daisy_class(badge_type: Optional[str]) -> str:
    mapping = {
        "success": "badge-success",
        "warning": "badge-warning",
        "danger": "badge-error",
        "error": "badge-error",
        "info": "badge-info",
        "muted": "badge-ghost",
        "hoje": "badge-success",
        "atrasado": "badge-warning",
        "seguindo": "badge-info",
        "sem-atividade": "badge-ghost",
        "rascunho": "badge-ghost",
        "enviada": "badge-info",
        "aprovada": "badge-success",
        "rejeitada": "badge-error",
        "expirada": "badge-warning",
        "em-acompanhamento": "badge-info",
    }
    return mapping.get((badge_type or "").lower(), "badge-neutral")


def filtrar_vinculos_colisao_lookup(vinculos, lookup_ids):
    """Descarta FK que colidiu com o lookup Sim/Não de tbl_agencia.

    `tbl_agencia.id_agencia` costuma ser 1/2 (Sim/Não). Quando esse
    valor foi gravado em `tbl_cliente_agencia.id_agencia_cliente`, o
    JOIN aponta para o cliente #1 da base (ADALA), mesmo com a
    agência real em outra linha. Se existir ao menos um vínculo cujo
    id não é do lookup, os ids do lookup são ignorados. Se o único
    vínculo for ADALA de verdade (id 1), ele permanece.
    """
    lookup = set()
    for x in lookup_ids or []:
        try:
            lookup.add(int(x))
        except (TypeError, ValueError):
            pass
    if not lookup or not vinculos:
        return list(vinculos or [])
    claros = []
    for v in vinculos:
        raw = (v or {}).get("id_agencia_cliente")
        if raw is None:
            raw = (v or {}).get("agencia_id")
        try:
            aid = int(raw)
        except (TypeError, ValueError):
            aid = None
        if aid is None or aid not in lookup:
            claros.append(v)
    return claros if claros else list(vinculos)


def uf_por_capital_operacao(cidade: Optional[str]) -> Optional[str]:
    """UF das 3 capitais que a operação usa hoje (BH, Rio, São Paulo)."""
    import unicodedata

    chave = unicodedata.normalize("NFD", (cidade or "").strip().lower())
    chave = "".join(c for c in chave if unicodedata.category(c) != "Mn")
    chave = re.sub(r"\s+", " ", chave).strip()
    return {
        "belo horizonte": "MG",
        "rio de janeiro": "RJ",
        "sao paulo": "SP",
    }.get(chave)


def texto_sem_markdown(texto: Optional[str]) -> str:
    """Remove marcações markdown comuns de títulos/roteiros gerados por IA."""
    s = str(texto or "")
    s = re.sub(r"```[\s\S]*?```", lambda m: m.group(0).replace("```", ""), s)
    s = s.replace("```", "")
    s = re.sub(r"^#{1,6}\s+", "", s, flags=re.M)
    s = re.sub(r"\*\*(.+?)\*\*", r"\1", s)
    s = re.sub(r"__(.+?)__", r"\1", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?!\w)", r"\1", s)
    s = re.sub(r"`([^`]+)`", r"\1", s)
    s = re.sub(r"^[\s]*[-*+]\s+", "- ", s, flags=re.M)
    s = re.sub(r"^\s{0,3}>\s?", "", s, flags=re.M)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = s.replace("**", "").replace("__", "")
    s = re.sub(r"[ \t]+\n", "\n", s)
    return s.strip()


def titulo_atividade_lista(titulo: Optional[str], descricao: Optional[str] = None) -> str:
    """Primeira linha limpa para o card da coluna (sem markdown, sem bloco)."""
    bruto = texto_sem_markdown(titulo)
    if not bruto:
        bruto = texto_sem_markdown(descricao)
    linha = (bruto.splitlines()[0] if bruto else "").strip()
    if not linha:
        return "Atividade"
    return linha[:90] + ("…" if len(linha) > 90 else "")
