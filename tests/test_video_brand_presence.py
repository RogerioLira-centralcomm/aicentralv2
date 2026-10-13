"""Presença da marca no Vídeo: onde o logo oficial entra, cores e fonte da marca nas cenas, legendas e textos."""
import base64
import io
import shutil
import subprocess
from unittest.mock import Mock, patch

import pytest
from flask import Flask, session
from PIL import Image

from aicentralv2.creative_media.studio_storyboard import (
    assign_brand_marks, palette_names, plan_storyboard, regenerate_beat, scene_image_prompt,
)

BRIEF = "Internet fibra para famílias, com a oferta e o CTA no fim."


def beat(purpose, **extra):
    return {"purpose": purpose, "visual": f"Cena {purpose} com a família", "motion": "push-in", "hold": "produto",
            "transition": "cut", "spoken": "", **extra}


def beats(*purposes):
    return [dict(beat(purpose), id=f"b{index}") for index, purpose in enumerate(purposes)]


# ---- onde o logo entra ----

@pytest.mark.parametrize("presence, marks", [
    ("none", ["none", "none", "none", "none"]),
    ("discreet", ["none", "none", "none", "signature"]),
    ("balanced", ["none", "badge", "badge", "signature"]),
    ("strong", ["badge", "badge", "badge", "signature"]),
    ("qualquer", ["none", "none", "none", "signature"]),  # desconhecido = Discreta, o padrão
])
def test_nivel_de_presenca_define_o_ponto_de_partida(presence, marks):
    rows = assign_brand_marks(beats("hook", "offer", "proof", "end"), presence)
    assert [row["brand"] for row in rows] == marks


def test_storyboard_devolve_a_marcacao_e_o_nivel_escolhido():
    model = lambda messages, **options: {"message": {"content": {"beats": [beat("hook"), beat("offer"), beat("end")]}}}
    out = plan_storyboard(BRIEF, duration=12, text_callable=model, presence="balanced")
    assert out["brand_presence"] == "balanced"
    assert [row["brand"] for row in out["beats"]] == ["none", "badge", "signature"]
    # O modelo não decide onde o logo entra: o nível e quem edita decidem.
    model = lambda messages, **options: {"message": {"content": {"beats": [beat("hook", brand="signature"), beat("beat"), beat("end")]}}}
    assert [row["brand"] for row in plan_storyboard(BRIEF, duration=12, text_callable=model)["beats"]] == ["none", "none", "signature"]


def test_reescrever_a_cena_mantem_a_marcacao_dela():
    scenes = beats("hook", "offer", "end")
    scenes[1]["brand"] = "badge"
    model = lambda messages, **options: {"message": {"content": {"beat": {"visual": "Roteador na mesa", "brand": "none"}}}}
    assert regenerate_beat(BRIEF, scenes, 1, text_callable=model)["beat"]["brand"] == "badge"


# ---- diretor em duas passadas ----

def director(plan_beats, review=None):
    calls = []

    def model(messages, **options):
        calls.append((options.get("step"), options.get("reasoning"), messages))
        if options.get("step") == "review":
            if isinstance(review, Exception):
                raise review
            return {"message": {"content": {"beats": review if review is not None else plan_beats}}}
        return {"message": {"content": {"conceito": {"ideia": "A fibra que some da sala", "gancho": "Cabo cortado", "arco": "Do caos à calma"},
                                        "beats": plan_beats}}}
    return model, calls


def test_conceito_e_revisao_critica_substituem_o_rascunho():
    first = [beat("hook", shot="geral", setting="Sala"), beat("offer", shot="geral", setting="Sala"), beat("end", shot="close", setting="Rua")]
    better = [beat("hook", shot="detalhe", setting="Sala à noite", visual="Mão corta um cabo emaranhado"), beat("offer", shot="médio", setting="Cozinha"),
              beat("end", shot="geral", setting="Fachada")]
    model, calls = director(first, better)
    out = plan_storyboard(BRIEF, duration=12, text_callable=model, style="illustration")
    assert [step for step, _, _ in calls] == ["plan", "review"]
    assert calls[0][1] == {"effort": "medium"}
    assert out["concept"]["ideia"] == "A fibra que some da sala" and out["style"] == "illustration"
    assert out["beats"][0]["visual"] == "Mão corta um cabo emaranhado" and out["beats"][0]["shot"] == "detalhe"
    assert "Ilustração digital" in calls[0][2][1]["content"]
    assert "A fibra que some da sala" in calls[1][2][1]["content"]  # a revisão conhece o conceito
    assert not any("mesmo plano" in warning for warning in out["warnings"])


