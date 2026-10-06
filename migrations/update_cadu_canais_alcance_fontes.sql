-- Alcance dos canais com fonte pública (pesquisa de 2026-10-06, só escopo Brasil). Idempotente: reaplicar grava os mesmos valores.
-- Depende de add_cadu_canais_fontes_metricas.sql (coluna fontes_metricas).
UPDATE cadu_canais c SET
    alcance = v.alcance,
    alcance_numero = v.alcance_numero,
    fontes_metricas = COALESCE(c.fontes_metricas, '{}'::jsonb) || jsonb_build_object('alcance',
        jsonb_build_object('texto', v.texto, 'ano', v.ano, 'fontes', v.fontes, 'pesquisado_em', '2026-10-06')),
    metricas_atualizadas_em = NOW()
FROM (VALUES
  ('99', '+60M usuários BR', 60000000, '+60 mi usuários ativos no Brasil', '2026', '["https://99app.com/newsroom/usuarios-da-99-crescem-15-em-um-ano-e-chegam-a-mais-de-60-milhoes-no-brasil/", "https://99app.com/99ads/", "https://propmark.com.br/anunciantes/99-transforma-dados-de-mobilidade-em-nova-frente-de-midia-por-meio-da-99ads/"]'::jsonb),
  ('ifood', '+55M usuários BR', 55000000, '+55 mi usuários ativos', '2025', '["https://institucional.ifood.com.br/transparencia/", "https://tab.uol.com.br/noticias/redacao/2025/09/06/a-guerra-de-ifood-rappi-99food-e-keeta-pelo-mercado-de-delivery-no-brasil.htm"]'::jsonb),
  ('instagram', '+147M usuários BR', 147000000, '147 milhões de pessoas alcançáveis por anúncios no Brasil', '2025', '["https://datareportal.com/reports/digital-2025-brazil"]'::jsonb),
  ('kwai', '+60M usuários BR', 60000000, '+60 mi usuários/mês', '2025', '["https://blog.opinionbox.com/kwai-no-brasil/", "https://www.meioemensagem.com.br/patrocinado/kwai/cultura-brasileira-na-nova-economia-da-influencia", "https://content.app-us1.com/JY8yY/2025/03/13/77c53aa6-6081-4ffb-a748-a38b11e00f42.pdf"]'::jsonb),
  ('linkedin', '+75M usuários BR', 75000000, '+75 mi usuários', '2024', '["https://www.meioemensagem.com.br/midia/linkedin-no-brasil", "https://datareportal.com/reports/digital-2024-brazil"]'::jsonb),
  ('tiktok', '+91,7M usuários BR', 91700000, '91,7 mi usuários ativos mensais (18+ no Brasil)', '2025', '["https://www.mlabs.com.br/blog/tiktok-marketing/"]'::jsonb),
  ('twitch', '+15M espectadores BR', 15000000, '+15 mi espectadores/mês', '2024', '["https://theglobaldigest.com/br/twitch-tv/", "https://safety.twitch.tv/sfc/servlet.shepherd/document/download/069at00000Ce210AAB?operationContext=S1"]'::jsonb),
  ('youtube', '+120M usuários BR', 120000000, '120 mi usuários/mês', '2025', '["https://business.google.com/br/think/search-and-video/youtube-20-anos-brasil/", "https://datareportal.com/reports/digital-2024-brazil", "https://marketingltb.com/blog/statistics/youtube-ads-statistics/"]'::jsonb),
  ('amazon-music', '+8M ouvintes BR', 8000000, '+8M ouvintes', '2026', '["https://www.centralcomm.media/canal/amazon-music"]'::jsonb),
  ('deezer', '+16M ouvintes BR', 16000000, '+16M ouvintes', '2025', '["https://www.centralcomm.media/canal/deezer", "https://newsroom-deezer.com/br/2025/07/deezer-e-azerion-anunciam-parceria-exclusiva-para-vendas-publicitarias-no-brasil/", "https://sensortower.com/blog/2024-q4-br-leading-3-Music---Podcasts-brands"]'::jsonb),
  ('disney-plus', '+15M assinantes BR', 15000000, '+15M assinantes BR', '2026', '["https://www.centralcomm.media/canal/disney-plus", "https://www.senalnews.com/es/digital/mas-de-60-anunciantes-eligen-disney-para-llegar-a-audiencias-de-america-latina"]'::jsonb),
  ('hbo-max', '+10M assinantes BR', 10000000, '+10M assinantes BR', '2026', '["https://www.centralcomm.media/canal/hbo-max", "https://www.omelete.com.br/hbo-max/max-e-hbo-bateram-110-milhoes-de-assinantes"]'::jsonb),
  ('paramount-plus', '+8M assinantes BR', 8000000, '+8M assinantes BR', '2025', '["https://www.centralcomm.media/canal/paramount-plus", "https://adsmanager.paramount.com/insights/ctv-advertising-platforms"]'::jsonb),
  ('samsung-tv-plus', '+22,4M usuários BR', 22400000, '+22,4 mi usuários ativos (Brasil)', '2025', '["https://news.samsung.com/br/samsung-tv-plus-atinge-88-milhoes-de-usuarios-ativos-mensais-globalmente", "https://www.samsung.com/br/tvs/smart-tv/samsung-tv-plus/", "https://variety.com/2025/tv/global/sofa-digital-fast-brazil-1236410625", "https://www.centralcomm.media/canal/samsung-tv-plus"]'::jsonb),
  ('spotify', '+56M usuários BR', 56000000, '+56 milhões de usuários ativos mensais no Brasil', '2025', '["https://ads.spotify.com/pt-BR/noticias-insights/spotify-musica-ao-vivo-brasil/", "https://ads.spotify.com/en-US/display-advertising/"]'::jsonb)
) AS v(slug, alcance, alcance_numero, texto, ano, fontes)
WHERE c.slug = v.slug;
