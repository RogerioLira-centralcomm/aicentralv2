-- Padroniza formatos interativos como experiências de portal baseadas em imagens.
-- Migração aditiva e idempotente.

UPDATE cx_format_templates
   SET channel_id = (
           SELECT id FROM cx_channels WHERE slug = 'portal_generico' LIMIT 1
       ),
       default_viewer_profile_id = (
           SELECT id
             FROM cx_creative_viewer_profiles
            WHERE slug = 'g1' AND is_active = TRUE
            LIMIT 1
       ),
       placement_spec = jsonb_build_object(
           'context', 'portal',
           'viewport', jsonb_build_object('width', 1280, 'height', 800),
           'slot', CASE slug
               WHEN 'native-infeed'
                   THEN '{"x":10,"y":28,"width":52,"height":45}'::jsonb
               ELSE '{"x":14,"y":22,"width":72,"height":52}'::jsonb
           END,
           'fit', 'contain',
           'responsive', 'scale'
       ),
       behavior_spec = CASE slug
           WHEN 'hotspot'
               THEN '{"type":"hotspot","trigger":"hover_tap","transition_ms":220}'::jsonb
           WHEN 'cartas'
               THEN '{"type":"flip","trigger":"click","transition_ms":420}'::jsonb
           WHEN 'puxe-descubra'
               THEN '{"type":"reveal","trigger":"drag_vertical","transition_ms":280}'::jsonb
           WHEN 'arraste-descubra'
               THEN '{"type":"compare","trigger":"drag_horizontal","transition_ms":0}'::jsonb
           WHEN 'quiz'
               THEN '{"type":"quiz","trigger":"click","transition_ms":180}'::jsonb
           ELSE '{"type":"carousel","trigger":"auto","transition_ms":420}'::jsonb
       END
 WHERE slug IN (
     'hotspot', 'cartas', 'puxe-descubra', 'arraste-descubra',
     'quiz', 'native-infeed', 'video-outstream'
 );

UPDATE cx_format_templates
   SET media_type = 'image',
       engine = 'gpt_image_2',
       mechanic = 'image_carousel',
       behavior_spec = '{"type":"carousel","trigger":"auto","transition_ms":420}'::jsonb
 WHERE slug IN (
     'video-outstream', 'netflix-logo-bumper',
     'netflix-anuncio-simulado', 'hbomax-interactive-midroll'
 );
