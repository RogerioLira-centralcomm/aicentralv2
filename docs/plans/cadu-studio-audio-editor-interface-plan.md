# Cadu Studio Áudio — plano revisado de criação, edição e mixagem

## Revisão 2 — decisões vigentes

Atualização de 23/09/2026. Esta revisão substitui as decisões incompatíveis da proposta inicial preservada abaixo. O documento é planejamento; nenhuma capacidade descrita foi implementada ou testada nesta revisão.

### Uma sessão para criar e finalizar áudio

A unidade principal é uma **sessão multifaixa**: roteiro, locuções, música, efeitos, gravações e transcrição convivem na mesma bancada. Cada geração vira um clipe editável em uma faixa, com alternativas para comparar. A timeline ocupa do meio da tela até a parte inferior, sempre visível durante criação, conversa com o agente e revisão.

Multifaixa entra na primeira entrega funcional. O usuário cria voz, compõe música, transcreve, corta, trata, combina camadas e exporta sem trocar de ferramenta. A grande waveform isolada do plano anterior é substituída pela montagem; o detalhe da waveform aparece acima apenas quando um clipe precisa de edição precisa.

**Regra de linguagem:** nenhum fornecedor, modelo, endpoint ou roteamento aparece na ferramenta, nem em “Detalhes”, mensagens do agente ou erros. O usuário vê atividade, destino, duração, custo estimado, progresso e resultado. Informações de tecnologia ficam exclusivamente nos registros internos da equipe.

### Organização da tela

```text
┌ Cadu Studio  Criar  Editor  Vídeos  Áudio  Analyzer  Biblioteca ──────────┐
│ Campanha primavera · Spot 30s   Projeto ▾   Salvo  ↶ ↷  Exportar áudio │
├──────────────┬─────────────────────────────────────┬────────────────────┤
│ Arquivos     │ Criar voz | Música | Efeito | Texto │ Agente | Ajustes   │
│ Buscar       │                                     │                    │
│ + Importar   │ Roteiro / criação / revisão         │ Deixe a voz mais   │
│ + Gravar     │ do trecho ou clipe selecionado      │ clara e abaixe a   │
│              │                                     │ música na fala.    │
│ Do projeto   │ Voz ▾  Idioma ▾  Interpretação       │                    │
│ Vozes salvas │ Ouvir amostra    Gerar no trecho     │ Ouvir proposta     │
│ Alternativas │                                     │ Aplicar | Descartar│
├──────────────┴─────────────────────────────────────┴────────────────────┤
│ ◀ ▶ ⏺  00:08.240 / 00:30.000  Loop  Ímã  Zoom − +  Mixer  Histórico   │
├────────────────┬──────────────────────────────────────────────────────┤
│ Faixa  M S  dB │ 0s       5s       10s       15s       20s       30s   │
│ Locução        │ [Abertura ╱╲╱╲] [Oferta ╱╲╱╲]       [Fechamento ╱╲] │
│ Segunda voz    │              [Resposta ╱╲╱╲]                         │
│ Música         │ [Trilha ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲──────────fade]     │
│ Ambiente       │ [Ambiente ╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲╱╲]           │
│ Efeitos        │ [Vinheta]                        [Transição]         │
│ + Nova faixa   │ [+ Gerar neste intervalo]                            │
├────────────────┴──────────────────────────────────────────────────────┤
│ Saída final  Medidores L/R  Volume percebido  Pico  Revisão da sessão   │
└───────────────────────────────────────────────────────────────────────┘
```

Referência desktop: 1440 × 960. Barras superiores com aproximadamente 108 px; área superior de 280–310 px; transporte com 48 px; timeline usa o restante. Biblioteca com cerca de 220 px, painel direito com 320 px e centro flexível. O divisor horizontal permite ampliar a montagem; “Focar edição” recolhe a área superior.

A timeline atravessa toda a largura abaixo dos painéis, com cabeçalhos de faixa fixos e rolagem compartilhada entre régua e clipes. Agente e Ajustes são abas do mesmo painel direito. Selecionar clipe, faixa ou saída muda o inspetor e mantém o escopo visível. Em 1024 px, Biblioteca vira gaveta e o inspetor pode ser recolhido; em telas pequenas, priorizar ouvir, revisar texto e aprovar versões.

### Atividades da bancada

