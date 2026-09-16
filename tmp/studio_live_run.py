"""Live Studio run: marca da base + OpenRouter (texto, imagem, vídeo)."""

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aicentralv2 import create_app  # noqa: E402
from aicentralv2.config import Config, DevelopmentConfig  # noqa: E402
from aicentralv2.creative_format_lab.brand_context import build_brand_context  # noqa: E402
from aicentralv2.creative_format_lab.campaign_models import load_campaign_model  # noqa: E402
from aicentralv2.creative_format_lab.prototype import (  # noqa: E402
    CAST_MODEL,
    SEEDANCE_MODEL,
    animate_spec,
    build_refs,
    build_script,
    compose_scenes,
    quote_prototype,
    video_payload,
)
from aicentralv2.creative_modeling_fx import brl_from_usd, usd_brl_rate  # noqa: E402
from aicentralv2.services.openrouter_service import (  # noqa: E402
    chat_completion,
    generate_image,
    generate_video,
    poll_video,
    resolve_api_key,
)

OUT = ROOT / "tmp" / "studio-live-vivara"
OUT.mkdir(parents=True, exist_ok=True)
LEDGER = []
TEXT_USAGE = []


def now():
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def usage_cost(usage):
    if not isinstance(usage, dict):
        return 0.0
    for key in ("cost", "total_cost"):
        if usage.get(key) not in (None, ""):
            try:
                return float(usage[key])
            except (TypeError, ValueError):
                pass
    details = usage.get("cost_details") if isinstance(usage.get("cost_details"), dict) else {}
    raw = details.get("upstream_inference_cost")
    if raw not in (None, ""):
        try:
            return float(raw)
        except (TypeError, ValueError):
            pass
    return 0.0


def log_step(name, model, usage, extra=None):
    usd = usage_cost(usage)
    rate, source = usd_brl_rate()
    row = {
        "step": name,
        "model": model,
        "usd": round(usd, 6),
        "brl": brl_from_usd(usd, rate),
        "usage": usage or {},
        "at": now(),
    }
    if extra:
        row.update(extra)
    LEDGER.append(row)
    print(
        f"\n[{now()}] {name}\n"
        f"  modelo: {model}\n"
        f"  custo:  US$ {usd:.4f}  ·  R$ {brl_from_usd(usd, rate):.2f}"
        f"  (câmbio {rate:.2f} {source})",
        flush=True,
    )
    return row


def text_callable(messages, **kwargs):
    result = chat_completion(messages, **kwargs)
    TEXT_USAGE.append({
        "model": result.get("model") if isinstance(result, dict) else "",
        "usage": (result or {}).get("usage") if isinstance(result, dict) else {},
    })
    return result


def flush_text_costs(label):
    if not TEXT_USAGE:
        log_step(label, "openai/gpt-5-nano", {})
        return
    calls = list(TEXT_USAGE)
    TEXT_USAGE.clear()
    total = {"cost": sum(usage_cost(item.get("usage")) for item in calls)}
    log_step(
        label,
        calls[-1].get("model") or "openai/gpt-5-nano",
        total,
        extra={"calls": len(calls)},
    )


def image_callable(prompt, aspect_ratio="16:9", resolution="1K", model=None, **_extra):
    return generate_image(
        prompt,
        aspect_ratio=aspect_ratio,
        resolution=resolution or "1K",
        model=model or CAST_MODEL,
        timeout=180,
    )


def save_still(name, still):
    if not still or not still.get("url"):
        return ""
    raw = still["url"]
    if raw.startswith("data:image"):
        import base64

        encoded = raw.split(",", 1)[-1]
        path = OUT / f"{name}.png"
        path.write_bytes(base64.b64decode(encoded))
        return str(path)
    return ""


