# Plano final — Cadu Video Studio

Atualizado em 14/09/2026. Rota: `/parametros/modelagem-criativos/video`.

Este documento consolida o escopo pedido, a implementação local e a sequência restante. O planejamento está fechado; o estúdio completo ainda não está implementado nem publicado por esta tarefa.

## Objetivo e decisões

Criar um estúdio de vídeos publicitários com geração assistida por IA, montagem, cortes, áudio, textos, efeitos, animações e exportação. Usar a organização da referência enviada: biblioteca à esquerda, preview central, ferramentas à direita e timeline inferior. Interações e acabamento inspirados em editores profissionais, com identidade Cadu.

- Frontend: templates HTML existentes, Tailwind com prefixo `vs-`, CSS próprio e JavaScript vanilla em módulos.
- Não adicionar React ou DaisyUI ao editor.
- Backend: Python; processamento determinístico com FFmpeg/FFprobe.
- Geração: integração existente com modelo configurado no servidor, apresentada na aba Seedance.
- Diferenciar parâmetros da próxima geração e ajustes de um clipe pronto.
- Biblioteca, salvamento, exportação e acompanhamento assíncronos, sem recarregar a página.
- Cada controle funcional precisa produzir resultado correspondente no arquivo exportado.
- Textos incorporados a imagens não são camadas editáveis; novas sobreposições serão camadas próprias.

## Estado real da implementação

| Área | Implementado localmente | Pendência |
|---|---|---|
| Interface | Tema claro/escuro, painéis redimensionáveis, foco, rolagem interna, Tailwind dedicado, foco de teclado e movimento reduzido | Validação com o shell completo publicado e testes ampliados de dispositivos |
| Biblioteca visual | Peças e clipes da integração existente, busca, miniaturas compactas e lazy loading | Upload de vídeo, uploads múltiplos, paginação, pastas, favoritos e filtros por campanha |
| Biblioteca sonora | Upload de áudio até 25 MB/10 min, conversão AAC, categorias, reprodução, waveform calculada e armazenamento por marca | Catálogo licenciado, filtros avançados, paginação, favoritos e edição de metadados |
| Geração | Aba Seedance com modelo do servidor, proporção, duração, qualidade/resolução, movimento, intensidade, instruções, som e seed | Verificação real no provedor com custo e observação do áudio produzido |
| Áudio padrão | Novos projetos usam ambiente; escolha explícita de silêncio é preservada; player do estúdio não força mute | Confirmar capacidades efetivas de outros modelos configurados e do fallback |
| Edição de vídeo | Corte de um clipe por campos, alças e marcadores; régua, playhead e zoom | Montagem de vários clipes, divisão, duplicação, exclusão com fechamento de espaço e encaixe por quadro |
| Efeitos | Preto e branco, espelhamento e fades de entrada/saída | Cor, enquadramento, escala, rotação, velocidade, transições entre clipes e keyframes |
| Áudio da edição | Volume original + uma trilha adicional, offset, loop e fades, prévia sincronizada | Várias faixas independentes, mover/dividir áudio, desvincular som do vídeo, medidor e ducking configurável |
| Locução | Fluxo existente de locução separada na geração; correção na mixagem e preservação da duração | Gerar/regenerar locução isoladamente e inserir como item independente na timeline |
| Texto e legendas | Roteiro existente para geração | Camadas de texto, tipografia, animação, transcrição, legendas temporizadas e SRT |
| Persistência | Projeto existente guarda edição e seed; histórico de undo/redo em memória | IDs de projetos, vários projetos por marca, schema de composição, revisões concorrentes e migração |
| Exportação | MP4 de um clipe com corte, trilha e efeitos; execução assíncrona, status e download; ID de requisição evita duplicação | Composição completa, presets de saída, histórico de revisões, fila durável e retenção de ativos |

A sequência de cenas existente é um storyboard de entrada da IA. Ela ainda não constitui uma montagem determinística de vários vídeos. A timeline de edição atual representa um clipe pronto e uma trilha adicional.