def test_revisao_que_falha_ou_muda_a_quantidade_mantem_o_rascunho():
    first = [beat("hook", shot="geral", setting="Sala"), beat("beat", shot="close", setting="Sala"), beat("end", shot="detalhe", setting="Rua")]
    for review in (ValueError("json"), RuntimeError("saldo insuficiente"), KeyError("message"), [beat("hook"), beat("end")]):
        model, _ = director(first, review)
        out = plan_storyboard(BRIEF, duration=12, text_callable=model)
        assert [row["shot"] for row in out["beats"]] == ["geral", "close", "detalhe"]


def test_repeticao_de_plano_e_ambiente_vira_aviso():
    same = [beat("hook", shot="médio", setting="Sala"), beat("beat", shot="médio", setting="sala"), beat("end", shot="geral", setting="Rua")]
    model, _ = director(same)
    assert "Cenas com o mesmo plano e ambiente da anterior: 2." in plan_storyboard(BRIEF, duration=12, text_callable=model)["warnings"]


def test_diretor_recebe_a_marca_de_verdade_e_seus_numeros_valem_como_fato():
    from aicentralv2.creative_media.studio_storyboard import _brand
    brand = {"name": "Cemig", "products_services": ["Fibra 500 mega", "Wi-Fi 6"], "differentiators": ["Instalação em 24h"],
             "proof_points": ["98% de satisfação"], "visual_motifs": ["ondas verdes"], "forbidden_elements": ["concorrentes"],
             "creative_line": {"signature_summary": "Tecnologia que some na casa"}, "logo_url": "/static/x.png"}
    context = _brand(brand)
    assert context["products"] == "Fibra 500 mega; Wi-Fi 6" and context["forbidden"] == "concorrentes"
    assert context["summary"] == "Tecnologia que some na casa" and "logo" not in str(context)
    rows = [beat("hook"), beat("proof", visual="Selo de 98% de satisfação na parede"), beat("end")]
    model, _ = director(rows)
    assert not any("Números" in warning for warning in plan_storyboard(BRIEF, duration=12, text_callable=model, brand=brand)["warnings"])


def test_imagem_da_cena_usa_plano_ambiente_estilo_e_ancora_so_de_identidade():
    prompt = scene_image_prompt({"visual": "Mão corta um cabo", "shot": "detalhe", "setting": "Sala à noite"}, 1, 4, anchored=True, style="3d")
    assert prompt.startswith("Cena 2 de 4 de um vídeo publicitário. Render 3D")
    assert "Plano detalhe · Sala à noite." in prompt
    assert "define só a identidade" in prompt and "plano, ângulo, ambiente, luz e ação" in prompt
    assert "Fotografia publicitária realista" in scene_image_prompt({"visual": "x"}, 0, 2, style="desconhecido")


# ---- cores e lugar do logo na imagem da cena ----

def test_cores_da_marca_chegam_por_nome_e_sem_codigo():
    assert palette_names({"palette": ["#176b5e", "#1a6f60", "#ffffff", "#fff"]}) == ["verde-azulado escuro", "branco", "#fff"]
    prompt = scene_image_prompt({"visual": "Família na sala"}, 0, 3, palette=["verde-azulado escuro", "#fff"])
    assert "verde-azulado escuro" in prompt and "#" not in prompt


