import json
from pathlib import Path

PLUGIN = Path(__file__).resolve().parents[1] / "plugins" / "cadu"


def _manifest():
    return json.loads((PLUGIN / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))


def test_listing_fields_respect_the_openai_limits():
    interface = _manifest()["interface"]
    assert len(interface["displayName"]) <= 30 and len(interface["shortDescription"]) <= 30
    assert len(interface["longDescription"]) <= 4000 and len(interface["developerName"]) <= 80
    assert len(interface["defaultPrompt"]) <= 3 and all(len(item) <= 128 for item in interface["defaultPrompt"])
    assert len(interface["capabilities"]) <= 20 and all(len(item) <= 120 for item in interface["capabilities"])
    for key in ("websiteURL", "supportURL", "privacyPolicyURL", "termsOfServiceURL"):
        assert interface[key].startswith("https://") and len(interface[key]) <= 1024


def test_review_cases_are_five_positive_and_three_negative_with_required_fields():
    cases = _manifest()["extensions"]["com.openai"]["review"]["test_cases"]
    assert len(cases["positive"]) == 5 and len(cases["negative"]) == 3
    for case in cases["positive"]:
        assert all(case.get(key) for key in ("description", "prompt", "tools_triggered", "expected_behavior"))
    for case in cases["negative"]:
        assert case["description"] and case["prompt"]


def test_referenced_assets_skills_and_mcp_exist():
    manifest = _manifest()
    interface = manifest["interface"]
    for key in ("logo", "composerIcon"):
        assert (PLUGIN / interface[key]).is_file()
    assert (PLUGIN / manifest["extensions"]["com.openai"]["onboardingSkill"]).is_file()
    mcp = json.loads((PLUGIN / ".mcp.json").read_text(encoding="utf-8"))
    assert mcp["mcpServers"]["cadu"]["url"].endswith("/mcp/cadu/v1")
    skills = [item.name for item in (PLUGIN / "skills").iterdir() if (item / "SKILL.md").is_file()]
    assert {"primeiros-passos", "nova-marca", "pesquisar-projeto", "pesquisar-planner"} <= set(skills)


def test_positive_cases_only_name_real_public_tools():
    from aicentralv2.cadu_public_mcp.routes import PUBLIC_TOOLS

    for case in _manifest()["extensions"]["com.openai"]["review"]["test_cases"]["positive"]:
        for tool in (name.strip() for name in case["tools_triggered"].split(",")):
            assert tool in PUBLIC_TOOLS, tool
