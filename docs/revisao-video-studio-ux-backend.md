# Revisão do Video Studio: experiência criativa e backend

14/09/2026. Revisão estática do código local; não é uma homologação da aplicação publicada nem uma comparação verificada com versões atuais de produtos concorrentes. Complementa `plano-video-studio.md`.

## Diagnóstico

A estrutura visual já oferece biblioteca, preview, ferramentas e timeline, mas o modelo funcional ainda é um editor de um clipe com uma trilha adicional. O storyboard orienta a geração por IA; ele não monta os vídeos da timeline. A prioridade é tornar o resultado previsível, preservar o trabalho e permitir montar uma campanha antes de ampliar o catálogo de efeitos.

O usuário precisa responder sem dúvida: qual material estou alterando, o que será salvo, o que exige nova geração e o que sairá no MP4?

## Problemas confirmados no código

| Prioridade | Evidência | Impacto criativo | Correção e aceite |
|---|---|---|---|
| Alta | `mc-cadu-video.js:448` troca `activeClipId` sem restaurar uma edição própria do clipe; `studio.js:15` não inclui esse ID no histórico | Corte, som e efeitos de A podem permanecer em B; desfazer não recupera a fonte correspondente | Vincular edição e histórico à fonte/composição. Testar A editado → B → desfazer → recarregar, conferindo fonte e ajustes |
| Alta | `studio.js:201–225` apaga a identificação do job em qualquer erro do POST e repete consultas após erros sem limite | Uma queda de rede pode gerar exportação duplicada; erro permanente pode deixar o editor esperando indefinidamente | Preservar ID quando resultado for incerto, consultar antes de reenviar, tratar autenticação/404 e oferecer retomar/tentar novamente |
| Alta | `creative_media/studio.py:26,251–303` usa executor e limite por processo, sem recuperação de jobs | Reiniciar servidor pode interromper entrega; concorrência cresce com número de workers | Fila durável, estado persistido, revisão da composição, recuperação e limite global. Testar reinício durante renderização |
| Média | `mc-cadu-video.js:336` invalida orçamento e agenda cotação para toda edição | Alterar volume ou corte provoca atividade de geração sem necessidade | Separar alterações da composição e parâmetros de geração. Volume/corte não devem consultar cotação |
| Média | `studio.js:178–195` sincroniza um segundo player com correções de até 200 ms e ignora erros de reprodução | Música pode falhar sem explicação; preview não possui tratamento explícito para buffering | Relógio de reprodução coordenado, tratamento de espera/seek/erro e comparação entre preview e render. Não repetir `play()` sem controle de tentativa |
| Média | `creative_media/studio.py:133–176` converte upload e calcula waveform durante a requisição; GET lê todos os JSONs | Biblioteca grande e envio demorado comprometem resposta da tela | Upload com progresso, processamento em job, estado por arquivo, paginação e busca no servidor |
| Média | `workspace.js:62–92` usa seek por clique e cortes em décimos; `studio.js:14` mostra segundos inteiros | Ajustes finos ficam difíceis de conferir | Arraste contínuo do playhead, tempo com quadros, avanço por quadro e encaixe na base de tempo da fonte |
| Média | `mc-cadu-video.js:638,672` usa confirmação nativa; `studio.js:201` exporta diretamente | Exclusão não explica contexto; exportação não permite revisar entrega | Diálogo acessível de exclusão com nome/impacto e modal de exportação com revisão, duração e formato |

Os cenários acima são deduzidos dos caminhos de execução; os testes de reprodução correspondentes ainda precisam ser adicionados/executados. Não confundir achados de leitura com falhas já reproduzidas em produção.

## Fluxo proposto para quem cria

1. **Começar:** abrir projeto recente, importar materiais ou gerar com IA. Mostrar um próximo passo útil no estado vazio.
2. **Gerar:** painel Seedance mantém configurações. Antes do envio, resumir referências, formato, duração, áudio e custo. O resultado entra na biblioteca sem substituir silenciosamente o trabalho aberto.
3. **Montar:** arrastar imagens e vídeos para uma sequência real; dividir, duplicar, mover, aparar e excluir. Mostrar duração total da entrega.
4. **Dar acabamento:** selecionar um item abre suas propriedades. Sem seleção, mostrar propriedades do projeto. Áudio, texto e efeitos pertencem ao item ou faixa identificados.
5. **Revisar:** reproduzir a composição, conferir voz/música, texto legível e áreas seguras. Permitir comparar antes/depois dos efeitos.
6. **Entregar:** escolher preset, nome e qualidade, revisar som e duração, exportar uma revisão identificada e acompanhar em segundo plano.

Manter a biblioteca e a timeline disponíveis durante o trabalho. Reservar modais para decisões curtas; ajustes frequentes continuam no inspector. Diferenciar explicitamente “Próxima geração” de “Edição do vídeo”.

## Frontend, efeitos e velocidade

