-- Storyboard estruturado e catálogos fictícios dos ambientes CTV.

ALTER TABLE cx_campaigns
    ADD COLUMN IF NOT EXISTS creative_brief JSONB NOT NULL DEFAULT '{}'::jsonb;

INSERT INTO cx_format_templates (
    slug, name_pt, name_en, channel_id, mechanic, media_type, engine,
    aspect_ratio, default_size, safe_area, responsive_rules,
    background_guidance, foreground_guidance, layers,
    placement_spec, behavior_spec, default_viewer_profile_id, status, is_active
)
SELECT
    'netflix-pause-banner',
    'Netflix — Banner na pausa',
    'Netflix — Pause banner',
    ch.id,
    'static_on_pause',
    'image',
    'gpt_image_2',
    '32:5',
    '1920x300',
    '{"top":24,"right":40,"bottom":24,"left":40,"unit":"px"}'::jsonb,
    'Composição horizontal compacta: produto à esquerda, mensagem curta ao centro e CTA à direita.',
    'Ambiente escuro de streaming com contraste contido e integração natural à pausa.',
    'Produto, mensagem em português e CTA devem permanecer totalmente dentro da área segura.',
    '[
      {"role":"sponsor_icon","description_template":"compact brand or product visual anchored at the left edge"},
      {"role":"message","description_template":"short Brazilian Portuguese headline and supporting line centered vertically"},
      {"role":"cta","description_template":"small high-contrast call-to-action button aligned to the right"}
    ]'::jsonb,
    '{"context":"tv","viewport":{"width":1600,"height":900},"slot":{"x":8,"y":6,"width":84,"height":15},"fit":"contain","responsive":"scale"}'::jsonb,
    '{"type":"static","trigger":"none","transition_ms":0}'::jsonb,
    vp.id,
    'formato_aberto',
    TRUE
  FROM cx_channels ch
  JOIN cx_creative_viewer_profiles vp ON vp.slug = 'netflix'
 WHERE ch.slug = 'netflix'
ON CONFLICT (slug) DO UPDATE SET
    name_pt = EXCLUDED.name_pt,
    name_en = EXCLUDED.name_en,
    channel_id = EXCLUDED.channel_id,
    mechanic = EXCLUDED.mechanic,
    media_type = EXCLUDED.media_type,
    engine = EXCLUDED.engine,
    aspect_ratio = EXCLUDED.aspect_ratio,
    default_size = EXCLUDED.default_size,
    safe_area = EXCLUDED.safe_area,
    responsive_rules = EXCLUDED.responsive_rules,
    background_guidance = EXCLUDED.background_guidance,
    foreground_guidance = EXCLUDED.foreground_guidance,
    layers = EXCLUDED.layers,
    placement_spec = EXCLUDED.placement_spec,
    behavior_spec = EXCLUDED.behavior_spec,
    default_viewer_profile_id = EXCLUDED.default_viewer_profile_id,
    is_active = TRUE;