| Atividade | Controles contextualizados | Resultado |
|---|---|---|
| Criar voz | Texto falado, voz com amostra, idioma, interpretação e pronúncia | Clipe com roteiro associado |
| Criar música | Descrição, duração, energia, instrumental/com voz quando suportado | Clipe musical com alternativas |
| Criar efeito | Descrição, duração e posição/intervalo | Clipe na faixa de efeitos |
| Gravar | Microfone, medidor, contagem regressiva e faixa de destino | Nova tomada |
| Transcrever | Idioma, falantes e texto com tempos | Documento sincronizado |
| Editar | Waveform detalhada, início/fim, fades, velocidade e ganho | Alteração reversível |
| Tratar e mixar | Efeitos do clipe, faixa ou saída | Processamento e automação |

Transcrição não é uma faixa sonora: aparece como visão textual e, opcionalmente, linha de referência sincronizada. Corrigir texto não altera o áudio. “Remover trecho do áudio” e “Regravar este trecho” são ações distintas, com prévia.

### Timeline multifaixa e geração em camadas

- Primeira entrega com oito faixas de áudio e vários clipes por faixa; limite ajustável após medir desempenho.
- Faixa: nome, função, cor, mute, solo, ganho, panorama, bloqueio e medidor. Cor indica voz, música, ambiente ou efeito.
- Clipe: fonte preservada, waveform, posição, entrada/saída da fonte, velocidade, ganho, fades e tomada ativa.
- Edição: arrastar, aparar com alças, dividir no cursor, duplicar, agrupar, alinhar, criar crossfade e inserir silêncio.
- Exclusão comum deixa espaço; “Excluir e fechar espaço” informa se afeta a faixa ou o grupo vinculado.
- Seleção de intervalo, clipe e faixa são estados diferentes. Barra de ações e agente mostram qual está ativo.
- Ímã em bordas, marcadores e cursor; loop de seleção; zoom centrado na seleção; atalhos e alternativa por teclado ao arrastar.
- Automação inicial de volume por pontos, incluindo redução da música sob a voz. Curvas expandem sob a faixa.
- Música, locução e efeitos podem sobrepor-se. Alternativas de uma mesma tomada nunca tocam juntas por padrão.

Fluxo de geração: selecionar faixa e intervalo → escolher atividade na área superior → ver destino e custo → gerar → ouvir sozinho ou na mixagem → aceitar tomada. Durante o processamento, uma região provisória mostra o progresso; o restante da sessão continua editável. O destino é capturado ao iniciar e não muda se o usuário mover o cursor.

“Outra versão” preserva tomadas anteriores na gaveta do clipe. “Adicionar em nova camada” cria sobreposição explicitamente. Se o resultado exceder o intervalo, oferecer ajustar texto, velocidade, duração da sessão ou manter a sobra. Nunca truncar fala automaticamente. Regeneração localizada preserva clipes vizinhos e oferece transição ajustável.

### Criação de voz, música e transcrição

Voz: separar “Texto falado” de “Como interpretar”; permitir roteiro em blocos e voz por personagem. A duração-alvo é uma meta, conferida pela duração medida. Preservar pronúncias do projeto e permitir regenerar uma frase. Exibir apenas parâmetros com efeito comprovado.

Música: atalhos “Trilha de fundo”, “Vinheta”, “Abertura”, “Encerramento” e “Ambiente”. Descrição, referências e letra são entradas separadas. Andamento/tonalidade só aparecem como controles garantidos quando suportados; caso contrário, como orientação. Extensão musical, separação de voz/instrumental e pistas por instrumento são capacidades independentes a validar, não consequências automáticas de gerar música.

Transcrição: clicar em frase move o cursor, selecionar palavras destaca o áudio, revisar falantes e exportar TXT/SRT/VTT. Propostas de remover pausas e repetições preservam margens da fala e são reversíveis. A correspondência entre palavras e clipes deve acompanhar cortes e mudanças de velocidade ou solicitar realinhamento.

### Agente de áudio contextual

O agente usa a seleção, roteiro, clipes, transcrição, duração-alvo e medições disponíveis. Exemplos: “Crie uma versão de 15 segundos mantendo preço e chamada final”, “Deixe a voz mais clara”, “Reduza a música durante a fala” e “Marque pausas longas para revisar”.

Ciclo: **pedido → escopo → proposta → prévia → aplicar → revisão salva**. Propostas descrevem operações concretas e os alvos: “Locução: reduzir ruído; Música: reduzir volume durante a fala; Saída: ajustar volume percebido”. Oferecer ouvir antes/depois, aceitar item individual, aplicar conjunto ou descartar. O conjunto aceito forma um único grupo de undo.

Comandos simples explicitamente pedidos, como mover um clipe ou reduzir ganho, podem ser aplicados com undo imediato. Reescritas, cortes de conteúdo e substituição de tomadas aceitas exigem revisão contextual. Geração mostra custo estimado no momento pertinente. Sugestões não aceitas não entram na exportação.

