"""Animação do Trocar: plano, cotação, first frame e append sem 409."""

import base64
import unittest
from unittest.mock import patch

from aicentralv2.creative_format_lab.animate import quote_animate
from aicentralv2.creative_format_lab.service import FormatLabService
from aicentralv2.creative_format_lab.swap_session import TrocrStore
from aicentralv2.creative_media.geometry import map_aspect, output_size, prepare_frame
from aicentralv2.creative_media.planner import build_plan
from aicentralv2.creative_media.repository import MemoryMediaRepository
from aicentralv2.creative_media.worker import AnimateWorker
from aicentralv2.creative_modeling_service import CreativeModelingService
from aicentralv2.services.openrouter_service import build_video_payload
from tests.test_creative_format_lab import TINY_PNG
from tests.test_modelagem_criativos import FakeGenerator, FakeRepository


class TrocrAnimatePlanTest(unittest.TestCase):
    def test_seedance_25_trinta_segundos_sem_frame_e_refs(self):
        payload = build_video_payload(
            "move",
            model="bytedance/seedance-2.5",
            duration=30,
            resolution="720p",
            aspect_ratio="9:16",
            frame_images=[{"frame_type": "first_frame"}],
        )
        self.assertEqual(payload["model"], "bytedance/seedance-2.5")
        self.assertEqual(payload["duration"], 30)
        self.assertIn("frame_images", payload)
        self.assertNotIn("input_references", payload)
        with self.assertRaises(ValueError):
            build_video_payload(
                "x",
                frame_images=[{"frame_type": "first_frame"}],
                input_references=[{"type": "image_url"}],
            )

    def test_quote_8s_720p_9x16(self):
        plan = build_plan({
            "duration": 8,
            "quality": "production",
            "aspect_ratio": "9:16",
            "source": {"mode": "flattened_still", "base_id": "v1"},
        })
        self.assertEqual(plan["model"], "bytedance/seedance-2.5")
        self.assertEqual(plan["resolution"], "720p")
        self.assertEqual(plan["aspect_ratio"], "9:16")
        self.assertEqual(plan["size"], "720x1280")
        self.assertGreater(plan["quote"]["estimated_cost_usd"], 1)
        quoted = quote_animate({"duration": 8, "quality": "production", "aspect_ratio": "9:16"})
        self.assertIn("imagem única", quoted["warning"])

    def test_protege_cena_sem_snapshot_nao_cai_em_achatado(self):
        plan = build_plan({"source": {"mode": "protected_scene"}})
        self.assertEqual(plan["source"]["mode"], "protected_scene")
        self.assertIsNone(plan["source"]["snapshot"])
        from aicentralv2.creative_media.composition.scene_snapshot import validate_snapshot
        with self.assertRaises(ValueError):
            validate_snapshot({})

    def test_4x5_vira_3x4_com_frame_tecnico(self):
        self.assertEqual(map_aspect("4:5"), "3:4")
        self.assertEqual(output_size("720p", "3:4"), (834, 1112))
        from PIL import Image
        from io import BytesIO
        buf = BytesIO()
        Image.new("RGB", (400, 500), (20, 20, 20)).save(buf, format="PNG")
        frame = prepare_frame(buf.getvalue(), "4:5", "720p")
        out = Image.open(BytesIO(frame))
        self.assertEqual(out.size, (834, 1112))