def load_brand():
    import psycopg
    from psycopg.rows import dict_row

    conn = psycopg.connect(
        dbname=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        row_factory=dict_row,
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, name, sector, tone_of_voice, logo_url,
                       logo_upload_path, primary_color, secondary_color,
                       website_url, brand_profile, analysis_metadata,
                       price_policy
                  FROM cx_clients
                 WHERE name ILIKE %s
                 ORDER BY id
                 LIMIT 1
                """,
                ("%vivara%",),
            )
            row = cursor.fetchone()
            if not row:
                cursor.execute(
                    """
                    SELECT id, name, sector, tone_of_voice, logo_url,
                           logo_upload_path, primary_color, secondary_color,
                           website_url, brand_profile, analysis_metadata,
                           price_policy
                      FROM cx_clients
                     WHERE COALESCE(brand_profile, '{}'::jsonb) <> '{}'::jsonb
                     ORDER BY id
                     LIMIT 8
                    """
                )
                rows = list(cursor.fetchall() or [])
                print("Vivara não encontrada. Candidatas:", [item["name"] for item in rows], flush=True)
                row = rows[0] if rows else None
    finally:
        conn.close()
    if not row:
        raise SystemExit("Nenhuma marca na base.")
    return dict(row)


def boot_app():
    app = create_app(DevelopmentConfig)
    ctx = app.app_context()
    ctx.push()
    return app, ctx


def main():
    _app, _ctx = boot_app()
    key = resolve_api_key()
    if not key:
        raise SystemExit("OpenRouter não está configurado na base.")
    print("OpenRouter autenticado via credencial do sistema.", flush=True)

    campaign = load_campaign_model("vivara-presente-ctv")
    client = load_brand()
    brand = build_brand_context(client)
    print(
        f"\nMarca: {brand.get('name')} (id {brand.get('id')})\n"
        f"Setor: {brand.get('sector') or '—'}\n"
        f"Paleta: {brand.get('palette') or [brand.get('primary_color')]}\n"
        f"Campanha simulada: {campaign.get('title')} · {campaign.get('format')} · variante {campaign.get('variant')}\n"
        f"CTA: {campaign.get('cta')} · objetivo: {campaign.get('objective')}",
        flush=True,
    )
    (OUT / "brand.json").write_text(
        json.dumps(
            {
                "id": brand.get("id"),
                "name": brand.get("name"),
                "sector": brand.get("sector"),
                "palette": brand.get("palette"),
                "target_audience": brand.get("target_audience"),
                "campaign": {
                    "slug": campaign.get("slug"),
                    "title": campaign.get("title"),
                    "offer": campaign.get("offer"),
                    "cta": campaign.get("cta"),
                    "objective": campaign.get("objective"),
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    payload = {
        "format_key": campaign.get("format") or "video-linear-15",
        "scene_count": 4,
        "variant": campaign.get("variant") or "C",
        "objective": campaign.get("objective") or "Consideração",
        "offer": campaign.get("offer") or campaign.get("title"),
        "cta": campaign.get("cta") or "Encontre a peça",
        "elenco": "1 pessoa",
        "idade": "35-44",
        "fundo": "imagem",
        "need_cast": True,
        "video": True,
        "video_resolution": "720p",
    }

    quote = quote_prototype(payload)
    print(
        f"\n[{now()}] Cotação prévia (estimativa de catálogo)\n"
        f"  US$ {quote.get('estimated_cost_usd')}  ·  R$ {quote.get('spent_brl')}\n"
        f"  linhas: {quote.get('line')}",
        flush=True,
    )
    (OUT / "00-quote.json").write_text(json.dumps(quote, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"\n[{now()}] 1/5 Roteiro v1→v2→v3 (gpt-5-nano)…", flush=True)
    script = build_script(payload, brand=brand, text_callable=text_callable)
    (OUT / "01-script.json").write_text(
        json.dumps(
            {
                "selected": script.get("selected"),
                "early_exit": script.get("early_exit"),
                "persona": script.get("persona"),
                "v1": script.get("v1"),
                "v2": script.get("v2"),
                "v3": script.get("v3"),
                "storyboard": script.get("storyboard"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        f"  selected={script.get('selected')} early_exit={script.get('early_exit')} "
        f"cenas={len(script.get('storyboard') or [])}",
        flush=True,
    )
    for index, scene in enumerate(script.get("storyboard") or [], start=1):
        print(f"  {index}. [{scene.get('purpose')}] {scene.get('headline')}", flush=True)
    flush_text_costs("roteiro")

    print(f"\n[{now()}] 2/5 Referências — elenco + cenário (gemini-3-pro-image 1K)…", flush=True)
    refs = build_refs(
        {**payload, "storyboard": script.get("storyboard")},
        brand=brand,
        text_callable=text_callable,
        image_callable=image_callable,
    )
    cast_path = save_still("02-cast", refs.get("cast"))
    ground_path = save_still("02-ground", refs.get("ground"))
    (OUT / "02-refs.json").write_text(
        json.dumps(
            {
                "persona": refs.get("persona"),
                "cast_model": (refs.get("cast") or {}).get("model"),
                "ground_model": (refs.get("ground") or {}).get("model"),
                "cast_usage": (refs.get("cast") or {}).get("usage"),
                "ground_usage": (refs.get("ground") or {}).get("usage"),
                "cast_path": cast_path,
                "ground_path": ground_path,
                "cast_prompt": ((refs.get("prompts") or {}).get("cast") or {}).get("v3"),
                "ground_prompt": ((refs.get("prompts") or {}).get("ground") or {}).get("v3"),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    flush_text_costs("prompts_imagem")
    log_step("elenco", CAST_MODEL, (refs.get("cast") or {}).get("usage"), extra={"path": cast_path})
    log_step("cenário", CAST_MODEL, (refs.get("ground") or {}).get("usage"), extra={"path": ground_path})
    print(f"  elenco: {cast_path or '—'}\n  cenário: {ground_path or '—'}", flush=True)

    print(f"\n[{now()}] 3/5 Cenas HTML (sem IA por quadro)…", flush=True)
    built = compose_scenes(
        {
            **payload,
            "storyboard": script.get("storyboard"),
            "refs": refs,
        },
        brand=brand,
    )
    for scene in built.get("scenes") or []:
        (OUT / f"03-{scene['id']}.html").write_text(scene.get("html") or "", encoding="utf-8")
    (OUT / "03-scenes.json").write_text(
        json.dumps(
            {
                "format_key": built.get("format_key"),
                "canvas": built.get("canvas"),
                "safe_area": built.get("safe_area"),
                "scenes": [
                    {
                        "id": item.get("id"),
                        "purpose": item.get("purpose"),
                        "headline": item.get("headline"),
                        "cta": item.get("cta"),
                        "cta_kind": item.get("cta_kind"),
                        "recipe": item.get("recipe"),
                    }
                    for item in (built.get("scenes") or [])
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    last = (built.get("scenes") or [{}])[-1]
    print(
        f"  {len(built.get('scenes') or [])} cenas · {built.get('canvas')} · safe {built.get('safe_area')}\n"
        f"  última CTA kind={last.get('cta_kind')} texto={last.get('cta')!r}",
        flush=True,
    )
    log_step("cenas_html", "html/stack", {}, extra={"usd": 0, "note": "overlay local, $0"})

    print(f"\n[{now()}] 4/5 Display CSS…", flush=True)
    spec = animate_spec({"format_key": payload["format_key"], "seconds": 5, "scenes": built.get("scenes")})
    (OUT / "04-animate.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  {spec.get('seconds')}s · {spec.get('presets')} · US$ {spec.get('cost_usd')}", flush=True)
    log_step("display_css", "css", {}, extra={"usd": 0})

    print(f"\n[{now()}] 5/5 Seedance 5s 720p (first=elenco, last=cenário)…", flush=True)
    first_url = (refs.get("cast") or {}).get("url") or ""
    last_url = (refs.get("ground") or {}).get("url") or first_url
    plan = video_payload(
        {
            "format_key": payload["format_key"],
            "resolution": "720p",
            "scenes": [
                {"id": "scene_01", "render_url": first_url},
                {"id": "scene_04", "render_url": last_url},
            ],
        }
    )
    (OUT / "05-video-plan.json").write_text(
        json.dumps({k: v for k, v in plan.items() if k != "frame_images"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    job = generate_video(
        plan["prompt"],
        model=plan["model"],
        duration=plan["duration"],
        resolution=plan["resolution"],
        aspect_ratio=plan["aspect_ratio"],
        generate_audio=plan["generate_audio"],
        frame_images=plan["frame_images"],
        timeout=90,
    )
    print(f"  job={job.get('id')} status={job.get('status')}", flush=True)
    (OUT / "05-video-job.json").write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

    status = dict(job)
    deadline = time.time() + 420
    while time.time() < deadline:
        time.sleep(8)
        status = poll_video(job.get("id") or "", polling_url=job.get("polling_url"))
        print(f"  poll {now()} → {status.get('status')}", flush=True)
        if str(status.get("status") or "").lower() in {"completed", "complete", "succeeded", "success", "failed", "error"}:
            break
    (OUT / "05-video-status.json").write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    urls = status.get("unsigned_urls") or []
    if urls:
        import requests

        media = requests.get(urls[0], timeout=90)
        media.raise_for_status()
        (OUT / "05-video.mp4").write_bytes(media.content)
        print(f"  vídeo salvo: {OUT / '05-video.mp4'} ({len(media.content)} bytes)", flush=True)
    log_step(
        "video_seedance",
        SEEDANCE_MODEL,
        status.get("usage") or job.get("usage"),
        extra={"job_id": job.get("id"), "status": status.get("status"), "urls": urls[:1]},
    )

    total_usd = sum(float(item.get("usd") or 0) for item in LEDGER)
    rate, source = usd_brl_rate()
    summary = {
        "brand": brand.get("name"),
        "campaign": campaign.get("slug"),
        "total_usd": round(total_usd, 6),
        "total_brl": brl_from_usd(total_usd, rate),
        "rate": rate,
        "rate_source": source,
        "steps": LEDGER,
        "quote_estimate_usd": quote.get("estimated_cost_usd"),
    }
    (OUT / "ledger.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"\n=== TOTAL REAL ===\n"
        f"  US$ {total_usd:.4f}  ·  R$ {summary['total_brl']:.2f}\n"
        f"  estimativa prévia US$ {quote.get('estimated_cost_usd')}\n"
        f"  artefatos: {OUT}",
        flush=True,
    )


if __name__ == "__main__":
    main()
