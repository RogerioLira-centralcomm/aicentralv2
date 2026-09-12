"""Fecha o Ads: trilhas migradas e projeção órfã."""

from pathlib import Path
from unittest.mock import patch
import unittest

from aicentralv2.creative_modeling_service import CreativeModelingService
from aicentralv2.design_system_ads.centralcomm import centralcomm_preset
from aicentralv2.design_system_ads.materialize import ensure_brand_design_system
from aicentralv2.design_system_ads.prompt_context import build_ads_prompt_context
from aicentralv2.design_system_ads.revision import ORPHAN_PROJECTION, storage_report
from aicentralv2.design_system_ads.runtime_policy import MIGRATED_TASKS, UNMIGRATED_TASKS
from aicentralv2.design_system_ads.schema import dump_system
from aicentralv2.design_system_ads.tracks import build_track_prompt, prompt_for_track

ROOT = Path(__file__).resolve().parents[1]


class FakeProjectionRepo:
    def __init__(self, tokens):
        self.tokens = tokens
        self.profile = {}

    def get_design_system_ads(self, client_id):
        return {"client_id": client_id, "tokens": self.tokens, "name": "Design System Ads"}

    def update_client_brand_profile_cas(self, client_id, profile, expected):
        from aicentralv2.creative_modeling_repository import CreativeConflictError
        from aicentralv2.design_system_ads.revision import read_revision

        stored = read_revision((self.profile.get("design_system_ads") or {}))
        if stored != expected:
            raise CreativeConflictError("A marca mudou. Recarregue.")
        self.profile = dict(profile)


class DesignSystemAdsFinalizeTest(unittest.TestCase):
    def test_trilhas_entraram_no_runtime(self):
        self.assertIn("tracks", MIGRATED_TASKS)
        self.assertEqual(UNMIGRATED_TASKS, ())
        context = build_ads_prompt_context(
            "tracks",
            centralcomm_preset(),
            format_context={"track_id": "packshot", "aspect": "1:1"},
        )
        self.assertTrue(context["migrated"])
        self.assertEqual(context["prompt_version"], "ads-tracks-2026-09-12")
        self.assertEqual(context["contract"]["output"], "image-prompt")
        self.assertIn("ink", context["identity"]["locked_tokens"])
        prompt, built = build_track_prompt(centralcomm_preset(), "packshot")
        self.assertIn("#1E4D4F", prompt)
        self.assertNotIn("reconhecível", prompt)
        self.assertEqual(prompt_for_track(centralcomm_preset(), "packshot"), prompt)
        self.assertEqual(built["task"], "tracks")

    def test_projecao_orfã_nao_entra_no_cas(self):
        stored = dump_system(
            ensure_brand_design_system(
                {"id": 9, "name": "Clara", "primary_color": "#082C9C"}
            )
        )
        stored["revision"] = 4
        repo = FakeProjectionRepo(stored)
        service = CreativeModelingService.__new__(CreativeModelingService)
        service.repository = repo
        client = {"id": 9, "name": "Clara", "brand_profile": {}}
        service.get_client = lambda _cid: {
            **client,
            "brand_profile": dict(repo.profile),
        }
        payload = service.get_brand_design_system(9)
        self.assertTrue(payload["storage"]["orphan"])
        self.assertEqual(payload["storage"]["label"], ORPHAN_PROJECTION)
        self.assertEqual(payload["revision"], 0)
        self.assertIsNone(service._stored_brand_design_system(client))
        promoted = service.ensure_brand_design_system(9, expected_revision=0)
        self.assertFalse(promoted["storage"]["orphan"])
        self.assertEqual(promoted["revision"], 1)
        self.assertTrue(repo.profile.get("design_system_ads"))

    def test_mesa_mostra_aviso_de_projecao(self):
        js = (ROOT / "aicentralv2" / "static" / "js" / "mc-design-system.js").read_text(
            encoding="utf-8"
        )
        html = (
            ROOT / "aicentralv2" / "templates" / "parametros" / "_mc_design_system.html"
        ).read_text(encoding="utf-8")
        self.assertIn("function renderStorage", js)
        self.assertIn("mcDsaStorage", html)
        self.assertEqual(storage_report("projection")["orphan"], True)

    def test_trilha_grava_contexto_no_run(self):
        service = CreativeModelingService.__new__(CreativeModelingService)
        service.repository = object()
        service.storage = type("S", (), {"save_generated_base64": staticmethod(lambda _b: "/media/pack.png")})()
        system = ensure_brand_design_system(
            {
                "id": 9,
                "name": "Clara",
                "primary_color": "#082C9C",
                "brand_assets": [{"asset_url": "/media/clara-pack.jpg", "role": "packshot"}],
            }
        )
        data = dump_system(system)
        data["dna"] = {
            "name": "Clara",
            "personality": ["icônica"],
            "must": ["logo"],
            "avoid": ["resize"],
        }
        data["ad_copy"] = {**(system.ad_copy or {}), "legal": "Clara"}
        from aicentralv2.design_system_ads.schema import parse_system

        filled = parse_system(data)
        service.get_client = lambda _cid: {
            "id": 9,
            "brand_profile": {"design_system_ads": dump_system(filled)},
        }
        service._stored_brand_design_system = lambda _client: filled
        service._pin_brand_revision = lambda _client, expected: (expected or 0, "client")
        service._persist_brand_design_system = lambda _client, parsed, expected_revision=None: parsed
        service._track_input_references = lambda *_a, **_k: []
        with patch(
            "aicentralv2.services.openrouter_service.resolve_api_key",
            return_value="sk-test",
        ), patch(
            "aicentralv2.services.openrouter_service.generate_image",
            return_value={"b64_json": "QQ==", "model": "openai/gpt-image-2"},
        ):
            payload = service.generate_brand_track(9, "wash", expected_revision=0)
        self.assertEqual(payload["run"]["context"]["task"], "tracks")
        self.assertTrue(payload["run"]["context"]["instruction_hash"])
        self.assertEqual(payload["run"]["context"]["generation_mode"], "model")


if __name__ == "__main__":
    unittest.main()