## Entrega local e arquivos

### Frontend

- `templates/parametros/_mc_video.html`: estrutura do editor e painel Seedance.
- `templates/parametros/modelagem_desk.html`: carregamento do CSS exclusivo.
- `static/css/tailwind/video-studio.input.css`: fonte dos estilos.
- `static/css/video-studio.css`: CSS compilado.
- `tailwind.studio.config.js`: utilitários com prefixo e sem preflight/DaisyUI.
- `static/js/cadu-video/studio.js`: áudio, efeitos, undo/redo e exportação.
- `static/js/cadu-video/workspace.js`: painéis, aparência, régua, zoom e corte por gestos.
- `static/js/cadu-video/seedance-panel.js`: parâmetros consultados no servidor.
- `static/js/mc-cadu-video.js`, `cadu-video/state.js`, `cadu-video/render.js`: integração com o projeto existente.
- `static/js/trocr/animate-player.js`: comportamento de som e reprodução no estúdio.

Caminhos acima são relativos a `aicentralv2/`, exceto a configuração Tailwind, que fica na raiz do repositório.

Build: `npm run build:studio`. O comando `npm run build` também inclui esse build.

### Backend

- `creative_media/studio.py`: biblioteca sonora, parâmetros disponíveis, processamento e exportação.
- `creative_media/planner.py`: validação e encaminhamento da seed.
- `creative_media/transcode.py`: correção da mixagem de locução.
- `creative_format_lab/swap_session.py`: persistência dos ajustes do vídeo e seed.
- `creative_format_lab/swap_routes.py`: registro das rotas.

Rotas novas, com prefixo `/parametros/api/format-lab/studio`:

| Método | Caminho | Função |
|---|---|---|
| GET | `/capabilities` | Modelo e opções configuradas no servidor |
| GET/POST | `/sounds` | Listar ou enviar sons da marca |
| GET | `/sounds/<id>` | Reprodução autenticada |
| POST | `/exports` | Exportar uma edição de clipe |
| GET | `/exports/<id>` | Acompanhar resultado |
| GET | `/exports/<id>/content` | Baixar MP4 |

O controle de acesso segue as APIs existentes do estúdio: usuários admin/superadmin autenticados, CSRF nas mutações e resolução de mídia por marca. IDs externos não são aceitos como URLs arbitrárias de renderização.

## Sequência restante de implementação

### 1. Consolidar projetos e processamento — prioridade alta

1. Criar projeto com ID próprio, `schema_version` e revisão monotônica.
2. Persistir uma composição estruturada em vez de somente `scene_ids` e ajustes de um clipe.
3. Migrar o projeto existente de cada marca preservando os dados atuais.
4. Implementar atualização condicional por revisão e mensagem recuperável de conflito.
5. Vincular cada exportação à revisão imutável da composição.
6. Mover exportações para fila durável/reutilizar a infraestrutura de jobs existente; sobreviver à reinicialização de processos.
7. Definir limites por usuário/marca, concorrência global, retenção, limpeza de temporários e exclusão recuperável.
8. Corrigir/validar troca de clipe e troca de marca durante salvamento e geração, sem sobrescrever edições nem mostrar resultado de outro contexto.

Aceite: dois projetos da mesma marca são independentes; reabrir recupera a composição; uma exportação não muda se o usuário continuar editando; interrupções não deixam acompanhamento infinito.

### 2. Montagem de vários clipes — prioridade alta

1. Upload de vídeos e imagens com metadados, miniaturas e prévias leves.
2. Faixa principal de vídeo com itens independentes da biblioteca.
3. Cada item terá `id`, `asset_id`, `start_frame`, `duration_frames`, `source_in` e `source_out`.
4. Usar taxa de quadros de projeto explícita e conversão consistente das fontes.
5. Arrastar, selecionar, aparar, dividir, duplicar e excluir.
6. Oferecer exclusão simples e exclusão com fechamento do espaço.
7. Encaixar bordas e playhead, respeitando limites das fontes.
8. Compor sequências de imagens e vídeos com FFmpeg; a duração será calculada pela composição.
9. Uma única cena poderá ser exportada; exigência de múltiplas cenas fica limitada ao fluxo de IA que precisar delas.

