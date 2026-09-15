# [Video Studio] Composição e timeline multiclipes

## Objetivo

Transformar o storyboard atual em um editor determinístico com múltiplos clipes, edição por frame e histórico confiável.

![Mockup — timeline multiclipes](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/02-timeline-multiclipes.png)

## Cena representada no mockup

O playhead está em `00:08:12`, um clipe acabou de ser dividido e o usuário escolhe entre excluir mantendo a lacuna ou fechar o espaço. A timeline mostra vídeos, textos, legendas, voz e música, com snapping, trim handles, timecode e atalhos J/K/L.

## Estado atual

- A timeline representa um único vídeo pronto e uma faixa adicional de áudio.
- Existem trim, playhead, zoom, velocidade e undo/redo limitados ao clipe atual.
- O storyboard de cenas é entrada da geração por IA; não é uma composição exportável de vários clipes.

## Escopo funcional

- Schema de composição v2 com FPS explícito, canvas, ativos, tracks e items.
- Tempo interno em frames inteiros; `start_frame`, `duration_frames`, `source_in` e `source_out`.
- Faixa principal para imagens e vídeos, mais faixas sobrepostas.
- Inserir no playhead/fim, arrastar, reordenar, trim, split, duplicar e excluir.
- Excluir simples e ripple delete/Fechar espaço.
- Snapping em playhead, bordas, marcadores e início/fim.
- Régua, scrub, zoom no cursor, auto scroll e navegação J/K/L.
- Imagens recebem duração padrão editável.
- Preview sincronizado da composição com recuperação de drift.
- Comandos estruturados e undo/redo agrupado por gesto.
- Migração do documento atual para o schema v2.

## Backend

- Validador e migrador de schema versionado.
- Persistência por revisão monotônica e referências de ativo verificadas.
- Compilação segura da sequência para o renderizador.

## Frontend

- Timeline virtualizada e baseada no mesmo FPS do projeto.
- Seleção única/múltipla, handles, guias, menus contextuais e feedback de drop.
- Estado central da composição; nenhuma ação visual pode existir apenas no DOM.

## Critérios de aceite

- [ ] Montar três vídeos e duas imagens em qualquer ordem.
- [ ] Dividir o segundo vídeo no frame escolhido e remover uma pausa em até três ações.
- [ ] Reordenar e aparar clipes sem perder áudio vinculado.
- [ ] Undo/redo de 30 operações conserva IDs, seleção e tempos.
- [ ] Salvar e reabrir não desloca nenhum item em um frame.
- [ ] Preview e export têm a mesma ordem, duração e sincronismo audiovisual.
- [ ] Seek e reprodução recuperam sincronia com erro perceptível inferior a 80 ms.

## Dependências

- Ingestão de mídia e biblioteca.
- Render e exportação profissional.

