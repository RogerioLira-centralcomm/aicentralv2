# Cortes automáticos e tratamento de voz — 15/09/2026

## Implementado
- Importação com cortes ativados por padrão, modo moderado/agressivo, limite de 1–30 remoções e transição.
- Upload com progresso real. Tarefa persistente com etapas de validação, preparação e análise.
- FFmpeg identifica silêncio; tempos por palavra do faster-whisper protegem a fala. Repetições ambíguas são marcadas para revisão. Hesitações isoladas de alta confiança podem ser removidas.
- Original binário preservado como `.original`, cópia editável independente e montagem por intervalos do vídeo com áudio nativo vinculado.
- Restauração individual ou integral. A restauração reconstrói a montagem importada; revisar antes de editar manualmente. Histórico existente registra as alterações.
- Até 120 itens para acomodar 31 segmentos resultantes de 30 remoções e edições posteriores.
- Voz limpa, voz encorpada e redução de ruído, intensidade 0–1, por segmento ou faixa adicional. Processamento FFmpeg na prévia renderizada e exportação. Graves suaves sem alteração do pitch.
- Pequenos fades de áudio nas junções. Transições curtas em pausas; corte seco em hesitações.
- Finalização recorta o acúmulo de padding AAC/concat para respeitar a duração da timeline.
- Correção da conversão entre tempo da montagem renderizada e tempo de origem ao dividir vídeo.

## Validação
- Suíte existente mais novos testes: 75 testes passaram; após proteção adicional para ausência de fala, 16 testes direcionados passaram.
- Chrome/Playwright: fluxo de montagem, áudio multifaixa, legenda, exportação, presets, intensidade e restauração de cortes.
- Vídeo WhatsApp enviado: 288 palavras reconhecidas localmente com Whisper tiny para teste; moderado 3 remoções/3,963 s; agressivo 6 remoções/5,517 s.
- Render real moderado com voz encorpada: 720×1280, 30 fps, duração final ajustada à grade de quadros 104,666667 s. Artefato local `/tmp/cadu-real-edited-final.mp4`.

## Limites e operação
- Nenhuma chamada paga a Seedance, publicação ou instalação SSH realizada nesta etapa.
- Requer modelo de transcrição provisionado no worker. Se falhar, importação conclui com original e aviso explícito, sem cortes.
- A prévia instantânea não aplica limpeza de voz. Usar “Renderizar prévia da montagem” para ouvir o tratamento final.
- Separação neural de voz/fundo, substituição de trechos por Seedance e correção semântica por LLM não foram implementadas nesta etapa.
- A detecção não garante identificar toda falha de linguagem. Naturalidade das junções e qualidade perceptual da limpeza precisam de revisão por escuta.
- O arquivo testado foi exportado a 30 fps; preservação automática dos 60 fps nominais da fonte ainda é pendente.
