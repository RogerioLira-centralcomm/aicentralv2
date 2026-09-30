# Revisão das fases 1–6 do editor de fluxos

Base: commits `b7dfa56a`–`18c65b44` sobre `1bcd4b4e`. Conferidos o plano de refatoração, frontend React, rotas Flask, contrato JSON v2 e documentação atual da skill TypeSafe AI.

## Corrigido nesta revisão

- **P0 — Editor quebrava ao renderizar:** o efeito dos atalhos estava declarado dentro do efeito de autosave em `frontend/reports-v1/main.jsx`. Hooks precisam ser chamados no nível superior do componente. Os efeitos agora são irmãos.
- **P1 — Jornada atribuía passagens inexistentes:** `reports_flow.py` contava qualquer visita posterior ao nó de destino como travessia da aresta. Agora a métrica usa pares de etapas consecutivas da sessão; os caminhos sugeridos usam a mesma definição. A consulta retorna todos os pares para não zerar arestas menos frequentes.

## Pendências de aceite antes de integrar

| Prioridade | Fase | Evidência | Trabalho necessário |
| --- | --- | --- | --- |
| Alta | 1/3 | `main.jsx` mantém autosave em 900 ms, bloqueia a saída com `beforeunload` e apenas mostra erro para um 409. | Implementar o fluxo de conflito (recarregar ou sobrescrever com decisão explícita), salvar na navegação da aplicação e verificar recarga durante edição. |
| Alta | 3/4 | `FlowCanvas.jsx` não implementa deslocamento de nós com setas, retorno com Esc ou atalhos de inspeção. | Completar teclado e teste de interação com foco no canvas. |
| Alta | 4 | `flow-workspace.css` reserva colunas de 200 px e 264 px para paleta/inspetor e altura `100dvh - 280px`; os painéis continuam dentro do grid. | Validar a meta de ≥90% do viewport no editor em 1440×900 e 1280 px; converter painéis em superfícies sobre o canvas se necessário. |
| Alta | 5 | `flowValidation.js` e `reports_flow_validation.py` só cobrem conversão, mapeamento, órfão e ciclo sem condição; a duplicidade de URL não aparece no painel (o servidor barra apenas identidades medidas idênticas). | Alinhar validação cliente/servidor, incluir duplicidade e testar publicações com ramos. |
| Média | 2/3 | `_normalize_flow_config` limita a 100 nós, enquanto o checklist pede uma verificação com 200; `addNode` não bloqueia o limite antes do autosave. | Definir o limite suportado, ajustar servidor e UI juntos e medir pan/zoom com fluxo grande. |
| Média | 5/6 | A lista de versões permite restaurar, mas não oferece comparação visual; o simulador percorre o primeiro ramo automaticamente. | Comparação de versões e escolhas de ramo no modo automático. |
| Média | 6 | Templates são locais e cobrem branco, lead e compra; o plano também lista webinar e WhatsApp e endpoint de templates. | Completar templates e decidir se a API é necessária para distribuição/versionamento. |
| Média | 6 | Jornada não apresenta taxa de conversão fim a fim nem série temporal/origens no inspetor. | Usar métricas da publicação selecionada, separar evidência observada de inferência e acrescentar visões com testes de totais contra Eventos. |

## Aplicação da skill TypeSafe AI

As regras de grafo, revisões, contagens e permissão são determinísticas e devem permanecer no código. Uma decisão semântica de papel de página pode usar IA somente com evidência verificável, resposta estruturada e revisão humana antes de alterar o rascunho. Nenhuma chamada nova ao serviço TypeSafe é necessária para estas seis fases. Os resultados da Jornada são observações da Super Tag; sugestões de aresta precisam continuar identificadas como sugestões até o usuário adicioná-las.

## Verificação desta revisão

- `npm run build:reports`: passou; Vite ainda informa bundles grandes.
- `python3 -m unittest discover -s tests -p test_reports_flow_schema_v2.py` com o Python 3.12 do runtime: 3 testes passaram.
- `git diff --check`: passou.

Não houve revisão visual em sessão autenticada, teste de carga de 200 nós nem consulta à base de produção neste ambiente isolado. Os critérios de aceite correspondentes permanecem abertos.