def test_cena_com_logo_reserva_o_lugar_dele_e_nunca_pede_logo_a_ia():
    signature = scene_image_prompt({"visual": "Fachada da loja", "brand": "signature"}, 2, 3)
    badge = scene_image_prompt({"visual": "Fachada da loja", "brand": "badge"}, 1, 3)
    plain = scene_image_prompt({"visual": "Fachada da loja"}, 0, 3)
    assert "centro do quadro" in signature and "canto inferior direito" in badge
    assert "centro do quadro" not in plain and "canto inferior direito" not in plain
    assert all("Sem texto, sem logotipo" in text for text in (signature, badge, plain))


def test_referencia_da_marca_orienta_a_primeira_cena():
    assert "referência mostram o produto" in scene_image_prompt({"visual": "x"}, 0, 3, brand_references=True)
    # Com âncora, a 1ª cena manda; a referência da marca não entra no texto.
    assert "referência mostram o produto" not in scene_image_prompt({"visual": "x"}, 1, 3, anchored=True, brand_references=True)


def test_rota_da_imagem_usa_paleta_e_referencia_da_marca_sem_ancora():
    from aicentralv2.creative_media import studio, studio_create
    app = Flask(__name__)
    app.secret_key = "test"
    brand = {"name": "Cemig", "palette": ["#176b5e"], "logo_url": "/static/logo.png",
             "assets": {"logo": ["/static/logo.png"], "references": ["/static/logo.png", "/static/produto.jpg"]}}
    history = Mock()
    history.claim_image.return_value = {"state": "claimed"}
    history.owned_image_urls.return_value = {"/static/a.png"}
    create = Mock(return_value={"image_url": "/static/new.png", "charged_credits": 120})
    modeling = Mock()
    modeling.add_format_lab_swap_library_still.return_value = {"id": "lib-1", "run_id": "run-1"}

    def call(payload):
        http = (lambda fn: fn(), lambda: payload, lambda data: data, lambda: modeling)
        with app.test_request_context("/x", method="POST"):
            session["user_id"] = 32
            with patch.object(studio, "_http", return_value=http), patch.object(studio, "_scope"), \
                 patch.object(studio, "_creation_history", return_value=history), \
                 patch.object(studio, "_storyboard_brand", return_value=brand), \
                 patch.object(studio_create, "create_image", create):
                return studio.studio_storyboard_image.__wrapped__.__wrapped__()

    assert call({"client_id": 31, "dry_run": True})["brand_reference"] is True
    call({"client_id": 31, "request_id": "req-12345678", "beat": {"visual": "Família", "brand": "badge"}})
    request = create.call_args.args[0]
    assert [ref["url"] for ref in request["references"]] == ["/static/produto.jpg"]  # o logo nunca vira referência
    assert "verde-azulado escuro" in request["prompt"] and "canto inferior direito" in request["prompt"]
    call({"client_id": 31, "request_id": "req-87654321", "beat": {"visual": "Família"}, "anchor_url": "/static/a.png"})
    assert [ref["url"] for ref in create.call_args.args[0]["references"]] == ["/static/a.png"]


# ---- do roteiro ao plano do job ----

def png_url(color=(200, 20, 40, 255), size=(300, 100), transparent=True):
    image = Image.new("RGBA", size, (0, 0, 0, 0) if transparent else color)
    if transparent:
        image.paste(color, (20, 20, size[0] - 20, size[1] - 20))
    out = io.BytesIO()
    image.save(out, "PNG")
    return "data:image/png;base64," + base64.b64encode(out.getvalue()).decode()


def test_plano_leva_a_marcacao_na_ordem_das_cenas():
    from aicentralv2.creative_format_lab.animate import brand_marks_for_plan
    script = [{"id": "s2", "brand": "signature"}, {"id": "s1", "brand": "badge"}, {"id": "s3", "brand": "x"}]
    marks = brand_marks_for_plan({"logos": [png_url(), "data:image/svg+xml;base64,AAAA", "https://evil/logo.png"]}, script, ["s1", "s2", "s3"])
    assert marks["scenes"] == ["badge", "signature", "none"]
    assert len(marks["logos"]) == 1  # só PNG embutido, lido pelo servidor
    assert marks["status"] == "pending"
    # Cena marcada sem logo legível: o plano guarda isso para o Vídeo avisar na entrega.
    assert brand_marks_for_plan({"logos": []}, script, ["s1"]) == {"scenes": ["badge"], "logos": [], "status": "missing"}
    assert brand_marks_for_plan({"logos": [png_url()]}, [{"id": "s1", "brand": "none"}], ["s1"]) is None


