-- Preserve complete planning context instead of truncating channel descriptions.
ALTER TABLE cadu_canais
    ALTER COLUMN alcance TYPE text,
    ALTER COLUMN integracao TYPE text;
