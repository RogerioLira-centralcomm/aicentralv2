import pytest
from io import BytesIO
from PIL import Image
from werkzeug.datastructures import FileStorage

from aicentralv2 import creative_brand_analysis as analysis


def _homepage():
    text = (
        "Acme Energia é uma empresa brasileira. Conheça nossos serviços, soluções, "
        "projetos, atendimento e compromisso com os clientes. "
    ) * 8
    return ({
        "markdown": text,
        "links": ["https://acme.example/sobre", "https://acme.example/contato"],
        "metadata": {
            "sourceURL": "https://acme.example/", "url": "https://acme.example/",
            "title": "Acme Energia", "description": "Serviços e soluções de energia.",
            "statusCode": 200,
        },
    }, "https://acme.example/")


def _type_safe_result(site_probability, evidence_probability):
    return {
        "model": "jev-test",
        "answers": {
            "is_brand_site": {"type": "noul", "noul": site_probability},
            "has_researchable_evidence": {"type": "noul", "noul": evidence_probability},
        },
        "usage": {"input_tokens": 128, "output_tokens": 12},
    }


@pytest.mark.parametrize("mode", ["complete", "deep"])
def test_unmatched_brand_stops_before_broad_crawl_and_paid_llm(monkeypatch, mode):
    monkeypatch.setattr(analysis, "_firecrawl_scrape_com_variantes", lambda *_args, **_kwargs: _homepage())
    monkeypatch.setattr(
        "aicentralv2.services.integration_credentials.resolve_typesafe_api_key",
        lambda: "configured",
    )
    monkeypatch.setattr(
        "aicentralv2.services.typesafe_service.system_one",
        lambda *_args, **_kwargs: _type_safe_result(0.03, 0.91),
    )
    monkeypatch.setattr(
        analysis, "_compact_web_evidence",
        lambda *_args, **_kwargs: pytest.fail("a busca ampla não deveria começar"),
    )
    billed = []
    analyzer = analysis.CreativeBrandAnalyzer(
        llm=lambda *_args, **_kwargs: pytest.fail("nenhum LLM de alto custo deveria ser chamado"),
    )

    with pytest.raises(analysis.BrandPreflightBlocked, match="não confirmou") as error:
        analyzer.analyze(
            "https://acme.example", billing_callback=lambda *event: billed.append(event),
            analysis_mode=mode, brand_name="Marca Diferente", preflight=True,
        )

    assert error.value.preflight_report["decision"] == "reject_typesafe"
    assert error.value.preflight_report["status"] == "blocked"
    assert error.value.preflight_report["usage"]["input_tokens"] == 128
    assert billed == []


def test_ambiguous_typesafe_decision_is_reported_as_blocked_for_manual_review(monkeypatch):
    monkeypatch.setattr(analysis, "_firecrawl_scrape_com_variantes", lambda *_args, **_kwargs: _homepage())
    monkeypatch.setattr(
        "aicentralv2.services.integration_credentials.resolve_typesafe_api_key",
        lambda: "configured",
    )
    monkeypatch.setattr(
        "aicentralv2.services.typesafe_service.system_one",
        lambda *_args, **_kwargs: _type_safe_result(0.53, 0.67),
    )
    analyzer = analysis.CreativeBrandAnalyzer(
        llm=lambda *_args, **_kwargs: pytest.fail("nenhum LLM de alto custo deveria ser chamado"),
    )

    with pytest.raises(analysis.BrandPreflightBlocked, match="inconclusiva") as error:
        analyzer.analyze(
            "https://acme.example", brand_name="Marca Diferente", preflight=True,
        )

    assert error.value.preflight_report["decision"] == "manual_review"
    assert error.value.preflight_report["status"] == "blocked"


def test_confirmed_site_reuses_initial_scrape_for_full_collection(monkeypatch):
    homepage = _homepage()
    calls = []
    monkeypatch.setattr(
        analysis, "_firecrawl_scrape_com_variantes",
        lambda *_args, **_kwargs: (calls.append("homepage") or homepage),
    )
    monkeypatch.setattr(
        "aicentralv2.services.integration_credentials.resolve_typesafe_api_key",
        lambda: "configured",
    )
    monkeypatch.setattr(
        "aicentralv2.services.typesafe_service.system_one",
        lambda *_args, **_kwargs: _type_safe_result(0.97, 0.94),
    )

    initial_page, report = analysis._brand_source_preflight("https://acme.example", "Acme Energia")

    assert report["decision"] == "pass_typesafe"
    assert report["usage"] == {"input_tokens": 128, "output_tokens": 12}
    assert initial_page[0] is homepage[0]
    assert calls == ["homepage"]