UPDATE cx_creative_viewer_profiles
   SET shell_spec = shell_spec || CASE slug
       WHEN 'g1' THEN
           '{
             "layout":"news_home",
             "nav":["Últimas","Brasil","Economia","Tecnologia","Cultura"],
             "network_links":["globo.com","g1","ge","gshow","globoplay","valor"],
             "edition_label":"Notícias",
             "account_label":"Conta Globo",
             "hero":{
               "eyebrow":"Mobilidade urbana",
               "title":"Cidades testam novas linhas elétricas para reduzir ruído e emissões",
               "description":"Projetos-piloto conectam bairros e avaliam autonomia, conforto e impacto ambiental.",
               "image":"/static/images/creative-viewers/g1-mobilidade-eletrica.jpg"
             },
             "sections":[{"title":"Destaques","items":[
               {"category":"Meio ambiente","title":"Monitoramento registra recuperação de espécies no Cerrado","summary":"Pesquisadores combinam imagens de campo e sensores para acompanhar a fauna.","time":"Há 28 minutos","image":"/static/images/creative-viewers/g1-lobo-guara.jpg"},
               {"category":"Gastronomia","title":"Feiras de bairro ampliam espaço para cozinhas regionais","summary":"Eventos aproximam produtores, cozinheiros e novos públicos.","time":"Há 1 hora","image":"/static/images/creative-viewers/g1-festival-gastronomia.jpg"}
             ]},{"title":"Mais notícias","items":[
               {"category":"Tecnologia","title":"Aplicativos ajudam moradores a acompanhar o consumo de água","summary":"Ferramentas transformam dados diários em alertas simples.","time":"Há 2 horas","image":"/static/images/creative-viewers/g1-mobilidade-eletrica.jpg"},
               {"category":"Bem-estar","title":"Parques urbanos ganham rotas de caminhada com sombra e descanso","summary":"Novos percursos priorizam acessibilidade e contato com áreas verdes.","time":"Há 3 horas","image":"/static/images/creative-viewers/g1-lobo-guara.jpg"}
             ]}]
           }'::jsonb
       WHEN 'disney-plus' THEN
           '{
             "hero":{"eyebrow":"Estreia em destaque","title":"Além das Constelações","description":"Uma aventura para descobrir novos mundos em família."},
             "sections":[{"title":"Histórias para toda a família","items":[
               {"title":"Clube da Imaginação","image":"/static/images/creative-viewers/catalog/disney-catalog.svg"},
               {"title":"A Ilha dos Inventores","image":"/static/images/creative-viewers/catalog/disney-catalog.svg"},
               {"title":"Guardiões do Horizonte","image":"/static/images/creative-viewers/catalog/disney-catalog.svg"},
               {"title":"Ritmo de Verão","image":"/static/images/creative-viewers/catalog/disney-catalog.svg"},
               {"title":"O Segredo da Floresta","image":"/static/images/creative-viewers/catalog/disney-catalog.svg"}
             ]}]
           }'::jsonb
       WHEN 'netflix' THEN
           '{
             "layout":"ranked_portrait",
             "headline_style":"ranked",
             "hero":{"eyebrow":"Conteúdo patrocinado","title":"Sua marca no momento certo","description":"Uma pausa integrada à experiência de entretenimento."},
             "sections":[{"title":"Em alta","ranked":true,"card_shape":"portrait","items":[
               {"title":"Entre Dois Mundos","image":"/static/images/creative-viewers/catalog/netflix-top10.svg"},
               {"title":"Nando: Além da Cidade","image":"/static/images/creative-viewers/catalog/netflix-top10.svg"},
               {"title":"O Mentalista","image":"/static/images/creative-viewers/catalog/netflix-top10.svg"},
               {"title":"Noite em Blackwood","image":"/static/images/creative-viewers/catalog/netflix-top10.svg"},
               {"title":"Bancos de Areia","image":"/static/images/creative-viewers/catalog/netflix-top10.svg"},
               {"title":"A Última Casa","image":"/static/images/creative-viewers/catalog/netflix-top10.svg"},
               {"title":"Horizonte Verde","image":"/static/images/creative-viewers/catalog/netflix-top10.svg"}
             ]}]
           }'::jsonb
       WHEN 'hbo-max' THEN
           '{
             "layout":"premium_layers",
             "hero":{"eyebrow":"Uma nova série original","title":"Herança Sombria","description":"Poder, segredos e uma família à beira do colapso."},
             "sections":[{"title":"Séries premiadas para maratonar","card_shape":"landscape","items":[
               {"title":"O Último Acordo","image":"/static/images/creative-viewers/catalog/hbo-catalog.svg"},
               {"title":"Cidade de Vidro","image":"/static/images/creative-viewers/catalog/hbo-catalog.svg"},
               {"title":"Linha de Poder","image":"/static/images/creative-viewers/catalog/hbo-catalog.svg"},
               {"title":"Arquivo 27","image":"/static/images/creative-viewers/catalog/hbo-catalog.svg"},
               {"title":"Maré Alta","image":"/static/images/creative-viewers/catalog/hbo-catalog.svg"}
             ]},{"title":"Cinema que fica com você","card_shape":"landscape","items":[
               {"title":"Depois do Horizonte","image":"/static/images/creative-viewers/catalog/hbo-cinema.svg"},
               {"title":"A Travessia","image":"/static/images/creative-viewers/catalog/hbo-cinema.svg"},
               {"title":"Ecos da Memória","image":"/static/images/creative-viewers/catalog/hbo-cinema.svg"},
               {"title":"Palácio de Inverno","image":"/static/images/creative-viewers/catalog/hbo-cinema.svg"},
               {"title":"Mar Aberto","image":"/static/images/creative-viewers/catalog/hbo-cinema.svg"}
             ]}]
           }'::jsonb
       ELSE '{}'::jsonb
   END,
       updated_at = NOW()
 WHERE slug IN ('g1', 'disney-plus', 'netflix', 'hbo-max');

UPDATE cx_format_templates
   SET placement_spec = jsonb_build_object(
       'context', 'tv',
       'viewport', jsonb_build_object('width', 1600, 'height', 900),
       'slot', CASE slug
           WHEN 'disney-pause-plus' THEN '{"x":22,"y":22,"width":56,"height":48}'::jsonb
           WHEN 'disney-branded-slate' THEN '{"x":20,"y":18,"width":60,"height":54}'::jsonb
           WHEN 'hbomax-pause-ad' THEN '{"x":18,"y":21,"width":64,"height":50}'::jsonb
           WHEN 'hbomax-interactive-midroll' THEN '{"x":14,"y":18,"width":72,"height":54}'::jsonb
           WHEN 'netflix-logo-bumper' THEN '{"x":26,"y":24,"width":48,"height":44}'::jsonb
           WHEN 'netflix-pause-banner' THEN '{"x":8,"y":6,"width":84,"height":15}'::jsonb
           ELSE '{"x":16,"y":19,"width":68,"height":52}'::jsonb
       END,
       'fit', 'contain',
       'responsive', 'scale'
   )
 WHERE slug IN (
     'disney-pause-plus', 'disney-branded-slate',
     'hbomax-pause-ad', 'hbomax-interactive-midroll',
     'netflix-logo-bumper', 'netflix-anuncio-simulado',
     'netflix-pause-banner'
 );