class TrocrAnimateSessionTest(unittest.TestCase):
    def test_append_video_nao_da_409(self):
        class _MemStorage:
            def __init__(self):
                self.sessions = {}

            def save_trocr_still(self, encoded, output_format="png"):
                return f"/parametros/api/format-lab/swap/still/{'a' * 32}.png"

            def save_trocr_session(self, key, data):
                self.sessions[key] = data

            def load_trocr_session(self, key):
                return self.sessions.get(key)

        modeling = CreativeModelingService(FakeRepository(), FakeGenerator(), storage=_MemStorage())
        lab = FormatLabService(modeling)
        png = "data:image/png;base64," + TINY_PNG.hex()
        first = lab.save_swap_history(
            {
                "client_id": 3,
                "active_id": "v1",
                "base_id": "v1",
                "revision": 0,
                "versions": [{"id": "v1", "name": "Original", "origin": "original", "image": png}],
            },
            user_id=1,
        )
        store = TrocrStore(modeling, modeling.repository)
        # Outra aba já incrementou o histórico
        lab.save_swap_history(
            {
                "client_id": 3,
                "run_id": first["run_id"],
                "revision": first["revision"],
                "active_id": "v1",
                "base_id": "v1",
                "versions": first["versions"] + [{
                    "id": "v2",
                    "name": "Rascunho",
                    "origin": "draft",
                    "image": png,
                }],
            },
            user_id=1,
        )
        created = store.persist_animate(
            {"client_id": 3, "run_id": first["run_id"], "base_id": "v1", "source_revision": first["revision"]},
            {
                "video_url": "/parametros/api/media/assets/asset_abc/content",
                "poster_url": "/parametros/api/media/assets/asset_poster/content",
                "image_url": "/parametros/api/media/assets/asset_poster/content",
                "master_asset_id": "asset_abc",
                "job_id": "anim_1",
                "duration": 8,
            },
            user_id=1,
        )
        self.assertEqual(created["origin"], "animate")
        self.assertTrue(created["based_on_stale_revision"])
        self.assertEqual(created["media"], "video")


class TrocrAnimateWorkerTest(unittest.TestCase):
    def test_get_nao_materializa_e_worker_grava_versao(self):
        repo = MemoryMediaRepository()
        plan = build_plan({
            "duration": 5,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {"mode": "flattened_still", "base_id": "v1"},
        })
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (32, 32), (12, 12, 12)).save(buf, format="PNG")
        plan["reference"] = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        job = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40
        persisted = {}

        def persist(_job, _plan, version):
            persisted["version"] = version
            return version

        worker = AnimateWorker(
            repo,
            persist_fn=persist,
            video={
                "submit": lambda *a, **k: {"id": "or-1", "polling_url": "https://x/or-1", "status": "pending"},
                "poll": lambda *a, **k: {"id": "or-1", "status": "completed"},
                "download": lambda *_a, **_k: fake_mp4,
            },
        )
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                    worker.run(job["public_id"])
        ready = repo.get_job(job["public_id"])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(persisted["version"]["media"], "video")
        self.assertTrue(persisted["version"]["master_asset_id"])
        self.assertNotIn("polling_url", ready.get("version_payload") or {})
        self.assertTrue(persisted["version"]["seedance_base_asset_id"])


def _scene_snapshot(version=1, headline="OFERTA"):
    from aicentralv2.creative_media.composition.scene_snapshot import snapshot_scene

    return snapshot_scene({
        "creative_id": "crt_test",
        "scene_version": version,
        "scene": {"id": "scn_1"},
        "elements": [
            {
                "id": "el_h",
                "role": "headline",
                "label": "Headline",
                "type": "text",
                "bbox": {"x": 10, "y": 10, "w": 30, "h": 20},
                "text": headline,
            },
            {
                "id": "el_bg",
                "role": "background",
                "label": "Fundo",
                "type": "image",
                "bbox": {"x": 0, "y": 0, "w": 100, "h": 100},
            },
        ],
    }, source_version_id="v1")


