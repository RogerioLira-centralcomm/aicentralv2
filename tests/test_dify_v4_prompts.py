"""The Dify v4 JSON files are generated from the markdown sources and must stay in sync."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_dify_prompts", ROOT / "scripts" / "build_dify_prompts.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_json_files_match_the_markdown_sources():
    for name, expected in builder.build().items():
        assert json.loads((builder.ROOT / name).read_text(encoding="utf-8")) == expected, \
            f"{name} desatualizado: rode python scripts/build_dify_prompts.py"


def test_every_input_variable_is_used_and_memory_is_off():
    for name, content in builder.build().items():
        assert all("{{" + variable + "}}" in content["system_prompt"] for variable in content["inputs"]), name
        assert content["settings"]["conversation_memory"] is False and content["settings"]["tools"] == []
        assert not any("{{" + legacy + "}}" in content["system_prompt"] for legacy in builder.LEGACY_UNUSED), name
