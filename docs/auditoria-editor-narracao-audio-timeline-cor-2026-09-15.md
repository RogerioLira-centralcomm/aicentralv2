# Auditoria do Studio: narração, áudio, cortes e cor

Data: 15/09/2026. Base: código local após commit 059e92d. Inspeção estática e reproduções locais; não houve acesso à sessão de produção, geração paga nem teste de vozes no provedor. Este documento é diagnóstico e plano de correção, não declaração de implementação das pendências.

## Conclusão

A estrutura do editor existe, mas não há um contrato único entre o áudio de geração, a edição de um clipe e a montagem. A prioridade é corrigir texto/voz e a conversão entre tempo do arquivo e tempo do projeto antes de expandir os controles. Adicionar apenas campos visuais repetiria problemas já existentes.

## Achados confirmados

### P0 — Voz ignorada no modo “Gerar pela peça”

- `templates/parametros/_mc_video.html:116` coloca Homem/Mulher apenas no painel de texto exato; `static/js/cadu-video/render.js:99` oculta esse painel no modo guiado.
- `creative_media/planner.py:101` só lê e valida `audio.voice` dentro do modo `voiceover`.
- Reprodução: `build_plan` com narração `guided`, alterando apenas `voice` entre `male` e `female`, produziu o mesmo prompt.
- Texto exato: o mapeamento existe (`male → Charon`, `female → Kore`) e é passado ao cliente de síntese. Isso confirma o encaminhamento, não a qualidade/percepção da voz final no provedor.
- Correção: seletor de voz comum aos modos com fala; identidade de voz, idioma e direção separados do texto; indicação clara dos modos que oferecem voz determinística. Preferir síntese separada para cumprir escolha explícita de voz.
- Aceite: voz selecionada persiste ao trocar de aba/reabrir projeto e aparece no payload final; teste audível com amostras reais dos dois perfis.

### P0 — Texto de locução não é limpo

- `creative_media/voiceover.py:25` apenas normaliza espaços e valida tamanho/palavras. Preserva HTML, Markdown, rótulos e instruções entre colchetes.
- Reprodução: `Narrador: **Conheça nossa oferta** [pausa] <b>Agora!</b>` saiu intacto.
- `creative_media/studio_agent.py:150` usa o nome do arquivo como informação de fallback. Uma cena chamada `criativo_final_v7.png` produziu essa string como fala.
- A requisição de sugestão em `static/js/mc-cadu-video.js:1017` não envia a escolha de voz nem o ritmo.
- Correção: preservar texto bruto para revisão, gerar texto falado limpo e manter direção de voz separada. Remover marcação/nomes de arquivo, sem apagar preço, datas, siglas ou negações. Sem conteúdo factual suficiente, pedir texto em vez de inventar uma fala.
- Aceite: nenhum nome de arquivo ou rótulo operacional é narrado; números e informação comercial permanecem corretos; prévia do texto realmente enviado ao sintetizador.

### P0 — Ritmo e duração não são controlados efetivamente

- `creative_media/voiceover.py:49` implementa “Rápida” adicionando `[excited]`; emoção e velocidade não são equivalentes.
- `services/openrouter_service.py:980` aceita um argumento `speed`, mas `creative_media/worker.py:498` não o passa. A capacidade efetiva de cada modelo precisa ser validada antes de expor limites na UI.
- O orçamento é estimado por palavras, mas a duração real do áudio sintetizado não é reconciliada com o vídeo.
- Reprodução FFmpeg: vídeo de 1 s + áudio de 3 s em `mix_voiceover` gerou vídeo de 1 s e áudio de 0,998 s. O uso de `-shortest` cortou o restante.
- Correção: medir o áudio antes de mixar; oferecer reescrita mais curta, extensão visual ou ajuste de velocidade com limites e preservação de pitch. Nunca cortar fala silenciosamente.
- Aceite: fala longa bloqueia a conclusão ou apresenta opção explícita de ajuste; exportação preserva todas as palavras aprovadas.

### P0 — Tempos de fonte e projeto se misturam na divisão

- `static/js/cadu-video/composition.js:52`: na prévia renderizada, usa `video.currentTime` diretamente como tempo do arquivo original. Esse tempo pertence à montagem inteira.
- Exemplo: um clipe começa no projeto em 10 s, usa o arquivo a partir de 2 s e está em 1×. O cursor em 12 s deve dividir a fonte em 4 s; a lógica atual tenta usar 12 s.
- Imagens são divididas ao meio, independentemente da posição do cursor.
- Faixas adicionais de áudio não têm vínculo explícito com o item de vídeo; mover, dividir ou excluir cenas não faz uma edição vinculada de áudio/legendas.
- Correção: funções únicas `sourceToProject`/`projectToSource`, com início, trim, velocidade e sobreposição de transição; operações de edição atômicas com undo, vínculo e opção ripple explícita.
- Aceite: dividir em qualquer clipe mantém o quadro do cursor e a sincronia, tanto na prévia instantânea quanto na renderizada.

### P1 — Editor de áudio é básico e tem termos ambíguos

