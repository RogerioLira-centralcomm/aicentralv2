"""Logos das plataformas de mídia (nomes de cadu_pi_camp_plataforma) e resumo por plataforma."""

from __future__ import annotations

import unicodedata

# Nome normalizado da plataforma da campanha -> slug de logo já existente no app.
_SLUGS = {
    "dv360": "google-dv360", "google dv360": "google-dv360", "display & video 360": "google-dv360",
    "meta ads": "facebook", "meta": "facebook", "facebook ads": "facebook", "instagram ads": "instagram",
    "you tube": "youtube", "youtube": "youtube", "youtube ads": "youtube",
    "tik tok ads": "tiktok", "tiktok ads": "tiktok", "tiktok": "tiktok",
    "amazon dsp": "amazon-ads", "amazon ads": "amazon-ads",
    "disney +": "disney-plus", "disney+": "disney-plus",
    "spotify": "spotify", "spotify ads": "spotify",
    "linkedin ads": "linkedin", "linkedin": "linkedin",
    "programatica": "programatica", "programática": "programatica",
    "google ads": "google-ads", "hbo max": "hbo-max", "max": "hbo-max",
    "paramount +": "paramount-plus", "paramount+": "paramount-plus",
    "netflix": "netflix",
}
_CACHE: dict[str, str] = {}


def _chave(nome) -> str:
    texto = " ".join(str(nome or "").split()).lower()
    return texto


def logo(nome) -> str:
    """URL do logo da plataforma ('' quando não há logo conhecido)."""
    chave = _chave(nome)
    if not chave:
        return ""
    if chave not in _CACHE:
        slug = _SLUGS.get(chave) or _SLUGS.get(unicodedata.normalize("NFKD", chave).encode("ascii", "ignore").decode())
        url = ""
        if slug == "facebook":
            url = "/static/images/creative-viewers/facebook.svg"
        elif slug:
            try:
                from ..crm_v3_canais import _resolver_logo
                url = _resolver_logo(slug, "") or ""
            except Exception:
                url = ""
        _CACHE[chave] = url
    return _CACHE[chave]


def iniciais(nome) -> str:
    partes = [p for p in str(nome or "").replace("+", " ").split() if p[:1].isalnum()]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def resumo(campanhas) -> list[dict]:
    """Uma linha por plataforma: campanhas, no ar e entrega média (sem custos)."""
    grupos: dict[str, dict] = {}
    for c in campanhas or []:
        nome = c.get("plataforma") or "Outras"
        g = grupos.setdefault(nome, {"nome": nome, "logo": logo(nome), "iniciais": iniciais(nome),
                                     "n": 0, "no_ar": 0, "pcts": []})
        g["n"] += 1
        g["no_ar"] += 1 if c.get("no_ar") else 0
        if c.get("pct") is not None:
            g["pcts"].append(c["pct"])
    saida = []
    for g in grupos.values():
        pcts = g.pop("pcts")
        g["pct"] = round(sum(pcts) / len(pcts)) if pcts else None
        saida.append(g)
    return sorted(saida, key=lambda g: (-g["n"], g["nome"]))