def test_logo_vem_da_marca_no_servidor_e_nao_do_navegador():
    from aicentralv2.creative_format_lab import service as lab
    svc = lab.FormatLabService.__new__(lab.FormatLabService)
    svc._client = Mock(return_value={"id": 31})
    marked = {"client_id": 31, "script": {"beats": [{"id": "a", "brand": "signature"}]}, "brand_marks": {"logos": ["data:image/png;base64,FORJADO"]}}
    with patch.object(lab, "build_brand_context", return_value={"name": "Cemig"}), \
         patch("aicentralv2.creative_media.studio_brand_kit.logo_variants_data", return_value=["data:image/png;base64,OFICIAL"]):
        assert svc._with_brand_marks(marked)["brand_marks"] == {"logos": ["data:image/png;base64,OFICIAL"]}
    plain = {"client_id": 31, "script": {"beats": [{"id": "a", "brand": "none"}]}}
    assert svc._with_brand_marks(plain) is plain


# ---- logo por cima do vídeo ----

def test_janelas_do_logo_por_cena():
    from aicentralv2.creative_media.composition.brand_marks import mark_windows
    assert mark_windows(["none", "badge", "none", "signature"], 8.0) == [(1, "badge", 2.15, 3.85), (3, "signature", 6.0, 8.0)]
    # Muitas cenas curtas: a assinatura fica pelo menos 2 s no ar.
    assert mark_windows(["none"] * 9 + ["signature"], 10.0)[-1] == (9, "signature", 8.0, 10.0)


def overlay_box(png):
    image = Image.open(io.BytesIO(png))
    return image.size, image.getchannel("A").getbbox()


def test_selo_no_canto_e_assinatura_no_centro():
    from aicentralv2.creative_media.composition.brand_marks import _logo_images, mark_overlay
    logos = _logo_images([png_url()])
    (width, height), badge = overlay_box(mark_overlay(720, 1280, logos, "badge"))
    assert (width, height) == (720, 1280) and badge[0] > width / 2 and badge[1] > height * 0.8
    _, signature = overlay_box(mark_overlay(720, 1280, logos, "signature"))
    middle_x, middle_y = (signature[0] + signature[2]) / 2, (signature[1] + signature[3]) / 2
    assert abs(middle_x - 360) < 4 and abs(middle_y - 640) < 4 and signature[2] - signature[0] > badge[2] - badge[0]


