-- O Waze deixou de existir como canal do catálogo. Idempotente: só desativa, não apaga (planos antigos mantêm o snapshot).
UPDATE cadu_canais SET is_active = FALSE WHERE slug = 'waze' AND is_active IS DISTINCT FROM FALSE;
