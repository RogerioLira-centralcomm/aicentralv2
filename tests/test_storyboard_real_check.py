import importlib.util
from pathlib import Path

import pytest
from flask import Flask, jsonify

SPEC = importlib.util.spec_from_file_location("storyboard_real_check", Path(__file__).resolve().parents[1] / "scripts" / "storyboard_real_check.py")
check = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(check)


def _response(body, status=200):
    with Flask(__name__).app_context():
        return jsonify(body), status


def test_response_data_extracts_data_and_raises_the_server_message():
    assert check.response_data(_response({"success": True, "data": {"image_url": "/x.png"}})) == {"image_url": "/x.png"}
    with pytest.raises(RuntimeError, match="Saldo insuficiente"):
        check.response_data(_response({"success": False, "error": "Saldo insuficiente."}, 400))


def test_script_refuses_to_charge_without_the_explicit_flag():
    source = Path(check.__file__).read_text()
    assert source.index("if not args.confirm_real_charge") < source.index("def call(view, path, payload)")
