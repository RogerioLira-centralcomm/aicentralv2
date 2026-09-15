# Dados de canais

`channels.csv` é um snapshot exportado de `cadu_canais` por `scripts/export_channels.py`.

Cada linha representa um canal ativo. Campos JSON preservam listas estruturadas de formatos, segmentações e diferenciais. O agente deve filtrar por `slug`, `nome`, `categoria` e `tipo`, carregando os campos extensos somente para os canais candidatos.

## Atualização

Execute o exportador dentro do ambiente da aplicação após mudanças no catálogo. A exportação usa `listar_canais()`, portanto mantém o mesmo fallback da interface quando o banco não está disponível. Em produção, valide que o log não indicou fallback antes de publicar a nova versão.

## Limites

- `alcance`, `viewability` e `investimento_minimo` são referências comerciais, não garantias.
- `formatos` descreve possibilidades técnicas; disponibilidade e preço precisam de confirmação.
- Não exponha observações internas ou credenciais em links públicos.
