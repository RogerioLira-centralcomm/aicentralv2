# Validação dos plugins e Artefatos 2.0 — 25/09/2026

## Verificações executadas

| Escopo | Resultado | Leitura |
| --- | --- | --- |
| Roteamento, evidência e contratos de artefato (`test_cadu_agent_v2.py`, `test_cadu_plugin_evidence.py`, `test_cadu_plugin_artifact_contract.py`) | 289 passaram | Cobre tipos semânticos nomeados, fonte lida versus descoberta, Quick Scan, cálculos e os contratos principais do agente. |
| Fluxo de crédito/finalização de artefato (`test_cadu_mcp_credit_artifact_flow.py`) | 12 passaram na rodada focada anterior | Cobre finalização e idempotência por mocks; não substitui uma sessão real autenticada. |
| Suíte ampla `tests/test_cadu_*.py` | 988 passaram, 25 falharam | Falhas incluem templates, identidade, stream legado, skills e rotas de catálogo. Investigar em seus respectivos fluxos; esta rodada não alterou esses componentes. |
| Integração frontend `cadu-conversations-v2-integration.test.cjs` | 35 passaram, 13 falharam | Falhas em contratos de shell/CSS e componentes alterados em paralelo. Exigem reconciliação com a versão final dessas telas. |

## Mudanças cobertas por esta rodada

- Pedido explícito de `media_plan`, `scenario`, `research`, `note` e `executive_summary` mantém o tipo semântico e a saída editável.
- Roteamento para HTML não converte cadastro de marca com URL em criação de página.
- Radar faz no máximo uma segunda busca pública quando a primeira não traz página lida pertinente.
- Fonte descoberta não entra na lista de citações como se tivesse sido lida; seção de fontes inclui `read_status`.
- Pesquisa editável sem página lida é interrompida antes de salvar um artefato factual.
- Pesquisa web preserva `source_ids` por seção somente quando correspondem a fontes lidas; IDs de citação são definidos pelo servidor.
- Market Intelligence longo salva `research`, com `source_markdown`; Quick Scan sem arquivo entrega no chat.

## Validação operacional ainda necessária

Executar A01–A12 do [guia de avaliação](cadu-plugins-v2-guia-avaliacao.md) num projeto de teste com credenciais e conectores autorizados. Registrar IDs de conversa, chamadas concluídas, URLs realmente lidas, versão do artefato, exportação `.md`, recuperação após recarregar e vínculo ao projeto. A suíte por mocks e o build não comprovam o ciclo completo em produção. Também comparar os renderizadores após o commit da revisão React de referências inline e tabelas.
