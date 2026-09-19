import base64
import io
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

    result, _ = studio_create.create({
        "count": 1, "prompt": "Criar anúncio para Reserva.",
        "context": {"references": [{"name": "Máscara feed", "source": "global", "role": "composition", "url": "/static/images/cadu/studio/references/feed/feed-mask-01.webp"}]},
    }, provider)

    content = captured["messages"][1]["content"]
    assert any(block.get("type") == "image_url" for block in content)
    assert all("base64" not in str(block) for block in content)
    assert result["directions"][0]["reference_plan"][0]["layout"]["subject_zone"] == "centro-direita"


def test_direction_logs_both_provider_failures_without_leaking_the_brief(caplog):
    def provider(*_args, **_kwargs):
        raise studio_create.OpenRouterError("reference image URL is invalid")

    with caplog.at_level("WARNING", logger="aicentralv2.creative_media.studio_create"):
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
    references = studio_create.normalize_image_references([{
        "url": "/static/uploads/creative_references/product.webp",
        "role": "identity",
    }], SimpleNamespace())

    assert references[0]["data"] == "/static/uploads/creative_references/product.webp"


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
    }, modeling, 10, 20)

    assert "IMAGE 1" in captured["prompt"]
    assert "primary/base image" in captured["prompt"]
    assert "IMAGE 2" in captured["prompt"]
    assert "element source" in captured["prompt"]
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
