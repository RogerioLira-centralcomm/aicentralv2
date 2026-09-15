# [Video Studio] Efeitos, transições e animações

## Objetivo

Entregar o acabamento visual mais usado em conteúdo social: enquadramento, cor, transições e movimento por keyframes.

![Mockup — efeitos e animações](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/05-efeitos-animacoes.png)

## Cena representada no mockup

Um vídeo vertical está sendo reenquadrado em 16:9 com fundo desfocado. Dois clipes têm transição Dissolver selecionada e duração ajustável. O inspetor mostra transformação/cor, enquanto a faixa inferior expõe keyframes e curvas de posição, escala e opacidade.

## Estado atual

- Existem preto e branco, espelhamento, fades e velocidade constante.
- Não há crop, posição, escala, rotação, cor completa, transições entre clipes ou keyframes.

## Escopo funcional

- Fit, fill, crop, fundo por cor/blur/mídia, posição, escala, rotação e opacidade.
- Controles no canvas, campos numéricos e reset individual/global.
- Brilho/exposição, contraste, saturação, temperatura e tint.
- Transições essenciais: corte, cross dissolve, dip to black/white, slide e wipe.
- Duração limitada pelos handles disponíveis, sem alterar o projeto de forma inesperada.
- Keyframes de posição, escala, rotação e opacidade.
- Interpolações linear, ease in, ease out, ease in-out e hold.
- Navegar, copiar/colar e remover keyframes.
- Reverse e freeze frame; speed ramp/optical flow ficam após Core 80.

## Backend

- Contratos tipados; nenhuma expressão de filtro fornecida pelo cliente.
- Render de transformações, cor, transições e interpolação determinística.
- Tratamento de áudio em mudanças de velocidade.

## Frontend

- Handles no canvas, safe area, guias e inspetor contextual.
- Galeria compacta de transições com preview.
- Faixa de keyframes e editor simples de easing.

## Critérios de aceite

- [ ] Vídeo 16:9 em projeto 9:16 pode preencher, caber ou ser reenquadrado sem deformação.
- [ ] Transição pode ser aplicada/ajustada sem criar frames pretos ou drift.
- [ ] Zoom progressivo em imagem e movimento de texto coincidem no export.
- [ ] Reset restaura valores e cada gesto pode ser desfeito.
- [ ] Reverse/freeze mantêm duração e áudio conforme a opção escolhida.
- [ ] Golden frames ficam dentro da tolerância visual definida.

## Dependências

- Composição e timeline multiclipes.
- Renderizador completo.

