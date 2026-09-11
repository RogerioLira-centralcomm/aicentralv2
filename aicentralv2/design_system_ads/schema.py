"""Contrato do Design System Ads: tabela HTML → --dsa-* → tema Tailwind."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

FRAMEWORK = "design-system-ads"
MAX_PASSES = 4
MIN_CONTRAST = 4.5
_HEX = re.compile(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$")

TOKEN_ROWS = (
    ("paper", "Fundo", "--dsa-paper", "bg-dsa-paper"),
    ("ink", "Texto", "--dsa-ink", "text-dsa-ink"),
    ("accent", "CTA", "--dsa-accent", "bg-dsa-accent"),
    ("muted", "Apoio", "--dsa-muted", "text-dsa-muted"),
    ("cta_ink", "Texto do CTA", "--dsa-cta-ink", "text-dsa-cta-ink"),
    ("highlight", "Acento", "--dsa-highlight", "bg-dsa-highlight"),
    ("logo", "Logo", "--dsa-logo", ""),
    ("font-display", "Fonte do título", "--dsa-font-display", "font-dsa-display"),
    ("font-body", "Fonte do apoio", "--dsa-font-body", "font-dsa-body"),
    ("type-headline", "Tamanho do título", "--dsa-type-headline", "text-dsa-headline"),
    ("type-support", "Tamanho do apoio", "--dsa-type-support", "text-dsa-support"),
    ("type-cta", "Tamanho do CTA", "--dsa-type-cta", "text-dsa-cta"),
    ("type-legal", "Tamanho do legal", "--dsa-type-legal", "text-dsa-legal"),
    ("cta-radius", "Canto do CTA", "--dsa-cta-radius", "rounded-dsa-cta"),
    ("safe", "Margem segura", "--dsa-safe", ""),
    ("weight-display", "Peso do título", "--dsa-weight-display", ""),
    ("weight-cta", "Peso do CTA", "--dsa-weight-cta", ""),
    ("tracking", "Tracking do título", "--dsa-tracking", ""),
    ("cta-pad", "Miolo do CTA", "--dsa-cta-pad", ""),
    ("cta-shadow", "Sombra do CTA", "--dsa-cta-shadow", ""),
    ("hairline", "Filete", "--dsa-hairline", ""),
    ("ground", "Imagem de fundo", "--dsa-ground", ""),
    ("ground-fit", "Encaixe do fundo", "--dsa-ground-fit", ""),
    ("ground-kind", "Tipo de fundo", "--dsa-ground-kind", ""),
    ("overlay", "Véu do fundo", "--dsa-overlay", ""),
)


def normalize_hex(value, default=""):
    raw = str(value or "").strip()
    if not raw:
        return default
    if not raw.startswith("#") and re.fullmatch(r"[0-9a-fA-F]{3,6}", raw):
        raw = f"#{raw}"
    if not _HEX.match(raw):
        return default
    if len(raw) == 4:
        raw = "#" + "".join(ch * 2 for ch in raw[1:])
    return raw.upper()


def relative_luminance(color):
    raw = normalize_hex(color).lstrip("#")
    if len(raw) != 6:
        return 0.0
    red, green, blue = (int(raw[i : i + 2], 16) for i in (0, 2, 4))

    def to_lin(channel):
        sample = channel / 255
        if sample <= 0.04045:
            return sample / 12.92
        return ((sample + 0.055) / 1.055) ** 2.4

    return 0.2126 * to_lin(red) + 0.7152 * to_lin(green) + 0.0722 * to_lin(blue)


def contrast_ratio(first, second):
    left = relative_luminance(first)
    right = relative_luminance(second)
    lighter, darker = (max(left, right), min(left, right))
    return (lighter + 0.05) / (darker + 0.05)


def token_row(token_id, value):
    for key, role, css_var, tw_class in TOKEN_ROWS:
        if key == token_id:
            return {
                "id": key,
                "role": role,
                "css_var": css_var,
                "tw_class": tw_class,
                "value": value,
            }
    return {
        "id": token_id,
        "role": token_id,
        "css_var": f"--dsa-{token_id}",
        "tw_class": "",
        "value": value,
    }


class DesignSystemPass(BaseModel):
    attempt: int = 1
    passed: bool = False
    score: float = 0.0
    defects: List[str] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    patches: List[Dict[str, Any]] = Field(default_factory=list)


class DesignSystemAds(BaseModel):
    framework: str = FRAMEWORK
    id: str = "dsa-draft"
    scope: str = "brand"
    name: str = "Design System Ads"
    source: str = "brand"
    status: str = "draft"
    version: int = 1
    client_id: Optional[Any] = None
    logo_url: str = ""
    tokens: Dict[str, Any] = Field(default_factory=dict)
    css_vars: Dict[str, str] = Field(default_factory=dict)
    tailwind: Dict[str, Any] = Field(default_factory=dict)
    contrast: Dict[str, Any] = Field(default_factory=dict)
    ad_copy: Dict[str, str] = Field(default_factory=dict)
    inherits_brand_id: Optional[Any] = None
    creative_line: str = ""
    elements: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    dna: Dict[str, Any] = Field(default_factory=dict)
    backgrounds: List[Dict[str, Any]] = Field(default_factory=list)
    archetype: str = "brand"
    rules: Dict[str, Any] = Field(default_factory=dict)
    tracks: List[Dict[str, Any]] = Field(default_factory=list)
    passes: List[DesignSystemPass] = Field(default_factory=list)
    specimen_html: str = ""

    @field_validator("scope")
    @classmethod
    def _scope(cls, value):
        text = str(value or "brand").strip().lower()
        return text if text in {"brand", "campaign"} else "brand"

    @field_validator("status")
    @classmethod
    def _status(cls, value):
        text = str(value or "draft").strip().lower()
        return text if text in {"draft", "approved", "archived"} else "draft"

    @field_validator("framework")
    @classmethod
    def _framework(cls, value):
        return FRAMEWORK

    @model_validator(mode="after")
    def _compile(self):
        tokens = dict(self.tokens or {})
        tokens.setdefault("paper", "#FFFFFF")
        tokens.setdefault("ink", "#1E4D4F")
        tokens.setdefault("accent", tokens.get("ink") or "#1E4D4F")
        tokens.setdefault("muted", "#3D4451")
        tokens.setdefault("cta_ink", "#FFFFFF")
        tokens.setdefault("highlight", "#F3B71B")
        tokens.setdefault("font-display", "Inter")
        tokens.setdefault("font-body", tokens.get("font-display") or "Inter")
        tokens.setdefault("type-headline", "72px")
        tokens.setdefault("type-support", "28px")
        tokens.setdefault("type-cta", "22px")
        tokens.setdefault("type-legal", "14px")
        tokens.setdefault("cta-radius", "0.25rem")
        tokens.setdefault("safe", "6%")
        tokens.setdefault("weight-display", "700")
        tokens.setdefault("weight-cta", "600")
        tokens.setdefault("tracking", "-0.015em")
        tokens.setdefault("cta-pad", "0.7em 1.2em")
        tokens.setdefault("cta-shadow", "none")
        tokens.setdefault("hairline", tokens.get("muted") or "#3D4451")
        tokens.setdefault("ground", "")
        tokens.setdefault("ground-fit", "cover")
        tokens.setdefault("ground-kind", "paper")
        tokens.setdefault("overlay", "transparent")
        if self.logo_url and not tokens.get("logo"):
            tokens["logo"] = self.logo_url
        self.logo_url = str(tokens.get("logo") or self.logo_url or "")
        self.tokens = tokens
        self.css_vars = compile_css_vars(tokens)
        self.tailwind = compile_tailwind_theme(tokens)
        self.contrast = measure_contrast(tokens)
        if not self.backgrounds:
            from .components import default_backgrounds

            self.backgrounds = default_backgrounds(tokens)
        if not self.rules:
            from .components import compile_rules

            self.rules = compile_rules(self.dna, self.archetype)
        if not self.tracks:
            from .tracks import default_tracks

            self.tracks = default_tracks()
        from .copy import clean_ad_copy

        self.ad_copy = clean_ad_copy(self.ad_copy, self.name)
        return self


def compile_css_vars(tokens):
    mapping = {key: css_var for key, _role, css_var, _tw in TOKEN_ROWS}
    compiled = {}
    for key, value in (tokens or {}).items():
        compiled[mapping.get(key, f"--dsa-{key}")] = str(value)
    return compiled


def compile_tailwind_theme(tokens):
    tokens = tokens if isinstance(tokens, dict) else {}
    return {
        "base": "tailwind",
        "source": "static/css/tailwind/design-system.css",
        "theme": {
            "extend": {
                "colors": {
                    "dsa": {
                        "paper": "var(--dsa-paper)",
                        "ink": "var(--dsa-ink)",
                        "accent": "var(--dsa-accent)",
                        "muted": "var(--dsa-muted)",
                        "cta-ink": "var(--dsa-cta-ink)",
                        "highlight": "var(--dsa-highlight)",
                    }
                },
                "fontFamily": {
                    "dsa-display": [
                        "var(--dsa-font-display)",
                        "Inter",
                        "ui-sans-serif",
                        "sans-serif",
                    ],
                    "dsa-body": [
                        "var(--dsa-font-body)",
                        "Inter",
                        "ui-sans-serif",
                        "sans-serif",
                    ],
                },
                "borderRadius": {"dsa-cta": "var(--dsa-cta-radius)"},
                "boxShadow": {"dsa-cta": "var(--dsa-cta-shadow)"},
                "fontSize": {
                    "dsa-headline": "var(--dsa-type-headline)",
                    "dsa-support": "var(--dsa-type-support)",
                    "dsa-cta": "var(--dsa-type-cta)",
                    "dsa-legal": "var(--dsa-type-legal)",
                },
            }
        },
        "classes": {
            key: tw_class
            for key, _role, _css, tw_class in TOKEN_ROWS
            if tw_class
        },
        "values": {
            "paper": tokens.get("paper"),
            "ink": tokens.get("ink"),
            "accent": tokens.get("accent"),
            "muted": tokens.get("muted"),
        },
    }


def measure_contrast(tokens):
    tokens = tokens if isinstance(tokens, dict) else {}
    paper = normalize_hex(tokens.get("paper"), "#FFFFFF")
    ink = normalize_hex(tokens.get("ink"), "#1E4D4F")
    accent = normalize_hex(tokens.get("accent"), ink)
    cta_ink = normalize_hex(tokens.get("cta_ink"), "#FFFFFF")
    pairs = {
        "ink_on_paper": round(contrast_ratio(ink, paper), 2),
        "cta_on_accent": round(contrast_ratio(cta_ink, accent), 2),
    }
    return {
        "pairs": pairs,
        "min": MIN_CONTRAST,
        "passed": all(value >= MIN_CONTRAST for value in pairs.values()),
        "locks": [
            "ink sobre paper",
            "texto do CTA sobre accent",
        ],
    }


def parse_system(data):
    if isinstance(data, DesignSystemAds):
        return data
    payload = dict(data) if isinstance(data, dict) else {}
    tokens = payload.get("tokens") if isinstance(payload.get("tokens"), dict) else {}
    if payload.get("framework") != FRAMEWORK and tokens.get("framework") == FRAMEWORK:
        payload = dict(tokens)
    if payload.get("copy") and not payload.get("ad_copy"):
        payload["ad_copy"] = payload.get("copy")
    return DesignSystemAds.model_validate(payload or {})


def dump_system(system):
    parsed = parse_system(system)
    return parsed.model_dump()


def token_table_rows(system):
    parsed = parse_system(system)
    return [token_row(key, parsed.tokens.get(key, "")) for key, *_ in TOKEN_ROWS]