class TrocrAnimateProtectedTest(unittest.TestCase):
    def test_snapshot_copia_versao_e_nao_a_cena_live(self):
        first = _scene_snapshot(1, "A")
        second = _scene_snapshot(2, "B")
        self.assertEqual(first["creative_id"], "crt_test")
        self.assertEqual(first["scene_version"], 1)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])
        self.assertIn("el_h", first["protected_layer_ids"])
        self.assertIn("el_bg", first["animate_layer_ids"])

    def test_placa_some_com_o_tipo(self):
        from io import BytesIO
        from PIL import Image, ImageDraw
        from aicentralv2.creative_media.composition.plate_renderer import render_plate

        image = Image.new("RGB", (100, 100), (20, 20, 20))
        ImageDraw.Draw(image).rectangle((10, 10, 40, 30), fill=(240, 10, 10))
        buf = BytesIO()
        image.save(buf, format="PNG")
        plate = Image.open(BytesIO(render_plate(buf.getvalue(), _scene_snapshot())))
        sample = plate.getpixel((20, 18))
        self.assertNotEqual(sample[0], 240)

    def test_overlay_tem_alpha_na_regiao_protegida(self):
        from io import BytesIO
        from PIL import Image, ImageDraw
        from aicentralv2.creative_media.composition.overlay_renderer import render_overlay

        image = Image.new("RGB", (100, 100), (20, 20, 20))
        ImageDraw.Draw(image).rectangle((10, 10, 40, 30), fill=(240, 10, 10))
        buf = BytesIO()
        image.save(buf, format="PNG")
        overlay = Image.open(BytesIO(render_overlay(buf.getvalue(), _scene_snapshot()))).convert("RGBA")
        self.assertGreater(overlay.getpixel((20, 18))[3], 200)
        self.assertEqual(overlay.getpixel((80, 80))[3], 0)

    def test_4x5_overlay_depois_do_crop(self):
        from io import BytesIO
        from PIL import Image
        from aicentralv2.creative_media.composition.overlay_renderer import compose_still, render_overlay
        from aicentralv2.creative_media.geometry import crop_4x5, prepare_frame

        still = Image.new("RGB", (400, 500), (30, 30, 40))
        for x in range(40, 160):
            for y in range(50, 150):
                still.putpixel((x, y), (250, 20, 20))
        buf = BytesIO()
        still.save(buf, format="PNG")
        raw = buf.getvalue()
        snapshot = _scene_snapshot()
        overlay = render_overlay(raw, snapshot)
        technical = Image.open(BytesIO(prepare_frame(raw, "4:5", "720p")))
        cropped = crop_4x5(technical)
        composed = Image.open(BytesIO(compose_still(_jpeg(cropped), overlay)))
        self.assertEqual(composed.size, cropped.size)
        self.assertGreater(composed.getpixel((int(composed.width * 0.2), int(composed.height * 0.2)))[0], 100)

    def test_plan_protegido_nao_pede_letras(self):
        plan = build_plan({
            "duration": 5,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {"mode": "protected_scene", "snapshot": _scene_snapshot()},
        })
        self.assertIn("removed from the supplied plates", plan["prompt"])
        quoted = quote_animate({
            "source": {"mode": "protected_scene", "snapshot": _scene_snapshot()},
            "duration": 5,
        })
        self.assertIn("overlay", quoted["warning"])

    def test_recompose_sem_mudanca_e_append_com_base(self):
        from io import BytesIO
        from PIL import Image
        from aicentralv2.creative_format_lab.animate import AnimateService
        from aicentralv2.creative_media.composition.scene_snapshot import snapshot_fingerprint

        repo = MemoryMediaRepository()
        snap = _scene_snapshot(1, "A")
        plan = build_plan({
            "duration": 5,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {"mode": "protected_scene", "snapshot": snap, "base_id": "v1"},
        })
        buf = BytesIO()
        Image.new("RGB", (64, 64), (12, 12, 12)).save(buf, format="PNG")
        still = buf.getvalue()
        plan["reference"] = "data:image/png;base64," + base64.b64encode(still).decode("ascii")
        job = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        fake_mp4 = b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40
        versions = []

        def persist(_job, _plan, version):
            versions.append(version)
            return version

        worker = AnimateWorker(
            repo,
            persist_fn=persist,
            video={
                "submit": lambda *a, **k: {"id": "or-1", "polling_url": "https://x/or-1", "status": "pending"},
                "poll": lambda *a, **k: {"id": "or-1", "status": "completed"},
                "download": lambda *_a, **_k: fake_mp4,
            },
        )
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with patch("aicentralv2.creative_media.worker.overlay_video", side_effect=lambda video, _ov: video):
                with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                    with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                        worker.run(job["public_id"])
        ready = repo.get_job(job["public_id"])
        self.assertTrue(ready["version_payload"]["seedance_base_asset_id"])
        self.assertTrue(ready["version_payload"]["protected_layers"])

        class _Camadas:
            def get_creative(self, _creative_id):
                return {
                    "creative_id": "crt_test",
                    "creative": {"id": "crt_test"},
                    "scene_version": 1,
                    "scene": {"id": "scn_1"},
                    "elements": snap["elements"],
                }

        service = AnimateService(store=None, repository=repo, camadas=_Camadas(), spawn_job=lambda *_a, **_k: None)
        service._worker = lambda: worker
        service._live_plate = lambda data, user_id=None: (snap, still)
        with self.assertRaises(ValueError):
            service.recompose(job["public_id"])

        live = _scene_snapshot(2, "B")
        self.assertNotEqual(snapshot_fingerprint(live), snapshot_fingerprint(snap))
        service._live_plate = lambda data, user_id=None: (live, still)
        with patch("aicentralv2.creative_media.worker.overlay_video", side_effect=lambda video, _ov: video + b"x"):
            with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                    result = service.recompose(job["public_id"])
        self.assertTrue(result["version"]["master_asset_id"])
        self.assertEqual(len(versions), 2)