| Área | Próxima entrega útil | Critério de qualidade |
|---|---|---|
| Timeline | Vários clipes, seleção, divisão, duplicação, encaixe, zoom até seleção, atalhos espaço/I/O e avanço por quadro | Operações reversíveis e resultado exportado igual à sequência |
| Efeitos | Exposição/brilho, contraste, saturação, enquadramento e escala; ativar/desativar e restaurar cada efeito | Preview e FFmpeg compartilham parâmetros, limites e ordem; testes com imagens de referência |
| Transições | Corte seco, dissolvência e entrada/saída com duração visível | Transição pertence à junção entre clipes; duração total e áudio permanecem coerentes |
| Animações | Presets discretos de entrada de texto e aproximação de imagem, depois keyframes | Animação aparece na timeline e no arquivo, não apenas no CSS da interface |
| Velocidade do vídeo | Controle de velocidade com duração resultante e opção de preservar tom | Atualizar sincronismo, áudio, cortes e exportação juntos; não limitar a implementação a `playbackRate` |
| Som | Música, voz e efeitos independentes; mover/cortar, mute/solo, fades visuais e redução da música durante fala | Uma voz nova não substitui a música; waveform representa trecho/posição reais |
| Texto e legendas | Título, oferta, CTA, estilos da marca, transcrição revisável e legendas temporizadas | Texto editável como camada; imagem com texto incorporado não promete edição desse texto |
| Acabamento | Estados hover/foco/seleção claros, tooltips com atalhos, scroll por painel e espaço suficiente para preview | Operação por teclado, foco visível, contraste e responsividade verificados no shell completo |

### Modais necessários

- **Exportação:** nome, preset, resolução efetivamente suportada, duração, presença de áudio e revisão que será renderizada. Mensagem de erro específica com retomada.
- **Geração:** confirmação resumida do custo e parâmetros antes da operação paga; configurações continuam no painel.
- **Exclusão:** item identificado e consequência, com recuperação quando disponível.
- **Conflito de salvamento:** preservar a versão local e permitir comparar/restaurar ou salvar uma cópia.

Todos devem gerir foco inicial, ciclo de Tab, Escape quando aplicável, retorno de foco, estado de envio e erros. Não usar modais para sliders, busca de mídia ou controles de reprodução.

### Rapidez percebida e uso de recursos

- Atualizar somente a propriedade e a faixa afetadas; agrupar alterações de um arraste em uma ação de histórico.
- Abortar buscas obsoletas, usar debounce e evitar reconstruir a biblioteca sonora ao ajustar efeitos.
- Carregar miniaturas e waveform sob demanda; não pré-carregar todos os vídeos.
- Usar proxies de preview para arquivos pesados, mantendo a fonte original no render.
- Pausar trabalho visual em aba oculta; retomar corretamente após navegação e restauração da página.
- Definir metas e medi-las: resposta visual de comandos abaixo de 100 ms no dispositivo de referência; testar projetos com 20 clipes e bibliotecas com centenas de itens. São metas propostas, não medições atuais.

## Backend necessário para sustentar a interface

1. **Composição versionada:** projeto, fontes, faixas, itens com entrada/saída/posição, efeitos e revisão. Contrato validado e migração dos projetos atuais.
2. **Render determinístico:** consumir a revisão imutável da composição. Normalizar base de tempo, dimensões e áudio; registrar preset e resultado.
3. **Jobs recuperáveis:** geração, importação, waveform, locução, transcrição e exportação com estados claros, erros específicos e retentativas idempotentes.
4. **Áudio verificável:** detectar se o vídeo gerado contém faixa sonora e apresentar seu estado. A opção de áudio enviada ao provedor, sozinha, não comprova que o resultado tem som.
5. **Capacidades do provedor:** validar combinações de modelo/duração/resolução/áudio no servidor. Opções indisponíveis precisam explicar a restrição no painel.
6. **Mídia organizada:** paginação, metadados, fonte/licença quando houver catálogo, favoritos, limpeza de temporários e proteção contra exclusão de fonte em uso.
7. **Observabilidade:** ligar falha à geração/exportação e revisão, com métricas de tempo, fila e erros; mensagens úteis ao criativo sem expor detalhes internos.

## Ordem de execução revisada

1. Corrigir troca de fonte/histórico, recuperação de exportação e recotações desnecessárias.
2. Consolidar composição versionada, jobs duráveis e revisão exportada.
3. Entregar montagem de vários clipes e áudio independente, com testes ponta a ponta.
4. Adicionar texto/legendas, cor, enquadramento, transições e velocidade.
5. Finalizar modais, presets de exportação, biblioteca escalável e validação de desempenho/acessibilidade.

Cada etapa precisa provar: criar → editar → desfazer → salvar → reabrir → exportar. Para áudio, também comparar o preview ao arquivo e executar uma geração real autorizada no provedor. A homologação final precisa ocorrer com autenticação, shell e infraestrutura reais.
