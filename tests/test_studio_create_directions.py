from aicentralv2.creative_media import studio_create


def test_project_suggestions_are_specific_to_its_brief():
    ideas = studio_create.suggestions({"name": "Verão Aurora", "objective": "apresentar vinhos leves", "audience": "pessoas em viagem"})

    assert any("vinhos leves" in item for item in ideas)
    assert any("pessoas em viagem" in item for item in ideas)


def test_create_returns_requested_number_of_safe_directions():
    def provider(*_args, **_kwargs):
        return {"model": "test", "message": {"content": {"directions": [
            {"title": "Momento de uso", "summary": "Vida real", "prompt": "Foto editorial de produto em uso."},
            {"title": "Encontro", "summary": "Pessoas e marca", "prompt": "Cena natural de encontro."},
            {"title": "Origem", "summary": "Detalhe do produto", "prompt": "Close de produto com luz suave."},
        ]}}, "usage": {"prompt_tokens": 10, "completion_tokens": 20}}

    result, provider_result = studio_create.create({
        "count": 3,
        "prompt": "Criar uma campanha de verão.",
        "context": {"project_name": "Verão", "brand": "Aurora", "channels": ["social"]},
    }, provider)

    assert result["count"] == 3
    assert len(result["directions"]) == 3
    assert provider_result["model"] == "test"


def test_direction_estimate_grows_with_requested_options():
    assert studio_create.estimated_tokens(1) < studio_create.estimated_tokens(5)
    assert studio_create.estimated_tokens(5) >= 2_900


def test_direction_prompt_requires_a_specific_advertising_brief():
    prompt = studio_create.system_prompt(3)

    assert "formato IAB" in prompt
    assert "praça ou contexto cultural brasileiro" in prompt
    assert "texto literal" in prompt
    assert "área livre para composição posterior" in prompt