class TrocrAnimateTransitionTest(unittest.TestCase):
    def test_ratio_incompativel_e_audio_ref(self):
        with self.assertRaises(ValueError) as mismatch:
            build_plan({
                "source": {"mode": "transition_ab", "to_id": "v2"},
                "aspect_ratio": "9:16",
                "to_aspect_ratio": "16:9",
            })
        self.assertIn("mesmo formato", str(mismatch.exception))
        with self.assertRaises(ValueError) as audio:
            build_plan({
                "source": {"mode": "transition_ab", "to_id": "v2"},
                "aspect_ratio": "1:1",
                "audio": {"mode": "music", "reference": "https://x/track.mp3"},
            })
        self.assertIn("Áudio de referência", str(audio.exception))

    def test_payload_dois_frames_sem_refs(self):
        from aicentralv2.services.openrouter_service import build_video_payload

        payload = build_video_payload(
            "move",
            model="bytedance/seedance-2.5",
            frame_images=[
                {"frame_type": "first_frame"},
                {"frame_type": "last_frame"},
            ],
        )
        self.assertEqual([item["frame_type"] for item in payload["frame_images"]], ["first_frame", "last_frame"])
        self.assertNotIn("input_references", payload)

    def test_4x5_mesma_placa_tecnica_e_overlay_so_no_fim(self):
        from io import BytesIO
        from PIL import Image
        from aicentralv2.creative_media.composition.compositor import overlay_covers_time
        from aicentralv2.creative_media.worker import AnimateWorker

        self.assertFalse(overlay_covers_time(0.2, 4, 5))
        self.assertTrue(overlay_covers_time(4.2, 4, 5))
        plan = build_plan({
            "duration": 5,
            "quality": "draft",
            "aspect_ratio": "4:5",
            "source": {"mode": "transition_ab", "to_id": "v2", "base_id": "v1"},
        })
        a = BytesIO()
        b = BytesIO()
        Image.new("RGB", (400, 500), (10, 10, 10)).save(a, format="PNG")
        Image.new("RGB", (400, 500), (40, 40, 40)).save(b, format="PNG")
        plan["source"]["reference"] = "data:image/png;base64," + base64.b64encode(a.getvalue()).decode("ascii")
        plan["source"]["reference_b"] = "data:image/png;base64," + base64.b64encode(b.getvalue()).decode("ascii")
        frames = AnimateWorker(MemoryMediaRepository())._frames(plan)
        self.assertEqual([item["frame_type"] for item in frames], ["first_frame", "last_frame"])
        sizes = []
        for item in frames:
            raw = base64.b64decode(item["image_url"]["url"].split(",", 1)[1])
            sizes.append(Image.open(BytesIO(raw)).size)
        self.assertEqual(sizes[0], sizes[1])
        self.assertEqual(sizes[0], (560, 752))

    def test_worker_envia_ab_e_overlay_b_no_ultimo_segundo(self):
        from io import BytesIO
        from PIL import Image
        from aicentralv2.creative_media.worker import AnimateWorker

        snap = _scene_snapshot(1, "FIM")
        plan = build_plan({
            "duration": 5,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {
                "mode": "transition_ab",
                "base_id": "v1",
                "to_id": "v2",
                "snapshot_b": snap,
            },
            "snapshot_b": snap,
        })
        buf = BytesIO()
        Image.new("RGB", (64, 64), (12, 12, 12)).save(buf, format="PNG")
        still = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        plan["source"]["reference"] = still
        plan["source"]["reference_b"] = still
        plan["reference"] = still
        repo = MemoryMediaRepository()
        job = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        captured = {}
        windows = []

        def submit(*_a, **kwargs):
            captured["frames"] = [item.get("frame_type") for item in kwargs.get("frame_images") or []]
            captured["refs"] = kwargs.get("input_references")
            return {"id": "or-1", "polling_url": "https://x/or-1", "status": "pending"}

        def overlay(video, _png, start=None, end=None):
            windows.append((start, end))
            return video

        worker = AnimateWorker(
            repo,
            persist_fn=lambda _job, _plan, version: version,
            video={
                "submit": submit,
                "poll": lambda *a, **k: {"id": "or-1", "status": "completed"},
                "download": lambda *_a, **_k: b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40,
            },
        )
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with patch("aicentralv2.creative_media.worker.overlay_video", side_effect=overlay):
                with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                    with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                        worker.run(job["public_id"])
        self.assertEqual(captured["frames"], ["first_frame", "last_frame"])
        self.assertIsNone(captured["refs"])
        self.assertEqual(windows, [(4, 5)])
        ready = repo.get_job(job["public_id"])
        self.assertEqual(ready["version_payload"]["transition_from"], "v1")
        self.assertEqual(ready["version_payload"]["transition_to"], "v2")
        quoted = quote_animate({"source": {"mode": "transition_ab", "to_id": "v2"}, "aspect_ratio": "1:1"})
        self.assertIn("último quadro", quoted["warning"])


