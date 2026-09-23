"""Private, versioned build workspaces for text and HTML artifacts."""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from flask import current_app

from ..agent_v2.guardrails import _clean_editor_html, _clean_runtime_html


TEXT_TYPES = {
    "brief", "document", "note", "executive_summary", "media_plan", "scenario", "research",
    "meeting_summary", "meeting_agenda",
}


def _root() -> Path:
    root = Path(str(current_app.config.get("CADU_ARTIFACT_WORKSPACE_DIR") or current_app.instance_path))
    return root / "cadu_artifact_workspaces"


def _directory(artifact: dict, version: int) -> Path:
    return (_root() / str(int(artifact["client_id"])) / str(artifact["id"]) / f"v{int(version)}").resolve()


def _document(artifact: dict, content: dict) -> str:
    title = str(artifact.get("title") or "Documento")
    artifact_type = str(artifact.get("type") or "document")
    if artifact_type == "html":
        body = _clean_runtime_html(content.get("html"), None)
        css = str(content.get("css") or "").replace("</style", "<\\/style")
        javascript = str(content.get("js") or "").replace("</script", "<\\/script")
        def color(value):
            return value if isinstance(value, str) and re.fullmatch(r"#[0-9a-fA-F]{3,8}", value) else ""
        primary, secondary = color(content.get("primary_color")), color(content.get("secondary_color"))
        theme = ";".join(part for part in (
            f"--cadu-brand-primary:{primary}" if primary else "",
            f"--cadu-brand-secondary:{secondary}" if secondary else "",
        ) if part)
        logo = str(content.get("logo_url") or "")
        logo = logo if logo.startswith("https://") or logo.startswith("/") and not logo.startswith("//") else ""
        brand_header = ""
        if logo and "<img" not in body.lower():
            brand_header = (
                '<header data-cadu-brand-header class="mx-auto flex w-full max-w-6xl items-center gap-3 '
                'border-b border-slate-200 px-6 py-4" style="border-bottom-color:var(--cadu-brand-primary,#176b5e)">'
                f'<img src="{escape(logo, quote=True)}" alt="" class="h-8 w-auto object-contain">'
                f'<span class="text-sm font-semibold text-slate-700">{escape(str(content.get("title") or title))}</span>'
                '</header>'
            )
        return f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{escape(title)}</title>
<link rel="stylesheet" href="/static/css/tailwind/artifact.css"><style>:root{{{theme}}}
html,body{{margin:0;min-height:100%;background:#f8fafc}}{css}</style></head>
<body>{brand_header}{body}{f'<script>{javascript}</script>' if javascript else ''}</body></html>"""
    else:
        body = _clean_editor_html(content.get("html") or content.get("content") or "", None)
        css = ""
        javascript = ""
    safe_title = (title.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                  .replace('"', "&quot;"))
    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{safe_title}</title>
  <link rel="stylesheet" href="/static/css/tailwind/artifact.css">
  <style>
    :root{{--artifact-bg:#f8fafc;--artifact-ink:#10232b;--artifact-muted:#5c7078;--artifact-accent:#167f73}}
    *{{box-sizing:border-box}}html,body{{margin:0;min-height:100%;background:var(--artifact-bg);color:var(--artifact-ink)}}
    body{{font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
    .cadu-artifact-page{{width:min(1180px,100%);margin:0 auto;padding:clamp(24px,5vw,72px)}}
    .cadu-artifact-page :where(p,li){{line-height:1.7}}.cadu-artifact-page :where(h1,h2,h3){{letter-spacing:-.025em}}
    {css}
  </style>
</head>
<body><main class="cadu-artifact-page">{body}</main>{f'<script>{javascript}</script>' if javascript else ''}</body>
</html>"""


def materialize(artifact: dict) -> Path | None:
    """Write the current immutable version after database persistence."""
    if artifact.get("type") not in TEXT_TYPES | {"html"}:
        return None
    version = int(artifact.get("current_version") or artifact.get("version") or 1)
    directory = _directory(artifact, version)
    directory.mkdir(parents=True, exist_ok=True)
    content = artifact.get("content") if isinstance(artifact.get("content"), dict) else {}
    target = directory / "index.html"
    temporary = directory / "index.html.tmp"
    temporary.write_text(_document(artifact, content), encoding="utf-8")
    temporary.replace(target)
    (directory / "manifest.json").write_text(json.dumps({
        "artifact_id": str(artifact["id"]), "version": version, "type": artifact.get("type"),
        "title": artifact.get("title"),
    }, ensure_ascii=False), encoding="utf-8")
    return target
