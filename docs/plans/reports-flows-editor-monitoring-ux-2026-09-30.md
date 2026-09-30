# Reports — adequação do editor e monitoramento de fluxos

Data: 30/09/2026. Estado: plano de execução e análise estática; nenhuma alteração adicional de produto feita nesta revisão.

Este documento consolida as dez referências enviadas, o código atual e a direção já aprovada: React, Untitled UI, React Flow, navegação própria de Reports, fluxo horizontal e integrações de CRM futuras. Complementa o plano de plataforma de 29/09 e substitui suas decisões conflitantes sobre motor de canvas, navegação, monitoramento e CRM. O motor já instalado é @xyflow/react 12.12.0; não há mais uma decisão de biblioteca pendente.

## 1. Resultado desejado

Editar e monitorar devem ser dois modos claros do mesmo espaço de trabalho. O usuário reconhece o mesmo mapa, abre páginas reais, entende as origens e vê onde visitantes avançam, permanecem ou saem. Painéis servem à seleção e deixam o mapa utilizável em notebook. Números, estados de coleta e alertas precisam informar período, origem e cobertura.

Decisões centrais:

- Um canvas React Flow compartilhado para edição, monitoramento e simulação, com permissões e camadas próprias por modo.
- Editor manipula o rascunho; monitoramento lê uma publicação imutável. Rascunho e publicação aparecem identificados quando divergirem.
- Orientação padrão da esquerda para a direita. Organizar altera somente posições; criar conexões exige uma ação explícita e evidência ou intenção do usuário.
- Untitled fornece controles, formulários, menus, abas, badges, tooltips e diálogos; React Flow fornece o comportamento espacial. Nós e conexões usam as extensões próprias do React Flow.
- Grade vetorial discreta, única, acompanhando pan e zoom. Miniaturas de páginas vêm de captura real ou de um placeholder identificado. Imagens geradas não representam páginas existentes.
- CRM próprio e conectores nativos ficam “Em breve”. O webhook atual de confirmação continua disponível por cliente; não anunciar isolamento por conta nem execução de um bloco que o backend ainda não oferece.

## 2. Leitura das referências

| Referência enviada | O que funciona | Aplicação no Reports |
| --- | --- | --- |
| Mapa compacto com Meta, Google, landing, checkout e saída | Poucos elementos, métricas junto aos caminhos, saída explícita | Mapa de monitoramento com contagens e taxa por conexão; seleção abre explicação da perda |
| Editor amplo com barra superior e painel Forecast | Canvas dominante e ferramentas curtas | Header de 56 px, rail de ferramentas e resumo recolhível; projeções não se misturam a resultados |
| Jornada complexa com origens, páginas, segmentos e CRM | Famílias visuais distintas e ramificações compreensíveis | Círculos para origens, páginas com miniatura, eventos/objetivos com ícone, grupos nomeados |
| Recorte do header | Identidade, período e salvamento acessíveis | Logo Reports, voltar, nome, modo, estado, filtros contextuais e uma ação principal |
| Mapa com contagens e taxas nas conexões | Relação entre volume de entrada e avanço | Sessões únicas por etapa e por passagem; denominadores explícitos |
| Rail lateral estreito | Ferramentas acessíveis sem menu aberto permanente | Explorar, adicionar, selecionar/mover, organizar, revisão e configurações |
| Biblioteca de modelos | Reconhecimento visual antes de escolher | Cards com preview do grafo real do modelo, objetivo, etapas e pré-requisitos |
| Muitas páginas convergindo numa inscrição | Comparar contribuição de várias URLs | Porta de entrada com distribuição de conexões, rótulos sem sobreposição, filtro por origem |
| Apresentação com insights e ações | Comunicação do resultado com contexto | Exportação do mapa filtrado com período/versão/legenda; apresentação completa em fase posterior |
| Explorador de Sources / Pages / Actions | Lista pesquisável vinculada ao mapa | Abas Origens / Páginas / Eventos, busca, contagem, estado e ação Localizar/Adicionar |

As referências são direção de hierarquia e interação. Os números demonstrativos, previsões e alertas das imagens não provam capacidades nem dados atuais do Reports.

## 3. O que existe hoje e onde está o desvio

Inspeção do working tree, incluindo as mudanças locais ainda sem commit da entrega anterior. Build da entrega anterior passou; nesta revisão não houve execução do backend, consulta à base de produção ou validação visual ao vivo. As falhas HTTP 400 das capturas continuam sem causa de produção confirmada.

