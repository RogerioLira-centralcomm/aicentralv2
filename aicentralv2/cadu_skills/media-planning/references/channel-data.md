# Dados de canais

`channels.csv` é um snapshot exportado de `cadu_canais` pelo exportador da família Cadu. O script legado `scripts/export_channels.py` continua funcionando, mas agora sincroniza canais, audiências e formatos.

Cada linha representa um canal ativo. Campos JSON preservam segmentações, diferenciais e audiências relacionadas. Os formatos ficam normalizados em `formats.csv`. O agente deve filtrar por `slug`, `nome`, `categoria` e `tipo`, carregando campos extensos somente para os canais candidatos.

## Atualização

Execute `aicentralv2/cadu_skills/scripts/export_official_catalogs.py` dentro do ambiente da aplicação após mudanças no catálogo. Em produção, não publique se a conexão com o banco falhar ou se o processo usar um snapshot offline.

## Limites

- `alcance`, `viewability` e `investimento_minimo` são referências comerciais, não garantias.
- `audience_slugs` e `audience_names` são relações de catálogo, não garantia de match ou disponibilidade.
- Não exponha observações internas ou credenciais em links públicos.
