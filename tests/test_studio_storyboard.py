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