O agente não afirma ter ouvido ou medido o que não analisou: transcrição sustenta revisão textual; ruído, clipping e loudness exigem sinal e medições. A revisão mostra itens com tempo e ação, distinguindo “medido”, “sugestão” e “a revisar”, sem nota genérica de qualidade.

Alterações concorrentes não podem ser sobrescritas por uma proposta antiga. O resultado fica ligado à revisão-base e, quando incompatível com a atual, permanece disponível para inserção manual.

### Tratamento e entrega

Três escopos: **Clipe**, **Faixa**, **Saída final**. Clipe concentra corte, ganho e fades; faixa concentra EQ, ruído, compressor, de-esser, gate, panorama e automação; saída concentra loudness e limiter. Efeitos permitem desligar/ligar e restaurar valores. Comparação A/B usa o mesmo intervalo e informa eventual compensação de volume.

Presets orientados ao trabalho: “Voz mais clara”, “Entrevista equilibrada”, “Música de fundo” e “Preparar para vídeo”. Avançado mostra compressor com limiar em dB, proporção, ataque/liberação em ms; EQ com frequência em Hz e ganho em dB. **Compressor de volume** e **Reduzir tamanho do arquivo** são atividades diferentes.

Exportação escolhe sessão ou intervalo, áudio final ou faixas separadas, destino e qualidade. Resumo informa faixas incluídas e mute/solo ativos. Faixas separadas significam renderizar as faixas existentes, não separar instrumentos de uma fonte estéreo. Exportar uma revisão congelada permite continuar editando sem mudar o trabalho em curso.

Formatos planejados: WAV, FLAC, MP3, AAC/M4A e OGG/Opus conforme suporte validado. Mostrar 44,1/48 kHz como opções usuais, bits onde aplicáveis, bitrate para compressão com perdas e mono/estéreo. Aumentar Hz não recupera detalhe perdido. Fontes diferentes convertem para a taxa da sessão preservando duração e tom; definir dither ao reduzir bits.

Prévia e exportação compartilham a descrição dos efeitos. Prévia aproximada é identificada; render de referência valida duração, sincronia, loudness e pico verdadeiro. Medir também o arquivo após codificação. Presets de destino não presumem um único alvo LUFS universal. Salvar na Biblioteca, baixar ou enviar ao vídeo preserva a revisão e a posição de origem.

### Mockup principal revisado

Produzir uma bancada 1440 × 960 com sessão “Campanha primavera · Spot 30s”, cinco faixas, cursor em 00:08.240, locução selecionada e curva de música abaixando durante a fala. Acima, roteiro de voz; à direita, agente com proposta “Melhorar clareza da voz e equilibrar a música”, botões “Ouvir proposta” e “Aplicar”. Nenhum fornecedor/modelo visível. Valores são exemplos de interface, não medições reais.

Usar o shell React existente: estrutura `#0C1519`, bancada `#111E23`, faixas `#19292E`, texto `#E5EFEC`, secundário `#8FA5A0`. Voz em teal, música em violeta, ambiente em azul e efeitos em âmbar. Alertas têm texto e ícone. Tipografia do Studio, tempos tabulares, bordas discretas e timeline com maior peso visual. Evitar waveform gigante redundante acima da montagem.

Variações da mesma interface: criação musical no intervalo; transcrição sincronizada; compressor de faixa; alternativas de tomada; exportação. Estados essenciais: vazio, geração em andamento, resultado em revisão, falha recuperável, arquivo ausente, conflito de salvamento, duração excedida e exportação concluída. “Image 2”, no briefing original, é tratado como referência ao modelo de geração do mockup, não como nome de tela.

### Execução e critérios de aceite

1. **Interface primeiro:** mockup principal e variações; protótipo navegável com dados de exemplo. Validar criação, seleção, movimento, revisão e exportação na mesma bancada.
2. **Núcleo:** fontes imutáveis, oito faixas, clipes, player, corte, fades, ganho/pan, mute/solo, undo, autosave e exportação.
3. **Criação integrada:** voz, música, efeitos e transcrição, habilitando cada atividade somente após validar sua integração real.
4. **Tratamento e agente:** EQ/dinâmica/ruído, automação, propostas, prévia e revisão reversível.
5. **Entrega:** análise final, render de faixas e retorno sincronizado ao vídeo. Expansões: dublagem, extensão musical e separação de fontes.

Aceite: criar um spot com voz, música e efeito sem mudar de página; corrigir transcrição sem alterar áudio; remover pausa com undo; comparar tomadas tocando apenas a ativa; reabrir sessão sem perdas; respeitar escopo do agente; manter destino de geração durante edição concorrente; conferir render e prévia; preservar todas as palavras aceitas. Medir desempenho com dez minutos, oito faixas e vários clipes em equipamento de referência, definindo orçamento de memória, carregamento e resposta antes do lançamento.

