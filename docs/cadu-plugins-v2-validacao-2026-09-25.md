# Validação dos plugins e Artefatos 2.0 — 25/09/2026

## Verificações executadas

| Escopo | Resultado | Leitura |
| --- | --- | --- |
| Roteamento, evidência e contratos de artefato (`test_cadu_agent_v2.py`, `test_cadu_plugin_evidence.py`, `test_cadu_plugin_artifact_contract.py`) | 290 passaram | Cobre tipos semânticos nomeados, fonte lida versus descoberta, Quick Scan, cálculos e os contratos principais do agente. |
| Fluxo de crédito/finalização de artefato (`test_cadu_mcp_credit_artifact_flow.py`) | 12 passaram na mesma rodada focada | Cobre finalização e idempotência por mocks; não substitui uma sessão real autenticada. |
| Suíte ampla `tests/test_cadu_*.py` | 988 passaram, 25 falharam | Falhas incluem templates, identidade, stream legado, skills e rotas de catálogo. Investigar em seus respectivos fluxos; esta rodada não alterou esses componentes. |
| Integração frontend `cadu-conversations-v2-integration.test.cjs` | 35 passaram, 13 falharam | Falhas em contratos de shell/CSS e componentes alterados em paralelo. Exigem reconciliação com a versão final dessas telas. |
| Build do frontend de conversas | Passou após o commit `8dbbac95` | Confirma compilação dos renderizadores atualizados; não comprova navegação autenticada. |

## Mudanças cobertas por esta rodada

- Pedido explícito de `media_plan`, `scenario`, `research`, `note` e `executive_summary` mantém o tipo semântico e a saída editável.
- Roteamento para HTML não converte cadastro de marca com URL em criação de página.
- Radar faz no máximo uma segunda busca pública quando a primeira não traz página lida pertinente.
- Fonte descoberta não entra na lista de citações como se tivesse sido lida; seção de fontes inclui `read_status`.
- Pesquisa editável sem página lida é interrompida antes de salvar um artefato factual.
- Pesquisa web preserva `source_ids` por seção somente quando correspondem a fontes lidas; IDs de citação são definidos pelo servidor.
- Market Intelligence longo salva `research`, com `source_markdown`; Quick Scan sem arquivo entrega no chat.

## Validação operacional ainda necessária

Executar A01–A12 do [guia de avaliação](cadu-plugins-v2-guia-avaliacao.md) num projeto de teste com credenciais e conectores autorizados. Registrar IDs de conversa, chamadas concluídas, URLs realmente lidas, versão do artefato, exportação `.md`, recuperação após recarregar e vínculo ao projeto. A suíte por mocks e o build não comprovam o ciclo completo em produção. A revisão React de referências inline, estado de leitura e tabelas responsivas foi concluída no commit `8dbbac95`; os 13 testes de integração frontend ainda falham no conjunto amplo de contratos da tela e precisam ser reconciliados com as mudanças paralelas.

## Revisão posterior

- Corrigido o Quick Scan para respeitar pedidos explícitos sem artefato e para priorizar a página lida quando busca e leitura retornam a mesma URL. Os 303 testes focados passaram.
- Corrigida a reconciliação da resposta no frontend: quando o evento final traz só uma frase curta, o texto completo já transmitido continua visível. Build de conversas passou.
- Após corrigir o último tópico do cartão de briefing, a suíte ampla ficou em 991 aprovados e 24 falhas. Várias falhas de stream pertencem à fachada legada que agora delega ao Workspace, mas ainda são necessárias verificações por fluxo antes de alterar esses contratos.
- A integração frontend ficou em 36 aprovados e 12 falhas. Parte das asserções exige CSS e nomes internos antigos, inclusive fonte de 15 px, em conflito com o ajuste de tipografia para telas menores. As demais devem ser avaliadas pelo comportamento antes de mudar o produto ou os testes.
