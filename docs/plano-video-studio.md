# Plano refinado — experiência do Cadu Video Studio

Atualizado em 15/09/2026. Rota: `/parametros/modelagem-criativos/video`.

Este documento substitui o plano de 14/09. Ele parte do código atual: upload de
vídeo, composição com vários itens, transições, legendas, áudio multifaixa,
keyframes básicos, cortes automáticos, projetos versionados, undo/redo e
exportação já possuem implementação. O próximo ciclo não deve adicionar mais
controles isolados; deve transformar essas capacidades em uma experiência de
edição direta, previsível e rápida.

## Estado de execução em 15/09/2026

A primeira entrega do plano já está implementada no produto:

- timeline única baseada em segundos, com régua adaptativa e zoom de `1×` a `5×`;
- clipes, áudio original, faixas adicionais, legendas, sugestões de corte,
  transições e keyframes alinhados ao mesmo playhead;
- waveform que ocupa a duração real de cada faixa, com níveis de 96, 384 e
  1.536 picos selecionados automaticamente conforme o zoom;
- handles para aparar clipes e áudio, arraste de faixas, split no cursor e
  atalhos `S`, `Delete` e `Backspace`;
- snapping magnético em playhead, bordas de clipes e legendas, com guia visual,
  alternância por `N` e suspensão temporária por `Shift` durante o arraste;
- transição visível na junção, com duração ajustável por arraste;
- keyframes em diamante, selecionáveis e reposicionáveis na timeline;
- mute, solo, loop, fades, trim e divisão por faixa de áudio, respeitados na
  prévia e no FFmpeg;
- envelope de volume por faixa, com pontos criados na waveform, edição de tempo
  e ganho e interpolação igual na prévia e na exportação;
- alinhamento manual de áudio ao cursor e restauração da posição de vínculo;
- corte inteligente convertido em proposta não destrutiva: aceitar, ignorar,
  aplicar e restaurar o original;
- presets de legenda reorganizados para leitura e seleção rápidas;
- fluxo coberto por testes de navegador e testes de renderização.

O ripple do modelo atual também foi concluído: `Shift + Delete` e a ação
“Remover e fechar” retiram o item, fecham a sequência, reposicionam áudio que
participa do ripple e ajustam ou removem legendas atingidas. Aparar um clipe
também desloca áudio e legendas posteriores pelo delta real da junção. Continuam
nas fases seguintes os grupos explícitos de vínculo do contrato v3, beat grid,
sincronização automática por correlação e proxy/cache de mídia. A ordem e os
critérios de aceite dessas etapas permanecem definidos abaixo.

Faixas adicionais participam do ripple por padrão e podem desativar
“Acompanhar cortes”. Essa escolha é persistida e normalizada no servidor; uma
música desvinculada permanece fixa enquanto a montagem e as legendas fecham o
espaço.

## Resultado esperado

O Studio deve entregar uma experiência tão boa quanto o CapCut no fluxo central
de vídeo publicitário curto, sem tentar copiar todo o catálogo do produto:

1. importar mídia;
2. montar e cortar diretamente na timeline;
3. gerar e corrigir legendas;
4. equilibrar voz, música e efeitos;
5. animar posição, escala, rotação, opacidade e volume;
6. revisar sugestões automáticas antes de aplicá-las;
7. exportar um resultado igual à prévia.

“Tão boa quanto” significa pouca fricção, resposta visual imediata e segurança
para experimentar. Não significa paridade de quantidade de filtros, templates ou
efeitos.

## Referência de produto validada

As páginas oficiais do CapCut consultadas reforçam quatro padrões relevantes:

- mídia entra por arrastar e pode ser aparada, dividida e reorganizada na própria
  timeline;
- dividir é uma ação de primeiro nível e possui atalho;
- legendas automáticas e remoção de pausas, repetições e palavras de preenchimento
  reduzem trabalho mecânico;
- keyframes aparecem como pontos em forma de diamante ao longo da timeline para
  controlar movimento, zoom, opacidade e áudio;
- áudio pode ser separado do vídeo, aparado e dividido como item independente;
- cortes automáticos podem combinar silêncio, cenas e batidas da música, com
  transições coerentes com o ritmo.