def test_logo_claro_sobre_cena_clara_vira_versao_escura():
    from aicentralv2.creative_media.composition.brand_marks import _logo_images, mark_overlay
    still = io.BytesIO()
    Image.new("RGB", (640, 360), (250, 250, 250)).save(still, "JPEG")
    png = mark_overlay(640, 360, _logo_images([png_url(color=(255, 255, 255, 255))]), "signature", still.getvalue())
    image = Image.open(io.BytesIO(png)).convert("RGBA")
    box = image.getchannel("A").getbbox()
    pixel = image.getpixel(((box[0] + box[2]) // 2, (box[1] + box[3]) // 2))
    assert pixel[3] == 255 and sum(pixel[:3]) < 100


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg ausente")
def test_video_pronto_recebe_o_logo_so_nas_cenas_marcadas(tmp_path):
    from aicentralv2.creative_media.composition.brand_marks import apply_brand_marks
    source = tmp_path / "base.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=gray:s=320x568:r=24:d=4",
                    "-f", "lavfi", "-i", "sine=d=4", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
                    str(source)], check=True)
    out = tmp_path / "out.mp4"
    out.write_bytes(apply_brand_marks(source.read_bytes(), {"logos": [png_url()], "scenes": ["badge", "none"]}))

    def corner(at):
        frame = tmp_path / f"{at}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(at), "-i", str(out), "-frames:v", "1", str(frame)], check=True)
        image = Image.open(frame).convert("RGB")
        return image.crop((image.width // 2, int(image.height * 0.8), image.width, image.height)).getextrema()

    assert corner(1.0)[0][1] > 150  # vermelho do logo no canto durante a cena 1
    assert corner(3.0)[0][1] < 150  # cena 2 sem logo
    streams = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type", "-of", "csv=p=0", str(out)],
                             capture_output=True, text=True, check=True).stdout.split()
    assert streams == ["video", "audio"]


def test_sem_logo_legivel_a_aplicacao_falha_e_o_worker_registra():
    from aicentralv2.creative_media.composition.brand_marks import apply_brand_marks
    with pytest.raises(ValueError):
        apply_brand_marks(b"video", {"logos": ["data:image/png;base64,quebrado"], "scenes": ["signature"]})


def test_status_do_job_diz_se_o_logo_entrou():
    from aicentralv2.creative_media.public import job_payload
    assert job_payload({"plan_json": {"brand_marks": {"status": "missing"}}})["plan"]["brand_logo"] == "missing"
    assert job_payload({"plan_json": {}})["plan"]["brand_logo"] == ""


def test_so_nomes_de_cor_chegam_ao_prompt_da_imagem():
    prompt = scene_image_prompt({"visual": "x"}, 0, 2, palette=["verde-azulado escuro", "rgb(23, 107, 94)", "0x176b5e", "#fff", "Azul Cemig"])
    assert "verde-azulado escuro, Azul Cemig." in prompt and "rgb" not in prompt and "0x" not in prompt


# ---- fonte e cores da marca no editor ----

def test_so_fontes_do_studio_entram_no_mp4():
    from aicentralv2.creative_media.brand_fonts import video_font_path
    assert video_font_path("/static/fonts/brand/Montserrat-Bold.ttf").name == "Montserrat-Bold.ttf"
    for bad in ("fonts/brand/../OpenSans-Regular.ttf", "/etc/passwd", "fonts/brand/LICENSES.md", "uploads/brand_fonts/nao-existe.ttf", ""):
        assert video_font_path(bad) is None


def test_texto_e_legenda_guardam_a_fonte_da_marca():
    from aicentralv2.creative_media.studio_caption_style import caption_image, normalize_style
    from aicentralv2.creative_media.studio_layers import normalize_layers
    layers = normalize_layers([{"text": "Oi", "font": "/static/fonts/brand/Montserrat-Bold.ttf"}, {"text": "Oi", "font": "../x.ttf"}])
    assert [row["font"] for row in layers] == ["fonts/brand/Montserrat-Bold.ttf", ""]
    style = normalize_style({"preset": "brand", "font": "brand", "brand_font": "fonts/brand/Montserrat-Bold.ttf", "brand_family": "Montserrat",
                             "background": "#176b5e", "background_opacity": .85})
    assert (style["preset"], style["font"], style["brand_font"], style["background"]) == ("brand", "brand", "fonts/brand/Montserrat-Bold.ttf", "#176b5e")
    assert normalize_style({"font": "brand", "brand_font": "../../segredo.ttf"})["font"] == "open"
    assert caption_image("Legenda da marca", 640, 360, style).getbbox()


def test_kit_da_marca_resume_logo_cores_e_fonte():
    from aicentralv2.creative_media.studio_brand_kit import brand_kit
    kit = brand_kit({"name": "Cemig", "logo_url": "/static/logo.png", "palette": ["#176B5E", "#176b5e", "#ffffff"],
                     "fonts": [{"family": "Montserrat", "role": "display"}]})
    assert kit["logo_url"] == "/static/logo.png" and kit["primary_color"] == "#176b5e"
    assert [color["name"] for color in kit["palette"]] == ["verde-azulado escuro", "branco"]
    assert kit["font"]["family"] == "Montserrat" and kit["font"]["source"] == "bundled"
    assert kit["font"]["url"] == "/static/fonts/brand/Montserrat-Bold.ttf"
    empty = brand_kit({})
    assert (empty["logo_url"], empty["palette"], empty["font"]["source"]) == ("", [], "fallback")