def test_compact_collection_reuses_the_preflight_homepage(monkeypatch):
    raw, url = _homepage()
    monkeypatch.setattr(
        analysis, "_firecrawl_scrape_com_variantes",
        lambda *_args, **_kwargs: pytest.fail("homepage must not be scraped twice"),
    )
    monkeypatch.setattr(analysis, "_relevant_pages", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis, "_extract_candidates", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis, "_montar_registro", lambda *_args, **_kwargs: {
        "titulo": "Acme Energia", "descricao": "Empresa de energia.",
        "menu_links": [], "dados_extras": {}, "setor": "energia",
    })
    monkeypatch.setattr(analysis, "_firecrawl_image_search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis, "_firecrawl_market_search", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(analysis, "_ocr_vet_visual_candidates", lambda *_args, **_kwargs: ([], []))
    monkeypatch.setattr(analysis, "_css_color_evidence", lambda *_args, **_kwargs: [])

    evidence, _record = analysis._compact_web_evidence(
        url, deep=False, initial_page=(raw, url, False),
    )

    assert evidence["pages"][0]["url"] == url
    assert evidence["pages"][0]["content"]


def test_typesafe_outage_only_allows_strong_deterministic_brand_match(monkeypatch):
    monkeypatch.setattr(analysis, "_firecrawl_scrape_com_variantes", lambda *_args, **_kwargs: _homepage())
    monkeypatch.setattr(
        "aicentralv2.services.integration_credentials.resolve_typesafe_api_key",
        lambda: "configured",
    )
    monkeypatch.setattr(
        "aicentralv2.services.typesafe_service.system_one",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
    )

    _page, report = analysis._brand_source_preflight("https://acme.example", "Acme Energia")

    assert report["decision"] == "pass_deterministic_fallback"
    assert report["deterministic_match"] is True
    assert report["thresholds"] == {"pass": 0.80, "reject": 0.10}


def test_deterministic_fallback_requires_brand_name_sequence_in_host_or_title():
    substantive_page = (
        "Acme provides products, services, customers and business solutions. "
    ) * 8

    assert analysis._deterministic_preflight_match(
        "Acme Energia", "https://acme-energia.example", substantive_page,
    )
    assert analysis._deterministic_preflight_match(
        "Acme Energia", "https://brand.example", substantive_page,
        title="Acme Energia | Soluções empresariais",
    )
    assert not analysis._deterministic_preflight_match(
        "Acme Energia", "https://brand.example",
        ("Acme provides products and services. " * 8)
        + ("Renewable energy for customers. " * 8),
        title="Welcome",
    )


def test_homepage_provider_failure_blocks_without_entering_expensive_audit(monkeypatch):
    monkeypatch.setattr(
        analysis, "_firecrawl_scrape_com_variantes",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(ValueError("provider timeout")),
    )
    analyzer = analysis.CreativeBrandAnalyzer(
        llm=lambda *_args, **_kwargs: pytest.fail("nenhum LLM deveria ser chamado"),
    )

    with pytest.raises(analysis.BrandPreflightBlocked, match="não conseguiu consultar") as error:
        analyzer.analyze(
            "https://acme.example", brand_name="Acme Energia", preflight=True,
        )

    assert error.value.preflight_report["decision"] == "source_unavailable"
    assert error.value.preflight_report["source_error"] == "provider timeout"


def test_image_only_audit_requires_an_already_approved_brand_asset(monkeypatch):
    monkeypatch.setattr(
        analysis, "_compact_web_evidence",
        lambda *_args, **_kwargs: pytest.fail("imagem sem fonte validada não deve iniciar análise"),
    )
    analyzer = analysis.CreativeBrandAnalyzer(
        llm=lambda *_args, **_kwargs: pytest.fail("nenhum LLM deveria ser chamado"),
    )
    stream = BytesIO()
    Image.new("RGB", (4, 4), "#123456").save(stream, format="PNG")
    stream.seek(0)
    image = FileStorage(stream=stream, filename="referencia.png", content_type="image/png")

    with pytest.raises(analysis.BrandPreflightBlocked, match="site oficial"):
        analyzer.analyze(image=image, brand_name="Acme", preflight=True)


def test_deep_audit_requires_an_official_site_even_with_approved_images(monkeypatch):
    monkeypatch.setattr(
        analysis, "_compact_web_evidence",
        lambda *_args, **_kwargs: pytest.fail("deep research must not start without an official site"),
    )
    analyzer = analysis.CreativeBrandAnalyzer(
        llm=lambda *_args, **_kwargs: pytest.fail("nenhum LLM deveria ser chamado"),
    )
    stream = BytesIO()
    Image.new("RGB", (4, 4), "#123456").save(stream, format="PNG")
    stream.seek(0)
    image = FileStorage(stream=stream, filename="referencia.png", content_type="image/png")

    with pytest.raises(analysis.BrandPreflightBlocked, match="precisa do site oficial"):
        analyzer.analyze(
            image=image, brand_name="Acme", preflight=True,
            has_trusted_brand_assets=True, analysis_mode="deep",
        )
