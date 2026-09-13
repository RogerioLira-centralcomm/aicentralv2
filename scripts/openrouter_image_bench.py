#!/usr/bin/env python
"""CLI antigo de screening t2i no OpenRouter (menor tier, custo em BRL).

O plano que decide Trocr + Gerar — e a futura página com prompts das
mesas — está em docs/image-model-bench.md. Não use este script como
teste do Trocr: ele não manda still nem build_optimized_prompt.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

OPENROUTER_IMAGES = "https://openrouter.ai/api/v1/images"
OPENROUTER_MODELS = "https://openrouter.ai/api/v1/images/models"
USD_BRL = float(os.getenv("USD_BRL", "5.1254"))
ASPECT = "16:9"

PROMPTS = [
    {
        "id": "place-fotoreal",
        "label": "Place fotoreal (uso atual de Places)",
        "prompt": (
            "Photoreal dusk exterior of Congonhas Airport CGH in Sao Paulo, Brazil. "
            "Wide real place, people and architecture as they are, no text, no logos, "
            "no UI, cinematic, 16:9."
        ),
    },
    {
        "id": "anuncio-tipografia",
        "label": "Anúncio com texto exato (uso de Ads)",
        "prompt": (
            "Premium outdoor billboard photograph at dusk, wet pavement reflections. "
            "The headline reads exactly \"CENTRALCOMM\" in bold condensed white sans-serif. "
            "Below, a smaller line reads exactly \"mídia que chega\". Deep navy background, "
            "one warm spotlight, no extra text, no logos besides the headline, 16:9."
        ),
    },
]

MODELS = [
    {
        "id": "openai/gpt-image-2",
        "label": "GPT Image 2 (baseline)",
        "quality": "low",
        "output_format": "jpeg",
    },
    {
        "id": "openai/gpt-image-2.5-flare",
        "label": "GPT Image 2.5 Flare",
        "quality": "low",
        "output_format": "jpeg",
    },
    {
        "id": "google/gemini-3.1-flash-image",
        "label": "Nano Banana 2",
        "resolution": "512",
        "output_format": "jpeg",
    },
    {
        "id": "google/gemini-3-pro-image",
        "label": "Nano Banana Pro",
        "resolution": "1K",
        "output_format": "jpeg",
    },
    {
        "id": "bytedance-seed/seedream-5-0-lite",
        "label": "Seedream 5 Lite",
        "resolution": "2K",
        "output_format": "jpeg",
    },
    {
        "id": "bytedance-seed/seedream-4.5",
        "label": "Seedream 4.5",
        "resolution": "1K",
        "output_format": "jpeg",
    },
    {
        "id": "black-forest-labs/flux.2-klein-4b",
        "label": "FLUX.2 Klein 4B",
        "output_format": "jpeg",
    },
    {
        "id": "qwen/qwen-image-3",
        "label": "Qwen Image 3",
        "resolution": "1K",
        "output_format": "jpeg",
    },
]


def _api_key() -> str:
    env = os.getenv("OPENROUTER_API_KEY", "").strip()
    if env:
        return env
    from aicentralv2 import create_app
    from aicentralv2.services.openrouter_service import resolve_api_key

    app = create_app()
    with app.app_context():
        key = resolve_api_key()
    if not key:
        raise SystemExit("OpenRouter não está configurado (env ou credencial no banco).")
    return key


def _headers(key: str) -> dict:
    return {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://centralcomm.media",
        "X-Title": "CentralX image bench",
    }


def catalog(key: str) -> dict:
    response = requests.get(OPENROUTER_MODELS, headers=_headers(key), timeout=30)
    response.raise_for_status()
    return {item["id"]: item for item in response.json().get("data") or []}


def lowest_payload(spec: dict, prompt: str, capabilities: dict | None) -> dict:
    params = (capabilities or {}).get("supported_parameters") or {}
    payload = {
        "model": spec["id"],
        "prompt": prompt,
        "n": 1,
        "aspect_ratio": ASPECT,
    }
    if "resolution" in spec and "resolution" in params:
        allowed = ((params.get("resolution") or {}).get("values") or [])
        wanted = spec["resolution"]
        payload["resolution"] = wanted if wanted in allowed else (allowed[0] if allowed else wanted)
    if "quality" in spec and "quality" in params:
        payload["quality"] = spec["quality"]
    if "output_format" in spec and "output_format" in params:
        allowed = ((params.get("output_format") or {}).get("values") or [])
        wanted = spec["output_format"]
        if not allowed or wanted in allowed:
            payload["output_format"] = wanted
    return payload


def generate(key: str, payload: dict, timeout: int = 180) -> dict:
    started = time.perf_counter()
    response = requests.post(
        OPENROUTER_IMAGES,
        headers=_headers(key),
        json=payload,
        timeout=timeout,
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    try:
        data = response.json()
    except ValueError:
        data = {"error": {"message": response.text[:400]}}
    if response.status_code >= 400:
        error = data.get("error") if isinstance(data, dict) else {}
        message = ""
        if isinstance(error, dict):
            message = str(error.get("message") or "")
        raise RuntimeError(message or f"HTTP {response.status_code}")
    images = data.get("data") or []
    first = images[0] if images else {}
    encoded = first.get("b64_json") if isinstance(first, dict) else None
    url = first.get("url") if isinstance(first, dict) else None
    if not encoded and url:
        fetched = requests.get(url, timeout=60)
        fetched.raise_for_status()
        encoded = base64.b64encode(fetched.content).decode("ascii")
    if not encoded:
        raise RuntimeError("O provedor não retornou a imagem.")
    usage = data.get("usage") or {}
    cost_usd = float(usage.get("cost") or 0)
    return {
        "b64_json": encoded,
        "media_type": first.get("media_type") or "image/jpeg",
        "model": data.get("model") or payload["model"],
        "usage": usage,
        "cost_usd": cost_usd,
        "cost_brl": round(cost_usd * USD_BRL, 4),
        "elapsed_ms": elapsed_ms,
        "payload": payload,
    }


def _slug(value: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in value.lower()).strip("-")


ESTIMATES = {
    "openai/gpt-image-2": {
        "tier": "quality=low · 16:9",
        "usd": 0.005,
        "note": "Calculadora OpenAI para 1536×1024 low. Playground high 16:9 cobra ~US$ 0,13.",
    },
    "openai/gpt-image-2.5-flare": {
        "tier": "quality=low · 16:9",
        "usd": 0.005,
        "note": "Mesma tabela de tokens do Image 2 no catálogo OpenRouter (US$ 30/M output).",
    },
    "google/gemini-3.1-flash-image": {
        "tier": "resolution=512",
        "usd": 0.0448,
        "note": "747 tokens × US$ 60/M. 1K sobe para ~US$ 0,067; 2K ~US$ 0,101.",
    },
    "google/gemini-3-pro-image": {
        "tier": "resolution=1K (mínimo)",
        "usd": 0.134,
        "note": "Nano Banana Pro: ~1.120 tokens × US$ 120/M. Não tem 512.",
    },
    "bytedance-seed/seedream-5-0-lite": {
        "tier": "resolution=2K (mínimo)",
        "usd": 0.035,
        "note": "Preço fixo por imagem no OpenRouter. Mínimo já é 2K.",
    },
    "bytedance-seed/seedream-4.5": {
        "tier": "resolution=1K",
        "usd": 0.04,
        "note": "Preço fixo por imagem.",
    },
    "black-forest-labs/flux.2-klein-4b": {
        "tier": "16:9 ~1 MP",
        "usd": 0.014,
        "note": "US$ 0,014/megapixel. Custo sobe se o provedor entregar mais pixels.",
    },
    "qwen/qwen-image-3": {
        "tier": "resolution=1K",
        "usd": 0.03,
        "note": "Preço fixo 1K/2K = US$ 0,03.",
    },
}


def estimate(only: list[str] | None = None) -> dict:
    models = [item for item in MODELS if not only or item["id"] in only]
    rows = []
    for spec in models:
        info = ESTIMATES[spec["id"]]
        usd = info["usd"]
        rows.append(
            {
                "model": spec["id"],
                "label": spec["label"],
                "tier": info["tier"],
                "usd": usd,
                "brl": round(usd * USD_BRL, 4),
                "usd_two_prompts": round(usd * len(PROMPTS), 4),
                "brl_two_prompts": round(usd * len(PROMPTS) * USD_BRL, 4),
                "note": info["note"],
            }
        )
    total_usd = round(sum(row["usd_two_prompts"] for row in rows), 4)
    report = {
        "usd_brl": USD_BRL,
        "prompts": len(PROMPTS),
        "rows": rows,
        "total_usd": total_usd,
        "total_brl": round(total_usd * USD_BRL, 4),
        "production_gpt_image_2_high_usd": 0.1303,
        "production_gpt_image_2_high_brl": round(0.1303 * USD_BRL, 4),
    }
    print(f"Câmbio USD/BRL {USD_BRL:.4f} · {len(PROMPTS)} prompts · menor tier\n")
    print(f"{'Modelo':<28} {'tier':<24} {'1 img':>10} {'2 prompts':>12}")
    for row in rows:
        print(
            f"{row['label']:<28} {row['tier']:<24} "
            f"R${row['brl']:>7.3f}  R${row['brl_two_prompts']:>8.3f}"
        )
    print(
        f"\nLote completo (todos os modelos × {len(PROMPTS)} prompts): "
        f"${report['total_usd']:.3f} / R${report['total_brl']:.2f}"
    )
    print(
        f"Produção atual GPT Image 2 high 16:9: "
        f"${report['production_gpt_image_2_high_usd']:.3f} / "
        f"R${report['production_gpt_image_2_high_brl']:.2f} por imagem"
    )
    return report


def run(out_dir: Path, only: list[str] | None = None) -> dict:
    key = _api_key()
    caps = catalog(key)
    dest = out_dir / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dest.mkdir(parents=True, exist_ok=True)
    models = [item for item in MODELS if not only or item["id"] in only]
    rows = []
    for spec in models:
        for prompt in PROMPTS:
            payload = lowest_payload(spec, prompt["prompt"], caps.get(spec["id"]))
            row = {
                "prompt_id": prompt["id"],
                "prompt_label": prompt["label"],
                "model": spec["id"],
                "label": spec["label"],
                "payload": payload,
            }
            print(f"→ {spec['label']} · {prompt['id']}", flush=True)
            try:
                result = generate(key, payload)
                ext = "jpg" if "jpeg" in result["media_type"] else "png"
                filename = f"{prompt['id']}__{_slug(spec['id'])}.{ext}"
                path = dest / filename
                path.write_bytes(base64.b64decode(result["b64_json"]))
                row.update(
                    {
                        "ok": True,
                        "file": str(path),
                        "served_model": result["model"],
                        "usage": result["usage"],
                        "cost_usd": result["cost_usd"],
                        "cost_brl": result["cost_brl"],
                        "elapsed_ms": result["elapsed_ms"],
                    }
                )
                print(
                    f"  ok {result['elapsed_ms']}ms "
                    f"${result['cost_usd']:.4f} / R${result['cost_brl']:.3f} → {filename}",
                    flush=True,
                )
            except Exception as exc:
                row.update({"ok": False, "error": str(exc)[:400]})
                print(f"  falhou: {exc}", flush=True)
            rows.append(row)
    report = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "usd_brl": USD_BRL,
        "aspect_ratio": ASPECT,
        "prompts": PROMPTS,
        "rows": rows,
        "totals": _totals(rows),
    }
    (dest / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_markdown(dest / "report.md", report)
    print(f"\nRelatório: {dest / 'report.md'}")
    return report


def _totals(rows: list[dict]) -> dict:
    ok = [row for row in rows if row.get("ok")]
    by_model = {}
    for row in ok:
        bucket = by_model.setdefault(
            row["model"],
            {"label": row["label"], "usd": 0.0, "brl": 0.0, "ok": 0, "ms": 0},
        )
        bucket["usd"] += float(row.get("cost_usd") or 0)
        bucket["brl"] += float(row.get("cost_brl") or 0)
        bucket["ok"] += 1
        bucket["ms"] += int(row.get("elapsed_ms") or 0)
    return {
        "ok": len(ok),
        "failed": len(rows) - len(ok),
        "usd": round(sum(float(row.get("cost_usd") or 0) for row in ok), 4),
        "brl": round(sum(float(row.get("cost_brl") or 0) for row in ok), 4),
        "by_model": by_model,
    }


def _write_markdown(path: Path, report: dict) -> None:
    lines = [
        "# Bancada OpenRouter — modelos de imagem",
        "",
        f"Câmbio usado: USD 1 = R$ {report['usd_brl']:.4f} (fechamento 11/09/2026).",
        f"Aspecto: `{report['aspect_ratio']}`. Cada modelo no menor tier que aceita.",
        "",
        "## Custo por modelo (soma dos prompts que passaram)",
        "",
        "| Modelo | Imagens | USD | BRL | Tempo médio |",
        "|---|---:|---:|---:|---:|",
    ]
    for model, bucket in report["totals"]["by_model"].items():
        avg = int(bucket["ms"] / bucket["ok"]) if bucket["ok"] else 0
        lines.append(
            f"| {bucket['label']} (`{model}`) | {bucket['ok']} | "
            f"${bucket['usd']:.4f} | R${bucket['brl']:.3f} | {avg} ms |"
        )
    lines.extend(
        [
            "",
            f"Total: **${report['totals']['usd']:.4f} / R${report['totals']['brl']:.3f}** "
            f"({report['totals']['ok']} ok, {report['totals']['failed']} falhas).",
            "",
            "## Detalhe",
            "",
        ]
    )
    for row in report["rows"]:
        status = "ok" if row.get("ok") else f"falhou: {row.get('error')}"
        cost = (
            f"${row.get('cost_usd', 0):.4f} / R${row.get('cost_brl', 0):.3f}"
            if row.get("ok")
            else "—"
        )
        lines.append(f"- **{row['label']}** · {row['prompt_id']}: {status} · {cost}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Bancada de modelos de imagem OpenRouter")
    parser.add_argument(
        "--out",
        default=str(ROOT / "temp" / "image-bench"),
        help="Pasta de saída (gitignored)",
    )
    parser.add_argument("--only", nargs="*", help="Slugs OpenRouter para filtrar")
    parser.add_argument(
        "--estimate",
        action="store_true",
        help="Só imprime custo estimado no menor tier, sem gastar créditos",
    )
    args = parser.parse_args()
    if args.estimate:
        estimate(only=args.only)
        return
    run(Path(args.out), only=args.only)


if __name__ == "__main__":
    main()
