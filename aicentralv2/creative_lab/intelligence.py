"""Two creative agents for the Lab, both grounded in docs/creative-lab/01-anatomia-criativos-reais.md.

- ``write_brief``: a loose idea + the audited brand → a structured briefing v2 (archetype, copy levels,
  casting, devices). The copy is written as final Portuguese strings, never described.
- ``read_anatomy``: a real ad image → its anatomy (archetype, hero, copy levels, people, devices,
  signature), so real pieces teach the system and can seed a briefing or be reformatted.
"""

from __future__ import annotations

import json
import os
import time

from psycopg.types.json import Json

from ..db import get_db
from ..services.openrouter_service import OpenRouterError, chat_completion, message_text
from . import files, repository
from .archetypes import ARCHETYPES, FORMATS

BRIEF_MODEL = os.getenv("CREATIVE_LAB_BRIEF_MODEL", "openai/gpt-5.4")
ANATOMY_MODEL = os.getenv("CREATIVE_LAB_ANATOMY_MODEL", "openai/gpt-5.4")

RULES = """Rules learned from real Brazilian ads (MaxMilhas, Sebrae, TIM, BDMG, ALMG, Governo de Minas, Uhuru):
1. One hero per piece: an offer number (60% OFF, 29GB, 4,5%) or a concept word (CARNAVAL), 2–4x the headline, in the accent color.
2. Fixed copy levels: kicker → headline → highlight (hero) → support → CTA → seal → tagline → legal. Each is a final string.
3. Copy is written, not described. Qualifiers are part of the text: "até", "ao ano + Selic", "por até 30 dias".
4. Signature: logo bottom-right, usually on a solid band.
5. Flat brand-color fields dominate; photos enter as cut-out people or as a photo block, never as an atmospheric scene.
6. People are the audience persona: Brazilian, diverse, cut out, looking at the camera or using the product. Describe age, profession, action, wardrobe, expression.
7. Each brand has a graphic kit (ribbon, bars, circular seal, badge in a brand shape, 3D icon, doodles).
8. Heavy sans headlines, mostly uppercase; intentional devices: italic, condensed rhythm, syllable break, one word in accent color.
9. The format dictates the layout (story stacks top copy / middle hero / bottom CTAs with UI margins; 300x250 uses few words).
10. Category requirements: finance → rate + qualifier + ombudsman/legal; government → "apresenta" + government signature; retail/telecom → price/allowance + purchase CTA.
11. Display and story have an explicit CTA verb; institutional pieces use a tagline instead.
12. Text covers 25–50% of the area and stays legible at 300 px wide.
Never invent prices, rates or legal claims that are not in the idea or in the brand facts: when a number is missing, use a concept-word hero instead."""


def _json_call(messages, *, model, max_tokens=3000, timeout=150) -> tuple[dict, dict, int]:
    started = time.monotonic()
    result = chat_completion(messages, model=model, max_tokens=max_tokens, response_format={"type": "json_object"},
                             timeout=timeout, provider="openrouter")
    text = message_text(result.get("message") or {})
    try:
        data = json.loads(text[text.find("{"):text.rfind("}") + 1])
    except ValueError as exc:
        raise OpenRouterError("O agente não devolveu JSON.") from exc
    return data, result.get("usage") or {}, round((time.monotonic() - started) * 1000)


