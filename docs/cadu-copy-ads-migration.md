# Copy Ads → Studio: etapa de editor e contrato de formatos

Implementado em Python em 15/09/2026, sob a flag existente `CADU_FAMILY_ENABLED`.

## Entregue no código

- Tela `/familia/studio/copy-ads`, integrada à navegação e contexto da família, sem agente central.
- Catálogo autenticado `/familia/api/studio/copy-ads/formats`: consulta somente leitura dos formatos e plataformas ativos.
- Validação `/familia/api/studio/copy-ads/validate`: autenticação, contexto autorizado e CSRF. Limites são obtidos no servidor, não aceitos do navegador.
- Regras de campos recriadas a partir de `api/copy-ads/formatos.php`, incluindo prioridades de `dados_extras.campos_copy`, dimensões e recomendações.
- Editor com contagem Unicode, prévia textual, rascunhos em memória por formato, aviso ao sair e download local de texto.
- Sem gravação de dados, envio de email, publicação de anúncios ou chamada a modelos nesta etapa.

## Evidências

- Comparação local com as funções puras do PHP: 1.120 combinações produziram os mesmos campos, rótulos, limites e recomendações.
- Testes unitários de formatos, validação e rotas em `tests/test_cadu_copy_ads.py`.
- Verificação de sintaxe JavaScript com `node --check`.
- Ainda falta validação visual no navegador em desktop/tablet/mobile e consulta do catálogo real pela nova API.

Os limites preservam o contrato legado; não foram apresentados como regras atuais verificadas das plataformas.

## Ainda não migrado

1. Extração de briefing com IA, revisão dos dados extraídos e geração de variações A/B/C.
2. Metodologias e prompts completos do gerador.
3. Cotas, registro de consumo e persistência/histórico: implementação futura precisa preservar o isolamento por cliente e respeitar a autorização para alterações no banco.
4. Extração de URL, geração de imagens e exportações avançadas.
5. Testes ponta a ponta, ativação de produção e retirada das rotas PHP.

A tela identifica essas limitações. Não considerar o módulo totalmente migrado nesta etapa.