class TrocrAnimateVoiceoverTest(unittest.TestCase):
    def test_roteiro_obrigatorio_e_cabe_na_duracao(self):
        with self.assertRaises(ValueError) as missing:
            build_plan({"audio": {"mode": "voiceover"}})
        self.assertIn("roteiro", str(missing.exception).lower())
        with self.assertRaises(ValueError) as overflow:
            build_plan({
                "duration": 5,
                "audio": {"mode": "voiceover", "script": "palavra " * 30},
            })
        self.assertIn("duração", str(overflow.exception))
        plan = build_plan({
            "duration": 10,
            "quality": "draft",
            "audio": {
                "mode": "voiceover",
                "script": "Recarregue trinta reais e tenha muita internet.",
                "voice": "male",
                "pace": "fast",
            },
        })
        self.assertEqual(plan["voiceover_provider_voice"], "Charon")
        self.assertEqual(plan["tts_model"], "google/gemini-3.1-flash-tts-preview")
        self.assertIn("No speech", plan["prompt"])
        self.assertGreater(plan["quote"]["tts_estimated_cost_usd"], 0)
        self.assertTrue(plan["generate_audio"])
        quoted = quote_animate({"audio": {"mode": "voiceover"}})
        self.assertIn("Gemini TTS", quoted["warning"])

    def test_worker_mixa_locucao_sem_seedance_falar_o_roteiro(self):
        from io import BytesIO
        from PIL import Image

        plan = build_plan({
            "duration": 8,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {"mode": "flattened_still", "base_id": "v1"},
            "audio": {
                "mode": "voiceover",
                "script": "Recarregue trinta reais e tenha internet.",
                "voice": "female",
                "pace": "normal",
            },
        })
        buf = BytesIO()
        Image.new("RGB", (64, 64), (12, 12, 12)).save(buf, format="PNG")
        still = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        plan["source"]["reference"] = still
        plan["reference"] = still
        repo = MemoryMediaRepository()
        job = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        captured = {}
        wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 20

        def speech(text, **kwargs):
            captured["input"] = text
            captured["voice"] = kwargs.get("voice")
            return wav

        worker = AnimateWorker(
            repo,
            persist_fn=lambda _job, _plan, version: version,
            video={
                "submit": lambda *a, **k: captured.update(k) or {"id": "or-1", "polling_url": "https://x/or-1", "status": "pending"},
                "poll": lambda *a, **k: {"id": "or-1", "status": "completed"},
                "download": lambda *_a, **_k: b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40,
            },
            speech={"generate": speech},
        )
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with patch("aicentralv2.creative_media.transcode.mix_voiceover", side_effect=lambda video, _au: video + b"mix"):
                with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                    with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                        worker.run(job["public_id"])
        ready = repo.get_job(job["public_id"])
        self.assertTrue(ready["version_payload"]["voiceover_asset_id"])
        self.assertTrue(ready["version_payload"]["has_audio"])
        self.assertEqual(captured["voice"], "Kore")
        self.assertNotIn("[excited]", captured["input"])
        self.assertIn("Recarregue", captured["input"])

    def test_pcm_vira_wav_e_tag_rapida(self):
        from aicentralv2.creative_media.voiceover import spoken_input
        from aicentralv2.services.openrouter_service import _pcm_to_wav, is_audio_bytes

        self.assertTrue(spoken_input("Recarregue agora.", "fast").startswith("[excited]"))
        wav = _pcm_to_wav(b"\x00\x00" * 24)
        self.assertTrue(is_audio_bytes(wav))
        self.assertEqual(wav[8:12], b"WAVE")