Fontes: [tutorial oficial para iniciantes](https://www.capcut.com/resource/capcut-tutorial-for-beginners),
[edição de vídeos curtos](https://www.capcut.com/resource/short-form-video-editor) e
[guia oficial de keyframes](https://www.capcut.com/resource/how-to-add-keyframes-in-capcut),
[corte de áudio](https://www.capcut.com/resource/audio-cutter-online) e
[AutoCut](https://www.capcut.com/resource/autocut-for-videos).

Essas referências orientam o comportamento, não a aparência. O Studio deve
preservar a linguagem Cadu e priorizar publicidade, formatos de mídia, marca,
locução e segurança comercial.

## Diagnóstico que originou o plano

Esta tabela registra a linha de base anterior à primeira entrega; os itens já
atendidos estão resumidos no estado de execução acima.

| Capacidade | Estado real | Problema de experiência |
|---|---|---|
| Montagem | Vários vídeos e imagens, split, duplicação, reordenação e transições | Os itens são cards proporcionais por `flex-grow`, não objetos em uma escala temporal precisa |
| Zoom | Funciona na edição de um clipe | Não controla a montagem; o modo de composição esconde a timeline que recebe o zoom |
| Keyframes | Persistência, interpolação, preview e exportação | São formulários numéricos no inspetor; não aparecem nem podem ser manipulados na timeline |
| Waveform | Picos para áudio original e arquivos sonoros | Todo o arquivo vira até 96 picos e o SVG é esticado; não acompanha zoom, trim, posição ou velocidade |
| Cortes automáticos | Silêncio, proteção por palavras, hesitações e restauração | A montagem é reconstruída assim que a análise termina; a revisão é uma lista distante do tempo afetado |
| Áudio | Até oito faixas, posição, trim numérico, volume, mute, loop e fades | A faixa visual é apenas uma barra textual, sem waveform, handles, split, solo ou envelope |
| Sincronismo | O render força 48 kHz e termina vídeo/áudio com a mesma duração | A prévia usa relógio de animação e vários elementos HTML; corrige drift apenas por limiar e não possui contrato por frame/amostra |
| Transições | Corte, dissolve, dip to black, slide e wipe com `xfade`/`acrossfade` | A transição pertence ao clipe anterior, não aparece na junção e reduz a duração total sem explicar handles ou política de áudio |
| Processamento | Upload, tarefas persistentes, progresso e prévia renderizada | A interface ainda mistura “enviar”, “analisar”, “processar” e “renderizar”, bloqueando escolhas que poderiam continuar disponíveis |
| Legendas | Transcrição, SRT, edição, dez estilos e exportação | Os segmentos não são manipuláveis na timeline e não estão alinhados visualmente às palavras |
| Histórico | Undo/redo e revisões de projeto | Gestos contínuos precisam virar uma única operação e preservar seleção/viewport |

## Princípios de interação

### Uma timeline, um modelo mental

Remover a separação operacional entre “editar clipe” e “montar sequência”. Abrir
um clipe cria ou seleciona um item na composição. O usuário permanece no mesmo
canvas, inspetor, playhead, régua e conjunto de atalhos.

### A timeline é a fonte de verdade

Campos numéricos continuam disponíveis para precisão, mas todo ajuste temporal
precisa aparecer e, quando seguro, ser manipulável na timeline. Nenhum estado
relevante pode existir apenas no DOM.

### IA propõe; a pessoa decide

Corte automático, legendas e ajustes criativos produzem uma proposta visual. A
proposta informa o que será alterado, permite escutar/visualizar e só modifica a
composição após confirmação explícita.

### Prévia e exportação têm o mesmo contrato

Tempo, transformações, easing, fades, captions e mixagem usam os mesmos valores
normalizados no navegador e no FFmpeg. Quando a prévia instantânea precisar ser
aproximada, a interface deve identificá-la e oferecer a prévia renderizada.

### O básico fica perto do cursor

Selecionar, mover, aparar, dividir, apagar, fechar espaço e adicionar keyframe
não podem exigir procurar uma seção longa no inspetor. O inspetor serve para
propriedades; a timeline serve para edição.

### Simples primeiro, precisão quando necessária

O estado padrão deve servir a quem só quer encurtar um vídeo. Selecionar um item
revela ações rápidas e nomes cotidianos. “Precisão” expande frames, amostras,
curvas e parâmetros avançados sem criar outro editor ou esconder a composição.

### Processar sem tirar o controle

Upload, proxy, waveform, transcrição, análise e render são tarefas distintas. A
interface mostra o que já pode ser feito enquanto as próximas etapas terminam,
permite cancelar/tentar novamente e nunca troca silenciosamente o original por
uma versão analisada.

## Jornadas que definem a experiência

O plano deve ser validado por tarefas completas, não por telas ou componentes
isolados.

### Corte rápido de uma fala

1. Arrastar o vídeo para a timeline.
2. Reproduzir ou navegar pela transcrição.
3. Pressionar `S` no início e no fim do erro.
4. Selecionar o trecho e usar “Remover e fechar espaço”.
5. Ouvir automaticamente 1,5 s antes e depois da junção.
6. Ajustar a emenda pelas bordas se necessário.

Meta: o usuário não abre o inspetor nem digita segundos.

### Limpeza assistida

1. Escolher “Encontrar pausas e erros de fala”.
2. Continuar editando enquanto a análise roda.
3. Receber sugestões sobre waveform e transcrição.
4. Ouvir cada emenda com contexto ou aceitar apenas as sugestões seguras.
5. Aplicar o conjunto como uma ação reversível.

Meta: a automação reduz trabalho sem assumir a decisão editorial.

### Música sincronizada

1. Arrastar música abaixo do vídeo.
2. Ver a waveform e os marcadores de batida.
3. Usar “Ajustar ao projeto” ou aparar manualmente.
4. Encaixar cortes em batidas quando desejado.
5. Ativar redução automática durante fala e ajustar a intensidade.

Meta: voz compreensível e ritmo consistente sem exigir conhecimento de mixagem.

### Transição entre cenas

1. Selecionar a junção entre dois clipes.
2. Escolher corte, dissolver ou outro preset em uma faixa compacta.
3. Arrastar a borda do bloco de transição para alterar duração.
4. Ver se existem handles suficientes e ouvir a política de áudio aplicada.
5. Comparar corte seco/transição sem perder o playhead.

Meta: a duração do projeto não muda inesperadamente.

## Experiência de processamento

### Estados independentes da mídia

Cada ativo deve apresentar estados progressivos, com tarefa e erro próprios:

```text
local → enviando → validando → proxy pronto → analisando → enriquecido
                  ↘ falhou       ↘ waveform/transcrição/cenas podem falhar separadamente
```

- `local`: card imediato com nome, tamanho e opção de cancelar.
- `enviando`: progresso real, velocidade e tempo aproximado; cancelar remove
  somente o upload incompleto.
- `validando`: FFprobe confirma vídeo, rotação, duração, FPS e áudio.
- `proxy pronto`: o ativo já pode ser inserido e editado.
- `analisando`: waveform, transcrição, cenas e batidas aparecem conforme ficam
  disponíveis.
- `enriquecido`: todas as facilidades estão prontas; o original continua
  preservado para exportação.

Falha na transcrição não invalida vídeo, proxy ou waveform. Falha na análise de
cortes não altera a composição. Cada etapa possui “Tentar novamente” específico.

### Centro de tarefas

- Toast informa início e conclusão; não permanece cobrindo a timeline.
- Centro de tarefas mostra fila, etapa atual, tempo, cancelar e tentar novamente.
- Operação longa continua em background e fica vinculada ao projeto/revisão que a
  originou.
- Resultado obsoleto nunca substitui a revisão atual; fica disponível como
  resultado da revisão anterior.
- Exportação usa snapshot imutável e permite continuar editando.

### Prévias com promessa clara

- **Prévia instantânea:** baixa latência, pode simplificar filtros pesados.
- **Prévia exata:** job curto do intervalo selecionado usando o render final.
- **Exportação:** projeto inteiro, preset e revisão imutáveis.

O botão deve dizer “Renderizar prévia exata”, não apenas “Processar”. A interface
mostra o intervalo e a duração estimada antes de iniciar.

## Direção visual

O editor deve parecer uma mesa de montagem Cadu, e não um painel SaaS de cards.
Superfícies são discretas; cor comunica tipo, seleção e risco.

### Tokens principais

| Token | Cor | Uso |
|---|---|---|
| Carvão de palco | `#171B20` | canvas e área de concentração |
| Grafite de mesa | `#232830` | painéis e timeline |
| Régua | `#39414C` | divisões, ticks e limites |
| Tinta clara | `#E6EBF1` | texto e ícones principais |
| Verde Cadu | `#4BD1AE` | playhead, foco, confirmação e ação primária |
| Âmbar de revisão | `#F1C75B` | sugestões automáticas e trechos que exigem decisão |

Sem gradientes decorativos. Vídeo usa azul controlado, áudio usa verde profundo,
texto/legendas usam violeta e automação usa âmbar. Vermelho fica reservado a
clipping, pico e ação destrutiva.

### Tipografia e densidade

- Manter Inter na interface por sua leitura em controles densos e números.
- Timecodes e medidas usam algarismos tabulares, não uma segunda fonte
  monoespaçada ornamental.
- Texto base de 12–13 px; nomes de faixa e metadados podem usar 11 px.
- Sentence case em português: “Dividir no cursor”, “Fechar espaço”, “Voz limpa”.
- Ícone sem rótulo apenas quando o atalho e o significado forem universais; todo
  restante recebe texto ou tooltip acessível.

### Estrutura da tela

```text
┌ Projeto / salvar ───── desfazer ─ prévia ─ formato ─ exportar ┐
├ Biblioteca ┬──────────────── Canvas ───────────────┬ Inspetor ┤
│ mídia      │                                      │ contexto │
│ texto      │          vídeo / guias               │ seleção  │
│ áudio      │                                      │ atual    │
├────────────┴──── reprodução / timecode / zoom ────┴──────────┤
│ ferramentas │ régua temporal e marcadores                     │
│ V1 vídeo    │ [clipe────][clipe──────][imagem──]              │
│ A1 original │ ▂▃▇▅▂▁▁▅▇▃▂                                      │
│ A2 voz      │       ▂▅▇▃▁      ▂▇▅                             │
│ A3 música   │ ▃▃▃▂▂▂▂▃▃▃▃  envelope                            │
│ CC legenda  │ [frase 1] [frase 2] [frase 3]                   │
│ KF escala   │     ◆────────────◆                               │
└─────────────┴──────────────────────────────────────────────────┘
```

Alinhamento é predominantemente à esquerda. O canvas é o foco visual; a timeline
é o foco operacional. O usuário pode aumentar a timeline até ocupar a maior parte
da tela, sem abrir outro modo.

### Revisão crítica da direção

Tema escuro com acento colorido é comum em editores e, sozinho, seria genérico.
A identidade não deve depender desse tratamento. O diferencial escolhido é a
timeline semântica: fala, ambiente, música, captions, transições, automação e
keyframes possuem formas e comportamentos próprios, sempre alinhados ao mesmo
tempo. Cards decorativos, gradientes e animações de entrada foram descartados
porque competiriam com o material editado. O verde Cadu identifica ação e
confirmação; não colore indiscriminadamente todos os controles.

## Fundação técnica: viewport temporal único

Esta é a primeira entrega e a dependência das demais.

### Contrato

- Tempo canônico do projeto em frames inteiros.
- Conversores únicos `frameToX`, `xToFrame`, `sourceToProject` e
  `projectToSource`.
- Estado de viewport: `pixels_per_second`, `scroll_frame`, `visible_start`,
  `visible_end`, largura e FPS.
- Uma função de schedule calcula início/fim real considerando trim, velocidade e
  sobreposição de transições.
- Todos os itens — vídeo, áudio, captions, sugestões e keyframes — usam essa
  escala.

### Comportamento do zoom

- Slider, `Ctrl/Cmd + roda` e gesto de pinça.
- Zoom ancorado no tempo sob o cursor; o conteúdo não “salta”.
- “Ajustar projeto” e “Ajustar seleção”.
- Régua adaptativa: minutos, segundos, décimos e frames conforme a escala.
- Scroll automático ao arrastar perto das bordas.
- Zoom e posição persistidos por projeto como preferência de visualização, sem
  criar revisão de conteúdo.

### Arquitetura frontend proposta

Criar módulos pequenos sob `static/js/cadu-video/timeline/`:

- `viewport.js`: escala, zoom, scroll e régua;
- `schedule.js`: geometria temporal e conversões;
- `renderer.js`: janela visível, faixas e playhead;
- `selection.js`: seleção única/múltipla e faixa ativa;
- `gestures.js`: mover, trim, split, ripple e snapping;
- `waveform.js`: picos, cache e desenho;
- `keyframe-lane.js`: pontos, propriedades e easing;
- `cut-review.js`: propostas automáticas.

`composition.js` continua coordenando estado e exportação, mas deixa de montar
HTML monolítico para todas as faixas.

### Composição v3 e migração

A evolução exige `schema_version: 3`. O documento separa conteúdo persistido de
preferências da interface:

- `composition`: tracks, items, transitions, captions, markers e vínculos;
- `media_assets`: metadados imutáveis das fontes e seus derivados;
- `analysis`: waveform, palavras, cenas, batidas e propostas versionadas;
- `view_state`: zoom, scroll, altura das faixas e painéis abertos, sem participar
  do render nem criar revisão editorial.

Migração v2 → v3:

1. converter segundos atuais para frames/samples usando metadados da fonte;
2. transformar `item.transition` em objeto de junção;
3. criar `linked_group_id` para vídeo e áudio nativo;
4. manter o documento original na revisão anterior;
5. renderizar v2 e v3 em testes de equivalência antes de promover a migração;
6. se faltarem metadados, deixar o projeto em modo compatível e gerar proxy antes
   de converter — nunca arredondar silenciosamente.

Toda mutação temporal passa por comandos tipados (`move_items`, `trim_edge`,
`split_items`, `ripple_delete`, `set_transition`, `move_keyframes`). Os mesmos
comandos alimentam UI, undo/redo, autosave, agente e testes.

## Edição direta da timeline

### Seleção e ferramentas

- Clique seleciona; `Shift + clique` amplia seleção.
- Marquee seleciona vários itens no intervalo.
- Arrastar o corpo move; arrastar bordas apara.
- Ferramentas mínimas: selecionar, lâmina e mão.
- Duplo clique abre propriedades detalhadas sem trocar de contexto.
- Menu contextual: dividir, duplicar, remover, fechar espaço, desvincular,
  substituir mídia e revelar na biblioteca.

### Snapping

O ímã deve encaixar em:

- playhead;
- início/fim do projeto;
- bordas de itens;
- marcadores e sugestões de corte;
- início/fim de palavras;
- keyframes.

Exibir uma guia e o timecode do alvo. `Alt/Option` desativa temporariamente o
snapping. A tolerância é em pixels, não em segundos, para permanecer previsível
em qualquer zoom.

### Operações seguras

- `Delete`: remove mantendo a lacuna quando a faixa permite.
- `Shift + Delete`: ripple delete/fecha o espaço.
- Split preserva o quadro do playhead e cria duas referências à mesma fonte.
- Vídeo, áudio original e captions usam `linked_group_id`; `Alt/Option` permite
  edição temporariamente desvinculada.
- Um gesto de drag gera uma entrada de undo, não dezenas.

### Tipos de corte e aparo

O usuário não precisa conhecer os nomes profissionais, mas o comportamento deve
ser preciso:

- **Aparar início/fim:** arrastar uma borda altera o intervalo da fonte.
- **Dividir:** cria dois itens no frame do playhead sem duplicar o arquivo.
- **Remover:** apaga o trecho e preserva a lacuna.
- **Remover e fechar espaço:** desloca os itens posteriores e preserva vínculos.
- **Ajustar a junção:** arrastar o encontro entre dois clipes aumenta um e reduz o
  outro sem mudar a duração da sequência.
- **Deslizar conteúdo:** no modo Precisão, mover a fonte dentro do item mantém sua
  posição e duração no projeto.

Durante qualquer aparo, o canvas mostra o frame da borda; ao ajustar uma junção,
mostra os frames de saída e entrada lado a lado. O timecode flutuante informa
posição e variação, por exemplo `00:08:12 · −6 frames`.

### Revisão de emenda

Após split, ripple delete ou aplicação de sugestão, oferecer “Ouvir emenda” sem
abrir modal. A reprodução começa 1,5 s antes e termina 1,5 s depois; `Shift +
Space` repete esse intervalo. Cliques, respirações cortadas e mudança brusca de
ambiente são sinalizados, mas não corrigidos silenciosamente.

## Transições previsíveis

### Modelo de dados

Transição deve ser um objeto da junção, não uma propriedade escondida no clipe da
esquerda:

```json
{
  "id": "transition-01",
  "left_item_id": "clip-a",
  "right_item_id": "clip-b",
  "type": "dissolve",
  "duration_frames": 12,
  "alignment": "center",
  "audio_mode": "crossfade"
}
```

Tipos iniciais: corte, dissolver, passar pelo preto, passar pelo branco,
deslizar e revelar. Nomes do schema permanecem estáveis; rótulos podem ser
localizados.

### Handles e duração

- A duração da sequência não muda ao adicionar uma transição.
- A transição usa mídia disponível antes/depois dos trims como handles.
- Se os handles forem insuficientes, limitar a duração e explicar: “Disponível:
  8 frames”.
- Nunca repetir frame, criar preto ou deslocar todos os itens sem escolha.
- Arrastar o bloco na junção altera a duração com preview em loop.
- Modo Precisão permite alinhar ao corte, início ou fim.

### Áudio durante a transição

- `crossfade`: padrão para continuidade entre trechos da mesma gravação.
- `cut`: troca de áudio exatamente no corte.
- `preserve_left`/`preserve_right`: mantém o ambiente dominante durante a
  transição visual.
- Música independente não recebe crossfade por causa de uma transição de vídeo.
- Alterar a política mostra o resultado na waveform/envelope.

O inspetor exibe tipo, duração, alinhamento e áudio. A timeline exibe o bloco e
permite todas as ações essenciais sem abrir o inspetor.

## Keyframes visuais

O backend e o preview atuais já suportam posição, escala, rotação e opacidade. O
trabalho principal é dar visibilidade e manipulação a esse contrato.

### Interface

- Botão de diamante ao lado de cada propriedade animável no inspetor.
- Diamantes agregados no clipe; expandir revela uma faixa por propriedade.
- Ponto selecionado mostra tempo e valor no inspetor.
- Arrastar horizontalmente altera o frame; valor continua editável no inspetor.
- Botões anterior, adicionar/remover e próximo junto ao controle da propriedade.
- Copiar/colar keyframes entre itens compatíveis.
- Seleção múltipla para mover um grupo preservando distâncias.
- Indicador de keyframe fora do playhead para evitar sobrescrita acidental.

### Easing

Primeira versão: linear, ease in, ease out, ease in-out e hold. A curva aparece
como miniatura entre os pontos; um editor Bézier completo fica fora do primeiro
ciclo. O schema deve deixar espaço para `bezier` sem aceitar expressões livres.

### Áudio

O mesmo padrão de diamante controla ganho. O envelope é desenhado sobre a
waveform e pode ser ajustado diretamente. Volume, transformação visual e
opacidade compartilham navegação, seleção e atalhos.

## Waveform proporcional ao zoom

### Dados

Substituir o resumo único de até 96 picos por uma pirâmide de resoluções. Exemplo:

- nível 0: 64 buckets;
- nível 1: 256;
- nível 2: 1.024;
- nível 3: 4.096;
- nível 4: blocos finos sob demanda para o intervalo visível.

Guardar mínimo e máximo de cada bucket para preservar transientes positivos e
negativos. O cache é identificado por ativo, versão do algoritmo e nível.
Todos os proxies de edição usam 48 kHz estéreo; o original permanece intacto.

### Renderização

- Canvas por faixa; não criar milhares de paths SVG.
- Desenhar somente o intervalo visível com margem pequena.
- Escolher automaticamente o nível com aproximadamente um bucket por pixel.
- Mapear `source_in`, `source_out`, `timeline_start` e `speed` antes de desenhar.
- Áudio original acompanha o vídeo até ser desvinculado.
- Fades e envelope aparecem sobre os picos.
- Canais estéreo podem aparecer combinados no modo simples e separados no modo
  Precisão.
- Trechos silenciados ficam atenuados; clipping aparece em vermelho apenas nos
  pontos afetados.
- Região além do fim do projeto fica visível, mas sinalizada.

### Interação

- Handles para trim e fades.
- Arrastar o corpo muda a posição.
- Split no playhead, duplicar, mute, solo, lock e loop do intervalo.
- `Shift + Space` toca somente a seleção; botão próprio oferece loop.
- Scrub de áudio opcional, desligado por padrão para não tornar a timeline ruidosa.

### Corte de áudio

- Arrastar as bordas faz trim preservando a fonte.
- Split usa posição exata em amostras e cria dois itens referenciando o mesmo
  ativo.
- Ripple delete de áudio vinculado acompanha o vídeo; áudio independente só se
  move quando selecionado ou quando a faixa participa do ripple.
- “Separar áudio” cria um item vinculado na faixa inferior e silencia a cópia
  nativa do item de vídeo, evitando áudio duplicado.
- Fades possuem handles nos cantos superiores e duração visível durante o drag.
- Crossfade é criado arrastando um fade sobre o item adjacente ou pela junção.
- Ganho é exibido em dB; `0 dB` preserva o nível, `−∞` representa silêncio.

## Sincronismo audiovisual

Sincronismo não é um ajuste posterior: é parte do schema, da reprodução e do
render.

### Domínios de tempo

- Vídeo persiste `start_frame`, `duration_frames`, `source_in_frame` e
  `source_out_frame` usando FPS racional da fonte e do projeto.
- Áudio persiste `timeline_start_sample`, `source_in_sample`,
  `duration_samples` e `sample_rate`.
- Captions, marcadores e propostas mantêm intervalos inteiros em microssegundos
  ou ticks versionados; a conversão para frames/amostras ocorre em funções únicas.
- Não persistir posições editoriais como floats em segundos.
- Toda fonte guarda `fps_num/fps_den`, `time_base`, `sample_rate`, duração e
  rotação obtidos por FFprobe.

### Relógio da prévia

- `AudioContext.currentTime` é o relógio mestre quando existe áudio em reprodução.
- Vídeo e canvas são atualizados por `requestVideoFrameCallback` quando disponível,
  com fallback para `requestAnimationFrame`.
- Play, pause e seek são transações: todas as fontes recebem a mesma versão de
  transporte antes de reproduzir.
- Drift menor que um frame é tolerado; acima disso, corrigir suavemente quando
  possível e fazer hard seek somente acima de 80 ms.
- A interface nunca mostra “sincronizado” enquanto alguma fonte necessária ainda
  está buscando dados.

### Operações que preservam sincronismo

- Mover vídeo desloca áudio original e captions vinculados.
- Trim de vídeo ajusta o mesmo intervalo de áudio, salvo quando desvinculado.
- Split cria novos grupos vinculados nos mesmos tempos de origem.
- Mudança de velocidade aplica o mesmo fator a A/V e preserva pitch por padrão;
  “Alterar pitch” é uma opção explícita.
- Ripple delete desloca todos os itens participantes pela mesma quantidade de
  frames/ticks.
- Transições usam os mesmos offsets no preview e no filtergraph final.

### Ferramentas de correção

- “Sincronizar por waveform” compara áudio de câmera e faixa externa e propõe um
  offset, sem aplicar automaticamente.
- “Sincronizar por marcador” alinha dois pontos escolhidos pelo usuário.
- Indicador de vínculo mostra deslocamento manual, por exemplo `+3 frames`.
- “Restaurar sincronismo” volta ao offset registrado na criação do vínculo.
- Itens sem fonte, com sample rate inesperado ou duração divergente mostram erro
  localizado, sem invalidar a montagem inteira.

### Contrato de exportação

- Normalizar a mixagem de trabalho em 48 kHz, sem alterar arquivos de origem.
- Gerar PTS de vídeo e áudio a partir do mesmo schedule compilado.
- Aparar o padding de AAC somente na borda final, sem encurtar fala aprovada.
- Medir início, fim e drift de cada stream após o render com FFprobe.
- Bloquear a conclusão quando a diferença ultrapassar um frame; guardar relatório
  de sincronismo junto ao job.

### Mixagem compreensível

O modo simples trabalha com intenção, não com jargão:

- **Voz clara:** limpeza moderada, ganho seguro e medidor visível.
- **Música de fundo:** volume inicial reduzido e fade curto nas extremidades.
- **Baixar música durante a fala:** gera envelope editável, nunca um efeito oculto.
- **Ambiente contínuo:** preserva room tone nas emendas quando houver material.

O modo Precisão revela ganho em dB, pico, loudness integrado, compressor, ducking,
attack/release e pan. O master mostra pico durante reprodução e alerta antes da
exportação quando houver clipping. Preset social pode sugerir `−14 LUFS` e pico
máximo de `−1 dBTP`, mas o valor permanece explícito e configurável por destino.

Aplicar limpeza, normalização ou ducking cria uma versão editável do ajuste; não
substitui o arquivo original. Bypass A/B permite comparar no mesmo trecho e no
mesmo volume percebido.

## Cortes inteligentes como revisão visual

O algoritmo atual de silêncio e proteção de palavras deve ser preservado, mas seu
resultado deixa de ser aplicado automaticamente.

### Fluxo

1. A importação conclui com o original intacto.
2. A análise cria uma `edit_proposal` versionada.
3. Regiões sugeridas aparecem em âmbar sobre waveform e transcrição.
4. Hover informa motivo, confiança e duração removida.
5. Clique seleciona e reproduz contexto antes/depois.
6. O usuário aceita, rejeita ou ajusta as bordas.
7. “Aplicar cortes aceitos” cria uma única operação de undo.

### Tipos separados de análise

- Remover silêncios.
- Detectar hesitações e palavras de preenchimento.
- Sinalizar repetições para revisão.
- Detectar mudanças de cena.
- Dividir por duração/ritmo-alvo.
- Detectar batidas da música e sugerir encaixes próximos, sem deslocar fala.

Não misturar todos em um botão opaco. Cada análise possui intensidade, margem e
efeito previsíveis. Nenhuma fala de baixa confiança é removida automaticamente.

### Classificação das sugestões

- **Segura:** silêncio confirmado, sem palavra protegida e com margem suficiente.
- **Revisar:** repetição, hesitação ambígua, respiração ou ruído de ambiente.
- **Cena:** mudança visual; sugere split, não remoção.
- **Ritmo:** aproxima um corte existente de uma batida dentro de tolerância curta.

Cada sugestão guarda algoritmo/versão, origem temporal, confiança, motivo,
margens, impacto na duração e itens vinculados. Reanalisar cria nova proposta e
não sobrescreve decisões anteriores até o usuário escolher substituí-las.

### Proteções editoriais

- Nunca cortar dentro de palavra ou a menos de uma margem configurada de fonema.
- Preservar respiração curta quando sua remoção tornar a fala artificial.
- Não mover corte para batida se o deslocamento quebrar uma frase ou exceder a
  tolerância escolhida.
- Sinalizar mudança brusca de ruído/room tone após remoção.
- Aplicar microfade apenas para evitar clique; não esconder uma emenda ruim.
- Limitar remoção total por análise e alertar quando o vídeo perder mais de 25%
  da duração.

### Painel de revisão

Exibir resumo fixo: “12 sugestões · 8 aceitas · 4 para revisar · 6,4 s
removidos”. A lista acompanha o playhead, mas a decisão principal ocorre sobre a
timeline. Deve existir “Aceitar seguras”, “Rejeitar todas” e “Restaurar original”.

Dois modos atendem perfis diferentes:

- **Rápido:** mostra resumo, sugestões seguras e comparação antes/depois.
- **Precisão:** revela transcrição por palavra, waveform, margens e confiança.

## Legendas e edição por texto

- Segmentos de caption aparecem como itens temporais editáveis.
- Palavras aparecem dentro dos segmentos quando houver espaço de zoom.
- Arrastar bordas ajusta início/fim sem sobreposição inválida.
- Selecionar uma palavra posiciona o playhead.
- Edição do texto no painel mantém a seleção na timeline.
- Futuro próximo: apagar texto selecionado propõe remover também o trecho de
  vídeo, sempre com preview e undo.
- Estilo global permanece separado de correção de conteúdo.

## Facilidades essenciais

### Atalhos iniciais

| Ação | Atalho |
|---|---|
| Reproduzir/pausar | `Espaço` |
| Voltar/parar/avançar | `J`, `K`, `L` |
| Um frame | `←`, `→` |
| Dez frames | `Shift + ←`, `Shift + →` |
| Dividir | `S` e `Ctrl/Cmd + B` |
| Apagar | `Delete/Backspace` |
| Fechar espaço | `Shift + Delete` |
| Desfazer/refazer | `Ctrl/Cmd + Z`, `Ctrl/Cmd + Shift + Z` |
| Zoom | `Ctrl/Cmd + roda` |
| Ajustar projeto | `\` |
| Marcar entrada/saída | `I`, `O` |
| Ativar/desativar snapping | `N` |

Atalhos não disparam enquanto o foco estiver em campo de texto. Um mapa
pesquisável deve estar disponível pelo botão “Atalhos”.

### Estados e feedback

- Cursor muda conforme ferramenta e zona de drag.
- Tooltip mostra ação e atalho.
- Drag exibe quadro fantasma, timecode e alvo de snapping.
- Alteração não salva mantém o indicador atual; conflito oferece “Salvar cópia”.
- Operações longas aparecem no centro de jobs sem bloquear a edição.
- Estados vazios dizem a próxima ação: “Arraste um vídeo para começar”.

## Roadmap executável

### Marco 0 — Protótipo e linha de base — P0 — 2 a 3 dias

- Fixar três projetos de referência: fala contínua, anúncio com música e montagem
  de cinco cenas.
- Medir tempo de importação, seek, drift, scroll, zoom e exportação atuais.
- Prototipar viewport temporal e uma faixa de waveform com dados reais.
- Congelar decisões de schema, tempo e transição antes de multiplicar componentes.

**Aceite:** métricas reproduzíveis, fixtures preservadas e decisão documentada
sobre FPS racional, samples e ticks.

### Marco 1 — Preparação progressiva da mídia — P0 — 4 a 6 dias

- Cards locais e progresso de upload cancelável.
- Estados independentes para validação, proxy, waveform, transcrição e análise.
- Proxy editável antes do fim dos enriquecimentos.
- Retry por etapa, prevenção de resultado obsoleto e centro de tarefas.

**Aceite:** falha de transcrição não impede editar/exportar; trocar de projeto não
mistura resultados; o usuário começa a montar assim que o proxy fica pronto.

### Marco 2 — Timeline e corte confiáveis — P0 — 7 a 10 dias

- Viewport temporal único, régua adaptativa, zoom ancorado e scroll.
- Unificação visual de clipe e composição.
- Mover, trim, split, delete, ripple, ajuste de junção e slip no modo Precisão.
- Snapping, seleção múltipla, vínculos A/V/captions e undo por gesto.
- Atalhos de reprodução/edição e revisão de emenda em loop.

**Aceite:** remover uma pausa exige no máximo três ações; zoom não altera o tempo
sob o cursor; salvar/reabrir não desloca itens; áudio e captions permanecem
sincronizados dentro de um frame.

### Marco 3 — Áudio visual e relógio mestre — P0 — 8 a 12 dias

- Pirâmide de picos, cache e waveform por janela visível.
- Itens de áudio com mover, trim, split, ripple, solo/mute/lock e separar áudio.
- Handles de fade/crossfade, ganho em dB e envelope simples.
- Schema por amostras, transporte atômico e `AudioContext` como relógio mestre.
- Medição de drift na prévia e no arquivo exportado.

**Aceite:** em qualquer zoom, waveform e reprodução continuam alinhadas; cortes
A/V permanecem vinculados; nenhuma fala aprovada é truncada; drift final não
ultrapassa um frame.

### Marco 4 — Transições previsíveis — P0 — 4 a 6 dias

- Transição como objeto de junção.
- Bloco visual, drag de duração e preview em loop.
- Validação de handles e duração estável da sequência.
- Política de áudio explícita: cut, crossfade ou preservar um lado.
- Migração das transições atuais sem alterar o resultado salvo.

**Aceite:** adicionar/remover transição não muda a duração do projeto; handles
insuficientes geram limite claro; prévia e FFmpeg usam os mesmos frames e fades.

### Marco 5 — Cortes inteligentes revisáveis — P1 — 7 a 10 dias

- `edit_proposal` persistida, versionada e não destrutiva.
- Overlays de silêncio, hesitação, repetição, cena e batida.
- Audição de contexto, aceitar/rejeitar/ajustar e modos Rápido/Precisão.
- Proteção de palavra, respiração, room tone e limite de remoção.
- Aplicação atômica, comparação antes/depois e restauração integral.

**Aceite:** nenhuma sugestão altera o projeto antes da confirmação; palavras não
são cortadas; cortes de ritmo não prejudicam fala; undo restaura a montagem
anterior completa.

### Marco 6 — Keyframes visuais — P1 — 4 a 6 dias

- Diamantes agregados e faixas por propriedade.
- Navegação, drag, copiar/colar e seleção múltipla.
- Cinco easings tipados.
- Envelope de volume usando o mesmo componente.

**Aceite:** criar zoom progressivo e ducking manual sem digitar tempos; golden
frames da prévia e exportação permanecem dentro da tolerância visual definida.

### Marco 7 — Legendas e edição por texto — P1 — 4 a 7 dias

- Segmentos e palavras alinhados à waveform.
- Trim visual, navegação por texto e validação de sobreposição.
- Proposta de remover vídeo ao apagar um intervalo de fala.
- Preservação dos dez estilos e do SRT existentes.

**Aceite:** corrigir texto e timing sem perder o playhead; exclusão por texto é
sempre revisável; exportação mantém conteúdo, estilo e sincronismo.

### Marco 8 — Polimento, desempenho e lançamento — P1 — 5 a 8 dias

- Virtualização da janela visível e limite de decodificadores ativos.
- Autoscroll, menus contextuais, tooltips e mapa de atalhos.
- Acessibilidade, foco, contraste e reduced motion.
- Testes de stress, telemetria, onboarding curto e correções de responsividade.
- Rollout por feature flag com projetos antigos em modo compatível.

**Aceite:** projeto de 5 minutos, 30 clipes, quatro faixas e 300 captions permite
scroll, zoom e seleção sem congelamentos perceptíveis; os fluxos de referência
passam integralmente em produção controlada.

Estimativa de referência: oito a onze semanas para uma pessoa trabalhando em
sequência, ou cinco a sete semanas com duas frentes depois do Marco 2. A estimativa
deve ser recalibrada no Marco 0; sincronismo e migração não podem ser comprimidos
para cumprir calendário.

## Métricas de qualidade

- Card local após soltar arquivo: menos de 200 ms.
- Mídia editável assim que o proxy fica pronto; análises não bloqueiam montagem.
- Primeiro corte após importação: menos de 90 segundos para usuário novo.
- Split + ripple delete: até três ações.
- Erro temporal entre prévia e exportação: no máximo um frame.
- Drift A/V após estabilização: no máximo um frame; hard seek somente acima de
  80 ms durante a prévia.
- Split de áudio: erro máximo de uma amostra na taxa de trabalho.
- Adicionar ou remover transição: zero alteração inesperada na duração do projeto.
- Waveform: pico, seleção e playhead permanecem dentro de um pixel na escala
  escolhida.
- Prévia de emenda disponível em uma ação após qualquer corte.
- Interação de zoom/scroll: alvo de 60 fps; nunca bloquear por mais de 100 ms em
  hardware de referência.
- Undo: pelo menos 50 operações sem perda de IDs, seleção ou vínculos.
- Nenhum corte automático aplicado sem confirmação.
- Resultado de job iniciado em revisão antiga nunca sobrescreve a revisão atual.
- Todo controle liberado possui efeito testado no arquivo exportado.

## Estratégia de testes

### Unitários

- Conversões frame/tempo/pixel, frame/sample/tick e fonte/projeto.
- Schedule com trim, velocidade e transições.
- Snapping em diferentes escalas.
- Resampling e seleção do nível da waveform.
- Keyframes, easing, envelope e migração de schema.
- Aplicação e reversão das propostas de corte.
- Idempotência dos comandos tipados e agrupamento de undo por gesto.

### Navegador

- Drag, trim e split com coordenadas reais.
- Zoom mantendo a âncora sob o cursor.
- Atalhos sem interferir em inputs.
- Seleção múltipla, snapping, undo/redo e reabertura.
- Waveform, captions, keyframes e sugestões alinhados ao mesmo playhead.
- Separar áudio, cortar, relinkar e restaurar sincronismo.
- Transição com/sem handles, três políticas de áudio e preview em loop.
- Falha/retry independente de proxy, waveform, transcrição e análise.
- Tema claro/escuro e viewports de notebook.

### Render

- Arquivos de referência com fala, música, silêncio e mudanças de cena.
- Comparação de duração, streams e frames conhecidos.
- Teste de áudio em junções, fades, velocidade e envelope.
- Medição automática de PTS, padding AAC, sample rate, clipping, loudness e drift.
- Transições não podem alterar duração nem criar frame preto fora do preset.
- Matriz 16:9, 9:16, 1:1 e 4:5; 24, 25, 30 e 60 fps quando suportados.

### Testes de jornada

| Jornada | Evidência obrigatória |
|---|---|
| Corte rápido | Gravação do fluxo, número de ações, projeto reaberto e MP4 final |
| Limpeza assistida | Proposta antes/depois, palavras protegidas e undo integral |
| Música sincronizada | Marcadores de batida, ducking editável e medição de loudness |
| Transição | Handles, duração invariável e A/B no mesmo playhead |
| Sincronização externa | Offset proposto, ajuste manual, drift de preview e FFprobe final |
| Falha de processamento | Retry isolado sem perder edição nem duplicar ativo |

## Fora do primeiro ciclo

- Editor Bézier completo e graph editor avançado.
- Speed ramp com optical flow.
- Multicam, nesting e adjustment layers.
- Plugins de áudio/VST e mixagem surround.
- Tracking avançado, rotoscopia e chroma key profissional.
- Edição completa em celular; mobile prioriza revisão, comentários e exportação.
- Catálogo massivo de templates e efeitos.

Esses itens não impedem uma experiência excelente no trabalho cotidiano de vídeo
publicitário curto.

## Riscos e decisões

| Risco | Decisão |
|---|---|
| Construir keyframes e waveform antes da escala comum | Bloquear essas frentes até o Marco 1 fechar o contrato temporal |
| Regressão em projetos salvos | Manter migração versionada e fixtures de documentos reais |
| Preview Canvas divergir do FFmpeg | Golden frames e rótulo explícito para prévia aproximada |
| Timeline travar com muitos elementos | Canvas, janela visível, cache e medição desde o primeiro marco |
| Vários elementos HTML acumularem drift | Relógio de áudio mestre, transporte versionado e correção medida |
| Transição encurtar a montagem | Objeto de junção, handles validados e duração do projeto invariável |
| Áudio separado tocar duplicado | Separação atômica: criar item vinculado e mutar áudio nativo na mesma operação |
| Falha parcial bloquear o ativo inteiro | Estados e retries independentes para proxy, waveform, transcrição e análise |
| Job antigo sobrescrever edição nova | Vincular tarefa a projeto, revisão e assinatura dos inputs |
| IA remover fala válida | Proposta não destrutiva, confiança e confirmação humana |
| Copiar o CapCut e perder identidade | Copiar fluidez e convenções aprendidas; preservar tokens, linguagem e prioridades Cadu |

## Definição de conclusão

O ciclo estará concluído quando uma pessoa puder soltar um vídeo, começar a editar
assim que o proxy estiver pronto, revisar cortes sugeridos, aparar vídeo e áudio
diretamente na timeline, ouvir cada emenda, aplicar uma transição sem alterar a
duração, ver waveforms coerentes em qualquer zoom, sincronizar uma faixa externa,
criar keyframes por diamantes, corrigir captions, equilibrar a mixagem, desfazer
qualquer gesto, reabrir o projeto e exportar um MP4 correspondente à prévia — sem
alternar entre dois modelos de edição e sem perder trabalho quando uma análise
falhar.
