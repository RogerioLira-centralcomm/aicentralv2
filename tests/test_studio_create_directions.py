import base64
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask
from PIL import Image, ImageDraw

from aicentralv2.creative_media import studio_create


def test_direction_charge_accounts_for_the_final_prompt_review():
    captured = {}

    class Credits:
        def authorize(self, *_args):
            return 10_000

        def charge_provider(self, **kwargs):
            captured.update(kwargs)
            return {"tokens_cobrados": 321}

        def balance(self, _client_id):
            return 9_679

    modeling = SimpleNamespace(
        _credits_crm_id=lambda value: value,
        credit_connector=Credits(),
        credit_ledger=SimpleNamespace(),
    )
    with patch(
        "aicentralv2.creative_modeling_service.CreativeModelingService",
        return_value=modeling,
    ):
        charged, remaining = studio_create.charge(
            {"model": "test", "usage": {"input_tokens": 100, "output_tokens": 40}},
            10, 20, 1, "", "run-review-1",
        )

    assert charged == 321
    assert remaining == 9_679
    assert captured["metadata"]["prompt_review_included"] is True
    assert captured["metadata"]["prompt_review_mode"] == "same_provider_call"
    assert captured["margin_multiplier"] == 1


def test_project_suggestions_are_specific_to_its_brief():
    ideas = studio_create.suggestions({"name": "Verão Aurora", "objective": "apresentar vinhos leves", "audience": "pessoas em viagem"})

    assert any("vinhos leves" in item for item in ideas)
    assert any("pessoas em viagem" in item for item in ideas)


def test_create_returns_requested_number_of_safe_directions():
    captured = {}

    def provider(*_args, **_kwargs):
        captured.update(_kwargs)
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
    assert captured["max_tokens"] == 1_860


def test_direction_director_receives_reference_pixels_without_base64():
    captured = {}

    def provider(messages, **_kwargs):
        captured["messages"] = messages
        return {"model": "test", "message": {"content": {"directions": [{
            "title": "Direção", "summary": "Composição", "prompt": "Peça com produto visível.",
            "reference_plan": [{"label": "Máscara feed", "source": "global", "use": "Aplicar a arquitetura.", "layout": {"subject_zone": "centro-direita", "safe_margin": "interna"}}],
        }]}}, "usage": {}}

    app = Flask(__name__)
    app.config.update(STUDIO_URL="https://studio.test")
    with app.app_context():
        result, _ = studio_create.create({
            "count": 1, "prompt": "Criar anúncio para Reserva.",
            "context": {
                "references": [{"name": "Máscara feed", "source": "global", "role": "composition", "url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp"}],
                "brand_context": {"name": "Reserva", "logo_url": "/static/uploads/creative_references/reserva-logo.png", "palette": ["#152f4e", "#ffffff"]},
            },
        }, provider)

    content = captured["messages"][1]["content"]
    image_urls = [block["image_url"]["url"] for block in content if block.get("type") == "image_url"]
    assert image_urls == [
        "https://studio.test/static/images/cadu/studio/references/feed/feed-mask-01.webp",
        "https://studio.test/static/uploads/creative_references/reserva-logo.png",
    ]
    provider_context = json.loads(content[0]["text"])["contexto"]
    assert provider_context["references"][0]["url"] == image_urls[0]
    assert provider_context["brand_context"]["logo_url"] == image_urls[1]
    assert all("base64" not in str(block) for block in content)
    assert result["directions"][0]["reference_plan"][0]["layout"]["subject_zone"] == "centro-direita"