def write_brief(idea: str, brand: dict | None, *, objective: str = "", format_key: str = "", archetype: str = "",
                anatomy: dict | None = None) -> dict:
    catalog = {key: {"label": item["label"], "when": item["when"], "copy_levels": item["copy_levels"]}
               for key, item in ARCHETYPES.items()}
    payload = {
        "idea": idea, "objective": objective, "format": FORMATS.get(format_key, {}).get("label") or format_key,
        "preferred_archetype": archetype or None, "brand_facts": brand or None,
        "reference_anatomy": anatomy or None, "archetypes": catalog,
    }
    schema = ('{"archetype": one of the archetype keys, "objective": short, "audience": who and what they need, '
              '"offer": the commercial fact behind the piece (or "" if none), '
              '"copy": {"kicker","headline","highlight","support","cta","seal","tagline","legal"} (Portuguese final strings; omit levels the archetype does not use), '
              '"casting": [one line per person: age, profession, action, wardrobe, expression, gaze], '
              '"devices": [graphic devices from the brand kit or the archetype], "rationale": one sentence in Portuguese}')
    messages = [
        {"role": "system", "content": "You are the senior art director of a Brazilian advertising agency. You turn a loose idea "
                                      "into a production-ready briefing for one ad. " + RULES + "\nReturn JSON only: " + schema},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]
    data, usage, latency = _json_call(messages, model=BRIEF_MODEL)
    if data.get("archetype") not in ARCHETYPES:
        data["archetype"] = archetype if archetype in ARCHETYPES else "oferta-heroi"
    data["format_key"] = format_key or ""
    data["copy"] = {key: str(value).strip() for key, value in (data.get("copy") or {}).items() if str(value or "").strip()}
    return {"brief": data, "usage": usage, "latency_ms": latency, "model": BRIEF_MODEL}


ANATOMY_SCHEMA = ('{"archetype": one of ' + ", ".join(ARCHETYPES) + ' or "outro", "format": "e.g. 1:1, 9:16, 300x250", '
                  '"hero": {"element": text or object, "why_it_dominates": short}, '
                  '"copy": {"kicker","headline","highlight","support","cta","seal","tagline","legal"} exact transcription (omit absent levels), '
                  '"reading_order": [levels in the order the eye reads], '
                  '"people": [{"description","role_in_message","pose","gaze"}], '
                  '"background": "flat color | gradient | photo | split | ...", '
                  '"palette_roles": {"background","accent","text","cta"} as hex, '
                  '"devices": [graphic devices], "type_style": "case, weight, italic/condensed, special devices", '
                  '"signature": {"position","band","elements"}, "text_area_share": 0..1, '
                  '"what_works": [3 short lessons in Portuguese], "risks": [what an AI model would likely get wrong reproducing it, in Portuguese]}')


def read_anatomy(client_id: int, ref_id: int) -> dict:
    ref = repository.get_reference(client_id, ref_id)
    messages = [
        {"role": "system", "content": "You are an advertising art director analyzing a real ad to teach a creative system how it works. "
                                      "Describe only what is visible; transcribe text character by character. Return JSON only: " + ANATOMY_SCHEMA},
        {"role": "user", "content": [
            {"type": "text", "text": "Decompose this ad. Archetype definitions: "
                                     + json.dumps({key: item["layout"] for key, item in ARCHETYPES.items()}, ensure_ascii=False)},
            {"type": "image_url", "image_url": {"url": files.jpeg_data_url(ref["file_id"], side=1280)}},
        ]},
    ]
    data, usage, latency = _json_call(messages, model=ANATOMY_MODEL, max_tokens=3500)
    data["_meta"] = {"model": ANATOMY_MODEL, "usage": usage, "latency_ms": latency}
    with get_db().cursor() as cursor:
        cursor.execute("UPDATE cx_lab_references SET anatomy = %s, is_benchmark = TRUE WHERE client_id = %s AND id = %s",
                       (Json(data), client_id, ref_id))
    get_db().commit()
    return repository.get_reference(client_id, ref_id)


def brief_from_anatomy(anatomy: dict, format_key: str = "") -> dict:
    """Seed a briefing from a real piece: same archetype and copy levels, ready to adapt."""
    people = [" — ".join(str(person.get(key) or "") for key in ("description", "pose", "gaze") if person.get(key))
              for person in anatomy.get("people") or []]
    return {"archetype": anatomy.get("archetype") if anatomy.get("archetype") in ARCHETYPES else "oferta-heroi",
            "format_key": format_key, "copy": {key: value for key, value in (anatomy.get("copy") or {}).items() if value},
            "casting": people, "devices": anatomy.get("devices") or []}