Aceite: montar três mídias, dividir a segunda, reordenar e exportar a sequência exata com áudio sincronizado.

### 3. Áudio multifaixa e biblioteca completa — prioridade alta

1. Separar áudio original, música, locução e efeitos em itens endereçáveis.
2. Mover, aparar, dividir, duplicar, silenciar e bloquear faixas.
3. Desvincular o áudio de um vídeo sem perder a origem.
4. Criar medidor, ajustes de volume e envelope por item.
5. Reduzir música durante a fala com controle de intensidade.
6. Gerar locução isolada e permitir substituir/regenerar um trecho.
7. Adicionar busca paginada, filtro por categoria, favoritos, origem e licença dos sons.
8. Integrar catálogo licenciado somente quando houver fonte aprovada e disponível; nenhum catálogo comercial foi adicionado nesta entrega.

Aceite: misturar vídeo, música, duas locuções e um efeito; a prévia e o MP4 devem conter os mesmos trechos e níveis de volume.

### 4. Texto e legendas — prioridade alta

1. Camada de texto com conteúdo, fonte, tamanho, peso, cor, fundo e alinhamento.
2. Posição, escala e duração ajustáveis no preview e na timeline.
3. Guias de alinhamento e áreas seguras.
4. Fontes consistentes entre navegador e renderizador.
5. Transcrição vinculada ao áudio; edição dos textos e dos intervalos.
6. Exportar legendas incorporadas e arquivo SRT.
7. Não confundir texto editável sobreposto com texto já gravado na peça original.

Aceite: inserir uma oferta, ajustar seu intervalo, corrigir uma legenda e confirmar ambos no MP4 e no SRT.

### 5. Efeitos, animações e transições — prioridade média

1. Dissolução entre clipes com duração limitada pelos trechos disponíveis.
2. Zoom suave e deslocamento para imagens.
3. Brilho, contraste, saturação e presets com correspondência documentada entre prévia e render.
4. Entrada/saída de textos.
5. Escala, posição, rotação e opacidade; depois keyframes e curvas de interpolação.
6. Ajuste de velocidade com tratamento explícito de áudio.
7. Restaurar padrões e desfazer/refazer cada ação.

Aceite: reproduzir uma composição de referência com transição, movimento e texto animado e comparar quadros/tempos com a exportação.

### 6. Desempenho e acabamento — transversal

1. Paginação de todas as bibliotecas e virtualização quando o volume justificar.
2. Previews/proxies reutilizados, sem baixar originais para renderizar miniaturas.
3. Cancelamento de buscas obsoletas, debounce e cache.
4. Desenhar somente a região visível da timeline; evitar reconstruir painéis durante reprodução.
5. Revogar URLs temporárias e liberar áudio/vídeo ao trocar contexto.
6. Testar 30 cenas, várias faixas e mídia de resoluções diferentes.
7. Validar teclado, redimensionamento, zoom, foco, contraste, rolagem e movimento reduzido no shell completo.
8. Em telas pequenas, priorizar revisão e ajustes; aperfeiçoar gavetas de painéis e gestos sem comprometer o desktop.

Aceite: navegação utilizável sem travamentos perceptíveis no projeto de referência, sem rolagem horizontal involuntária no documento e com timeline acessível em notebook.

### 7. Exportação completa e publicação