def test_direction_logs_both_provider_failures_without_leaking_the_brief(caplog):
    def provider(*_args, **_kwargs):
        raise studio_create.OpenRouterError("reference image URL is invalid")

    app = Flask(__name__)
    app.config.update(STUDIO_URL="https://studio.test")
    with app.app_context(), caplog.at_level("WARNING", logger="aicentralv2.creative_media.studio_create"):
        try:
            studio_create.create({
                "count": 1,
                "prompt": "Briefing confidencial da campanha Reserva.",
                "context": {"format": "4:5", "references": [{
                    "url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp",
                }]},
            }, provider)
        except studio_create.OpenRouterError as error:
            assert "preparar a direção criativa" in str(error)
        else:
            raise AssertionError("A criação deveria falhar depois dos dois provedores.")

    assert "openai: reference image URL is invalid" in caplog.text
    assert "openrouter: reference image URL is invalid" in caplog.text
    assert "Briefing confidencial" not in caplog.text


def test_direction_estimate_grows_with_requested_options():
    assert studio_create.estimated_tokens(1) < studio_create.estimated_tokens(5)
    assert studio_create.estimated_tokens(5) >= 2_900
    assert studio_create.estimated_tokens(1, 0) < studio_create.estimated_tokens(1, 3)


def test_reference_contract_allows_one_global_plus_base_plus_logo_only():
    global_reference = {"url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp", "source": "global", "role": "composition"}
    base_reference = {"url": "/static/uploads/creative_references/base.webp", "source": "user", "role": "reference"}
    brand = {"name": "Reserva", "logo_url": "/static/uploads/creative_references/reserva-logo.png"}

    references = studio_create.references_with_brand_logo([global_reference, base_reference], brand)

    assert [item["role"] for item in references] == ["composition", "reference", "identity"]
    try:
        studio_create.references_with_brand_logo([global_reference, dict(global_reference, url="/static/images/cadu/studio/references/feed/feed-mask-02.webp")], {})
    except ValueError as error:
        assert "somente uma referência global" in str(error)
    else:
        raise AssertionError("Duas referências globais não podem disputar a mesma composição.")
    try:
        studio_create.references_with_brand_logo([global_reference, base_reference, {"url": "/static/uploads/creative_references/style.webp", "source": "user"}], brand)
    except ValueError as error:
        assert "incluir o logo oficial" in str(error)
    else:
        raise AssertionError("O logo não pode ser removido silenciosamente do contrato visual.")


def test_direction_prompt_requires_a_specific_advertising_brief():
    prompt = studio_create.system_prompt(3)

    assert "formato IAB" in prompt
    assert "praça ou contexto cultural brasileiro" in prompt
    assert "texto literal" in prompt
    assert "área livre para composição posterior" in prompt


def test_direction_context_preserves_reference_roles_without_embedding_data_urls():
    context = studio_create.clean_context({"references": [
        {"name": "Foto base", "role": "primary", "url": "data:image/png;base64,large"},
        {"name": "Produto", "role": "insert", "url": "https://assets.test/product.png"},
    ]}, 3)

    assert context["references"][0]["role"] == "primary"
    assert context["references"][0]["url"] == "inline upload"
    assert context["references"][1]["role"] == "insert"
    assert context["references"][1]["instruction"] == studio_create.IMAGE_ROLES["insert"]
    assert "FORMATO É CONTROLADO PELO STUDIO" in studio_create.system_prompt(1)
    assert "ORDEM OBRIGATÓRIA DO PROMPT FINAL" in studio_create.system_prompt(1)
    assert "REVISÃO DO BRIEFING" in studio_create.system_prompt(1)
    assert "preço, volume, logo solicitado" in studio_create.system_prompt(1)
    assert "planta estrutural" in studio_create.system_prompt(1)
    cleaned = studio_create.clean_context({"brand_context": {"name": "Reserva", "palette": ["#6b21a8"], "assets": {"logo": ["/logo.svg"]}}}, 1)
    assert cleaned["brand_context"]["name"] == "Reserva"
    assert cleaned["brand_context"]["assets"]["logo"] == ["/logo.svg"]
    assert cleaned["brand_context"]["readiness"]["status"] == "ready"