| Área | Estado encontrado | Ajuste necessário |
| --- | --- | --- |
| Editor | FlowCanvas usa ReactFlow, Background, Handle, MiniMap, BaseEdge e EdgeLabelRenderer | Aproveitar Controls, Panel, NodeToolbar e seleção/conexão nativas; centralizar composição |
| Monitoramento | main.jsx desenha SVG e cards absolutos separadamente | Substituir pelo mesmo canvas; habilitar zoom, pan, seleção, foco e minimapa |
| Jornada no editor | Terceiro modo com grafo publicado e painel próprio; consulta isolada de 7/30/90 dias | Incorporar ao modo Monitorar com o mesmo contrato de filtros e revisão |
| Header | Logo adicionada localmente; ações e modos ainda competem por espaço | Hierarquia estável, overflow previsível, sem barra de erro empurrando o mapa |
| Navegação | Editor tem /connect/app/flows/:id; monitor usa query flow_view | Criar caminho próprio para monitor e preservar links antigos |
| Painéis | CSS absoluto com vários overrides; paleta 280 px e inspetor 320 px podem cobrir muito canvas | Um coordenador de painéis e cálculo de área útil; não apenas posicionamento por CSS |
| Miniaturas | Desenho esquemático de página para todos os tipos | Captura real, data da captura e estados de carregamento/indisponibilidade |
| Ícones | Catálogo compartilhado criado localmente; Google Ads ainda usa G genérico e Meta pode entrar como Facebook | Identidade canônica de plataforma, assets corretos e fallback explícito |
| Organização | ELK horizontal; dimensões fixas; resultado assíncrono pode substituir nós editados enquanto calcula | Dimensões medidas, revisão de origem, grupos e proteção contra resultado obsoleto |
| Monitor alinhado | Alinhamento local adicionado; fallback em três colunas, erro silencioso | Layout compartilhado, estado de falha visível, enquadramento e viewport persistido |
| Histórico | Snapshots com debounce de 200 ms | Comandos por gesto; arraste/organização/remoção agrupados em uma única operação |
| Eventos | Paleta mostra até cinco eventos reais locais; inspetor decide “recebendo” pela atividade da URL | Catálogo completo com paginação e identidade de evento; estado específico do evento |
| Grupos | pageGroup é uma string | Contêiner visual com membros, expansão e movimento conjunto |
| Tempo real | Polling a cada 15 s; sessão ativa com janela de 90 s; pulsos por transição nova | Preservar essa semântica, mostrar atualização e separar consulta leve do relatório completo |
| Disponibilidade | Checagem HTTP separada; até 101 URLs, incluindo a inicial | Mostrar cobertura parcial; alcançar todas as URLs configuradas em lotes |
| TypeSafe | Sugestão de papel de página, cache e proteção por revisão/evidência existentes | Reaproveitar; melhorar explicação, seleção entre candidatos reais e casos de avaliação |
| CRM | Webhook autenticado por organization_id/client_id, atribuição por campanha/visitante | Expor escopo verdadeiro; reservar associação por conta para contrato futuro |

Arquivos principais de evidência: frontend/reports-v1/{main.jsx,FlowCanvas.jsx,FlowInspector.jsx,FlowJourneyPanel.jsx,FlowPlatformLogo.jsx,flowLayout.js,useFlowHistory.js,flowValidation.js,flow-canvas.css,flow-workspace.css}; aicentralv2/cadu_connect/{reports_flow.py,reports_flow_live.py,reports_flow_monitor.py,reports_flow_schema.py,reports_flow_versions.py,reports_flow_suggestions.py,reports_typesafe.py,reports_ingest.py}.

## 4. Correções de confiança e integridade — P0

Estas correções precedem a nova camada visual de analytics.