1. Presets de proporção e saída; escolha entre ajustar e preencher.
2. 720p e 1080p na composição, com capacidade e memória medidas. Não confundir resolução de geração do modelo com resolução de exportação.
3. Histórico de exportações com projeto/revisão e reabertura.
4. Testar upload → montagem → roteiro/voz → legendas → efeitos → salvamento → exportação.
5. Verificar a instalação de FFmpeg/FFprobe e filtros necessários no ambiente alvo.
6. Testar uma geração real do modelo com áudio e contabilização de custo.
7. Validar a integração com sessão, marca, armazenamento e créditos reais.
8. Publicar a versão e verificar a URL de produção.

Aceite: todo o fluxo executado no ambiente alvo, com arquivos finais inspecionados e sem controles que prometam recursos ausentes.

## Validação realizada

- Build Tailwind exclusivo passou.
- Verificação sintática dos módulos JavaScript passou.
- `tests/test_video_studio.py`, `tests/test_trocr_session.py` e `tests/test_trocr_animate.py`: **50 testes passaram**.
- Testes reais de FFmpeg: mixagem com/sem áudio original, duração preservada, corte, loop, exportação silenciosa, efeitos em quadros e geração de waveform.
- Testes HTTP: autenticação, CSRF, upload inválido, isolamento de arquivos por marca, exportação e repetição idempotente da solicitação.
- Testes dos parâmetros: modelo e limites do servidor, seed, encaminhamento de `generate_audio`.
- Navegador local, com dados de teste: biblioteca, upload de som, seleção de trilha, parâmetros Seedance, corte, efeitos, salvamento e exportação concluída.
- Inspeção visual em 1366×768 e largura de documento em viewport móvel; falta a matriz completa no shell real.
- O frontend foi exercitado com a estrutura real do editor e os novos endpoints, mas biblioteca visual/projeto usaram serviço de teste isolado. Isso não equivale à validação em produção.
- Não houve chamada paga de geração nem deploy nesta tarefa.

Uma execução ampliada com `test_modelagem_criativos.py` encontrou três falhas em contratos de catálogo/templates, além de 175 testes aprovados naquele momento. O repositório está recebendo alterações concorrentes; essas falhas precisam ser triadas no fechamento integrado. O conjunto específico do estúdio acima está aprovado.

## Critério final de conclusão do plano

O plano completo só estará implementado quando for possível criar um projeto independente, combinar pelo menos três mídias, dividir e reordenar cenas, inserir texto e legendas, misturar múltiplos áudios, aplicar transições/animações, reabrir sem perda e exportar o resultado correspondente à prévia. A publicação e a confirmação do áudio gerado pelo provedor são etapas próprias, ainda pendentes.

## Continuação — projetos com revisões (14/09/2026)

Implementada a primeira parte da etapa 1: armazenamento SQLite por marca, snapshots imutáveis, controle transacional de revisão esperada e resposta HTTP 409 para conflito. O frontend abre a revisão mais recente e salva novas revisões; quando ainda não existe projeto versionado, lê o projeto legado e o próximo salvamento cria sua primeira revisão. Falhas de leitura/salvamento agora aparecem na interface.

Novas rotas: GET/POST `/studio/projects` e GET/POST `/studio/projects/<id>` sob o prefixo `/parametros/api/format-lab`. A consulta individual aceita `revision` para recuperar versões anteriores. A listagem retorna até 50 itens por página (`offset`). A interface de escolha de projetos e restauração de versões ainda não foi implementada.

Validação nesta continuação: 53 testes passaram (projetos, studio, sessão e animação), incluindo disputa de duas gravações concorrentes, imutabilidade da revisão antiga, autenticação, CSRF, conflito HTTP e isolamento por marca. Sintaxe dos módulos JavaScript alterados validada. Não houve validação de navegador nem publicação nesta continuação.

Limitações: documentos ainda usam o schema do editor de um clipe; não representam montagem multifaixa. SQLite exige armazenamento persistente local compartilhado pelos processos do mesmo host; não é uma solução distribuída entre hosts. A fila durável, composição multiclipes, áudio multifaixa, textos/legendas, animações avançadas e publicação permanecem pendentes. A versão inicial criada após perda de resposta de rede ainda precisa de chave idempotente de criação.
