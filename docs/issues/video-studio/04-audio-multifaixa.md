# [Video Studio] Áudio multifaixa, locução e mixagem

## Objetivo

Editar o som original, locução, música e efeitos como itens independentes e obter uma mixagem consistente na prévia e exportação.

![Mockup — áudio multifaixa](https://raw.githubusercontent.com/RogerioLira-centralcomm/aicentralv2/main/docs/mockups/video-studio/04-audio-multifaixa.png)

## Cena representada no mockup

A timeline possui faixas separadas de áudio original, locução IA, música e efeitos. A música apresenta envelope reduzido durante a fala; o inspetor mostra loudness, ruído, ducking, fades e pan; a biblioteca permite enviar áudio, gravar locução ou gerar voz.

## Estado atual

- Há volume do áudio original e apenas uma faixa sonora adicional.
- A faixa adicional oferece offset, loop e fades.
- Há áudio nativo Seedance e locução no fluxo de geração, mas não como itens independentes da timeline.

## Escopo funcional

- Tracks e items separados para áudio original, locução, música e efeitos.
- Mover, trim, split, duplicar, mute, solo, lock, volume, pan e fades por item.
- Waveforms assíncronas reutilizáveis.
- Destacar áudio do vídeo e manter vínculo A/V até o usuário desvincular.
- Gravar microfone, enviar voz ou gerar TTS na posição do playhead.
- Regenerar um trecho da locução sem refazer o vídeo.
- Volume envelope/keyframes, medidor de pico e normalização/loudness alvo.
- Redução de ruído de fala e ducking configurável da música.
- Presets iniciais: Voz clara, Social e Ambiente.
- Biblioteca interna por Música, Efeitos e Voz; catálogo licenciado fica em fase posterior.

## Backend

- Contrato de faixa/item e filtergraph de mixagem controlado pelo servidor.
- Análise de waveform/loudness em job; TTS versionado e contabilizado.
- Tratamento explícito de velocidade, pitch, sample rate e canais.

## Frontend

- Waveforms virtuais, envelopes editáveis e controles de faixa.
- Estados de gravação e permissão de microfone.
- Prévia com o mesmo ganho, fades e ducking usados no render.

## Critérios de aceite

- [ ] Misturar áudio de dois vídeos, música, locução e três efeitos.
- [ ] Remover imagem mantendo sua fala e manter imagem substituindo seu som.
- [ ] Split preserva vínculo A/V até desvincular.
- [ ] Música reduz durante a fala com intensidade, ataque e retorno controláveis.
- [ ] Nenhuma faixa clipa no preset padrão.
- [ ] Regenerar uma frase não altera o restante da locução.
- [ ] Prévia e arquivo exportado contêm os mesmos trechos e níveis.

## Dependências

- Composição e timeline multiclipes.
- Render e exportação profissional.