1. **Passagens diretas:** /journey calcula LEAD depois de um JOIN com etapas mapeadas. Uma visita intermediária sem mapeamento desaparece da sequência e pode criar A → B indevidamente. Construir a sequência com as visitas relevantes completas; página não mapeada interrompe passagem direta. Compartilhar a regra com o snapshot live.
2. **Conversão do funil:** a consulta atual verifica se entrada e conversão pertencem à mesma sessão, sem exigir conversão posterior à entrada. Exigir ordem temporal, com desempate por ID de ingestão, dentro da revisão e período selecionados.
3. **Presença:** node_presence atribui presença por URL a todos os nós da mesma URL. Exibir presença atual em páginas; eventos exibem ocorrências e sessões que executaram a ação. Uma sessão numa página de compra não prova compra em andamento.
4. **Evento recebido:** FlowInspector procura activity pelo caminho e usa views como evidência. Trocar por correspondência de host, path, event_kind e event_name. Visita à página não ativa o estado de um evento personalizado.
5. **Zero e indisponível:** origens visuais sem associação, campos não medidos, fonte desconectada e falha de consulta mostram “Não disponível” ou “Sem vínculo”. Zero só aparece quando a consulta válida mede aquela grandeza.
6. **HTTP 400:** reproduzir o payload que falha antes de atribuir causa. Hipóteses demonstráveis incluem eventos duplicados na mesma URL, path inválido, portas e posição fora do limite. Salvar duplicata deve apontar os nós envolvidos. O inventário de eventos pode repetir nome/caminho por origem: deduplicar pela identidade medida antes de oferecer “Adicionar”.
7. **Erro único:** save global e saveFlow podem exibir o mesmo erro em dois banners. Cada operação terá um responsável pela mensagem; falha de campo vai ao inspetor, falha de salvamento ao header com detalhes acionáveis.
8. **Layout assíncrono:** aplicar posições somente se fluxo e revisão local continuarem iguais aos do início do cálculo. Mesclar por ID; não substituir o documento completo com snapshot antigo. Cancelar/recalcular se houver alteração.
9. **Campos duplicados do schema:** manter title/path/x/y como origem canônica de gravação e usar adaptadores para data/position do React Flow. Alterar um nome ou URL não pode deixar cópia antiga usada por outro modo.
10. **Validação coerente:** placeholders têm estado explícito. Um evento real cujo nome começa por evento_ não é inválido apenas por esse prefixo. Frontend e publicação usam as mesmas regras de identidade, portas, limites e configuração incompleta.

## 5. Navegação e estrutura de tela

Rotas finais:

| Rota | Conteúdo |
| --- | --- |
| /connect/app/flows | Biblioteca de fluxos |
| /connect/app/flows/new | Criar com domínio/modelo; página própria |
| /connect/app/flows/:id | Editor do rascunho |
| /connect/app/flows/:id/monitor | Monitoramento da publicação selecionada |

client_id continua explícito na URL e é autorizado pelo servidor. Query de monitoramento conserva revision, período/datas, conta e campanha. Links antigos com flow_view são redirecionados preservando o contexto. Atualizar parser do frontend e rotas Flask em conjunto; back/forward e acesso direto devem carregar o mesmo estado.

A lista mantém a sidebar geral de Reports. Editor e monitor usam o workspace de canvas em tela inteira com logo Reports no topo. O seletor de soluções continua disponível pela marca; voltar leva à biblioteca preservando filtro. Troca de cliente volta à biblioteca desse cliente, pois o fluxo atual não pertence automaticamente ao novo contexto.

Header de 56 px, alinhado ao topo do rail:

- Esquerda: voltar, logo/seletor Reports, nome do fluxo com truncamento e tooltip, domínio no detalhe.
- Centro: Editar / Monitorar, com estado ativo claro. Simular é ação do editor e abre um painel com faixa “Simulação”.
- Direita no editor: salvo/pendente/falha, desfazer/refazer, Publicar e menu Mais. Snippet, histórico e exportar ficam no menu.
- Direita no monitor: período, Atualização ativa/pausada, filtros e menu. Revisão da publicação acessível junto ao período.
- Publicar é o único CTA primário do editor. Ações comuns usam variantes secundária/terciária do Untitled, sem bordas nativas acumuladas.
- Erros ficam num popover de estado ou faixa interna de altura limitada; o header permanece na mesma posição.

## 6. Canvas, rail e painéis flutuantes

Composição: header 56 px; rail esquerdo 48 px; canvas ocupa o restante. Painéis ficam ancorados ao canvas usando Panel e slots definidos; evitar drag livre de painéis na primeira entrega.

| Elemento | Editor | Monitoramento |
| --- | --- | --- |
| Explorar | Origens, Páginas, Eventos, grupos; localizar/adicionar | Mesmas abas com métricas e filtros; localizar/inspecionar |
| Adicionar | Paleta por categoria, modelos e página descoberta | Oculto; ação “Editar fluxo” no contexto |
| Selecionar/Mover | Alternância de ferramenta, atalho V/H | Mover mapa como padrão; seleção de itens permitida |
| Organizar | Tudo / seleção / grupo; desfazer disponível | Organizar visualização / usar layout publicado; não grava rascunho |
| Revisão | Pendências de publicação; clicar enquadra o nó | Saúde de coleta, URLs com falha e cobertura |
| Configurações | Grade, snap, nomes, miniaturas, portas | Camadas de volume, taxa, presença, disponibilidade e legendas |

Painel esquerdo 288 px; inspetor direito 320 px; padding interno 16 px e espaçamento de formulário 16 px. Títulos/abas ficam fixos dentro do painel e apenas o corpo rola. Nenhum campo encoberto pelo rodapé. Todos têm fechar e retorno de foco; clique num nó abre o inspetor e o centraliza na área livre.

Regras por largura útil:

- >=1440 px: até dois painéis, desde que sobrem 720 px de canvas útil; se não sobrar, fechar o explorador ao abrir inspetor.
- 1024–1439 px: um painel expandido por vez; preservar sua aba e busca ao alternar.
- 768–1023 px: um drawer de largura máxima 320 px; rail compacto; ações secundárias no menu.
- <768 px: monitor oferece lista de etapas e indicadores essenciais; editor apresenta orientação para tela maior e link para monitorar. Não manter editor invisível processando em background.

Controls no canto inferior esquerdo da área livre; MiniMap no inferior direito, opcional; mensagem de layout/erro acima dos controles. Painéis nunca cobrem esses alvos. Fechar painéis não chama fitView automaticamente. Ao enquadrar, descontar header, rail e painéis realmente abertos.

## 7. Componentes do React Flow a utilizar

A API instalada já exporta estes recursos. Customizar aparência com tokens Reports/Untitled, preservando a interação do motor.

| Recurso | Uso definido |
| --- | --- |
| ReactFlowProvider + useReactFlow | Um contexto por workspace; viewport, foco, fitBounds e conversão de coordenadas |
| Controls + ControlButton | Zoom +/−, ajustar, 100%, organizar e modo mão/seleção |
| Panel | Explorar, inspetor, resumo e avisos ancorados ao canvas |
| Background | Uma camada de pontos ou linhas discretas; alternância visual independente do snap |
| MiniMap | Visão geral, arrastar viewport e localizar grupos; não duplica o controle principal |
| NodeToolbar | Renomear, duplicar, agrupar, conectar e excluir; tamanho de controles legível em qualquer zoom |
| EdgeToolbar / EdgeLabelRenderer | Ações da conexão e rótulos de métricas com área de clique ampliada |
| Handle + useUpdateNodeInternals | Portas por direção e condição; recalcular âncoras depois de expandir grupos/alterar dimensões |
| BaseEdge + caminhos calculados | Desenho e hit area consistentes; curva e corredor de retorno |
| applyNodeChanges / applyEdgeChanges | Estado controlado; dimensões e seleção tratadas sem confundir com mutação de negócio |
| onReconnect + reconnectEdge | Mover ponta de conexão existente com validação e undo |
| NodeResizer | Redimensionar grupos e notas; nós comuns conservam geometria padronizada |
| parentId / extent | Agrupamento visual; filhos ordenados depois do pai no adaptador |
| useNodesInitialized / getNodesBounds | Medição antes de layout/enquadramento; remover timeouts fixos de 80 ms |

React Flow oferece componentes e APIs, mas o layout precisa de um algoritmo externo; manter ELK já instalado. Templates de React Flow UI que tragam outro design system não devem introduzir uma segunda biblioteca de controles. Exemplos Pro não são pré-requisito: usar a API pública instalada e implementar as regras de produto.