def test_missing_brand_identity_is_explicit_and_never_becomes_an_invented_mark():
    cleaned = studio_create.clean_context({"brand_context": {"name": "Centralcomm"}}, 1)

    assert cleaned["brand_context"]["readiness"] == {
        "status": "missing", "has_logo": False, "has_palette": False, "missing": ["logo", "cores"],
    }
    assert "nunca invente logotipo, monograma, inicial" in studio_create.system_prompt(1)
    assert "Do not invent, infer or stylize a logo" in studio_create.brand_identity_guard(cleaned["brand_context"])


def test_neutral_asset_mode_never_injects_brand_identity_or_safe_area():
    context = studio_create.clean_context({
        "creation_intent": "neutral_asset",
        "references": [{"url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp", "source": "global", "role": "reference"}],
        "brand_context": {"name": "Marca", "logo_url": "/static/uploads/logo.webp", "palette": ["#123456"]},
    }, 1)

    assert context["creation_intent"] == "neutral_asset"
    assert context["brand_context"] == {}
    assert [item["role"] for item in context["references"]] == ["composition"]
    assert "Do not apply, infer, reserve space for" in studio_create.brand_identity_guard(context["brand_context"], creation_intent="neutral_asset")
    source = Path(studio_create.__file__).read_text(encoding="utf-8")
    assert "NEUTRAL ASSET CHECK: Do not reserve space for a logo" in source


def test_user_visual_and_global_mask_activate_fast_visual_remix_without_brand_identity():
    context = studio_create.clean_context({"references": [
        {"name": "Peça anexada", "source": "user", "role": "reference", "url": "/static/uploads/creative_references/piece.webp"},
        {"name": "Máscara feed", "source": "global", "role": "reference", "url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp"},
    ], "brand_context": {"name": "Marca sem kit"}}, 1)

    assert context["reference_mode"] == "visual_remix"
    assert context["references"][0]["role"] == "reference"
    assert context["references"][1]["role"] == "composition"
    guard = studio_create.brand_identity_guard(context["brand_context"], visual_reference=True)
    assert "user-supplied image is the visual source" in guard
    assert "Keep a clean neutral safe area" not in guard
    assert "quando contexto.reference_mode for \"visual_remix\"" in studio_create.system_prompt(1)


def test_user_visual_reference_does_not_consume_a_slot_with_project_logo():
    user_reference = {"url": "/static/uploads/creative_references/piece.webp", "source": "user", "role": "reference"}
    assert studio_create.uses_user_visual_reference([user_reference]) is True
    assert studio_create.reference_mode([user_reference]) == "user_visual_reference"


def test_requested_palette_is_task_specific_and_validated_before_the_director_sees_it():
    context = studio_create.clean_context({"requested_palette": ["#6d4aff", "#FFFFFF", "invalid", "#6D4AFF"]}, 1)

    assert context["requested_palette"] == ["#6D4AFF", "#FFFFFF"]
    assert "contexto.requested_palette" in studio_create.system_prompt(1)


def test_official_logo_is_added_to_image_provider_when_a_reference_slot_is_free():
    references = studio_create.references_with_brand_logo([{
        "url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp",
        "role": "composition", "source": "global", "label": "Composição",
    }], {
        "name": "Reserva",
        "logo_url": "/static/uploads/creative_references/reserva-logo.png",
        "palette": ["#152f4e", "#ffffff"],
    })

    assert [item["role"] for item in references] == ["composition", "identity"]
    assert references[-1]["url"].endswith("reserva-logo.png")
    assert "Official color tokens: #152f4e, #ffffff." in studio_create.brand_identity_guard({
        "logo_url": "/static/uploads/creative_references/reserva-logo.png",
        "palette": ["#152f4e", "#ffffff"],
    })