### Arquitetura interna e evidência consultada

A [documentação indicada](https://elevenlabs.io/docs/eleven-api/quickstart), consultada nesta revisão, confirma autenticação, SDK e primeira requisição de texto para voz, e aponta guias de streaming, vozes e transcrição. Não valida sozinha geração musical, pistas separadas, extensão ou edição localizada. Cada capacidade exige documentação específica, permissões e teste real antes de habilitação.

ElevenLabs é a base proposta para serviços de áudio; OpenRouter atende ao raciocínio do agente e preparação textual. O código existente de síntese via OpenRouter não demonstra que todas as operações da ElevenLabs passam por ele. Usar adaptadores independentes e API direta quando necessário. Segredos ficam no servidor; tecnologia é exclusiva dos registros operacionais.

Reutilizar a camada de mídia/FFmpeg e as estruturas de projeto, biblioteca, créditos e autenticação mediante validação. A auditoria de 15/09 é evidência histórica: revalidar achados contra o código atual antes de assumir que persistem.

Componentes React propostos: `AudioStudioShell`, `SessionHeader`, `AssetLibrary`, `CreationWorkbench`, `TranscriptEditor`, `AudioAgentPanel`, `SelectionInspector`, `TransportBar`, `MultitrackTimeline`, `AudioClip`, `TakeDrawer`, `Mixer`, `ReviewPanel` e `ExportDialog`. Separar estado da sessão, motor de reprodução e trabalhos assíncronos; waveform com cache e clipes virtualizados.

Contratos: sessão/revisão/schema; fontes imutáveis/metadados; faixas/efeitos/automação; clipes com tempos de fonte e sessão; tomadas/aceite; transcrição com alinhamento; proposta com revisão-base e operações validadas; exportação com snapshot. Trabalhos guardam destino capturado, estado, resultado, erro recuperável e idempotência para evitar duplicação de clipe/cobrança após timeout. Cancelamento preserva resultados já disponíveis. Permissões são verificadas em leitura, geração e exportação.

---

## Proposta inicial — histórico, supersedida pela revisão 2 acima

Data: 23/09/2026  
Fase: definição de produto e interface, antes da implementação  
Base visual: editor de vídeo atual + editor React de imagem  

## Decisão de produto

O áudio será uma nova bancada do Cadu Studio, no mesmo nível de **Editor** e **Vídeos**. O nome principal na navegação será **Áudio**. “Editar áudio” aparece apenas em chamadas de ação e estados vazios.

O módulo deve atender primeiro a três trabalhos frequentes:

1. limpar e preparar um arquivo existente;
2. criar voz, diálogo ou efeito com IA;
3. entregar o áudio no formato e padrão técnico corretos.

Ele não deve nascer como uma DAW completa. A primeira versão é uma bancada editorial simples, rápida e não destrutiva, integrada à biblioteca, aos projetos, às marcas e ao histórico do Studio.

## Proposta de valor

> Envie, gere, trate e entregue áudio pronto para campanha sem sair do projeto.

A referência da ElevenLabs reforça quatro capacidades relevantes para o Studio: geração de fala integrada ao fluxo criativo, dublagem e localização, clonagem de voz com governança e diálogo preliminar para prototipação. O Cadu deve incorporar esses trabalhos dentro do contexto de campanha, sem reproduzir a interface da ElevenLabs.

## Arquitetura funcional

### Camada de experiência

- React, seguindo o editor de imagem já existente.
- Mesma barra superior do Studio: Criar, Editor, Vídeos, **Áudio**, Analyzer e Biblioteca.
- Projeto, marca, créditos, sessões, histórico e biblioteca continuam compartilhados.
- O editor de vídeo abre um item de áudio nesta bancada sem duplicar o arquivo.
- Uma edição salva pode voltar ao vídeo como nova versão ou substituir somente a instância selecionada.

### Camada de IA

- **ElevenLabs**: motor preferencial para voz, dublagem, clonagem autorizada, desenho de voz e efeitos quando a capacidade estiver disponível no contrato da conta.
- **OpenRouter**: orquestração de texto e raciocínio — preparação de roteiro, limpeza textual, pronúncia, versões de duração, direção de voz, resumo das alterações e fallback de síntese já suportado pelo serviço atual.
- Criar um adaptador de provedor. A interface trabalha com capacidades (`speech`, `dubbing`, `voice_clone`, `sound_effect`), não com nomes fixos de endpoints.
- Revisão 2: fornecedor e modelo ficam exclusivamente nos registros internos; a interface mostra atividade, custo estimado, duração e resultado.
- Nenhuma voz é clonada sem consentimento registrado, finalidade, responsável e escopo de uso.

### Camada de processamento

- FFmpeg para operações determinísticas: corte, conversão, resample, canais, fades, normalização, compressão, limiter e exportação.
- Waveform persistida em três níveis de detalhe para zoom fluido.
- Edição não destrutiva: o original nunca é alterado; cada entrega é uma versão.
- Jobs assíncronos para transcrição, dublagem, geração, redução de ruído e exportações pesadas.

## Escopo funcional

### P0 — primeira entrega utilizável

- Upload e importação da Biblioteca: MP3, WAV, M4A, AAC, OGG e FLAC.
- Player com waveform, régua de tempo, cursor, zoom, seleção de trecho e loop.
- Cortar início/fim, dividir no cursor, excluir seleção e inserir silêncio.
- Undo/redo e histórico de versões.
- Ganho, mute, fade-in e fade-out com alças visuais.
- Normalização por loudness com presets: voz, podcast, social e vídeo.
- Conversão de formato, sample rate (Hz), bit depth, bitrate, mono/estéreo e canais.
- Exportação WAV, MP3, AAC/M4A, OGG e FLAC.
- Geração de voz a partir de texto com voz, idioma, ritmo e prévia.
- Limpeza do texto falado antes da síntese; instruções e marcações não podem ser narradas.
- Medição real da duração gerada; nunca cortar fala silenciosamente.
- Salvar na Biblioteca, anexar ao projeto e enviar para o editor de vídeo.

### P1 — tratamento profissional acessível

- Redução de ruído, remoção de silêncio e detecção de fala.
- Equalizador simples: graves, presença e brilho; modo avançado com bandas.
- Compressor de dinâmica com presets, ganho de saída e redução visível.
- Limiter, de-esser e gate.
- Medidores de pico, LUFS integrado e alerta de clipping.
- Transcrição sincronizada e edição do áudio pelo texto.
- Ducking automático de música sob voz.
- Comparação A/B com loudness igualado.
- Lote de conversões e exportações.

### P2 — IA e localização

- Dublagem com preservação de identidade e estilo, revisão por falante e idioma.
- Diálogo preliminar com múltiplos personagens.
- Biblioteca de vozes da marca e vozes aprovadas por projeto.
- Clonagem profissional somente com fluxo de consentimento e auditoria.
- Efeitos sonoros gerados por descrição.
- Reescrita automática para caber em duração-alvo, sempre com aprovação do texto.

### Fora da primeira versão

- Gravação multicanal de estúdio.
- Plugins VST/AU.
- Automação avançada por curvas para todos os parâmetros.
- Edição espectral destrutiva.
- Mixagem de dezenas de faixas como uma DAW completa.

## Modelo mental da interface

O elemento memorável será a **waveform central ampla**, tratada como o “canvas” do áudio. Todo o restante fica contido e funcional.

```text
┌ Cadu Studio | Criar | Editor | Vídeos | Áudio | Analyzer | Biblioteca ┐
│ Projeto / marca                 Salvo        Exportar        Conta      │
├──────────────┬────────────────────────────────────┬─────────────────────┤
│ Biblioteca   │ faixa.wav               00:18.420 │ Propriedades        │
│              │                                    │                     │
│ Áudios       │        W A V E F O R M             │ Básico              │
│ Vozes IA     │ ────────╱╲╱╲──╱╲╱╲─────────────   │ Tratamento          │
│ Anteriores   │       [ trecho selecionado ]       │ Voz e IA            │
│              │                                    │ Entrega             │
│ + Enviar     │  ◀  ▶  1×   Loop   Zoom  −  +     │                     │
├──────────────┴────────────────────────────────────┴─────────────────────┤
│ Faixa 1  [M][S]  ┃ waveform editável e fades                         │
│ Texto/transcrição ┃ blocos sincronizados                               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Regiões

**Barra superior**  
Nome do arquivo/sessão, projeto e marca, status de salvamento, undo/redo, comparação, compartilhar e exportar.

**Rail esquerdo**  
Busca e filtros. Seções: arquivos do projeto, Biblioteca, vozes e gerações, versões anteriores. Upload sempre visível.

**Canvas central**  
Waveform principal, régua, seleção, playhead, marcadores, zoom e transporte. A duração e o trecho selecionado ficam próximos ao cursor, não em um painel distante.

**Timeline inferior**  
Revisão 2: oito faixas de áudio no núcleo inicial, com tomadas e geração por intervalo. Transcrição é uma visão sincronizada, não uma faixa sonora.

**Inspetor direito**  
Quatro abas com divulgação progressiva:

- **Básico**: ganho, velocidade, pitch preservado, fades e canais.
- **Tratamento**: ruído, EQ, compressor, de-esser, limiter e loudness.
- **Voz e IA**: gerar fala, transcrever, dublar, idioma, voz e direção.
- **Entrega**: formato, sample rate, bitrate/bit depth, canais e estimativa de tamanho.

## Fluxos principais

### 1. Tratar um arquivo

Enviar/selecionar → análise técnica → waveform → selecionar trecho → aplicar preset → comparar A/B → verificar loudness/clipping → exportar ou salvar versão.

### 2. Gerar uma locução

Abrir “Voz e IA” → escrever/importar roteiro → escolher idioma e voz → ouvir amostra → gerar prévia → revisar texto realmente enviado → aceitar na timeline → tratar → exportar.

### 3. Converter formato

Selecionar um ou vários arquivos → escolher preset de entrega → confirmar parâmetros e tamanho estimado → converter → salvar na Biblioteca ou baixar pacote.

### 4. Voltar ao vídeo

Abrir áudio vindo do vídeo → editar sem alterar o original → “Enviar ao vídeo” → escolher nova faixa ou substituir instância → manter o mesmo ponto de sincronia.

## Estados essenciais para o mockup

O primeiro conjunto visual deve conter quatro telas; a **Tela 2** será o mockup principal de alta fidelidade.

1. **Vazio / entrada** — convite para enviar áudio, gerar voz ou escolher da Biblioteca.
2. **Editor carregado** — waveform, trecho selecionado, timeline e inspetor “Tratamento” aberto. Esta é a melhor tela para comunicar o produto.
3. **Gerar voz** — roteiro, voz, idioma, direção, amostra e custo estimado.
4. **Exportar** — comparação entre origem e saída, formato, Hz, bitrate/bit depth, canais, loudness e tamanho.

Estados secundários: analisando, processando, falha recuperável, clipping, fala maior que a duração-alvo, sem consentimento para voz, exportação concluída e trabalho em segundo plano.

## Direção visual do mockup — Tela 2

### Tokens

- `Ink`: `#0C1519` — estrutura e barra superior.
- `Workbench`: `#111E23` — superfícies do editor.
- `Track`: `#19292E` — faixas e painéis selecionáveis.
- `Signal`: `#6EE1D1` — waveform, playhead ativo e medições seguras.
- `Voice`: `#9B7BFF` — ações de IA e regiões geradas.
- `Warning`: `#F0B45A` — pico, duração e revisão necessária.
- `Text`: `#E5EFEC`; `Muted`: `#8FA5A0`.

### Tipografia

- Manter a família já usada pelo Studio para continuidade.
- Números de tempo usam algarismos tabulares.
- Rótulos em sentence case; evitar caixa alta decorativa.
- Hierarquia compacta: 12–14 px em controles, 16–18 px em títulos locais.

### Forma e comportamento

- Waveform em teal com trechos de voz IA em violeta; seleção usa camada translúcida, não um cartão.
- Cantos de 6–10 px em controles; painéis não precisam parecer cartões independentes.
- Divisores redimensionáveis como no editor de vídeo.
- Sem gradiente ornamental. Cor comunica sinal, IA, alerta e seleção.
- Animação somente no playhead, processamento e abertura contextual.
- Foco de teclado visível; atalhos mostrados no tooltip.

### Conteúdo real do mockup

- Arquivo: `locucao_campanha_primavera.wav`
- Duração: `00:18.420`
- Seleção: `00:04.280 — 00:09.760`
- Medição: `-16.1 LUFS`, pico `-1.2 dB`, `48 kHz`, `24-bit`, mono.
- Preset aplicado: `Locução para vídeo`.
- Tratamentos visíveis: redução de ruído 32%, compressor “Voz clara”, de-esser leve e limiter -1 dB.

## Contratos mínimos de dados

```json
{
  "source": {"id": "...", "duration": 18.42, "sample_rate": 48000, "channels": 1},
  "edit": {"source_in": 0, "source_out": 18.42, "timeline_start": 0, "rate": 1},
  "mix": {"gain_db": 0, "fade_in": 0.15, "fade_out": 0.25, "muted": false},
  "processing": {"denoise": {}, "eq": {}, "compressor": {}, "deesser": {}, "limiter": {}},
  "voice": {"provider": "...", "voice_id": "...", "language": "pt-BR", "direction": "..."},
  "delivery": {"format": "wav", "sample_rate": 48000, "bit_depth": 24, "channels": "mono"}
}
```

Todo projeto precisa guardar versão do schema, proveniência do áudio, provedor/modelo utilizado, consentimento quando aplicável e custo da operação.

## Fases de implementação

### Fase 0 — protótipo validável

- Mockups das quatro telas e protótipo clicável da Tela 2.
- Teste com cinco tarefas: cortar, normalizar, gerar voz, converter e devolver ao vídeo.
- Validar vocabulário: “Hz”, “sample rate”, “compressão” e “normalização” devem ter ajuda curta em linguagem simples.

### Fase 1 — fundação técnica

- Contrato temporal único e testes de conversão fonte ↔ timeline.
- Serviço de assets/versões e waveform.
- Adaptador de provedor e capability discovery.
- Tela React com upload, player, corte, fades, undo e exportação.

### Fase 2 — tratamento e voz

- Loudness, compressor, limiter, EQ e redução de ruído.
- Geração de fala, limpeza do texto, duração real e voz explícita.
- Custos, jobs, falhas recuperáveis e biblioteca.

### Fase 3 — integração e inteligência

- Retorno ao editor de vídeo com sincronia preservada.
- Transcrição, edição por texto, ducking e dublagem.
- Vozes de marca e governança de consentimento.

## Critérios de aceite do MVP

- Um arquivo de 10 minutos abre e navega sem travar a interface.
- Corte, seleção, fades e exportação reabrem com os mesmos tempos.
- Prévia e arquivo exportado têm duração e loudness compatíveis dentro da tolerância definida.
- O original permanece recuperável.
- A fala gerada contém exatamente o texto aprovado e nunca é truncada silenciosamente.
- Parâmetros técnicos têm unidade e limites claros.
- O usuário consegue concluir os três trabalhos principais sem abrir configurações avançadas.
- Acessível por teclado e utilizável em 1280 px; em telas menores, Biblioteca e Inspetor viram drawers.

## Próximo passo recomendado

Criar a **Tela 2 — Editor carregado** em alta fidelidade na largura de 1440 px, usando o shell atual do Studio e o conteúdo real definido acima. Depois validar a hierarquia em uma versão responsiva de 1024 px antes de desenhar os demais estados.

## Revisão financeira — regra obrigatória

Todo custo de LLM, geração, transcrição, voz, música, agente e refinamento de roteiro é custo do cliente e deve ser tokenizado, reservado e debitado. O CentralX não absorve esse custo. O débito deve acontecer mesmo quando a operação é iniciada pelo agente, desde que gere processamento externo ou uma nova revisão.

Antes de executar uma atividade paga, a interface mostra: tokens estimados, saldo disponível, faixa de variação, quantidade de gerações e o que será cobrado. Depois, liquida pelo consumo real retornado pelo provedor, registra tentativas e devolve a reserva não utilizada. Cada operação tem chave idempotente para impedir cobrança duplicada em timeout ou retry.

### O que entra no tokenizador

- refinamento ou reescrita de roteiro;
- análise do roteiro pelo agente;
- transcrição e identificação de falantes;
- texto para voz, nova tomada e alternativas;
- geração de música, ambiente ou efeito;
- dublagem, tradução e adaptação de duração;
- propostas do agente que consultam ou alteram conteúdo com LLM;
- análise automática de qualidade, quando usar modelo externo;
- processamento de mídia que usar serviço pago, fila externa ou análise não local.

### O que pode ter custo zero de IA

Upload, leitura de arquivo, corte local, divisão, mover clipe, undo, mute, solo, fades, volume, pan e render local. Ainda assim, se a operação usar worker pago, armazenamento faturável, análise externa ou gerar uma nova saída persistida, ela recebe custo técnico e é tokenizada pela regra de edição do Studio.

### Centro da tela: roteiro/canvas e agente

O “canvas” da área superior é uma bancada de roteiro, não um campo solto. À esquerda ficam blocos editáveis do roteiro (abertura, oferta, prova, encerramento), duração de cada bloco e vínculo com o clipe na timeline. À direita fica o agente contextual, com conversa, refinamentos, diferenças antes/depois, custo em tokens e ações “Ouvir proposta”, “Aplicar” e “Descartar”. A timeline multifaixa permanece abaixo e recebe cada bloco aceito como clipe.

O agente nunca aplica uma reescrita ou geração paga sem exibir o custo e a alteração prevista. Refinamentos locais de texto podem ser revisados antes do débito; o usuário confirma a execução quando a ação chamar LLM ou geração de mídia.

### Base visual confirmada no Editor React atual

O shell existente usa fundo `#080D12`, navegação `#0B1117`, painéis `#10171D`, superfícies elevadas `#151E25`, texto `#E8EDF2`, texto secundário `#98A3AD` e roxo principal `#7C5CFF`, com realce claro `#A995FF`. O prompt do mockup deve preservar a marca Cadu Studio, a barra superior de 64 px, o layout de três colunas, bordas discretas, tema escuro e o medidor de créditos já presente.

## Matriz de custos para demandas de marketing

O Studio deve mostrar antes de iniciar: custo técnico estimado, créditos reservados e valor de referência no plano ativo. O job liquida pelo consumo medido e devolve o saldo não usado. Upload, corte, fades, volume, pan, mute/solo, undo e render local não devem parecer uma nova geração de IA; só geram consumo quando acionam análise, fila, armazenamento ou processamento externo.

| Demanda | Unidade de cotação | Regra de custo | Cobrança inicial |
|---|---|---|---:|
| Upload/importação | arquivo | normalmente sem custo técnico | 0 créditos; armazenamento conforme política |
| Corte, divisão, fades, ganho, pan, mute/solo | minuto processado + faixa | local: zero; worker se necessário | edição simples: mínimo de 1 crédito |
| Conversão de formato, Hz, bits e canais | minuto renderizado + tamanho | transcodificação e armazenamento | matriz de edição/conversão: 2× do custo técnico |
| Redução de ruído e remoção de silêncio | minuto analisado/renderizado | processamento de áudio e fila | 2×; uma revisão por aplicação |
| EQ, compressor, de-esser, limiter e loudness | minuto/faixa renderizada | processamento local ou worker | 2×; por revisão, não por clique |
| Transcrição | minuto de áudio + texto | serviço de fala para texto | custo medido + margem de mídia |
| Voz gerada | caracteres aprovados + duração medida | síntese de fala | custo real + margem de mídia 6× |
| Regravação de trecho | caracteres do trecho | síntese incremental | cobrar apenas o trecho |
| Música, ambiente ou efeito gerado | segundo ou clipe | geração + armazenamento | custo real + margem de mídia 6× |
| Mixagem multifaixa e ducking | minutos × faixas ativas | análise e render | 2× do custo técnico |
| Spot de áudio 15/30/60 s | pacote composto | voz/música/efeitos + mix + export | soma das atividades, discriminada |
| Áudio para vídeo | duração × faixas | áudio, mix e transcodificação | separar do custo de geração do vídeo |
| Áudio para banner animado | duração × formatos | criação opcional + mix + exports | uma criação + conversões adicionais |
| Exportar novamente sem alteração | arquivo/formato | normalmente render local | zero ou mínimo técnico |
| Faixas separadas | minuto × faixas incluídas | uma saída por faixa existente | 2× do processamento incremental |

Esses multiplicadores seguem a matriz comercial atual do projeto: edição/conversão em 2× e mídia gerada em 6×. Não são preços fixos em reais; o valor deve usar o preço unitário do plano ativo.

### Estimativa de locução

Usar caracteres aprovados, não uma contagem de palavras do agente. A fórmula de referência já existente considera aproximadamente `caracteres × custo de entrada + max(80, caracteres × 2) × custo de saída`. Com os parâmetros atuais do código e câmbio hipotético de R$ 5,50:

| Roteiro | Custo técnico ilustrativo antes da margem | Uso típico |
|---:|---:|---|
| 300 caracteres | US$ 0,0123 ≈ R$ 0,07 | locução curta |
| 750 caracteres | US$ 0,0308 ≈ R$ 0,17 | spot de 30 s, conforme ritmo |
| 1.500 caracteres | US$ 0,0608 ≈ R$ 0,33 | locução longa ou várias frases |

São referências do cotador local, não garantia de preço de fornecedor. A tela deve mostrar, por exemplo, “420 caracteres · 00:18 estimados · 1 tomada”; depois, o extrato registra duração, uso retornado, tentativas e alternativas rejeitadas.

### Pacotes visíveis ao usuário

- **Spot 15 s:** roteiro/voz + cama ou efeito + mix + WAV/MP3.
- **Spot 30 s:** roteiro/voz + música + até três efeitos + mix + saída para áudio e vídeo.
- **Áudio para vídeo:** locução ou trilha + ducking + mix no intervalo do vídeo + retorno sincronizado.
- **Banner animado:** áudio curto + mix + exportações para as durações e formatos solicitados.
- **Tratamento de arquivo:** limpeza, dinâmica, loudness e conversão, sem geração de conteúdo.

Pacote ajuda a explicar a atividade; o débito permanece detalhado por etapa e revisão. Não cobrar cliques em controles que não criaram nova revisão nem duplicar a locução quando o mesmo áudio for reutilizado no vídeo.
