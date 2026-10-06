import pytest

from aicentralv2.creative_media.studio_storyboard import plan_storyboard, suggested_scene_count


def fake(beats):
    return lambda messages, **options: {"message": {"content": {"beats": beats}}}


def beat(purpose, visual="Família na sala, luz natural", spoken="", **extra):
    return {"purpose": purpose, "visual": visual, "motion": "push-in", "hold": "logo", "transition": "cut", "spoken": spoken, **extra}


BRIEF = "Internet fibra: 500 mega por R$ 79,90 por mês, instalação grátis."


def test_quantidade_sugerida_por_duracao():
    assert [suggested_scene_count(s) for s in (4, 8, 15, 30)] == [2, 2, 3, 7]


def test_beats_no_formato_do_video_com_ids_estaveis():
    out = plan_storyboard(BRIEF, duration=15, text_callable=fake([beat("hook"), beat("offer", spoken="500 mega"), beat("end")]))
    assert [b["id"] for b in out["beats"]] == ["beat-1", "beat-2", "beat-3"]
    assert set(out["beats"][0]) == {"id", "purpose", "visual", "motion", "hold", "transition", "spoken"}
    assert out["warnings"] == []


def test_proporcao_no_visual_nao_conta_como_numero_inventado():
    out = plan_storyboard(BRIEF, duration=15, text_callable=fake(
        [beat("hook", visual="Cena em 16:9 e 1:1"), beat("beat"), beat("end")]))
    assert out["warnings"] == []


def test_numero_fora_do_briefing_gera_aviso():
    out = plan_storyboard(BRIEF, duration=15, text_callable=fake(
        [beat("hook"), beat("offer", spoken="só 49 reais"), beat("end")]))
    assert any("49" in w for w in out["warnings"])


def test_visual_em_objeto_vira_texto():
    out = plan_storyboard(BRIEF, duration=15, text_callable=fake(
        [beat("hook", visual={"sujeito": "família", "ambiente": "sala"}), beat("beat"), beat("end")]))
    assert out["beats"][0]["visual"] == "família. sala"


def test_valores_invalidos_sao_normalizados_e_fala_longa_avisa():
    out = plan_storyboard(BRIEF, duration=4, text_callable=fake(
        [beat("xyz", transition="barra"), beat("end", spoken="palavra " * 40)]))
    assert out["beats"][0]["purpose"] == "beat" and out["beats"][0]["transition"] == "cut"
    assert any("não cabe" in w for w in out["warnings"])
    assert any("abertura" in w for w in out["warnings"])


@pytest.mark.parametrize("briefing", ["", "curto"])
def test_briefing_vazio_ou_curto_e_recusado(briefing):
    with pytest.raises(ValueError):
        plan_storyboard(briefing, text_callable=fake([]))


def test_sem_cenas_suficientes_levanta_erro_claro():
    with pytest.raises(ValueError, match="cenas suficientes"):
        plan_storyboard(BRIEF, text_callable=fake([beat("hook")]))


def test_contexto_real_da_marca_chega_ao_diretor():
    seen = {}

    def model(messages, **options):
        seen["user"] = messages[1]["content"]
        return {"message": {"content": {"beats": [beat("hook"), beat("beat"), beat("end")]}}}

    plan_storyboard(BRIEF, duration=15, text_callable=model, brand={
        "name": "Cemig", "tone_of_voice": "próximo", "palette": ["#00a", "#fff"], "target_audience": "famílias", "logo": "x"})
    assert "próximo" in seen["user"] and "#00a" in seen["user"] and "famílias" in seen["user"]
    assert "logo" not in seen["user"]


# ---- reescrever uma cena ----
from aicentralv2.creative_media.studio_storyboard import regenerate_beat  # noqa: E402

SCENES = [
    {"id": "a", "purpose": "hook", "visual": "Família na sala", "motion": "push-in", "hold": "logo", "transition": "cut", "spoken": "Olá"},
    {"id": "b", "purpose": "offer", "visual": "Roteador em destaque", "motion": "zoom", "hold": "oferta", "transition": "cut", "spoken": "500 mega"},
    {"id": "c", "purpose": "end", "visual": "Logo final", "motion": "pull-back", "hold": "logo", "transition": "cut", "spoken": "Fale com a gente"},
]


