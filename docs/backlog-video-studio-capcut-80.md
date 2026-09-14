# Backlog para o Cadu Video Studio atingir 80% do fluxo essencial de CapCut, Edits e Captions

Atualizado em 14/09/2026. Tela analisada: `/parametros/modelagem-criativos/video`.

## Resposta direta

### Se entrar uma imagem

Sim. O Studio já aceita uma imagem, ajusta a proporção de entrada ao formato escolhido e pode gerar um vídeo de 4 a 30 segundos pelo modo Seedance de imagem para vídeo. A geração pode usar áudio nativo, ambiente, música e narração, conforme a configuração disponível. Com uma única imagem, o usuário também pode criar uma segunda cena pelo Trocr antes de gerar.

A imagem ainda não funciona como um clipe determinístico completo dentro de uma montagem tradicional. Faltam duração própria na timeline, movimento Ken Burns, transformações por quadro e composição com outros vídeos no exportador.

### Se entrar um vídeo enviado pelo usuário

Ainda não. A interface aceita somente `image/*`, o JavaScript rejeita qualquer arquivo que não seja imagem e o backend não expõe uma rota de ingestão de vídeo. Hoje o editor consegue abrir um **vídeo gerado pela própria plataforma** e aplicar uma edição limitada a um único clipe: corte de entrada e saída, velocidade entre 0,25× e 4×, volume do som original, uma faixa sonora adicional, fades, preto e branco e espelhamento.

Portanto, adicionar `accept="video/*"` não resolve o caso. É necessário implementar ingestão segura, análise com FFprobe, armazenamento, poster, proxy de prévia, estados de processamento e um modelo de composição multiclipes.

## Objetivo da meta de 80%

“80% dos principais usos” significa cobrir pelo menos 80 pontos de uma régua de 100 pontos formada pelos fluxos essenciais usados por um criativo de social e publicidade. Não significa reproduzir 80% de todos os templates, efeitos de tendência, recursos móveis, comunidade ou catálogos de CapCut, Edits e Captions.

O benchmark considera o fluxo oficial atual do CapCut Web/Desktop: importar mídia; cortar, dividir e reordenar clipes; transformar e animar camadas; adicionar música, voz e efeitos; gerar e editar legendas; e exportar com controle de formato, resolução e frame rate. As páginas oficiais descrevem, entre outros recursos:

- upload e timeline com trim, crop, split, reverse, mirror, áudio, texto, efeitos, transições, filtros, resize e auto captions ([CapCut Online Video Editor](https://www.capcut.com/tools/online-video-editor));
- split manual ou por cena, rearranjo dos segmentos e exportação com resolução, formato e qualidade ([CapCut Split Video](https://www.capcut.com/resource/split-video-into-parts));
- keyframes de posição, escala, rotação, opacidade, efeitos e áudio em timeline multicamada ([CapCut Keyframes](https://www.capcut.com/resource/how-to-add-keyframes-in-capcut));
- captions automáticas sincronizadas, edição em lote, tradução, fonte, posição, cor, animação e exportação incorporada ([CapCut Add Subtitles](https://www.capcut.com/tools/add-subtitles-to-video));
- sincronização e edição de texto, tempo, posição, tamanho, fonte, efeitos e animações de legendas ([CapCut Subtitle Editor](https://www.capcut.com/tools/subtitle-edit-online));
- separação do áudio do vídeo e controle independente ([CapCut Extract Audio](https://www.capcut.com/resource/extract-audio-from-video));
- redução de ruído, volume, fades e tratamento de voz ([CapCut Clean Up Audio](https://www.capcut.com/resource/clean-up-audio));
- união de vários vídeos, transições, múltiplas faixas de áudio e exportação em MP4/MOV ([CapCut Merge Videos](https://www.capcut.com/resource/merge-two-videos)).

### O que Edits e Captions mudam na prioridade

| Produto | Força observada nas fontes oficiais | Implicação para o Cadu Studio |
|---|---|---|
| CapCut | Editor horizontal amplo: montagem, transformação, efeitos, áudio, captions e exportação detalhada | Define a base técnica da timeline e do renderizador |
| Edits | Timeline com precisão de frame, edição por clipe, auto enhance, green screen, transições, estilos de texto/caption, storyboards, title cards, templates e publicação social | Reforça rapidez mobile/social, presets de formato, títulos e um fluxo simples de rough cut |
| Captions | AI Edit aplica captions, trim, transições, música, efeitos sonoros, B-roll, imagens geradas e motion graphics; o resultado continua editável por item | Reforça que o agente deve produzir uma composição estruturada e editável, em vez de entregar somente um vídeo achatado |

A Meta descreve no Edits uma timeline precisa por frame, edição no nível do clipe, auto enhance, green screen e transições. Atualizações posteriores adicionaram storyboards, title cards, templates e estilos de texto/caption com fontes, cores, animações e efeitos ([Meta: Introducing Edits](https://about.fb.com/news/2025/04/introducing-edits-streamlined-video-creation-app/)). A Meta também documenta edição em lote de captions, reverse, lip sync de fotos e uma biblioteca maior de efeitos sonoros ([Meta: Instagram and Edits updates](https://about.fb.com/news/2025/11/instagram-empowers-creators-to-go-global-with-local-voice-translations-and-fonts/)).

No Captions, o AI Edit recebe um clipe e devolve captions, trim, transições, efeitos sonoros, música, imagens geradas, B-roll e motion graphics; textos, imagens, música, cor e estilo das tomadas continuam ajustáveis na timeline ([Captions Help: AI Edit](https://help.captions.ai/docs/project/ai-edit)). A página atual do produto também oferece estilos e pedidos em linguagem natural para alterar a edição ([Captions: Edit with AI](https://captions.ai/features/edit-with-ai)).

Essas referências mantêm montagem e captions como P0 e elevam o agente de edição estruturada a P1. Green screen, lip sync, templates sociais e insights de distribuição continuam depois do Core 80 porque não impedem o fluxo diário de importar, cortar, legendar, sonorizar e exportar.

## Diagnóstico da implementação atual

### Matriz de entrada, edição e saída

| Fluxo | Estado | O que funciona | Limite atual |
|---|---:|---|---|
| Upload de imagem | Pronto | Uma imagem entra na biblioteca e pode iniciar geração | Sem upload múltiplo; ainda não é um item pleno da composição |
| Imagem para vídeo | Pronto | Seedance 2.5, 4–30 s, 720p, proporção de origem ou saída escolhida, áudio opcional | A validação real paga no provedor ainda é uma etapa operacional |
| Storyboard de 2+ imagens | Parcial | Cenas alimentam a geração; cena 2 pode nascer no Trocr | Storyboard não equivale a uma timeline determinística |
| Upload de vídeo do usuário | Ausente | — | Input aceita apenas imagem e não existe ingestão backend |
| Vídeo gerado no Studio | Parcial | Pode ser aberto e editado | Apenas um clipe por exportação |
| Upload de áudio | Pronto | MP3, WAV, M4A e OGG; waveform e armazenamento por marca | Uma faixa adicional no projeto |
| Áudio nativo do vídeo | Parcial | Volume e mudança de velocidade são preservados no export | Não pode ser destacado, cortado ou movido independentemente |
| Texto sobreposto | Ausente | O roteiro orienta a geração | Não há camada de texto renderizável |
| Legendas | Ausente | — | Sem transcrição, timing, estilo, SRT ou VTT |
| Exportação | Parcial | MP4 assíncrono de um clipe, corte, velocidade, mixagem e efeitos atuais | Sem composição, presets, 1080p, frame rate ou histórico completo |
| Projetos | Parcial | ID, revisões imutáveis e controle de conflito em SQLite | Documento ainda representa o editor de um clipe; fila não é durável/distribuída |
| Agente lateral | Parcial | Planeja e aplica os ajustes suportados no clipe atual | Não manipula itens, faixas, captions ou composição porque esses objetos não existem |
| Custos do workspace | Pronto para o escopo atual | Operações confirmadas e em processamento; export local custa zero de IA | Deve ganhar custo por ativo/job quando novos serviços forem integrados |

### Evidência no repositório

- `aicentralv2/templates/parametros/_mc_video.html`: `mcVideoFile` usa `accept="image/*"`.
- `aicentralv2/static/js/mc-cadu-video.js`: `takeFile()` retorna sem ação quando o MIME não começa com `image/`; as consultas `media=still` e `media=video` separam imagens e vídeos gerados.
- `aicentralv2/creative_media/studio.py`: `render_clip()` recebe uma fonte de vídeo, um objeto de edição e no máximo uma fonte sonora adicional.
- `aicentralv2/creative_media/studio_projects.py`: projetos e revisões já possuem base persistente, mas o documento salvo ainda não contém uma composição multifaixa.
- `tests/test_video_studio.py` e `tests/test_video_studio_agent.py`: cobrem corte, velocidade, áudio, fades, grayscale, flip, escopo por marca, persistência, custos e comandos do agente no escopo atual.

## Régua de paridade

| Área | Peso | Cobertura atual | Pontos atuais | Meta Core 80 |
|---|---:|---:|---:|---:|
| Ingestão, biblioteca e proxies | 10 | 30% | 3 | 9 |
| Timeline e montagem | 20 | 20% | 4 | 18 |
| Transformação, cor, efeitos e movimento | 13 | 23% | 3 | 10 |
| Texto e captions | 17 | 0% | 0 | 15 |
| Áudio e voz | 13 | 38% | 5 | 10 |
| Exportação e formatos | 10 | 40% | 4 | 8 |
| Projetos, desempenho e confiabilidade | 9 | 67% | 6 | 8 |
| Assistência por IA | 8 | 75% | 6 | 7 |
| **Total** | **100** |  | **31/100** | **85/100** |

O Studio está em aproximadamente **31% da cobertura prática** definida neste documento. Os recursos de geração por IA estão mais maduros que os recursos clássicos de edição. Para cruzar 80%, o caminho crítico é vídeo enviado → montagem multiclipes → captions → áudio multifaixa → exportação fiel.

## Princípios de produto

1. **O criativo começa pela mídia.** Imagem, vídeo e áudio devem entrar pela mesma biblioteca com drag and drop e feedback imediato.
2. **A timeline é a fonte de verdade.** Storyboard de geração e composição de edição são conceitos diferentes, embora uma geração possa virar um clipe da composição.
3. **Prévia e exportação precisam coincidir.** Um controle só deve ser liberado quando a renderização final reproduzir seu resultado.
4. **O básico precisa ser muito rápido.** Importar, dividir, apagar um trecho, legendar e exportar devem exigir poucos passos e ter atalhos.
5. **A IA prepara uma primeira versão editável.** O agente deve criar cortes, captions, música e enquadramento como operações estruturadas que o usuário pode revisar, desfazer e alterar.
6. **Formato é propriedade do projeto.** Cada ativo conserva sua orientação; `fit`, `fill` e auto reframe decidem como ele ocupa 16:9, 9:16, 1:1, 4:5 ou a proporção original.
7. **Custos aparecem antes da operação paga.** Transcrição, geração, tradução e voz mostram estimativa; edição e FFmpeg local continuam separados do consumo de IA.

## Backlog detalhado

As estimativas são tamanhos relativos: S (até 2 dias de engenharia), M (3–5 dias), L (1–2 semanas), XL (precisa ser fatiado). Dependências indicam a ordem técnica, não alocação de pessoas.

### Épico A — Ingestão de vídeo e biblioteca

#### VS-ING-001 — Contrato de ativo de mídia — P0 — M

**História:** como criativo, quero que imagens, vídeos e áudios tenham identidade e metadados persistentes para reutilizá-los em projetos.

- Backend: criar `media_assets` com `id`, `client_id`, `owner_id`, `kind`, `status`, `original_name`, `mime`, `bytes`, `width`, `height`, `duration_ms`, `fps_num/fps_den`, `has_audio`, `storage_key`, `poster_key`, `proxy_key`, `checksum`, datas e erro.
- Backend: aplicar isolamento por marca e IDs opacos em todas as leituras.
- Aceite: o mesmo arquivo pode ser referenciado por vários projetos sem duplicar o binário; ativos de outra marca retornam 404/403; exclusão em uso é bloqueada ou recuperável.

#### VS-ING-002 — Upload de vídeo validado — P0 — L

**História:** como criativo, quero enviar MP4, MOV e WebM para editar material existente.

- Frontend: aceitar imagem e vídeo, drag and drop, seleção múltipla, progresso individual, cancelar e tentar novamente.
- Backend: receber streaming; impor limites configuráveis; validar conteúdo real com FFprobe; rejeitar arquivo vazio, corrompido, sem vídeo ou com duração acima do limite.
- Segurança: não confiar em extensão/MIME do navegador; remover metadados no proxy; nunca aceitar caminho ou URL arbitrária no renderizador.
- Aceite: H.264/MP4, HEVC/MOV e VP9/WebM válidos entram; arquivo renomeado/corrompido falha com mensagem clara; upload interrompido não cria ativo pronto.
- Dependência: VS-ING-001.

#### VS-ING-003 — Poster e proxy de edição — P0 — L

**História:** como criativo, quero ver e percorrer vídeos rapidamente sem baixar o original pesado.

- Backend/job: gerar poster JPEG/WebP, proxy H.264 720p com keyframes regulares e áudio AAC; preservar original para export.
- Frontend: estados `enviando`, `processando`, `pronto`, `falhou`; trocar poster por proxy quando pronto.
- Aceite: um vídeo 4K aparece na biblioteca antes do fim do proxy; o editor usa o proxy; o export usa o original; rotação de metadados é respeitada.
- Dependência: VS-ING-002, VS-JOB-001.

#### VS-ING-004 — Biblioteca produtiva — P1 — M

- Busca, paginação, filtro por imagem/vídeo/áudio, ordenação, duração, proporção e status.
- Adicionar à timeline por clique, duplo clique e arrastar.
- Seleção múltipla e remoção recuperável.
- Aceite: biblioteca com 500 ativos não carrega todos os binários nem trava o painel.
- Dependência: VS-ING-001.

### Épico B — Documento de composição

#### VS-CMP-001 — Schema de composição v2 — P0 — L

**História:** como editor, quero que cada elemento exista como item temporal para salvar, reabrir e exportar o mesmo projeto.

Estrutura mínima proposta:

```json
{
  "schema_version": 2,
  "project": {"fps": 30, "duration_frames": 900},
  "canvas": {"width": 1080, "height": 1920, "background": "#000000"},
  "assets": [{"id": "asset_1", "kind": "video"}],
  "tracks": [
    {
      "id": "video_main",
      "kind": "video",
      "items": [
        {
          "id": "clip_1",
          "asset_id": "asset_1",
          "start_frame": 0,
          "duration_frames": 180,
          "source_in_frame": 30,
          "source_out_frame": 210,
          "transform": {"fit": "cover", "x": 0, "y": 0, "scale": 1, "rotation": 0, "opacity": 1},
          "speed": 1
        }
      ]
    }
  ]
}
```

- Definir tempo internamente em frames inteiros; converter para segundos somente na API/visualização.
- Versionar migração do documento atual de um clipe para v2.
- Validar limites, referências e sobreposições no backend.
- Aceite: salvar/reabrir não muda um frame; revisões antigas continuam legíveis; payload inválido não chega ao renderizador.

#### VS-CMP-002 — Comandos e histórico — P0 — M

- Cada ação vira comando: adicionar, mover, trim, split, delete, ripple delete, duplicate, reorder, change property.
- Undo/redo agrupa gesto contínuo em uma única ação.
- Atalhos: espaço, `J/K/L`, `Ctrl/Cmd+Z`, `Shift+Ctrl/Cmd+Z`, `S`, delete, setas e zoom.
- Aceite: desfazer e refazer uma sequência de 30 operações conserva IDs e seleção.
- Dependência: VS-CMP-001.

### Épico C — Timeline essencial

#### VS-TML-001 — Faixa principal com múltiplos clipes — P0 — L

- Inserir imagem ou vídeo no playhead/fim; reordenar; mostrar thumbnail, nome e duração.
- Imagem recebe duração padrão editável; vídeo usa duração da fonte.
- Fechar espaços na faixa principal por padrão, com modificador para manter lacuna.
- Aceite: montar três vídeos e duas imagens em qualquer ordem e reproduzir sem trocar de tela.
- Dependência: VS-CMP-001, VS-ING-003.

#### VS-TML-002 — Playhead, régua, zoom e snapping — P0 — M

- Régua baseada em FPS; scrub; zoom no cursor; auto scroll durante reprodução.
- Snap em playhead, bordas, marcadores e início/fim do projeto; tecla para desativar durante o gesto.
- Aceite: posicionar corte no frame desejado e navegar projeto de 5 minutos em notebook.

#### VS-TML-003 — Trim visual — P0 — M

- Alças esquerda/direita com ghost frame; limites da fonte; tooltip de timecode.
- Slip fica para P2; P0 altera `source_in/out` e duração.
- Aceite: trim não altera indevidamente a posição dos itens seguintes; opção ripple atualiza sequência.
- Dependência: VS-TML-001.

#### VS-TML-004 — Split, excluir, ripple e duplicar — P0 — M

- Split no playhead preserva origem, efeitos e sincronia de áudio vinculado.
- Excluir simples mantém lacuna; ripple delete fecha a lacuna; duplicar cria novo ID.
- Aceite: remover uma pausa no meio de um vídeo em no máximo três ações.
- Dependência: VS-TML-003, VS-CMP-002.

#### VS-TML-005 — Preview da composição — P0 — XL, fatiar por tipo

- Compor no navegador itens visíveis, fit/fill, opacidade e camadas; sincronizar vídeo/áudio com o relógio da timeline.
- Suspender mídia fora da janela ativa; recuperar drift ao buscar/reproduzir.
- Criar testes de quadros de referência para preview e export.
- Aceite: erro de sincronia audiovisual perceptível inferior a 80 ms após seek e reprodução contínua; composição visual coincide com quadros exportados.
- Dependência: VS-CMP-001, VS-TML-001.

### Épico D — Textos e captions

#### VS-TXT-001 — Camada de texto — P0 — L

- Adicionar texto com início/duração, fonte aprovada, tamanho, peso, alinhamento, cor, fundo, stroke, sombra, posição, escala e rotação.
- Editar no canvas e no inspetor; guias de centro e safe area.
- Backend: empacotar/registrar fontes e renderizar com a mesma métrica usada na prévia.
- Aceite: título inserido no navegador mantém quebras, posição e aparência no MP4.
- Dependência: VS-CMP-001, VS-RND-001.

#### VS-CAP-001 — Job de transcrição — P0 — L

**História:** como criativo, quero gerar captions sincronizadas a partir da fala do vídeo.

- UI: escolher fonte de áudio, idioma ou detecção automática e estilo inicial; exibir progresso e custo antes de iniciar.
- Backend: extrair áudio mono 16 kHz; enviar ao provedor configurado; persistir segmentos e palavras com timestamps, confiança, idioma e versão do modelo.
- Falhas são retomáveis e não apagam captions existentes.
- Aceite: português brasileiro de um vídeo de referência gera segmentos temporizados e editáveis; nova transcrição cria revisão, sem sobrescrever silenciosamente a anterior.
- Dependência: VS-CMP-001, VS-JOB-001.

#### VS-CAP-002 — Editor de captions — P0 — L

- Lista ligada à timeline; editar texto; buscar/substituir; dividir, unir e excluir segmentos.
- Arrastar início/fim; evitar sobreposição; navegação pelo segmento atual; edição em lote.
- Indicadores de caracteres por segundo, linha longa e trecho curto demais.
- Aceite: corrigir nome de marca em todas as ocorrências, dividir uma frase e ajustar seu tempo sem regenerar.
- Dependência: VS-CAP-001.

#### VS-CAP-003 — Estilos e presets — P0 — M

- Fonte, tamanho, caixa, cor, fundo, stroke, sombra, posição e safe area.
- Presets de marca e formato; aplicar ao selecionado ou a toda a faixa.
- P1: destaque palavra a palavra e animações simples de entrada/saída.
- Aceite: mudanças globais mantêm exceções locais quando o usuário escolher “somente esta legenda”.
- Dependência: VS-CAP-002, VS-TXT-001.

#### VS-CAP-004 — Importar/exportar SRT e VTT — P1 — M

- Importar com validação de encoding e tempos; exportar texto temporizado.
- Exportar vídeo com captions queimadas e, separadamente, arquivo SRT/VTT.
- Aceite: round trip SRT conserva texto e tempos dentro de um frame.
- Dependência: VS-CAP-002, VS-RND-001.

#### VS-CAP-005 — Tradução e captions bilíngues — P2 — M

- Traduzir a partir da faixa original, manter vínculo por segmento e custo auditável.
- Não entra na meta mínima de 80; entra depois que transcrição e edição forem sólidas.

### Épico E — Áudio multifaixa

#### VS-AUD-001 — Itens e faixas de áudio — P0 — L

- Faixas separadas de áudio original, locução, música e efeitos.
- Mover, trim, split, duplicate, mute, solo, lock, volume e fades por item.
- Renderizar waveforms de forma assíncrona e reutilizável.
- Aceite: misturar áudio de dois vídeos, música, uma locução e três efeitos com prévia e export iguais.
- Dependência: VS-CMP-001, VS-TML-004.

#### VS-AUD-002 — Destacar áudio do vídeo — P0 — M

- Criar item de áudio vinculado à mesma fonte; permitir desvincular e mover.
- Split de clipe mantém A/V ligados até o usuário desvincular.
- Aceite: remover imagem e manter sua fala, ou manter imagem e substituir seu som.
- Dependência: VS-AUD-001.

#### VS-AUD-003 — Locução independente — P1 — M

- Gravar pelo microfone, enviar arquivo ou gerar TTS como item da timeline.
- Regenerar somente um trecho e preservar os demais.
- Exibir custo e duração antes da geração paga.
- Aceite: substituir uma frase sem refazer a geração de vídeo.

#### VS-AUD-004 — Mixagem assistida — P1 — L

- Medidor de pico, normalização/loudness alvo, redução de ruído de fala e ducking da música.
- Envelope/keyframes de volume; presets “voz clara”, “social” e “ambiente”.
- Aceite: fala não clipa, música reduz durante locução e o usuário controla intensidade/ataque/retorno.

#### VS-AUD-005 — Biblioteca licenciada — P2 — L

- Catálogo, licença, origem, uso permitido, favoritos e busca por duração/clima.
- Bloquear publicação quando a licença estiver ausente ou incompatível.
- Não deve atrasar a meta Core 80; uploads e catálogo interno cobrem o primeiro release.

### Épico F — Transformação, efeitos e animação

#### VS-VIS-001 — Fit, fill, crop e transform — P0 — L

- `contain/cover`, crop, posição, escala, rotação, flip vertical/horizontal e opacidade.
- Alças no canvas, campos numéricos e reset.
- Regras explícitas para horizontal em vertical e vertical em horizontal; fundo por cor, blur ou mídia.
- Aceite: um 16:9 em projeto 9:16 pode preencher, caber ou ser reenquadrado manualmente sem deformação.

#### VS-VIS-002 — Cor essencial — P1 — M

- Exposição/brilho, contraste, saturação, temperatura, tint e presets leves.
- Reset individual e global; valores renderizados pelo mesmo contrato no FFmpeg.
- Aceite: quadros de referência ficam dentro da tolerância visual definida entre preview e export.

#### VS-VIS-003 — Transições essenciais — P1 — L

- Corte, cross dissolve, dip to black/white, slide e wipe; duração limitada por handles disponíveis.
- Preview em tempo real e render por transição tipada, sem strings FFmpeg fornecidas pelo cliente.
- Aceite: aplicar e ajustar uma transição entre dois clipes sem alterar a duração total inesperadamente.

#### VS-VIS-004 — Keyframes básicos — P1 — L

- Posição, escala, rotação e opacidade; linear, ease in/out e hold.
- Adicionar/remover no playhead; navegação anterior/próximo; copiar/colar propriedade.
- Aceite: criar zoom progressivo em uma imagem e mover um texto com resultado idêntico no export.

#### VS-VIS-005 — Velocidade, reverse e freeze — P1 — M

- Manter velocidade constante existente; adicionar reverse e freeze frame.
- P2: speed ramp/curva e optical flow.
- Aceite: áudio acompanha velocidade quando ligado e mantém pitch conforme opção do usuário.

### Épico G — Render e exportação

#### VS-RND-001 — Renderizador de composição — P0 — XL, fatiar por faixa

- Compilar o schema v2 em filtergraph controlado pelo servidor.
- Etapa 1: sequência de vídeo/imagem e transformações.
- Etapa 2: áudio multifaixa.
- Etapa 3: texto/captions.
- Etapa 4: transições e keyframes.
- Nunca aceitar filtros, paths ou protocolos fornecidos pelo cliente.
- Aceite: render de projeto com cinco clipes, duas imagens, captions, música e locução passa nos testes de duração, conteúdo de streams e quadros-chave.

#### VS-EXP-001 — Presets de exportação — P0 — M

- Proporções 16:9, 9:16, 1:1 e 4:5; 720p e 1080p; 24/25/30/60 fps conforme capacidade.
- Qualidade simples (`leve`, `recomendada`, `alta`) com detalhes de codec/bitrate em “Avançado”.
- MP4/H.264 primeiro; MOV e HEVC ficam para P2 se houver necessidade comprovada.
- Aceite: export informa dimensão, FPS, tamanho estimado e captions incluídas antes de iniciar.

#### VS-EXP-002 — Histórico e revisão imutável — P1 — M

- Cada job referencia `project_id`, `revision`, preset, usuário e ativos.
- Download, duplicar configuração, erro legível, tentar novamente e retenção.
- Aceite: editar o projeto enquanto exporta não altera o resultado daquele job.

### Épico H — Jobs, desempenho e confiabilidade

#### VS-JOB-001 — Fila durável — P0 — L

- Substituir o `ThreadPoolExecutor` local por worker/fila persistente já compatível com a infraestrutura do projeto.
- Estados `queued`, `processing`, `ready`, `failed`, `cancelled`; lease, heartbeat, retry idempotente e recuperação após restart.
- Limites por workspace e por usuário; prioridade separada para proxy, transcrição e export.
- Aceite: reiniciar o web process não perde jobs nem deixa status eterno.

#### VS-PERF-001 — Timeline e mídia eficientes — P1 — L

- Virtualizar faixa e waveform; carregar janela temporal; cache de poster/proxy; liberar object URLs e elementos inativos.
- Debounce de salvamento e buscas; `AbortController` para respostas obsoletas.
- Meta inicial: projeto de 5 min, 30 clipes, 4 faixas de áudio e 300 captions sem congelamento prolongado.

#### VS-PRJ-001 — Gestão de projetos e conflitos — P1 — M

- Lista, criar, renomear, duplicar, arquivar, restaurar versão e indicador “salvando/salvo/conflito”.
- Resolver 409 com comparação e cópia recuperável; autosave idempotente.
- Aceite: duas abas não sobrescrevem trabalho silenciosamente.

#### VS-OBS-001 — Telemetria e custos — P1 — M

- Tempo de upload/proxy/transcrição/export, fila, erros por codec, falhas por etapa e consumo de CPU/memória.
- Ledger por operação com estimado/confirmado, provedor/modelo, ativo, projeto, revisão e request id.
- Painel do workspace separa IA, armazenamento/processamento e operações locais quando houver cobrança aplicável.

### Épico I — Agente criativo

#### VS-AGT-001 — Ferramentas estruturadas da timeline — P1 — L

- Expor ao agente somente comandos permitidos: inserir ativo, montar rough cut, cortar silêncios, dividir, reordenar, criar captions, posicionar música, aplicar preset e reenquadrar.
- O agente retorna plano, diffs por item, custo e operações irreversíveis/pagas separadas.
- Aplicação vira um único grupo de undo.
- Aceite: “faça um corte de 15 s, vertical, com captions e música baixa” produz uma proposta editável sem exportar ou gastar créditos automaticamente.
- Dependência: épicos B, C, D e E.

#### VS-AGT-002 — Diagnóstico criativo contextual — P2 — M

- Sugerir ritmo, cortes, hook, legibilidade, safe area, loudness e duração por canal.
- Cada sugestão aponta o trecho/item afetado e explica o efeito prático.

## Ordem de execução para atingir Core 80

### Marco 1 — “Vídeo entra e vira projeto” — 3 a 4 semanas

VS-ING-001/002/003, VS-CMP-001/002, VS-JOB-001.

**Saída:** upload real de vídeo, proxy, persistência v2 e base durável. Ainda não deve ser anunciado como editor completo.

### Marco 2 — “Cortar e montar” — 3 a 4 semanas

VS-TML-001/002/003/004/005 e primeira parte de VS-RND-001.

**Saída:** usuário monta imagens e vídeos, divide, apaga, reordena e exporta sequência.

### Marco 3 — “Captions primeiro” — 3 semanas

VS-TXT-001, VS-CAP-001/002/003/004 e etapa de texto de VS-RND-001.

**Saída:** transcrição, revisão, timing, estilo, captions queimadas e SRT/VTT. Este marco tem alto valor para criativos sociais e deve preceder efeitos sofisticados.

### Marco 4 — “Som completo” — 2 a 3 semanas

VS-AUD-001/002/003, parte essencial de VS-AUD-004 e render multifaixa.

**Saída:** áudio original destacado, música, voz e efeitos independentes, waveform, mix e ducking.

### Marco 5 — “Acabamento de social” — 3 semanas

VS-VIS-001/002/003/004/005, VS-EXP-001/002.

**Saída:** reenquadramento, cor, transições, keyframes, reverse/freeze e presets 720p/1080p.

### Marco 6 — “Release Core 80” — 2 semanas

VS-PERF-001, VS-PRJ-001, VS-OBS-001, VS-AGT-001 e validação integrada.

**Saída:** meta esperada de **85/100**, com jornada completa e confiável. Estimativa global indicativa: 16–19 semanas para uma equipe pequena com frontend, backend/media e QA compartilhado. A estimativa deve ser recalibrada após o spike de preview/render e a escolha do serviço de transcrição.

## O que fica depois dos 80%

Estes recursos aproximam o produto dos catálogos amplos de CapCut, Edits e Captions, mas não devem bloquear o fluxo essencial:

- máscaras, blend modes, chroma key e remoção de fundo em vídeo;
- motion tracking e estabilização;
- speed ramp com optical flow;
- curvas avançadas de cor/HSL/LUT;
- multicam, nested/compound clips e adjustment layers;
- catálogo extenso de templates, stickers, efeitos corporais e tendências;
- title cards, teleprompter e templates sincronizados à batida;
- tradução automática e captions bilíngues;
- stock marketplace e gestão avançada de licenças;
- colaboração com comentários e links de revisão;
- publicação direta em redes sociais;
- insights de retenção/skip rate depois da publicação;
- avatares, clonagem de voz e ferramentas long-video-to-shorts.

## Critérios de aceite do release Core 80

O release pode ser considerado pronto quando um usuário conseguir, sem sair da tela:

1. enviar pelo menos três vídeos, duas imagens e arquivos de áudio;
2. montar, reordenar, aparar, dividir, duplicar e excluir clipes;
3. escolher o enquadramento de cada mídia para 16:9, 9:16, 1:1 ou 4:5;
4. adicionar texto e gerar captions em português, corrigir texto e tempo e aplicar estilo global/local;
5. destacar o áudio de vídeo e misturar música, locução e efeitos em faixas independentes;
6. aplicar ajustes de cor, transição e keyframes básicos;
7. salvar, fechar e reabrir o projeto sem diferença de frames ou perda de ativos;
8. desfazer/refazer as operações principais e recuperar conflito entre abas;
9. exportar MP4 em 720p e 1080p, com escolha de frame rate e captions queimadas ou em SRT/VTT;
10. confirmar por testes automatizados e inspeção audiovisual que preview, duração, sincronia, textos e exportação correspondem.

## Plano de validação

- **Unitário:** normalização/migração do schema, operações temporais, snapping, split, ripple, keyframes, captions e cálculo de custo.
- **Integração FFmpeg:** codecs de entrada, orientação, VFR/CFR, fontes, mixagem, transições, duração e A/V sync.
- **HTTP e segurança:** autenticação, CSRF, isolamento por marca, arquivos falsos/corrompidos, limites, IDs, retries e concorrência.
- **Contrato preview/export:** golden frames em tempos conhecidos, texto e posição, tolerância de cor e áudio.
- **Navegador:** drag and drop, teclado, resize, zoom, scroll interno, modais, foco, leitor de tela e `prefers-reduced-motion`.
- **Carga:** 500 ativos na biblioteca; composição de 5 min/30 clipes/4 faixas/300 captions; jobs simultâneos e restart de worker.
- **Jornada completa:** upload → proxy → montagem → captions → áudio → efeitos → autosave → revisão → export → download.

## Decisão recomendada

Começar por VS-ING-001 a VS-ING-003 e VS-CMP-001. Sem esses contratos, qualquer melhoria visual da timeline continuará presa ao clipe gerado atual e terá retrabalho. Depois, entregar montagem e captions antes de expandir a quantidade de efeitos: são as duas lacunas que mais impedem o Studio de substituir o fluxo cotidiano de CapCut, Edits ou um editor focado em captions.
