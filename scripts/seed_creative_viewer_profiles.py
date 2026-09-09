#!/usr/bin/env python
"""Seed idempotente dos visualizadores de portais e CTV."""

import os
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row
from psycopg.types.json import Json


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DISCLAIMER = "Simulação de ambiente · sem afiliação com o veículo"

PROFILES = (
    {
        "slug": "g1",
        "name": "G1",
        "viewer_kind": "portal",
        "source_url": "https://g1.globo.com/",
        "logo_asset_ref": "/static/images/creative-viewers/g1.svg",
        "palette": {
            "primary": "#C4170C", "secondary": "#8B0000",
            "surface": "#FFFFFF", "canvas": "#F3F3F3", "text": "#333333",
        },
        "shell_spec": {
            "masthead": "solid",
            "nav": ["Últimas", "Brasil", "Economia", "Tecnologia", "Cultura"],
            "network_links": ["globo.com", "g1", "ge", "gshow", "globoplay", "valor"],
            "edition_label": "Notícias",
            "account_label": "Conta Globo",
            "density": "roomy", "headline_style": "editorial",
            "layout": "news_home",
            "hero": {
                "eyebrow": "Mobilidade urbana",
                "title": "Cidades testam novas linhas elétricas para reduzir ruído e emissões",
                "description": "Projetos-piloto conectam bairros e avaliam autonomia, conforto e impacto ambiental.",
                "image": "/static/images/creative-viewers/g1-mobilidade-eletrica.jpg",
            },
            "sections": [{
                "title": "Destaques",
                "items": [{
                    "category": "Meio ambiente",
                    "title": "Monitoramento registra recuperação de espécies no Cerrado",
                    "summary": "Pesquisadores combinam imagens de campo e sensores para acompanhar a fauna.",
                    "time": "Há 28 minutos",
                    "image": "/static/images/creative-viewers/g1-lobo-guara.jpg",
                }, {
                    "category": "Gastronomia",
                    "title": "Feiras de bairro ampliam espaço para cozinhas regionais",
                    "summary": "Eventos aproximam produtores, cozinheiros e novos públicos.",
                    "time": "Há 1 hora",
                    "image": "/static/images/creative-viewers/g1-festival-gastronomia.jpg",
                }],
            }, {
                "title": "Mais notícias",
                "items": [{
                    "category": "Tecnologia",
                    "title": "Aplicativos ajudam moradores a acompanhar o consumo de água",
                    "summary": "Ferramentas transformam dados diários em alertas simples.",
                    "time": "Há 2 horas",
                    "image": "/static/images/creative-viewers/g1-mobilidade-eletrica.jpg",
                }, {
                    "category": "Bem-estar",
                    "title": "Parques urbanos ganham rotas de caminhada com sombra e descanso",
                    "summary": "Novos percursos priorizam acessibilidade e contato com áreas verdes.",
                    "time": "Há 3 horas",
                    "image": "/static/images/creative-viewers/g1-lobo-guara.jpg",
                }],
            }],
        },
    },
    {
        "slug": "cnn-brasil",
        "name": "CNN Brasil",
        "viewer_kind": "portal",
        "source_url": "https://www.cnnbrasil.com.br/",
        "logo_asset_ref": "/static/images/creative-viewers/cnn-brasil.svg",
        "palette": {
            "primary": "#CC0000", "secondary": "#191919",
            "surface": "#FFFFFF", "canvas": "#F5F5F5", "text": "#202020",
        },
        "shell_spec": {
            "masthead": "split", "nav": ["Política", "Economia", "Esportes", "Pop"],
            "density": "dense", "headline_style": "breaking",
        },
    },
    {
        "slug": "sbt-news",
        "name": "SBT News",
        "viewer_kind": "portal",
        "source_url": "https://sbtnews.sbt.com.br/",
        "logo_asset_ref": "/static/images/creative-viewers/sbt-news.svg",
        "palette": {
            "primary": "#4B2D83", "secondary": "#13A8D4",
            "surface": "#FFFFFF", "canvas": "#F4F6FA", "text": "#202538",
        },
        "shell_spec": {
            "masthead": "gradient", "nav": ["Notícias", "Brasil", "Mundo", "Esportes"],
            "density": "balanced", "headline_style": "broadcast",
        },
    },
    {
        "slug": "netflix",
        "name": "Netflix",
        "viewer_kind": "tv",
        "source_url": "https://www.netflix.com/br/",
        "logo_asset_ref": "/static/images/creative-viewers/netflix.png",
        "palette": {
            "primary": "#E50914", "secondary": "#B20710",
            "surface": "#181818", "canvas": "#000000", "text": "#FFFFFF",
        },
        "shell_spec": {
            "masthead": "overlay", "nav": ["Início", "Séries", "Filmes", "Minha lista"],
            "density": "cinematic", "headline_style": "ranked",
            "layout": "ranked_portrait",
            "hero": {
                "eyebrow": "Conteúdo patrocinado",
                "title": "Sua marca no momento certo",
                "description": "Uma pausa integrada à experiência de entretenimento.",
            },
            "sections": [{"title": "Em alta", "ranked": True, "card_shape": "portrait", "items": [
                {"title": "Entre Dois Mundos", "image": "/static/images/creative-viewers/catalog/netflix-top10.svg"},
                {"title": "Nando: Além da Cidade", "image": "/static/images/creative-viewers/catalog/netflix-top10.svg"},
                {"title": "O Mentalista", "image": "/static/images/creative-viewers/catalog/netflix-top10.svg"},
                {"title": "Noite em Blackwood", "image": "/static/images/creative-viewers/catalog/netflix-top10.svg"},
                {"title": "Bancos de Areia", "image": "/static/images/creative-viewers/catalog/netflix-top10.svg"},
                {"title": "A Última Casa", "image": "/static/images/creative-viewers/catalog/netflix-top10.svg"},
                {"title": "Horizonte Verde", "image": "/static/images/creative-viewers/catalog/netflix-top10.svg"},
            ]}],
        },
    },
    {
        "slug": "disney-plus",
        "name": "Disney+",
        "viewer_kind": "tv",
        "source_url": "https://www.disneyplus.com/pt-br",
        "logo_asset_ref": "/static/images/creative-viewers/disney-plus.png",
        "palette": {
            "primary": "#02D6E8", "secondary": "#113CCF",
            "surface": "#101A35", "canvas": "#040714", "text": "#F9F9F9",
        },
        "shell_spec": {
            "masthead": "overlay", "nav": ["Início", "Filmes", "Séries", "Originais"],
            "density": "cinematic", "headline_style": "franchise",
            "hero": {
                "eyebrow": "Estreia em destaque",
                "title": "Além das Constelações",
                "description": "Uma aventura para descobrir novos mundos em família.",
            },
            "sections": [{"title": "Histórias para toda a família", "items": [
                {"title": "Clube da Imaginação", "image": "/static/images/creative-viewers/catalog/disney-catalog.svg"},
                {"title": "A Ilha dos Inventores", "image": "/static/images/creative-viewers/catalog/disney-catalog.svg"},
                {"title": "Guardiões do Horizonte", "image": "/static/images/creative-viewers/catalog/disney-catalog.svg"},
                {"title": "Ritmo de Verão", "image": "/static/images/creative-viewers/catalog/disney-catalog.svg"},
                {"title": "O Segredo da Floresta", "image": "/static/images/creative-viewers/catalog/disney-catalog.svg"},
            ]}],
        },
    },
    {
        "slug": "hbo-max",
        "name": "HBO Max",
        "viewer_kind": "tv",
        "source_url": "https://www.hbomax.com/br/pt",
        "logo_asset_ref": "/static/images/creative-viewers/hbo-max.png",
        "palette": {
            "primary": "#9E86FF", "secondary": "#5822B4",
            "surface": "#211534", "canvas": "#0B0714", "text": "#FFFFFF",
        },
        "shell_spec": {
            "masthead": "overlay", "nav": ["Início", "Séries", "Filmes", "HBO"],
            "density": "cinematic", "headline_style": "premium",
            "layout": "premium_layers",
            "hero": {
                "eyebrow": "Uma nova série original",
                "title": "Herança Sombria",
                "description": "Poder, segredos e uma família à beira do colapso.",
            },
            "sections": [{"title": "Séries premiadas para maratonar", "card_shape": "landscape", "items": [
                {"title": "O Último Acordo", "image": "/static/images/creative-viewers/catalog/hbo-catalog.svg"},
                {"title": "Cidade de Vidro", "image": "/static/images/creative-viewers/catalog/hbo-catalog.svg"},
                {"title": "Linha de Poder", "image": "/static/images/creative-viewers/catalog/hbo-catalog.svg"},
                {"title": "Arquivo 27", "image": "/static/images/creative-viewers/catalog/hbo-catalog.svg"},
                {"title": "Maré Alta", "image": "/static/images/creative-viewers/catalog/hbo-catalog.svg"},
            ]}, {"title": "Cinema que fica com você", "card_shape": "landscape", "items": [
                {"title": "Depois do Horizonte", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
                {"title": "A Travessia", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
                {"title": "Ecos da Memória", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
                {"title": "Palácio de Inverno", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
                {"title": "Mar Aberto", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
            ]}],
        },
    },
)


def main():
    with psycopg.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "aicentralv2"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        row_factory=dict_row,
    ) as conn:
        with conn.cursor() as cursor:
            for profile in PROFILES:
                cursor.execute(
                    """
                    INSERT INTO cx_creative_viewer_profiles (
                        slug, name, viewer_kind, source_url, logo_asset_ref,
                        palette, shell_spec, evidence, disclaimer
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (slug) DO UPDATE SET
                        name = EXCLUDED.name,
                        viewer_kind = EXCLUDED.viewer_kind,
                        source_url = EXCLUDED.source_url,
                        logo_asset_ref = EXCLUDED.logo_asset_ref,
                        palette = EXCLUDED.palette,
                        shell_spec = EXCLUDED.shell_spec,
                        evidence = EXCLUDED.evidence,
                        disclaimer = EXCLUDED.disclaimer,
                        is_active = TRUE,
                        updated_at = NOW()
                    """,
                    (
                        profile["slug"], profile["name"], profile["viewer_kind"],
                        profile["source_url"], profile["logo_asset_ref"],
                        Json(profile["palette"]), Json(profile["shell_spec"]),
                        Json({"method": "firecrawl_branding_screenshot", "observed": True}),
                        DISCLAIMER,
                    ),
                )

            cursor.execute(
                """
                UPDATE cx_format_templates f
                   SET default_viewer_profile_id = vp.id
                  FROM cx_channels ch, cx_creative_viewer_profiles vp
                 WHERE f.channel_id = ch.id
                   AND (
                       (ch.slug = 'netflix' AND vp.slug = 'netflix')
                       OR (ch.slug = 'hbomax' AND vp.slug = 'hbo-max')
                       OR (ch.slug = 'disneyplus' AND vp.slug = 'disney-plus')
                       OR (ch.slug = 'portal_generico' AND vp.slug = 'g1')
                   )
                """
            )
            cursor.execute(
                """
                SELECT COUNT(*) AS profile_count
                  FROM cx_creative_viewer_profiles
                 WHERE is_active = TRUE
                   AND slug = ANY(%s)
                """,
                ([profile["slug"] for profile in PROFILES],),
            )
            profile_count = cursor.fetchone()["profile_count"]
            if profile_count != len(PROFILES):
                raise RuntimeError(
                    "Validação do seed falhou: "
                    f"esperados {len(PROFILES)} perfis, encontrados {profile_count}."
                )
        conn.commit()
    print(f"{profile_count} visualizadores de mídia populados e validados.")


if __name__ == "__main__":
    main()
