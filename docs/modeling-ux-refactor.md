# Refino UX da Mesa de Conceito

A Mesa continua no stack atual: Jinja, CSS da Modelagem e `mc-mesa.js`. Este documento descreve o sistema visual CentralX, os estados e o que ainda depende de backend.

## Arquitetura visual

Quatro regiões, nesta prioridade:

1. Canvas 16:9
2. Cenas / frames
3. Inspetor direito
4. Barra de controles
5. Navegação da Modelagem

O chrome é do CentralX. A cor da marca do cliente aparece só no key visual, no preview, nas amostras e nos assets.

## Fluxo

1. Selecionar marca
2. Selecionar campanha
3. Selecionar formato
4. Selecionar key visual
5. Montar conceito
6. Modelar base
7. Montar cena
8. Fechar still
9. Aprovar para a Bancada

O usuário sempre vê a etapa atual, o que falta e o próximo CTA.

## Estados do modal

Um único `#mcMesaBaseDialog` com `data-state`:

| Estado | Uso |
|---|---|
| `idle` | Conceito / base / cena em edição |
| `loading` | IA em andamento — etapas, sem porcentagem |
| `success` | Retorno pronto, próximo passo |
| `warning` | Precisa revisar antes de seguir |
| `error` | Falha acionável |

## Componentes (includes)

- `_modal_shell.html` — header, body, footer, ESC, focus
- `_modal_loading.html` — Análise / Conceito / Finalização
- `_modal_success.html` — check + aprovar
- `_modal_error.html` — três ações + detalhes técnicos
- `_modal_confirm.html` — só perda ou sobrescrita
- `_inspector_tabs.html` — Marca / Brief / Assets
- `_production_flow.html` — Conceito → Aprovar
- `_inline_message.html` — hint e erro de campo
- `_history_drawer.html` — versões da campanha

## Tokens

| Token | Valor | Uso |
|---|---|---|
| `--cx-mesa-white` | `#ffffff` | painéis |
| `--cx-mesa-gray-50` | `#f8fafc` | fundo da página |
| `--cx-mesa-gray-100` | `#f1f5f9` | trilho |
| `--cx-mesa-gray-200` | `#e2e8f0` | borda |
| `--cx-mesa-slate-700` | `#334155` | texto secundário |
| `--cx-mesa-slate-900` | `#0f172a` | texto e seleção |
| `--cx-mesa-teal` | `#0f766e` | ativo, foco |
| `--cx-mesa-success` | `#15803d` | check |
| `--cx-mesa-warning` | `#d97706` | aviso |
| `--cx-mesa-error` | `#dc2626` | erro |
| `--cx-mesa-info` | `#2563eb` | informação |
| `--cx-mesa-radius` | `8px` | controles |
| `--cx-mesa-motion` | `160ms` | modal, tab, toast |

## Regras de mensagem

- CTA no infinitivo do que acontece: Montar conceito, Modelar base.
- Toast só para confirmação rápida: Conceito salvo, Key visual atualizado.
- Erro crítico fica no modal, nunca no toast.
- Erro técnico só em “Ver detalhes técnicos”.
- Hint de campo aparece antes de gerar.

## Loading

Etapas reais. Sem % inventada. ESC não fecha. CTA conflitante desliga.

## Confirmação

Só para: substituir versão ativa, sobrescrever HTML, regenerar o que já foi aprovado, voltar com perda. Sem “Tem certeza?”.

## Histórico de versões

Na Mesa, v1/v2/v3 vêm das versões da sessão (`versionAttempt`). Restaurar troca o still ativo. Timestamps ricos e duplicar existem só na rota de estados até o backend gravar metadados.

## Rota de validação

`/lab/modelagem/states` — mocks dos estados, sem OpenRouter.

## Próximos passos (backend)

- Persistir metadados de versão (autor, hora, motivo)
- Cancelar job de IA
- Endpoint de “próxima etapa”
