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
            "masthead": "split",
            "nav": ["Ao vivo", "Política", "Money", "WW", "Agro", "Esportes", "Pop"],
            "density": "dense",
            "headline_style": "breaking",
            "layout": "news_dense",
            "edition_label": "Ao vivo",
            "account_label": "Entrar",
            "hero": {
                "eyebrow": "Breaking",
                "title": "Painel acompanha o impacto das novas rotas de transporte urbano",
                "description": "Edição densa reúne política, economia e o fio contínuo do noticiário.",
                "image": "/static/images/creative-viewers/g1-mobilidade-eletrica.jpg",
            },
            "sections": [{
                "title": "Em alta",
                "items": [{
                    "category": "Política",
                    "title": "Bastidores medem o custo das alianças antes da votação",
                    "summary": "Negociações avançam em silêncio enquanto o plenário espera sinais.",
                    "time": "Há 12 minutos",
                    "image": "/static/images/creative-viewers/g1-lobo-guara.jpg",
                }, {
                    "category": "Money",
                    "title": "Mercado reage a sinais de crédito e infraestrutura",
                    "summary": "Analistas cruzam o noticiário com o movimento das bolsas.",
                    "time": "Há 34 minutos",
                    "image": "/static/images/creative-viewers/g1-festival-gastronomia.jpg",
                }],
            }, {
                "title": "Mais lidas",
                "items": [{
                    "category": "Internacional",
                    "title": "Capitais revisam acordos de energia e mobilidade",
                    "summary": "Governos comparam custos, prazos e o efeito no cotidiano.",
                    "time": "Há 1 hora",
                    "image": "/static/images/creative-viewers/g1-mobilidade-eletrica.jpg",
                }, {
                    "category": "Tecnologia",
                    "title": "Redes de dados ganham rotas alternativas nas cidades",
                    "summary": "Projetos-piloto medem latência e consumo em horário de pico.",
                    "time": "Há 2 horas",
                    "image": "/static/images/creative-viewers/g1-lobo-guara.jpg",
                }],
            }],
        },
    },
    {
        "slug": "sbt-news",
        "name": "SBT News",
        "viewer_kind": "portal",
        "source_url": "https://sbtnews.sbt.com.br/",
        "logo_asset_ref": "/static/images/creative-viewers/sbt-news.svg",
        "palette": {
            "primary": "#006EFF", "secondary": "#051E41",
            "surface": "#FFFFFF", "canvas": "#F4F7FB", "text": "#051E41",
        },
        "shell_spec": {
            "masthead": "gradient",
            "nav": ["Ao vivo", "Últimas", "Vídeos", "Política", "Brasil", "Mundo"],
            "density": "balanced",
            "headline_style": "broadcast",
            "layout": "broadcast",
            "edition_label": "24h",
            "account_label": "Conta SBT",
            "hero": {
                "eyebrow": "Ao vivo",
                "title": "Edição acompanhou o dia com vídeo, política e o fato como ele é",
                "description": "Bloco de broadcast abre a home e segue para o feed de últimas.",
                "image": "/static/images/creative-viewers/g1-mobilidade-eletrica.jpg",
            },
            "sections": [{
                "title": "Vídeos",
                "items": [{
                    "category": "Política",
                    "title": "Entrevista resume o que mudou na pauta do dia",
                    "summary": "O estúdio cruza o fato com o que vem depois do comercial.",
                    "time": "Há 18 minutos",
                    "image": "/static/images/creative-viewers/g1-festival-gastronomia.jpg",
                }, {
                    "category": "Brasil",
                    "title": "Cidades mostram o efeito prático das novas linhas",
                    "summary": "Reportagem percorre terminais e o trajeto até a região central.",
                    "time": "Há 40 minutos",
                    "image": "/static/images/creative-viewers/g1-lobo-guara.jpg",
                }],
            }, {
                "title": "Últimas",
                "items": [{
                    "category": "Mundo",
                    "title": "Capitais comparam rotas de energia e transporte",
                    "summary": "O noticiário internacional entra depois do bloco local.",
                    "time": "Há 1 hora",
                    "image": "/static/images/creative-viewers/g1-mobilidade-eletrica.jpg",
                }, {
                    "category": "Saúde",
                    "title": "Parques ganham percursos com sombra e descanso",
                    "summary": "A edição fecha com o que muda no cotidiano das famílias.",
                    "time": "Há 3 horas",
                    "image": "/static/images/creative-viewers/g1-lobo-guara.jpg",
                }],
            }],
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
                "eyebrow": "Em reprodução",
                "title": "Sua marca no momento certo",
                "description": "Uma pausa integrada à experiência de entretenimento.",
                "image": "/static/images/creative-viewers/catalog/netflix-catalog.svg",
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
                "eyebrow": "Em reprodução",
                "title": "Além das Constelações",
                "description": "Uma aventura para descobrir novos mundos em família.",
                "image": "/static/images/creative-viewers/catalog/disney-catalog.svg",
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
                "eyebrow": "Em reprodução",
                "title": "Herança Sombria",
                "description": "Poder, segredos e uma família à beira do colapso.",
                "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg",
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
            ]            }],
        },
    },
    {
        "slug": "prime-video",
        "name": "Prime Video",
        "viewer_kind": "tv",
        "source_url": "https://www.primevideo.com/",
        "logo_asset_ref": "/static/images/creative-viewers/prime-video.svg",
        "palette": {
            "primary": "#00A8E1", "secondary": "#1A98FF",
            "surface": "#1B2329", "canvas": "#0F171E", "text": "#FFFFFF",
        },
        "shell_spec": {
            "masthead": "overlay",
            "nav": ["Início", "Loja", "TV ao vivo", "Kids"],
            "density": "cinematic",
            "headline_style": "pause",
            "layout": "pause_playback",
            "hero": {
                "eyebrow": "Em reprodução",
                "title": "A Travessia do Norte",
                "description": "O filme continua. Na pausa, o anúncio entra por cima da tela.",
                "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg",
            },
            "sections": [{"title": "Continuar assistindo", "card_shape": "landscape", "items": [
                {"title": "Noite no Porto", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
                {"title": "Rota 27", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
                {"title": "Depois da Maré", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
                {"title": "Casa de Inverno", "image": "/static/images/creative-viewers/catalog/hbo-cinema.svg"},
            ]}],
        },
    },
    {
        "slug": "instagram",
        "name": "Instagram",
        "viewer_kind": "social",
        "source_url": "https://www.instagram.com/",
        "logo_asset_ref": "/static/images/creative-viewers/instagram.svg",
        "palette": {
            "primary": "#E1306C", "secondary": "#F58529",
            "surface": "#FFFFFF", "canvas": "#FAFAFA", "text": "#262626",
        },
        "shell_spec": {
            "network": "instagram",
            "device": "phone",
            "layout": "feed_post",
            "masthead": "post",
            "nav": ["Início", "Reels", "Perfil"],
            "density": "social",
            "headline_style": "caption",
            "hero": {
                "eyebrow": "Patrocinado",
                "title": "Marca no feed",
                "description": "O anúncio preenche o poço da publicação.",
            },
        },
    },
    {
        "slug": "facebook",
        "name": "Facebook",
        "viewer_kind": "social",
        "source_url": "https://www.facebook.com/",
        "logo_asset_ref": "/static/images/creative-viewers/facebook.svg",
        "palette": {
            "primary": "#1877F2", "secondary": "#0866FF",
            "surface": "#FFFFFF", "canvas": "#F0F2F5", "text": "#050505",
        },
        "shell_spec": {
            "network": "facebook",
            "device": "phone",
            "layout": "feed_post",
            "masthead": "post",
            "nav": ["Início", "Watch", "Mercado"],
            "density": "social",
            "headline_style": "caption",
            "hero": {
                "eyebrow": "Patrocinado",
                "title": "Marca no feed",
                "description": "O anúncio preenche o poço da publicação.",
            },
        },
    },
    {
        "slug": "linkedin",
        "name": "LinkedIn",
        "viewer_kind": "social",
        "source_url": "https://www.linkedin.com/",
        "logo_asset_ref": "/static/images/creative-viewers/linkedin.svg",
        "palette": {
            "primary": "#0A66C2", "secondary": "#004182",
            "surface": "#FFFFFF", "canvas": "#F3F2EF", "text": "#191919",
        },
        "shell_spec": {
            "network": "linkedin",
            "device": "desktop",
            "layout": "share_card",
            "masthead": "bar",
            "nav": ["Início", "Rede", "Vagas"],
            "density": "social",
            "headline_style": "professional",
            "hero": {
                "eyebrow": "Promovido",
                "title": "Marca no feed profissional",
                "description": "O anúncio preenche o card 1.91:1 ou o poço do feed.",
            },
        },
    },
    {
        "slug": "tiktok",
        "name": "TikTok",
        "viewer_kind": "social",
        "source_url": "https://www.tiktok.com/",
        "logo_asset_ref": "/static/images/creative-viewers/tiktok.svg",
        "palette": {
            "primary": "#FE2C55", "secondary": "#25F4EE",
            "surface": "#161616", "canvas": "#000000", "text": "#FFFFFF",
        },
        "shell_spec": {
            "network": "tiktok",
            "device": "phone",
            "layout": "full_bleed",
            "masthead": "overlay",
            "nav": ["Início", "Amigos", "Caixa de entrada"],
            "density": "social",
            "headline_style": "caption",
            "hero": {
                "eyebrow": "Patrocinado",
                "title": "Marca no For You",
                "description": "O anúncio preenche o poço 9:16.",
            },
        },
    },
    {
        "slug": "youtube",
        "name": "YouTube",
        "viewer_kind": "social",
        "source_url": "https://www.youtube.com/",
        "logo_asset_ref": "/static/images/creative-viewers/youtube.svg",
        "palette": {
            "primary": "#FF0000", "secondary": "#0F0F0F",
            "surface": "#FFFFFF", "canvas": "#0F0F0F", "text": "#0F0F0F",
        },
        "shell_spec": {
            "network": "youtube",
            "device": "desktop",
            "layout": "watch_player",
            "masthead": "bar",
            "nav": ["Início", "Shorts", "Inscrições"],
            "density": "social",
            "headline_style": "watch",
            "hero": {
                "eyebrow": "Anúncio",
                "title": "Marca no player",
                "description": "O anúncio preenche o player 16:9 ou o poço dos Shorts.",
            },
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
                       OR (ch.slug = 'primevideo' AND vp.slug = 'prime-video')
                       OR (ch.slug = 'portal_generico' AND vp.slug = 'g1')
                       OR (ch.slug = 'meta_social' AND f.slug LIKE 'instagram%' AND vp.slug = 'instagram')
                       OR (ch.slug = 'meta_social' AND f.slug LIKE 'facebook%' AND vp.slug = 'facebook')
                       OR (ch.slug = 'tiktok_social' AND vp.slug = 'tiktok')
                       OR (ch.slug = 'linkedin_social' AND vp.slug = 'linkedin')
                       OR (ch.slug = 'youtube_social' AND vp.slug = 'youtube')
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
