# [Video Studio] Textos e legendas automáticas

## Objetivo

Gerar, corrigir, sincronizar, estilizar e exportar captions e textos sem sair do editor.

![Mockup — textos e legendas](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/03-textos-legendas.png)

## Cena representada no mockup

Uma legenda está selecionada no vídeo vertical, com safe areas e handles. A lista lateral permite corrigir segmentos e timestamps; o inspetor aplica estilo global ou somente à legenda atual; a timeline mostra palavras alinhadas à waveform.

## Estado atual

- O roteiro orienta a geração, mas não existe como texto editável sobre o vídeo.
- Não há transcrição, faixa de legendas, timing, presets ou SRT/VTT.

## Escopo funcional

- Camada de texto com início/duração, fonte, peso, tamanho, cor, fundo, stroke, sombra, alinhamento, posição, escala e rotação.
- Edição direta no canvas, guias de alinhamento e safe areas por formato.
- Job de transcrição com idioma selecionado ou detectado.
- Persistir segmentos e palavras com timestamps, confiança, idioma e versão do modelo.
- Lista ligada ao playhead: editar, buscar/substituir, dividir, unir e excluir.
- Ajustar início/fim na lista e timeline, impedindo sobreposições inválidas.
- Indicadores de caracteres por segundo, linhas longas e tempo de leitura.
- Presets de marca; aplicar a todas ou somente à selecionada.
- Importar/exportar SRT e VTT; captions queimadas opcionais no MP4.
- P1: destaque palavra a palavra e animações simples.

## Backend

- Extração de áudio padronizada e integração com provedor de transcrição configurável.
- Versionar resultado e custo; falha não apaga captions existentes.
- Render de fonte e métricas compatível com o navegador.

## Frontend

- Painel de geração/progresso/custo, editor em lista e faixa de captions.
- Edição em lote e exceções locais de estilo.
- Canvas com seleção, handles, safe area e preview de animação.

## Critérios de aceite

- [ ] Gerar captions em português brasileiro a partir do áudio escolhido.
- [ ] Corrigir nome de marca em todas as ocorrências sem regenerar.
- [ ] Dividir/unir frases e ajustar o tempo até o frame.
- [ ] Estilo global preserva exceções locais quando solicitado.
- [ ] Texto e quebras aparecem iguais na prévia e no MP4.
- [ ] Round trip SRT/VTT mantém conteúdo e tempo dentro de um frame.
- [ ] Nova transcrição cria revisão e mostra custo antes da operação paga.

## Dependências

- Schema de composição e fila durável.
- Renderizador de composição para queima de texto.