Fontes oficiais: [componentes](https://reactflow.dev/api-reference/components), [Panel](https://reactflow.dev/api-reference/components/panel), [Controls](https://reactflow.dev/api-reference/components/controls), [NodeToolbar](https://reactflow.dev/api-reference/components/node-toolbar), [subflows](https://reactflow.dev/learn/layouting/sub-flows) e [layout](https://reactflow.dev/learn/layouting/layouting).

## 8. Nós, ícones e miniaturas

Um catálogo único define kind, type, platformId, ícone, label e capacidade: medida, representação ou integração futura. Canvas, paleta, inspetor, templates, monitor e exportação consomem esse catálogo.

- **Origens:** logo oficial em superfície branca, 28 px no canvas a 100% e 20 px na lista. Google Ads, Google orgânico, Meta e Facebook têm identidades diferentes; aliases antigos são migrados por kind e não por substituição global. DV360, YouTube, Instagram, TikTok e LinkedIn usam assets locais versionados. Fallback com nome/ícone de plataforma, nunca imagem quebrada.
- **Páginas:** título de até duas linhas, miniatura 96×112 com object-fit contain, URL curta abaixo e URL completa no tooltip/inspetor. Preview ampliado sob demanda; abrir URL em nova aba. A página inicial / permanece visível.
- **Eventos:** ícone semântico e nome amigável; nome técnico no inspetor. Formulário, clique, download, vídeo e WhatsApp distinguíveis sem depender apenas de cor.
- **Conversões:** símbolo e label do objetivo. Mostrar “Evento do site” ou “Confirmação CRM” quando houver medição correspondente.
- **CRM/segmento/webhook:** badge “Etapa visual” e descrição da capacidade. “Em breve” para conector não disponível. Nenhum ícone pulsante sugere entrega de webhook executada sem registro de entrega.
- **Grupos:** contorno leve, título e quantidade de etapas. Métrica agregada usa união de sessões; não soma nós que podem conter as mesmas sessões.

A 100%: label 12–13 px, URL 11 px, métrica principal 15–16 px. Abaixo de 65% ocultar detalhes secundários; abaixo de 40% mostrar ícone, nome curto e volume principal. Seleção mantém detalhes via toolbar/inspetor fora da escala. Não reduzir tudo até texto ilegível para caber no mapa inteiro.

Capturas reais: criar serviço assíncrono por URL autorizada, reutilizando validação de domínio/IP e bloqueando redirecionamentos/requisições de browser para destinos privados. Capturar páginas públicas sem credenciais, guardar asset por cliente com data, limitar dimensão e tamanho, cachear por URL normalizada. Estados: sem captura, em fila, capturando, disponível, falhou, desatualizada. Falha de screenshot não impede medir a página. O campo thumbnail_asset_id já existe, mas serviço e autorização do asset precisam ser implementados; não tratar o campo isolado como funcionalidade pronta.

## 9. Conexões, agrupamentos e autoalinhamento

Organização horizontal por padrão: origens à esquerda, páginas/eventos no sentido das conexões, objetivos à direita; ramificações ocupam linhas, retornos usam corredores externos. ELK calcula usando dimensões medidas, espaço mínimo entre nós de 64 px e entre camadas de 112 px; ampliar quando títulos/labels exigirem.

Botão Organizar oferece Tudo, Seleção e Grupo. Preview imediato reversível com Desfazer; estado “Organizando…” bloqueia nova solicitação. Resultado aplicado como um comando se a revisão local não mudou. Manter identidade, propriedades, portas e edges. Não gerar conexões na organização.

Usar layout salvo como base ao entrar. O monitor oferece “Layout publicado” e “Organizado”; a preferência é local ao usuário/fluxo/revisão. Primeira abertura usa Organizado se houver layout legado irregular; após interação, preservar pan/zoom. Consulta de métricas não reexecuta layout nem reenquadra a tela.

Conexões planejadas: cinza tracejado. Selecionada: azul. Caminho observado: volume/taxa em label neutro; cor de sucesso ou alerta só quando uma regra explica o estado. Inatividade não é erro. Largura pode representar volume relativo dentro do filtro, com legenda e teto de 5 px. Não usar cor de canal como semântica de desempenho.

Múltiplas entradas/saídas distribuem portas para evitar setas sobrepostas. No escopo atual, uma conexão por par de nós; condições distintas exigem um nó de decisão e portas nomeadas. Porta de condição não executa automação sem contrato. Loops são rotas de navegação observadas e não motor de execução; validar identidade e oferecer corredor externo.

Grupos guardam id, nome, bounds e membros. No documento v2 adicionar groups e groupId com validação explícita, conservando x/y absolutos dos nós para compatibilidade; o adaptador transforma em coordenadas relativas para parentId. Colapsar é preferência visual. Conexões internas ocultas não são excluídas; as externas podem ser agregadas visualmente, com contagens deduplicadas e detalhe das conexões originais. Movimentar grupo atualiza membros num comando. Desagrupar preserva posições mundiais.

Limites atuais: 200 nós, 300 conexões, config 256 KB e x/y até 10000. O layout deve detectar falta de espaço e devolver mensagem acionável, sem produzir posições que o backend rejeita e sem reduzir a escala silenciosamente. Mostrar uso dos limites no painel de revisão.

## 10. Explorador e inspetor

Explorador com abas Origens / Páginas / Eventos e busca única por nome, URL ou evento. Filtros “No fluxo”, “Disponíveis no site”, “Com atividade”, “Com falha”. Cabeçalho mostra quantidade filtrada e total. Listas grandes paginadas; não limitar silenciosamente aos primeiros cinco itens.

Cada linha tem ícone/miniatura, nome, detalhe, estado e ação. Item já no grafo oferece Localizar; disponível oferece Adicionar. Localizar seleciona e enquadra sem perder contexto. Adicionar usa coordenadas do centro da área livre ou conexão selecionada; o novo nó fica selecionado com inspetor aberto.

Eventos são identificados por host + path + event_kind + event_name. Deduplicar origens de tráfego para a escolha do evento; somar ocorrências do inventário só quando a divisão por origem for disjunta, sem somar visitantes únicos. Antes de inserir, verificar se o mesmo evento já está mapeado: oferecer Localizar e nova conexão ao mesmo bloco.

Inspetor do editor:

- Cabeçalho: ícone, tipo, nome e fechar.
- Seção Essencial: nome, página/domínio, evento ou plataforma; campos variam conforme tipo.
- Seção Medição: o que dispara a etapa, último evento correspondente e instrução de instalação quando necessária.
- Seção Organização: grupo, entrada e descrição opcional, recolhida por padrão.
- Conexões: entrada/saída com nome da etapa e ação localizar; editar porta/condição no contexto.
- Remover no rodapé como ação terciária destrutiva; undo imediato.

Inspetor do monitor: resumo da etapa, URL, publicação, sessões, eventos, avanço, origem dos dados, série por período e duas saúdes independentes: HTTP e coleta. Clique numa conexão mostra origem/destino, sessões que percorreram, denominador, taxa e período. Não mostrar campos editáveis neste modo.

## 11. Monitoramento, métricas e animação

O primeiro conteúdo é o mapa. Resumo recolhível no topo do canvas: sessões de entrada, sessões com conversão e taxa do funil; presença atual aparece em bloco identificado “Agora”. Tabelas e histórico ficam no painel Explorar/Detalhes, com expansão para página quando necessário.

Camadas independentes: Volume, Taxa de passagem, Presença agora, Disponibilidade HTTP, Saúde da coleta. Começar com Volume + Taxa; Agora é ativável. Uma legenda curta explica cada camada e sua atualização.

Contrato de leitura:

| Indicador | Definição e apresentação |
| --- | --- |
| Sessões da etapa | COUNT DISTINCT session_id que correspondem à etapa, revisão e período |
| Eventos | Número de ocorrências; pode superar sessões |
| Passagem A → B | Sessões com transição direta válida após A; preserva páginas não mapeadas como quebra |
| Taxa A → B | Sessões com passagem / sessões de A no mesmo escopo; denominador zero => indisponível |
| Conversão do funil | Sessões que converteram depois de entrar / sessões que entraram; união entre múltiplos objetivos |
| Presença atual | Sessões com última atividade em até 90 s, exceto saída; label “sessões”, nunca “pessoas” sem identidade deduplicada |
| Saída observada | Sessão encerrada/inativa cuja última página pertence à etapa; janela e cobertura declaradas |
| Não avançaram | Sessões de A sem próxima etapa configurada; não chamar automaticamente de saída ou abandono |
| Receita e investimento | Somente integração com moeda e atribuição compatíveis; manter site, mídia e CRM identificados |
| Disponibilidade | Status e horário da última checagem HTTP; independente de visitas |

As taxas de diferentes ramificações podem somar mais de 100% se a sessão percorre mais de uma saída. Explicar no detalhe; não normalizar artificialmente. Receitas de várias moedas não são somadas sem política de conversão definida. Não introduzir ROI/Forecast com valores inventados ou apenas estimados sem modo específico.

Animação: preservar o marcador de última transição já usado em FlowLiveEdge, portado para o edge React Flow. O primeiro snapshot é referência; somente ID novo pulsa. Não reproduzir lote antigo ao trocar filtro/revisão, reconectar ou abrir a página. Pulsos duram até 1,8 s, respeitam prefers-reduced-motion e não representam literalmente uma pessoa por partícula. Contadores atualizam sem alterar dimensões dos nós.

Atualização inicial: polling leve a cada 15 s quando a aba estiver visível; sem sobreposição de requisições. Pausa, falha, dados antigos e retomada têm estados explícitos. Mostrar “Atualiza a cada 15 s” e última atualização. SSE fica fora desta adequação; a experiência não deve prometer streaming contínuo.

Alertas como “perda de 24%” exigem regra: usar “Não avançaram” com numerador/denominador para leitura descritiva. “Queda em relação ao período anterior” exige comparação equivalente e cobertura suficiente. Selecionar alerta enquadra etapa/conexão e abre evidência. Diagnóstico causal não é inferido só da taxa.

## 12. Contratos de backend e estado

Preservar endpoints de gravação/publicação/versionamento e sua concorrência. Acrescentar capacidade sem remover consumidores atuais durante a migração.

- Estender GET /flow/flows/:id/journey para aceitar revision, datas ou days, account_id, campaign_id e platform, com as mesmas regras de escopo do monitor. Retornar config da revisão, métricas por node_id/edge_id, scope, generated_at e estados de disponibilidade. O endpoint antigo sem parâmetros novos conserva comportamento.
- Criar GET /flow/flows/:id/live para snapshot leve da publicação atual. Escopo inicial: todas as origens do fluxo, explicitado na UI; filtros de período/conta do relatório não aparentam filtrar presença. Responder active_window_seconds, generated_at, node_presence, transition cursors e status. Presença em revisão antiga retorna unavailable.
- Manter GET /flow para biblioteca/contexto; retirar o recarregamento de histórico, descoberta e agregados caros a cada tick live depois da migração da UI.
- Estender resposta de disponibilidade com checked_pages, total_pages, coverage e revision verificada. Processar URLs únicas em lotes, cobrindo até o limite de nós; não mostrar “site online” se a checagem foi parcial sem indicar cobertura.
- Padronizar falhas em JSON: code, message, field_errors, node_ids, edge_ids e request_id. Backend devolve erros de validação sem HTML nas APIs. Cliente conserva status, escopo e erro; não converte falha em lista vazia.
- Separar no frontend documento persistido, seleção/viewport, métricas e requests. Métricas/estado live nunca entram no PATCH de config. Cancelar respostas antigas ao mudar fluxo, cliente, revisão ou filtros.
- Cache de viewport/painéis por usuário, cliente, fluxo e modo; monitor inclui revisão. Sem tokens ou eventos pessoais no cache local. Preferências não incrementam a revisão de negócio.
- groups/groupId e metadados de asset recebem allowlist, validação de referência, limites e round-trip nos testes de schema. Publicações antigas continuam legíveis.

## 13. Integrações e CRM por conta

Modelo de produto futuro: cliente é o limite de isolamento; cada integração pode ser associada a uma conta autorizada desse cliente; o bloco referencia integration_id e account_id validados no servidor. Credencial fica no backend. Remover integração não apaga histórico já confirmado.

Entrega atual deste plano: no inspetor, explicar “Representação de CRM”, fornecer acesso ao webhook de conversões existente do cliente e mostrar “API para seu CRM — Em breve”. O webhook atual recebe confirmações atribuídas por visitor_id/campaign_id; não dispara ações de CRM ao conectar uma seta.

Fase futura separada: cadastro de conexão por conta, teste de credencial, escopos, último envio, logs, revogação, deduplicação, fila de entrega e retries. Só então ativar blocos executáveis. Conectores nativos não recebem botão “Conectar” funcional antes do contrato. Nenhum client_id informado livremente pelo emissor pode mudar o escopo definido pela credencial.

## 14. TypeSafe: assistência com evidência

A skill orienta manter regras e cálculos em código e usar julgamentos estruturados onde há interpretação semântica. A implementação existente já classifica papéis de página com Choice e inclui none; reaproveitar esse caminho, cache de 15 minutos, revisão de origem, hash de evidência e limite atual de 50 análises/cliente/24 h.

Aplicação nesta adequação:

- Sugerir papel de página usando título, heading, formulário e caminho reais. Resultado oferece Aplicar ao rascunho e a evidência que sustenta a sugestão.
- Selecionar correspondência entre uma etapa desejada e páginas/eventos candidatos previamente encontrados. IDs e URLs vêm do catálogo; none quando nenhum candidato serve.
- Avaliar agrupamento semântico somente como proposta revisável após agrupamento determinístico por domínio/seção. Não usar IA para calcular coordenadas, taxas ou identidade de visitante.
- Resultados obsoletos ou sem evidência ficam bloqueados para aplicação. Falha do provedor mantém todas as funções manuais disponíveis.
- Confidence representa concentração da distribuição, não “certeza de que a configuração funciona”. Mostrar alternativas no detalhe, sem tratar alta confiança como aprovação para publicar.
- Não inferir abandono, receita, conversão, entrega de webhook ou causa de queda a partir do texto de uma página. Esses fatos dependem da coleta e dos contratos anteriores.

Avaliação: conjunto de páginas com formulário, botão de compra sem confirmação, página de obrigado, conteúdo ambíguo, erro, subdomínio e conteúdo que tenta instruir o modelo. Medir papel correto, escolha none, latência e falhas. Nova inferência só entra após avaliar seu comportamento; nenhum limiar numérico genérico é condição suficiente para ação automática.

Fontes: [índice TypeSafe](https://docs.typesafe.ai/llms.txt), [confiança](https://docs.typesafe.ai/confidence) e [seleção entre candidatos extraídos](https://docs.typesafe.ai/cookbooks/pre_parsed_value_extraction_cookbook). Não foi chamado o modelo TypeSafe nesta análise; a skill foi aplicada ao desenho e à revisão do contrato existente.

## 15. Modelos, biblioteca e exportação

Biblioteca: grid/lista, miniatura do grafo, nome, domínio, estado do rascunho/publicação, coleta e atualização. Busca por nome/domínio; filtros Rascunho/Publicado/Com atenção. CTA Criar fluxo. Card abre o último modo do usuário; Editar e Monitorar são acessos explícitos.

Modelos existentes: vazio, leads, compra, webinar e WhatsApp. Criar preview por renderer compartilhado e explicar quais URLs/eventos precisam ser conectados. Usar páginas descobertas como candidatos; preencher apenas após escolha, sem transformar placeholders em páginas medidas. O modelo não traz números demonstrativos para o monitor.

Exportação PNG/SVG reutiliza nós e edges atuais: título, cliente autorizado, período, revisão, legenda e horário dos dados. No editor incluir “Rascunho”; no monitor indicar filtros. Não incluir painéis, menus, tokens ou snippet. Painel Forecast, edição de slides e recomendações de negócio ficam para etapa futura; exportar mapa e resumo cobre o primeiro uso de relatório.

## 16. Arquitetura e sequência de implementação

Extrair progressivamente FlowDesktop de main.jsx. Módulos: workspace/rotas; editor/documento e comandos; canvas/adaptadores; painéis; monitor/consultas; catálogo de assets. Manter React 18 e JavaScript com JSDoc; validar payloads na fronteira. Sem migração global de stack.

| Fase | Entrega | Critério para seguir |
| --- | --- | --- |
| 0 — Contratos e falhas | HTTP 400 reproduzido; erro único; identidade de eventos; sequência/ordem temporal; presença correta | Fixtures de dados e testes dos contratos passam; nenhuma falha é mostrada como zero |
| 1 — Workspace único | Rotas, header, rail, painel coordenado, React Flow nos dois modos | Editor e monitor têm mesma navegação, zoom e seleção; nenhum painel cobre controles |
| 2 — Edição e geometria | Catálogo, portas, comandos, reconexão, ELK com revisão, grupos e fit útil | Ramificações/retornos/grupos legíveis; undo retorna o estado completo; sem perda em autosave |
| 3 — Monitoramento no mapa | Métricas nas conexões, presença, saúde, filtros, revisão e detalhe da seleção | Cada número tem definição/escopo; polling não move o mapa; pulsos só por transição nova |
| 4 — Exploração e páginas | Catálogo completo de eventos, origem/página, miniaturas reais e modelos visuais | Item localiza/adiciona corretamente; captura indisponível tem fallback; dados reais preservados |
| 5 — Consolidação | Exportação, acessibilidade, limpeza do SVG/manual/CSS antigo e documentação | Aceite por viewport; somente o renderer compartilhado atende editor/monitor/exportação |

Trabalhar em main conforme preferência do projeto; commits por fase concluída e revisável. Preservar e revisar as alterações locais já existentes antes de novos commits. Build de Reports gera os bundles versionados. Deploy exige aplicação das migrações realmente adicionadas e validação do ambiente; este plano não declara deploy realizado.

## 17. Cenários de teste e aceite

- **Navegação:** link direto de editor/monitor, refresh, back/forward, aliases antigos, troca de cliente e retorno à biblioteca; filtros conservados.
- **Dados:** A → B; A → página não mapeada → B; A → A → B; A → B → A; conversão antes/depois da entrada; várias entradas/objetivos; dois eventos na mesma URL; subdomínios; fim do período.
- **Métricas:** zero real, fonte indisponível, falha de API, amostra vazia, divisão por zero, revisões históricas; não somar sessões repetidas ou moedas diferentes.
- **Live:** primeiro snapshot sem pulso, evento repetido sem novo pulso, novo ID com pulso, reentrada, saída, aba oculta, offline, retomada e movimento reduzido. Filtro histórico não altera a definição de Agora.
- **Persistência:** arraste, grupo, organização, rename, copy/paste, excluir com conexões e undo/redo; conflito entre abas; salvar/publicar concorrentes; resultado ELK atrasado; dados não salvos ao voltar.
- **Geometria:** cadeias, convergência 10→1, divergência 1→10, ciclos, nós isolados, grupos expandidos/recolhidos; 200 nós/300 edges; falta de espaço retorna erro compreensível.
- **Visual:** 1920×1080, 1440×900, 1366×768, 1024×768 e tablet; 200% de zoom do navegador; nomes longos; sem logo; screenshot com proporção diferente; sidebar aberta e fechada.
- **Interação:** mouse, trackpad, toque, teclado; drag de paleta e clique para adicionar; reconectar; selecionar com Shift; Escape fecha contexto antes de navegar; nenhum atalho captura digitação em campos.
- **Acessibilidade:** tabulação, labels em português, foco ao abrir/fechar painel, contraste e estados por texto/ícone; ações equivalentes por lista para quem não opera o canvas espacial.
- **Isolamento:** referências a conta, campanha, asset e integração de outro cliente recusadas; viewer pode monitorar e não mutar; screenshot não alcança destino privado.
- **Build e regressão:** testes de flow/schema/versions/live existentes, novos casos de sequência e UI, build Reports, diff de bundles e cache busting do projeto. Não rodar suítes sem relação após checks relevantes passarem.

Condição final: usuário abre o fluxo, reconhece as URLs, organiza ou inspeciona o caminho, entende cada número e consegue voltar ao mesmo ponto. Falhas de coleta, edição e integração têm mensagens próprias, sem sobreposição de banners, métricas falsas ou ações decorativas.