def test_global_mask_base_piece_and_logo_keep_three_provider_slots_during_visual_remix():
    references = studio_create.references_with_brand_logo([
        {"url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp", "role": "composition", "source": "global"},
        {"url": "/static/uploads/creative_references/base-piece.webp", "role": "reference", "source": "user"},
    ], {"name": "Reserva", "logo_url": "/static/uploads/creative_references/reserva-logo.png"})

    assert [item["role"] for item in references] == ["composition", "reference", "identity"]
    assert references[0]["url"].endswith("feed-mask-01.webp")
    assert references[1]["url"].endswith("base-piece.webp")
    assert references[2]["url"].endswith("reserva-logo.png")


def image_data(color, size=(4, 4), mask_box=None):
    image = Image.new("RGB", size, color)
    if mask_box is not None:
        image = Image.new("L", size, 0)
        ImageDraw.Draw(image).rectangle(mask_box, fill=255)
    output = io.BytesIO()
    image.save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


def test_global_feed_reference_stays_url_first_for_image_providers():
    static_folder = Path(__file__).parents[1] / "aicentralv2" / "static"
    app = Flask(__name__, static_folder=str(static_folder))

    with app.app_context():
        references = studio_create.normalize_image_references([{
            "id": "feed-mask-01",
            "url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp",
            "role": "composition",
            "source": "global",
            "label": "Referência de composição",
        }], SimpleNamespace())

    assert len(references) == 1
    assert references[0]["source"] == "global"
    assert references[0]["role"] == "composition"
    assert references[0]["data"] == "/static/images/cadu/studio/references/feed/feed-mask-01.webp"

    provider_value = studio_create.provider_image_references(references, "")[0]
    assert provider_value == references[0]["data"]


def test_uploaded_reference_stays_url_first_until_pixels_are_needed():
    app = Flask(__name__)
    app.config.update(STUDIO_URL="https://studio.test")
    with app.app_context():
        references = studio_create.normalize_image_references([{
            "url": "https://studio.test/static/uploads/creative_references/product.webp",
            "role": "identity",
        }], SimpleNamespace())

    provider_references = studio_create.provider_image_references(references, "")
    assert references[0]["data"] == "https://studio.test/static/uploads/creative_references/product.webp"
    assert provider_references == [references[0]["data"]]
    assert not any("base64" in item for item in provider_references)


def test_generated_output_is_fitted_to_exact_selected_dimensions():
    encoded = image_data("blue", size=(12, 12)).split(",", 1)[1]

    fitted = studio_create.fit_generated_output(encoded, 108, 135, "png")
    result = Image.open(io.BytesIO(base64.b64decode(fitted)))

    assert result.size == (108, 135)


def test_mask_composition_preserves_every_pixel_outside_selection():
    source = image_data("red")
    generated = image_data("blue").split(",", 1)[1]
    mask = image_data("black", mask_box=(0, 0, 1, 3))

    encoded = studio_create.compose_inside_mask(generated, source, mask)
    result = Image.open(io.BytesIO(base64.b64decode(encoded))).convert("RGB")

    assert result.getpixel((0, 2)) == (0, 0, 255)
    assert result.getpixel((3, 2)) == (255, 0, 0)


