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
            "masthead": "solid", "nav": ["Últimas", "Brasil", "Economia", "Mundo"],
            "density": "roomy", "headline_style": "editorial",
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
            "density": "cinematic", "headline_style": "hero",
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
        conn.commit()
    print(f"{len(PROFILES)} visualizadores de mídia populados.")


if __name__ == "__main__":
    main()