- Há upload, compressão AAC, waveform na biblioteca, extração, mute, volume, fades e oito faixas adicionais.
- No editor de um clipe, “Começar áudio em (s)” é um deslocamento dentro do arquivo, não a posição de entrada na timeline. O campo é aplicado com `-ss` antes do input.
- Na montagem há `start`, `in` e `duration`, mas faltam alças na faixa, split/duplicate de áudio, solo, vínculo A/V e ganho por trecho.
- A compressão existente reduz tamanho por codec; não equivale a compressor dinâmico de voz.
- Existe ducking fixo na mistura da locução gerada; não é um controle geral do editor multifaixa.
- Correção: editor com waveform por item, régua, zoom, trim visual, posição independente, ajuste ao trecho selecionado, mute/solo, loop do intervalo selecionado e fades visuais. Segunda etapa: loudness, medidor de pico, compressor e ducking controláveis.
- Aceite: cortar uma locução, posicioná-la no segundo clipe, reduzir música durante a fala e exportar com a mesma duração/sincronia da prévia. Mostrar quando o som ultrapassa o fim do projeto.

### P1 — “Decupagem” atual são oito amostras fixas

- `creative_media/studio_media.py:45` extrai exatamente oito imagens em intervalos iguais. Em um vídeo de 5 minutos, o intervalo chega a 37,5 s.
- As miniaturas não representam necessariamente mudanças de cena; não há indexação de cortes nem comando para inserir um frame como imagem na montagem.
- Correção: duas camadas: filmstrip adaptativo ao zoom e lista de cenas detectadas com in/out, duração e thumbnail. Extração sob demanda em worker com cache por arquivo/tempo; seleção de frames para adicionar como stills.
- Aceite: importar um vídeo com cinco cenas conhecidas, navegar aos limites, corrigir cortes e inserir um frame na montagem sem reimportar o vídeo.

### P1 — Cortes automáticos ainda não existem

- Há split manual; não foi encontrado detector de mudanças de cena ou ferramenta de remover silêncios no editor.
- O VAD da transcrição filtra fala para reconhecimento; não cria cortes de vídeo.
- Correção: comandos separados para detectar cenas, remover silêncios e dividir por duração. Sensibilidade, duração mínima e margens antes/depois da fala devem ser explícitas. Primeiro mostrar proposta; só depois aplicar em um grupo de undo, preservando fontes e vínculos.
- Aceite: proposta de cortes revisável, silêncio removido sem cortar sílabas, undo restaura integralmente a montagem.

### P1 — Ajuste de cor não está implementado no contrato de edição

- O editor de clipe tem preto e branco, espelhamento e fades; a montagem não tem controles graduais de cor.
- Reprodução: inserir `brightness`, `contrast` e `saturation` em um item e chamar `normalize_composition` descartou os três campos.
- Correção: schema por item para exposição/brilho, contraste, saturação, temperatura e matiz; depois sombras/realces. Aplicar ao clipe selecionado ou copiar para outros itens, com reset por controle e geral. Correção determinística após a geração, sem depender de prompt de IA.
- Preview/export: definir ordem dos filtros e tratamento de cor SDR/Rec.709; não prometer equivalência entre `CSS filter` e FFmpeg sem medir quadros de referência. Tratamento HDR exige política de conversão própria.
- Aceite: parâmetros persistem no projeto, chegam ao renderizador e alteram quadros conhecidos conforme testes; comparação antes/depois no mesmo tempo; reset reproduz o original.

## Ordem de execução

1. **Contrato temporal e testes de divisão** — base para áudio, decupagem e cortes automáticos.
2. **Texto limpo e voz explícita** — separar fala, direção, idioma e identidade de voz, com prévia de áudio.
3. **Duração real da locução** — medir, ajustar ou bloquear; impedir truncamento silencioso.
4. **Áudio visual vinculado ao vídeo** — waveform por item, alças, split, posição, solo/mute, fades e ajuste ao corte.
5. **Cor por clipe** — persistência + render determinístico + comparação antes/depois; pode avançar independentemente após definir o contrato de edição.
6. **Decupagem e cortes automáticos** — indexação assíncrona, proposta revisável e aplicação com undo.
7. **Validação de jornada** — vídeos reais com fala/música, formatos vertical/horizontal, reabertura e exportação.

## Contratos mínimos propostos

- Narração: `spoken_text`, `voice_direction`, `voice_id`, `language`, `rate`, `fit_policy`, `target_duration`.
- Item temporal: `source_id`, `source_in`, `source_out`, `timeline_start`, `speed`, `linked_group_id`.
- Áudio: intervalo da fonte, posição, ganho, envelope/fades, mute/solo, loop do trecho e política de encaixe.
- Cor: parâmetros numéricos limitados, espaço de cor definido e ordem estável de filtros.
- Análise automática: job persistido, revisão da proposta, sensibilidade/limites e aplicação reversível.

Esses contratos devem ser versionados e migrados; os projetos salvos não podem perder edições anteriores.

## Evidência e limites da validação

Executados localmente: comparação de planos masculino/feminino nos dois modos, normalização de texto com marcação, fallback com nome de arquivo, rejeição de campos de cor pelo schema e render FFmpeg com locução maior que o vídeo. Os resultados estão descritos em cada achado.

Não executados: síntese paga de voz, verificação auditiva de Charon/Kore no provedor, reprodução da conta do usuário em produção, avaliação de todas as funções do backlog Core 80. Os testes existentes de exportação não cobrem, por si só, essas lacunas de produto.
