-- Prints dos portais: tipo 'editoria' para a página de uma seção (além de home, noticia e anuncio). Idempotente.
ALTER TABLE cadu_planner_portal_prints DROP CONSTRAINT IF EXISTS cadu_planner_portal_prints_kind_check;
ALTER TABLE cadu_planner_portal_prints
    ADD CONSTRAINT cadu_planner_portal_prints_kind_check CHECK (kind IN ('home', 'noticia', 'editoria', 'anuncio'));
