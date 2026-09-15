# [Video Studio] Agente criativo de edição

## Objetivo

Permitir que o usuário peça uma edição em linguagem natural e receba um plano estruturado, revisável, editável e reversível na própria timeline.

![Mockup — agente criativo](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/08-agente-criativo.png)

## Cena representada no mockup

O usuário pediu: “Faça um corte de 15 s, vertical, com legendas e música baixa.” O agente apresenta quatro operações selecionáveis, itens afetados, duração antes/depois, custo estimado e diff. Aplicar cria uma única ação no histórico e não exporta automaticamente.

## Estado atual

- O agente lateral reconhece o clipe aberto e planeja trim, velocidade, volume, fades, grayscale e flip.
- O usuário revisa e aplica; geração paga/export continuam separadas.
- O agente não monta clipes, captions ou áudio multifaixa porque esses objetos ainda não existem no schema.

## Escopo funcional

- Ferramentas fechadas para inserir ativo, montar rough cut, cortar silêncios, split, reordenar, criar captions, posicionar música, aplicar preset e reenquadrar.
- Contexto com canvas, duração, itens, transcrição, marca, canal e orçamento.
- Resposta como plano tipado, nunca como mutação livre de JSON/FFmpeg/DOM.
- Diff por item e seleção individual das operações propostas.
- Estimativa de custo antes de transcrição, geração, tradução ou TTS.
- Aplicação atômica como um grupo de undo/redo.
- Pedidos pagos, exportação, exclusão e publicação continuam como ações explícitas separadas.
- P2: sugestões de hook, ritmo, legibilidade, safe area e loudness apontando o trecho afetado.

## Backend

- Catálogo versionado de tools e schemas de entrada/saída.
- Validação de permissões, ativos, limites e revisão esperada.
- Planner determinístico com fallback seguro quando a solicitação não puder ser representada.
- Ledger idempotente e telemetria por operação.

## Frontend

- Chat lateral com atalhos, plano, diff, custo e itens afetados.
- Revisar no canvas/timeline antes de aplicar.
- Estado parcial quando somente algumas operações forem aceitas.

## Critérios de aceite

- [ ] Pedido de corte vertical com captions e música gera plano estruturado completo.
- [ ] Usuário pode desmarcar uma operação antes de aplicar.
- [ ] Aplicar altera a composição e cria uma única entrada no histórico.
- [ ] Desfazer restaura todos os itens afetados.
- [ ] Nenhum gasto, exportação, publicação ou exclusão ocorre automaticamente.
- [ ] Mudança concorrente de revisão produz conflito recuperável.
- [ ] O agente explica solicitações não suportadas e não inventa controles.

## Dependências

- Composição/timeline, captions, áudio e transformações precisam existir como ferramentas estruturadas.

