import base64
import io
from types import SimpleNamespace

from PIL import Image, ImageDraw

from aicentralv2.creative_media import studio_create


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


def image_data(color, size=(4, 4), mask_box=None):
    image = Image.new("RGB", size, color)
    if mask_box is not None:
        image = Image.new("L", size, 0)
        ImageDraw.Draw(image).rectangle(mask_box, fill=255)
    output = io.BytesIO()
    image.save(output, "PNG")
    return "data:image/png;base64," + base64.b64encode(output.getvalue()).decode()


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
