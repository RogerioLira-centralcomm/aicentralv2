"""Baixa fotos reais (Firecrawl) para os shoppings e lugares novos."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

try:
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from aicentralv2.places.schema import public_view
from aicentralv2.places.venues import VENUE_PLACES
from aicentralv2.places.visual_refs import collect_visual_refs


def main() -> None:
    if not os.getenv("FIRECRAWL_API_KEY"):
        raise SystemExit("FIRECRAWL_API_KEY ausente")
    out = {}
    for item in VENUE_PLACES:
        if item["payload"]["media"].get("hero_url"):
            print("skip", item["slug"])
            continue
        place = public_view(dict(item, id=0, status="published"))
        hero = collect_visual_refs(place, kind="hero", limit=4)
        core = next((point for point in place.get("points") or [] if point.get("scope") != "external"), None)
        point_refs = collect_visual_refs(place, kind="point", point=core, limit=3) if core else []
        local_hero = [row.get("url") for row in hero if str(row.get("url") or "").startswith("/static/")]
        local_point = [row.get("url") for row in point_refs if str(row.get("url") or "").startswith("/static/")]
        out[item["slug"]] = {
            "hero": local_hero or [row.get("url") for row in hero],
            "point_id": (core or {}).get("id"),
            "point": local_point or [row.get("url") for row in point_refs],
        }
        print(item["slug"], len(hero), len(point_refs), out[item["slug"]]["hero"][:1])
    dest = ROOT / "tmp" / "venue-gallery.json"
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("wrote", dest)


if __name__ == "__main__":
    main()