class TrocrAnimateStoryboardTest(unittest.TestCase):
    def test_storyboard_exige_tres_a_seis(self):
        with self.assertRaises(ValueError) as missing:
            build_plan({
                "source": {"mode": "storyboard", "ref_ids": ["v1", "v2"]},
                "require_refs": True,
            })
        self.assertIn("3 a 6", str(missing.exception))
        plan = build_plan({
            "source": {"mode": "storyboard", "ref_ids": ["v1", "v2", "v3"]},
            "require_refs": True,
        })
        self.assertEqual(plan["source"]["ref_ids"], ["v1", "v2", "v3"])
        self.assertIn("storyboard", plan["prompt"])
        quoted = quote_animate({"source": {"mode": "storyboard"}})
        self.assertIn("referências", quoted["warning"])

    def test_extensao_usa_tarifa_de_video_e_sem_frame(self):
        flat = build_plan({"duration": 8, "quality": "production", "aspect_ratio": "16:9"})
        plan = build_plan({
            "duration": 8,
            "quality": "production",
            "aspect_ratio": "16:9",
            "source": {"mode": "extend_video", "extended_from": "v3"},
        })
        self.assertLess(plan["quote"]["estimated_cost_usd"], flat["quote"]["estimated_cost_usd"])
        self.assertTrue(plan["quote"]["has_video_reference"])
        self.assertIn("Continue the supplied clip", plan["prompt"])
        quoted = quote_animate({"source": {"mode": "extend_video"}})
        self.assertIn("referência de vídeo", quoted["warning"])

    def test_worker_storyboard_manda_refs_sem_frames(self):
        from io import BytesIO
        from PIL import Image

        buf = BytesIO()
        Image.new("RGB", (64, 64), (20, 20, 20)).save(buf, format="PNG")
        still = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        plan = build_plan({
            "duration": 5,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {"mode": "storyboard", "ref_ids": ["v1", "v2", "v3"], "base_id": "v1"},
            "require_refs": True,
        })
        plan["source"]["references"] = [still, still, still]
        plan["source"]["reference"] = still
        plan["reference"] = still
        repo = MemoryMediaRepository()
        job = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        captured = {}

        def submit(*_a, **kwargs):
            captured["frames"] = kwargs.get("frame_images")
            captured["refs"] = kwargs.get("input_references")
            return {"id": "or-1", "polling_url": "https://x/or-1", "status": "pending"}

        worker = AnimateWorker(
            repo,
            persist_fn=lambda _job, _plan, version: version,
            video={
                "submit": submit,
                "poll": lambda *a, **k: {"id": "or-1", "status": "completed"},
                "download": lambda *_a, **_k: b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40,
            },
        )
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                    worker.run(job["public_id"])
        self.assertFalse(captured["frames"])
        self.assertEqual(len(captured["refs"]), 3)
        self.assertEqual(captured["refs"][0]["type"], "image_url")
        ready = repo.get_job(job["public_id"])
        self.assertEqual(ready["version_payload"]["storyboard_ids"], ["v1", "v2", "v3"])

    def test_worker_extensao_exige_https_publico(self):
        plan = build_plan({
            "duration": 5,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {"mode": "extend_video", "extended_from": "v2", "base_id": "v2"},
        })
        plan["source"]["reference"] = "data:video/mp4;base64,AAAA"
        repo = MemoryMediaRepository()
        job = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        worker = AnimateWorker(
            repo,
            persist_fn=lambda _job, _plan, version: version,
            video={
                "submit": lambda *a, **k: {"id": "or-1", "status": "completed"},
                "poll": lambda *a, **k: {"id": "or-1", "status": "completed"},
                "download": lambda *_a, **_k: b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40,
            },
        )
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with self.assertRaises(ValueError) as blocked:
                worker.run(job["public_id"])
        self.assertIn("HTTPS pública", str(blocked.exception))

        plan["source"]["video_url"] = "https://cdn.example.com/clip.mp4"
        captured = {}

        def submit(*_a, **kwargs):
            captured["frames"] = kwargs.get("frame_images")
            captured["refs"] = kwargs.get("input_references")
            return {"id": "or-1", "polling_url": "https://x/or-1", "status": "pending"}

        job2 = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        worker.video = {
            "submit": submit,
            "poll": lambda *a, **k: {"id": "or-1", "status": "completed"},
            "download": lambda *_a, **_k: b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40,
        }
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                    worker.run(job2["public_id"])
        self.assertFalse(captured["frames"])
        self.assertEqual(captured["refs"][0]["video_url"]["url"], "https://cdn.example.com/clip.mp4")


