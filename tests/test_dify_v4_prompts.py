"""The Dify v4 JSON files are generated from the markdown sources and must stay in sync."""
import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("build_dify_prompts", ROOT / "scripts" / "build_dify_prompts.py")
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_json_files_match_the_markdown_sources():
    for name, expected in builder.build().items():
        assert json.loads((builder.ROOT / name).read_text(encoding="utf-8")) == expected, \
            f"{name} desatualizado: rode python scripts/build_dify_prompts.py"


def test_system_prompt_only_references_core_because_data_lives_in_the_user_message():
    for name, content in builder.build().items():
        text = content["system_prompt_chatflow"]
        assert re.findall(r"\{\{#" + builder.START_NODE_ID + r"\.(\w+)#\}\}", text) == ["core"], name
        assert not re.search(r"\{\{(?!#)", text), "variável sem a sintaxe do Chatflow"
        assert re.findall(r"\{\{(\w+)\}\}", content["system_prompt"]) == ["core"], name
        assert "user_request" not in text and "Valores sugeridos" not in text and text.startswith("Você é o Cadu")
        sections = builder.OPERATOR_SECTIONS if name == "cadu-operator.json" else [s for s, _v in builder.USER_MESSAGE]
        for section in sections:
            assert section in text, f"{name}: seção {section} não descrita"


def test_every_input_variable_is_used_and_memory_is_off():
    for name, content in builder.build().items():
        assert "{{core}}" in content["system_prompt"], name
        assert content["settings"]["conversation_memory"] is False and content["settings"]["tools"] == []
        assert not any("{{" + legacy + "}}" in content["system_prompt"] for legacy in builder.LEGACY_UNUSED), name