def test_image_generation_keeps_reference_roles_in_provider_prompt():
    captured = {}
    source = image_data("red")
    generated = image_data("blue").split(",", 1)[1]

    class Generator:
        def generate_image(self, prompt, references, **kwargs):
            captured.update(prompt=prompt, references=references, kwargs=kwargs)
            return {"b64_json": generated, "model": "test-image", "output_format": "png"}

    class Storage:
        def save_generated_base64(self, encoded, _format):
            captured["saved"] = encoded
            return "/static/uploads/creative_generated/result.png"

    def charge_call(**kwargs):
        captured["charge"] = kwargs
        return {"tokens_cobrados": 12}

    modeling = SimpleNamespace(
        generator=Generator(), storage=Storage(),
        _estimate=lambda *_args: .01,
        _charge_studio_call=charge_call,
        _credits_crm_id=lambda value: value,
        credit_ledger=SimpleNamespace(
            assert_available=lambda _client, _estimate: 1000,
            available=lambda _client: 988,
        ),
    )
    result = studio_create.create_image({
        "prompt": "Coloque o produto no cenário.", "aspect_ratio": "4:5",
        "request_id": "image-request-123",
        "studio_session_id": "session-1", "studio_root_session_id": "root-1",
        "references": [
            {"url": source, "role": "primary", "label": "Cenário"},
            {"url": image_data("green"), "role": "insert", "label": "Produto"},
        ],
        "brand_context": {"name": "Centralcomm"},
    }, modeling, 10, 20)

    assert "IMAGE 1" in captured["prompt"]
    assert "primary/base image" in captured["prompt"]
    assert "IMAGE 2" in captured["prompt"]
    assert "element source" in captured["prompt"]
    assert "Do not invent, infer or stylize a logo" in captured["prompt"]
    assert captured["kwargs"]["aspect_ratio"] == "4:5"
    assert result["image_url"].endswith("result.png")
    assert result["remaining_credits"] == 988
    assert captured["charge"]["metadata"]["studio_session_id"] == "session-1"
    assert captured["charge"]["metadata"]["studio_root_session_id"] == "root-1"


def test_image_generation_checks_balance_before_calling_provider():
    called = []

    class Generator:
        def generate_image(self, *_args, **_kwargs):
            called.append("provider")

    modeling = SimpleNamespace(
        generator=Generator(), storage=SimpleNamespace(),
        _estimate=lambda *_args: .01,
        _credits_crm_id=lambda value: value,
        credit_ledger=SimpleNamespace(
            assert_available=lambda *_args: (_ for _ in ()).throw(ValueError("Saldo insuficiente")),
        ),
    )

    try:
        studio_create.create_image({
            "prompt": "Crie uma imagem.", "request_id": "image-request-no-credit",
        }, modeling, 10, 20)
    except ValueError as error:
        assert "Saldo insuficiente" in str(error)
    else:
        raise AssertionError("A geração deveria ter sido bloqueada sem saldo.")
    assert called == []


def test_mask_is_sent_as_visual_reference_when_there_is_only_a_base_image():
    captured = {}
    source = image_data("red")
    mask = image_data("black", mask_box=(0, 0, 1, 3))
    generated = image_data("blue").split(",", 1)[1]

    class Generator:
        def generate_image(self, prompt, references, **_kwargs):
            captured.update(prompt=prompt, references=references)
            return {"b64_json": generated, "model": "test-image", "output_format": "png"}

    modeling = SimpleNamespace(
        generator=Generator(),
        storage=SimpleNamespace(save_generated_base64=lambda *_args: "/result.png"),
        _estimate=lambda *_args: .01,
        _charge_studio_call=lambda **_kwargs: {},
        _credits_crm_id=lambda value: value,
        credit_ledger=SimpleNamespace(assert_available=lambda *_args: 1000, available=lambda *_args: 988),
    )
    studio_create.create_image({
        "prompt": "Troque a área marcada.", "request_id": "image-request-mask",
        "references": [{"url": source, "role": "primary", "label": "Base"}],
        "mask": mask,
    }, modeling, 10, 20)

    assert len(captured["references"]) == 2
    assert captured["references"][1] == mask
    assert "IMAGE 2 is a black-and-white selection mask" in captured["prompt"]


def test_mask_must_belong_to_the_declared_primary_image():
    try:
        studio_create.create_image({
            "prompt": "Troque a área marcada.", "request_id": "image-request-wrong-base",
            "references": [{"id": "base-a", "url": image_data("red"), "role": "primary"}],
            "mask": image_data("black", mask_box=(0, 0, 1, 3)), "mask_node_id": "base-b",
        }, SimpleNamespace(storage=SimpleNamespace()), 10, 20)
    except ValueError as error:
        assert "não pertence à imagem principal" in str(error)
    else:
        raise AssertionError("A máscara de outra imagem deveria ser rejeitada.")