def one(row):
    return lambda messages, **options: {"message": {"content": {"beat": row}}}


def test_reescreve_so_a_cena_pedida_e_mantem_id_e_funcao():
    seen = {}

    def model(messages, **options):
        seen["context"] = messages[1]["content"]
        return {"message": {"content": {"beat": {"visual": "Roteador sobre a mesa, luz de fim de tarde", "motion": "dolly", "hold": "oferta", "transition": "cut", "spoken": "500 mega para você"}}}}

    result = regenerate_beat(BRIEF, SCENES, 1, instruction="mais caloroso", duration=15, text_callable=model)
    assert result["beat"]["id"] == "b" and result["beat"]["purpose"] == "offer"
    assert result["beat"]["visual"].startswith("Roteador sobre a mesa")
    assert '"cena_para_reescrever": 2' in seen["context"] and "mais caloroso" in seen["context"]
    assert "Família na sala" in seen["context"] and "Logo final" in seen["context"]  # as outras cenas viajam como contexto


def test_numero_inventado_e_fala_longa_viram_aviso():
    row = {"visual": "Roteador", "spoken": "Só 99 reais " + "palavra " * 40}
    warnings = regenerate_beat(BRIEF, SCENES, 1, duration=6, text_callable=one(row))["warnings"]
    assert any("99" in w for w in warnings) and any("não caiba" in w for w in warnings)


@pytest.mark.parametrize("scenes,index", [([], 0), (SCENES, 3), (SCENES, -1), (SCENES, "1")])
def test_cena_invalida_e_recusada(scenes, index):
    with pytest.raises(ValueError, match="cena válida"):
        regenerate_beat(BRIEF, scenes, index, text_callable=one({"visual": "x"}))


def test_resposta_sem_visual_ou_sem_beat_e_recusada():
    with pytest.raises(ValueError, match="sem descrição visual"):
        regenerate_beat(BRIEF, SCENES, 0, text_callable=one({"visual": "", "spoken": "oi"}))
    with pytest.raises(ValueError, match="não devolveu a cena"):
        regenerate_beat(BRIEF, SCENES, 0, text_callable=lambda m, **o: {"message": {"content": {"outra": 1}}})


# ---- cores da marca: nomes em vez de hexadecimal ----
from aicentralv2.creative_media.studio_storyboard import color_name, plain_colors, scene_image_prompt  # noqa: E402


@pytest.mark.parametrize("code,name", [
    ("#176b5e", "verde-azulado escuro"), ("#dcece6", "verde claro"), ("#ff0000", "vermelho"), ("#000", "preto"),
    ("#ffffff", "branco"), ("#0b3d91", "azul escuro"), ("#8b4513", "marrom"), ("#9e9e9e", "cinza"),
])
def test_codigo_hex_vira_nome_de_cor(code, name):
    assert color_name(code) == name


def test_texto_com_hex_e_limpo_sem_tocar_em_outros_numeros():
    assert plain_colors("Almofadas (#176b5e, #dcece6) e 500 mega") == "Almofadas (verde-azulado escuro, verde claro) e 500 mega"


def test_hex_da_marca_no_visual_nao_gera_numero_inventado_nem_chega_ao_prompt_da_imagem():
    row = beat("hook", visual="Sala com almofadas nas cores da marca (#176b5e, #dcece6) e roteador")
    result = plan_storyboard(BRIEF, duration=9, brand={"name": "Marca", "colors": "#176b5e, #dcece6"},
                             text_callable=fake([row, beat("offer"), beat("end")]))
    assert result["warnings"] == []
    assert "#" not in result["beats"][0]["visual"] and "verde-azulado escuro" in result["beats"][0]["visual"]
    assert "#" not in scene_image_prompt({"visual": "Parede #176b5e"}, 0, 3)


def test_texto_comum_com_cerquilha_nao_vira_cor():
    assert plain_colors("Pedido #500, hashtag #bad e #fee, cor #176b5e") == "Pedido #500, hashtag #bad e #fee, cor verde-azulado escuro"