class TrocrAnimateDisplayTest(unittest.TestCase):
    def test_prompt_1x1_e_display_em_loop_nao_filme(self):
        plan = build_plan({
            "duration": 8,
            "quality": "production",
            "aspect_ratio": "1:1",
            "source": {"mode": "flattened_still", "base_id": "v1"},
            "motion": {"preset": "live", "intensity": "subtle"},
            "audio": {"mode": "music", "music_note": "forró leve de festa junina"},
        })
        self.assertEqual(plan["format_surface"], "display_square")
        self.assertEqual(plan["aspect_ratio"], "1:1")
        self.assertEqual(plan["size"], "960x960")
        self.assertIn("display loop", plan["prompt"])
        self.assertIn("finished square display", plan["prompt"])
        self.assertIn("artist names", plan["prompt"])
        self.assertIn("Do not restack", plan["prompt"])
        self.assertIn("forró leve", plan["prompt"])
        from aicentralv2.creative_format_geometry import _family_from_size, format_direction
        self.assertEqual(_family_from_size((640, 640)), "square_1x1")
        direction = format_direction({
            "slug": "instagram-feed",
            "default_size": "640x640",
            "mechanic": "static_display",
        }, 1)
        self.assertEqual(direction["orientation"], "square")
        self.assertIn("aprovado", direction["beats"][0]["job"])

    def test_worker_cai_no_fallback_quando_seedance_barra_pessoa_real(self):
        from io import BytesIO
        from PIL import Image
        from aicentralv2.services.openrouter_service import OpenRouterError

        plan = build_plan({
            "duration": 8,
            "quality": "draft",
            "aspect_ratio": "1:1",
            "source": {"mode": "flattened_still", "base_id": "v1"},
        })
        buf = BytesIO()
        Image.new("RGB", (64, 64), (80, 40, 160)).save(buf, format="PNG")
        still = "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")
        plan["reference"] = still
        repo = MemoryMediaRepository()
        job = repo.create_job({"plan_json": plan, "plan_hash": plan["plan_hash"], "quote_json": plan["quote"]})
        models = []

        def submit(_prompt, **kwargs):
            models.append(kwargs.get("model"))
            if kwargs.get("model") == "bytedance/seedance-2.5":
                raise OpenRouterError("O Seedance recusou o still: a imagem parece ter uma pessoa real.")
            return {"id": "or-fallback", "status": "pending"}

        worker = AnimateWorker(
            repo,
            persist_fn=lambda _job, _plan, version: version,
            video={
                "submit": submit,
                "poll": lambda *a, **k: {"id": "or-fallback", "status": "completed"},
                "download": lambda *_a, **_k: b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 40,
            },
        )
        with patch("aicentralv2.creative_media.worker.POLL_INTERVAL", 0):
            with patch("aicentralv2.creative_media.transcode.poster_jpg", side_effect=RuntimeError("skip")):
                with patch("aicentralv2.creative_media.transcode.small_mp4", side_effect=RuntimeError("skip")):
                    worker.run(job["public_id"])
        self.assertEqual(models[0], "bytedance/seedance-2.5")
        self.assertEqual(models[1], "kwaivgi/kling-v3.0-pro")
        ready = repo.get_job(job["public_id"])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual((ready.get("plan_json") or {}).get("model"), "kwaivgi/kling-v3.0-pro")
        self.assertTrue((ready.get("plan_json") or {}).get("model_fallback"))


def _jpeg(image):
    from io import BytesIO
    buf = BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()
