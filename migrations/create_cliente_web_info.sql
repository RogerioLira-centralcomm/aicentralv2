-- Cria a tabela `cliente_web_info` para o CRM v3 armazenar informações
-- extraídas do site oficial de cada cliente (via Firecrawl `/scrape`).
--
-- Objetivo (set/2026): eliminar a dependência de cascatas de favicon
-- (Clearbit / Google Favicons / DuckDuckGo) que retornam ícones
-- pequenos/pixelados ou globos genéricos para sites fora do catálogo
-- global. Substituímos por og:image (ou <link rel="icon"> HTMl) real
-- do próprio site do cliente, cacheado no banco.
--
-- 1:1 com tbl_cliente (UNIQUE em id_cliente). Suporta upsert por
-- (id_cliente) e ON DELETE CASCADE para limpar quando o cliente é
-- removido.
--
-- Idempotente: pode rodar múltiplas vezes sem quebrar (IF NOT EXISTS
-- em tabela e índice).
CREATE TABLE IF NOT EXISTS cliente_web_info (
    id                SERIAL PRIMARY KEY,
    id_cliente        INTEGER NOT NULL UNIQUE
                        REFERENCES tbl_cliente(id_cliente) ON DELETE CASCADE,
    dominio           VARCHAR(255) NOT NULL,
    -- Logo canônico do site (og:image priorizado; cai em favicon
    -- retina/<link rel="icon" sizes="180x180"> etc.). Salvamos a URL
    -- absoluta; a UI só faz <img src="...">.
    logo_url          TEXT,
    -- Favicon menor, usado como fallback quando logo_url falha ou o
    -- espaço é apertado (ex.: badges de vinculação).
    favicon_url       TEXT,
    -- <title> ou og:site_name. Não é o nome comercial cadastrado no
    -- cliente (que fica em tbl_cliente.nome_fantasia).
    titulo            TEXT,
    -- meta description ou og:description. Sem limite rígido; espera-se
    -- ~160 caracteres, mas alguns sites publicam parágrafos.
    descricao         TEXT,
    -- Links do menu principal detectados no scrape. Formato:
    -- [{"label":"Sobre","url":"https://cliente.com/sobre"}, ...]
    -- Usado pela aba Web para dar acesso rápido a páginas-chave.
    menu_links        JSONB,
    -- Reservado para expansão futura (Fase B/C do plano macro):
    -- {"equipe": [...], "clientes_atendidos": [...], "blog": [...],
    --  "redes_sociais": {...}, "sobre_longo": "...", "screenshot_url": "..."}
    -- Não é obrigatório e não substitui os campos acima (que ficam
    -- indexáveis via SELECT direto).
    dados_extras      JSONB,
    -- 'ok' = scrape bem-sucedido com dados válidos.
    -- 'erro' = scrape falhou (Firecrawl 4xx/5xx, domínio inválido,
    --          site fora do ar); usar erro_mensagem para diagnóstico.
    -- 'em_progresso' = scrape disparado, aguardando conclusão
    --                  (reservado para futura fila assíncrona; hoje
    --                   o scrape é síncrono e nunca fica nesse estado).
    status            VARCHAR(20) NOT NULL DEFAULT 'ok',
    erro_mensagem     TEXT,
    atualizado_em     TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    criado_em         TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Índice por domínio para permitir buscas cruzadas (ex.: "qual cliente
-- tem site XYZ?") sem varredura completa. Não é o índice único (esse
-- fica em id_cliente).
CREATE INDEX IF NOT EXISTS idx_cliente_web_info_dominio
    ON cliente_web_info (dominio);

-- Índice em atualizado_em para dashboards / batch job futuro que
-- refresque as informações mais antigas em background.
CREATE INDEX IF NOT EXISTS idx_cliente_web_info_atualizado_em
    ON cliente_web_info (atualizado_em);
