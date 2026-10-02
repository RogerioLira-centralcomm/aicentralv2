"""Criar → Vídeo: imagens do Studio entram no storyboard em uma chamada."""
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask, session

from aicentralv2.creative_media import studio

ROOT = Path(__file__).resolve().parents[1]


def _undecorated(view):
    while hasattr(view, "__wrapped__"):
        view = view.__wrapped__
    return view


def _call(payload, *, owned=None, history=True):
    app = Flask(__name__)
    app.secret_key = "test"
    modeling = MagicMock()
    calls = []

    def add(item, user_id):
        calls.append(item)
        return {"id": f"run-1:v{len(calls)}", "run_id": "run-1"}

    modeling.add_format_lab_swap_library_still.side_effect = add
    store = MagicMock()
    store.owned_image_urls.return_value = set(owned if owned is not None else
                                              [i["image_url"] for i in payload.get("items", [])])
    http = (lambda run: run(), lambda: payload, lambda data: data, lambda: modeling)
    with app.test_request_context("/"):
        session["user_id"] = 5
        with patch.object(studio, "_http", return_value=http), \
                patch.object(studio, "_scope"), \
                patch.object(studio, "_assert_project_brand_access") as guard, \
                patch.object(studio, "_creation_history", return_value=store if history else None):
            result = _undecorated(studio.studio_send_to_video)()
    return result, calls, guard


def test_sends_images_in_order_as_one_storyboard_run():
    payload = {"client_id": 174, "project_id": "p1", "items": [
        {"image_url": "/static/uploads/creative_generated/a.png", "title": "Abertura", "aspect_ratio": "16:9"},
        {"image_url": "/static/uploads/creative_generated/b.png", "title": "Fecho"},
    ]}
    result, calls, guard = _call(payload)
    assert result == {"scene_ids": ["run-1:v1", "run-1:v2"], "run_id": "run-1"}
    assert calls[0]["new_run"] is True and "run_id" not in calls[0]
    assert calls[1]["run_id"] == "run-1" and "new_run" not in calls[1]
    assert [c["name"] for c in calls] == ["Abertura", "Fecho"]
    guard.assert_called_once_with("p1", 174)


def test_rejects_an_image_from_another_brand():
    payload = {"client_id": 174, "items": [{"image_url": "/static/uploads/creative_generated/x.png"}]}
    with pytest.raises(ValueError, match="não pertence"):
        _call(payload, owned=[])


def test_requires_at_least_one_image_and_caps_the_storyboard():
    with pytest.raises(ValueError, match="ao menos uma"):
        _call({"client_id": 174, "items": []})
    many = [{"image_url": f"/static/uploads/creative_generated/{i}.png"} for i in range(31)]
    with pytest.raises(ValueError, match="no máximo 30"):
        _call({"client_id": 174, "items": many})


def test_create_and_video_screens_are_wired_to_the_handoff():
    create_js = (ROOT / "aicentralv2/static/js/cadu-studio-create-v2.js").read_text(encoding="utf-8")
    create_html = (ROOT / "aicentralv2/templates/cadu_studio/create.html").read_text(encoding="utf-8")
    video_js = (ROOT / "aicentralv2/static/js/mc-cadu-video.js").read_text(encoding="utf-8")
    assert "/format-lab/studio/send-to-video" in create_js
    assert 'class="result-video"' in create_js and 'id="sendAllToVideo"' in create_html
    assert "data-video-url" in create_html
    assert "adoptHandoffScenes(params)" in video_js and 'params.get("scenes")' in video_js


def test_every_create_image_is_registered_in_the_shared_library():
    source = (ROOT / "aicentralv2/creative_media/studio.py").read_text(encoding="utf-8")
    assert "history.register_asset(" in source and "'studio_create'" in source


def test_finished_clip_is_mirrored_into_the_shared_library_without_failing_the_job():
    from aicentralv2.creative_format_lab import animate

    repo = MagicMock()
    with patch("aicentralv2.creative_media.studio_history.StudioCreationHistory") as history:
        history.return_value.register_asset.return_value = "asset-1"
        job = {"client_id": 174, "user_id": 5, "public_id": "job-9"}
        version = {"video_url": "/parametros/api/media/assets/a1/content", "name": "Clipe 8s", "duration": 8}
        assert animate.register_library_video(repo, job, version) == "asset-1"
        args = history.return_value.register_asset.call_args.args
        assert args[3:6] == ("video", "studio_video", "job-9")

        history.return_value.register_asset.side_effect = RuntimeError("db down")
        assert animate.register_library_video(repo, job, version) == ""
        repo.conn.rollback.assert_called_once()

    assert animate.register_library_video(object(), job, version) == ""
