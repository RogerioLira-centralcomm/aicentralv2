-- Categoria editorial para o catálogo de criativos interativos do Planner.
-- Não substitui tipo técnico ou plataforma: explica qual trabalho a mecânica faz.
ALTER TABLE cadu_formatos
    ADD COLUMN IF NOT EXISTS categoria_criativa VARCHAR(80);

UPDATE cadu_formatos
   SET categoria_criativa = CASE
       WHEN LOWER(nome) LIKE '%quiz%' THEN 'Participação'
       WHEN LOWER(nome) LIKE ANY (ARRAY['%hotspot%', '%cartas%', '%card%']) THEN 'Exploração'
       WHEN LOWER(nome) LIKE ANY (ARRAY['%puxe%', '%arraste%', '%scratch%', '%descubra%']) THEN 'Descoberta'
       WHEN LOWER(nome) LIKE ANY (ARRAY['%native%', '%in-feed%']) THEN 'Conteúdo editorial'
       WHEN LOWER(nome) LIKE ANY (ARRAY['%vídeo%', '%video%', '%outstream%']) THEN 'Narrativa em vídeo'
       ELSE 'Experiência de marca'
   END
 WHERE is_interativo = TRUE
   AND COALESCE(TRIM(categoria_criativa), '') = '';

CREATE INDEX IF NOT EXISTS idx_cadu_formatos_interativos_categoria
    ON cadu_formatos (categoria_criativa, ordem, nome)
    WHERE is_active = TRUE AND is_interativo = TRUE;
