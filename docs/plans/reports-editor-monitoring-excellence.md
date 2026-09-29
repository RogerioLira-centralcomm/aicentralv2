# Plano de evolução — editor, fluxos e monitoramento

Data: 29/09/2026. Escopo: Reports / Fluxos / Super Tag / mapas de interação.

## Base da análise

Revisão estática do código atual, incluindo as alterações locais de descoberta automática. Não houve validação visual da aplicação em execução nem validação de dados de produção. Medidas abaixo são propostas de design, não dimensões já aprovadas. As telas novas devem passar por referência visual e implementação com React e componentes Untitled existentes.

Fontes inspecionadas:
- `frontend/reports-v1/main.jsx`: FlowDesktop, editor, descoberta, monitoramento, Super Tag e campanha.
- `frontend/reports-v1/flow-workspace.css`: dimensões, espaçamentos, cards e animações.
- `aicentralv2/cadu_connect/reports_flow.py`: descoberta, grupos, rascunhos e criação de fluxos adicionais.
- `aicentralv2/cadu_connect/reports_flow_monitor.py`: worker, verificações HTTP e histórico.
- `aicentralv2/cadu_connect/reports_supertag.py`: agregação de eventos e mapa de interação.
- `aicentralv2/static/cadu_connect/cadu-supertag-v1.js`: coleta de cliques, formulários e rolagem.

## Inventário e decisões por tela

| Tela / superfície | Situação no código | Próxima entrega | Prioridade |
|---|---|---|---|
| Biblioteca de fluxos | Lista e ações existentes | Busca, filtros, domínio, publicação, coleta, cobertura e última checagem como atributos distintos | P1 |
| Mapeamento do domínio | Sitemap, leitura HTML, lotes e montagem do rascunho | Progresso, cancelamento, retomada, erros por URL e contagem descobertas/verificadas/incluídas | P0 |
| Escolha dos fluxos adicionais | Painel recém-adicionado com seleção | Cards com domínio, evidência, páginas e prévia; seleção em lote; resultado por fluxo | P1 |
| Editor de fluxo | Paleta, canvas, inspetor, arraste e conexões | Navegação espacial, seleção múltipla, histórico de edição e cards adaptáveis | P0 |
| Editor de etapa | Inspetor na lateral | Formulário por tipo, regras, evidência, validação e vínculo da página | P1 |
| Pré-publicação | Publicar e testar existentes | Resumo da revisão, erros, cobertura e diferenças para a versão publicada | P0 |
| Monitor do fluxo | Canvas com valores e estados; atualização de 15 s | Separar saúde técnica, coleta e performance; comparação e investigação da etapa | P0 |
| Saúde de páginas | Checagem HTTP e histórico no backend | Tela com cobertura, linha do tempo, latência, incidentes e retentativas | P0 |
| Detalhe do link / página | Dados distribuídos entre áreas | Tela dedicada que reúna disponibilidade, tráfego, cliques, saída e conversões | P1 |
| Mapa de calor visual | Apenas tabela agregada no trecho inspecionado | Tela nova com fundo compatível, dispositivo, versão e métricas por elemento | P0 dados / P1 visual |
| Mapa de calor da campanha | Aba encaminha à Super Tag por falta de vínculo seguro | Associação explícita instalação/domínio/campanha e filtros consistentes | P1 |
| Alertas e incidentes | Não confirmada central dedicada nos arquivos revisados | Central com regras, responsáveis, histórico e silenciamento | P2 |

## Problemas concretos e correções

### Editor, drag and drop e conexões

1. Cards do editor usam 172 × 116 px; cards do monitor usam 172 × 144 px. Título, caminho, grupo e ações competem pelo espaço. Substituir altura rígida por composição com altura medida e conectar arestas às dimensões reais do nó. Testar nomes extensos, URLs, traduções e zoom do navegador.
2. Arraste usa coordenadas do ponteiro e rolagem do canvas. Acrescentar transformação única de coordenadas para pan e zoom; não implementar zoom somente via CSS. Usar captura do ponteiro e cancelamento previsível.
3. Paleta usa HTML drag and drop. Oferecer adicionar por clique e teclado, além de arraste compatível com toque. Alvos interativos não devem iniciar movimentação do card.
4. Adicionar zoom 25–200%, ajustar tudo à tela, centralizar seleção, pan com espaço + arraste, minimapa e auto-pan nas bordas.
5. Seleção múltipla, alinhamento, distribuição, duplicação, exclusão com desfazer, copiar/colar dentro do cliente, atalhos documentados e Escape para cancelar conexões.
6. Histórico local de desfazer/refazer para operações do editor. Histórico de versões publicadas permanece uma função distinta.
7. Conexões por portas, área de clique generosa, seleção e remoção de aresta, rótulos editáveis e retorno visual antes de soltar. Mostrar retornos e ciclos sem sobrepor cards.
8. “Conectar sequência” conecta pela ordem visual. Exigir prévia e rotular a origem da conexão: link detectado, relação manual ou transição observada. Uma relação do sitemap não comprova uma jornada de visitantes.
9. Layout automático deve respeitar grupos, preservar posições fixadas e oferecer desfazer. Grupos precisam ser contêineres visuais com recolher/expandir; hoje `pageGroup` é um rótulo e ordenação, não um agrupador completo.
10. Cards de regras, delays, webhooks e Growth precisam declarar capacidade disponível. A presença de um bloco no canvas não comprova execução de automação.

Aceite: 100 nós sem cortes de conteúdo; drag correto com zoom e rolagem; todas as operações essenciais acessíveis por teclado; desfazer recupera posições e conexões; salvar/reabrir mantém o documento.

### Cards, números, padding e espaçamentos

Proposta inicial para protótipo:
- Escala de espaçamento: 4, 8, 12, 16, 24, 32 px; página 24 px, painel 16–24 px, card 16 px, intervalo interno 8 px.
- Paleta 240 px e inspetor 320 px recolhíveis; canvas usa o restante da largura. Em tablet, abrir inspetor sobre área lateral sem comprimir todos os painéis simultaneamente.
- Cards de etapa com largura inicial 240–280 px e altura por conteúdo; título até duas linhas, caminho abreviado com cópia e acesso ao texto completo.
- Ícones 16–20 px; logos em caixa de 24–32 px com `object-fit: contain`; não esticar nem cortar a marca.
- Texto operacional 14 px, auxiliar 12 px, títulos de painel 16–18 px. Controles 40 px; alvos de toque 44 px.
- Números tabulares, unidade explícita, localidade pt-BR e total exato disponível quando abreviado. Exibir “—” para indisponível, “0” somente para zero medido.
- Estado não depende só de cor: ícone + texto. Ações primárias reservadas para salvar/publicar/criar; ferramentas do canvas usam hierarquia secundária.
- Remover regras CSS duplicadas e dimensões divergentes entre geometria JS e CSS. Centralizar tokens e reutilizar Untitled para botões, campos, tabs, badges, tooltip e drawer.

Aceite: sem sobreposição em 1280, 1440 e 1920 px; navegação operável com 200% de zoom do navegador; títulos e KPIs não mudam a posição dos controles quando os números atualizam.

### Descoberta automática e fluxos principais

- A seleção atual dos principais é heurística por URL e papel detectado. LPs com URLs arbitrárias podem passar despercebidas. Expor evidências e permitir reclassificar antes de criar.
- Identificar domínios/subdomínios, seções e LPs por combinação de caminho, título, formulário e links; não declarar classificação infalível.
- Criar visão principal enxuta; propor fluxos separados de aquisição, contato e conversão apenas quando houver páginas e relações que os sustentem.
- Oferecer outros fluxos por LP/seção, com evidência e contagem. Antes de criar todos, informar quantos rascunhos serão criados e grupos grandes demais.
- Mostrar limites de 100 blocos e 300 conexões e páginas excluídas; dividir grandes grupos em vez de omitir silenciosamente.
- Mover varreduras longas para jobs retomáveis: status, progresso, cancelamento, retentativas e recuperação após fechar a aba. A continuação atual depende da página aberta.
- Reprocessamento deve permitir manter decisões manuais, detectar novas páginas e revisar removidas. Guardar identidade estável por domínio/caminho e origem da proposta.
- Prévia do vínculo entre fluxos evita perder a conexão LP → formulário → confirmação quando as páginas ficam em grupos separados.

### Monitoramento e números confiáveis

1. Separar três indicadores: disponibilidade HTTP; atividade da coleta; resultados de negócio. Ausência de visitas não implica indisponibilidade.
2. O worker corta a lista em 20 páginas. Exibir monitoradas/total e implementar fila rotativa ou cobertura integral em lotes; priorização explícita das páginas críticas.
3. `_page_targets` também consulta etapas ativas da tag. Revisar o escopo para impedir que etapas de outros fluxos da mesma tag contaminem a cobertura de um fluxo.
4. Falha interna do worker hoje pode marcar o fluxo como offline. Distinguir erro do verificador, timeout, HTTP inválido, redirecionamento, coleta desatualizada e página realmente indisponível.
5. Registrar início/fim do check, versão publicada, resultado por página e motivo. Tempo total HTTP atual não equivale a Core Web Vitals ou carregamento no navegador.
6. Adotar estados desconhecido, verificando, disponível, degradado e indisponível. Confirmar incidentes com falhas consecutivas configuráveis e registrar recuperação.
7. Histórico atual retém 200 checks por fluxo: definir retenção temporal e agregados antes de prometer SLA de 30/90 dias.
8. Atualização atual a cada 15 s: mostrar última atualização, atraso e erro de rede; pausar em aba oculta e retomar com atualização imediata. Não animar tráfego como prova de movimento quando só existe saúde técnica.
9. KPIs: sessões únicas, eventos, conversões, taxa e perdas com denominador, janela temporal, fuso e versão explícitos. Comparar períodos equivalentes; não somar mídia, site e CRM.
10. Transições observadas precisam de ordenação de sessão, deduplicação e regra de reentrada. Contagem de página isolada não determina volume de uma aresta.
11. Clique em card abre detalhe da etapa: URL, disponibilidade, últimas ocorrências, origem, conversão e ações “Abrir página”, “Ver mapa”, “Editar rascunho”.
12. Alertas por incidente confirmado, coleta ausente com critério definido e queda de conversão com amostra mínima. Deduplicação, cooldown, responsável e log das notificações.

### Mapa de calor do link

Achado principal: a tag coleta `clientX/clientY` normalizados pelo viewport; a API agrupa em células de 5%, por página e elemento, em 30 dias. A UI exibe tabela. O conjunto atual não permite posicionar corretamente cliques de diferentes scrolls sobre um screenshot de página inteira.

Entregas em sequência:
1. Ranking por elemento/link com identificador estável, cliques, sessões e taxa por exposição quando houver exposição medida. Não chamar cliques/sessões de CTR de exposição.
2. Contrato de coleta versionado: posição no documento, scroll, dimensões do documento e viewport, breakpoint, identidade de elemento e versão do layout. Medir o volume adicional antes de ativar.
3. Normalizar destino dos links, removendo parâmetros sensíveis; excluir campos, áreas marcadas e conteúdo pessoal. Preservar consentimento e retenção existentes.
4. Armazenar captura de referência pública por URL, dispositivo e versão. Caso a captura esteja indisponível, usar ranking e grade abstrata com explicação; não desenhar calor sobre imagem incompatível.
5. Filtros por domínio, URL, período, dispositivo, versão e campanha quando houver vínculo real. Não misturar layouts móveis e desktop.
6. Modos: cliques, profundidade de scroll, visibilidade de elementos. Legenda, intensidade ajustável, total de sessões e data da captura.
7. Inspeção por elemento: destino, cliques, exposição, cliques por sessão e evolução. Comparação antes/depois depende de versões identificadas.
8. Rage clicks, dead clicks e abandono por campo são recursos futuros: exigem instrumentação e definição próprias. O throttle global de 250 ms atual impede tratar a coleta como sequência completa de cliques rápidos.
9. Validar significado dos quartis de scroll e páginas sem rolagem antes de apresentar percentuais de alcance.

Aceite: evento sintético conhecido cai no elemento correto em desktop/mobile e diferentes scrolls; layouts incompatíveis não são agregados; nenhum dado sensível aparece na captura; ausência de dados gera estado vazio honesto.

## Recursos complementares

| Recurso | Dependência | Prioridade |
|---|---|---|
| Busca global de páginas e nós | Índice por fluxo e domínio | P1 |
| Revisão visual de publicação | Diferença rascunho/versão | P0 |
| Comentários e responsáveis por etapa | Permissões e histórico | P2 |
| Templates a partir de fluxo existente | Duplicação com revisão de domínio | P2 |
| Exportação PNG/PDF e tabela de métricas | Captura do canvas e filtros auditáveis | P2 |
| Comparar versões e períodos | Séries com versão e denominador | P1 |
| Análise de links quebrados | Checks por URL e evidências | P1 |
| Detecção de alteração de página | Hash de estrutura pública e baseline | P2 |
| Monitor de formulários | Verificação de presença; envio sintético só em ambiente controlado | P2 |
| Sessões e caminhos agregados | Identidade de sessão e retenção | P1 |

## Prompts para GPT Image 2

Uso: criar referências visuais antes de implementar telas ausentes ou com geometria ainda indefinida. Não são telas funcionais. Usar capturas atuais como referência quando disponíveis. Gerar uma tela por imagem, frontal, sem mockup de notebook, sem perspectiva. Valores abaixo são exemplos explicitamente ilustrativos; na implementação usar dados reais ou estados vazios.

### A — Editor de fluxo: nova geometria e interação

“Crie uma referência de interface desktop 1600 × 1000 para CentralX Reports, em português do Brasil, com linguagem visual Untitled UI React. Fundo branco, bordas cinza suaves, tipografia legível, azul reservado à seleção. Preserve o seletor de soluções no topo com apenas ‘Reports’. Sidebar da solução estreita; área de trabalho com paleta de 240 px, canvas amplo e inspetor de 320 px. Título ‘Fluxo principal’, badge ‘Rascunho’, estado ‘Salvo’, CTA ‘Revisar publicação’. Canvas com seis cards de altura confortável agrupados por seção: Início, Serviços, Contato, Formulário, Confirmação e Saída. Mostrar portas de conexão, arestas curvas, uma seleção com contorno azul e handle de arraste. Distinguir visualmente link detectado de relação manual com legenda. Cards têm ícone, título, URL abreviada, grupo e menu; sem métricas inventadas. Controles zoom, ajustar à tela, desfazer, refazer e minimapa discretos. Inspetor com campos Untitled e evidência da descoberta. Usar espaçamento de 8/16/24 px. Nenhum texto sobreposto ou cortado.”

### B — Revisão do mapeamento e fluxos adicionais

“Desenhe uma página desktop CentralX Reports de revisão de descoberta, Untitled UI, 1600 × 1000, português. Cabeçalho ‘Mapeamento concluído’ com domínio de demonstração exemplo.com.br e aviso ‘Dados ilustrativos’. Resumo de páginas descobertas, verificadas e pendentes. Seção ‘Fluxo principal’ com prévia compacta. Abaixo, pergunta ‘Deseja criar os outros fluxos identificados?’ e cards selecionáveis para ‘LP · campanha de verão’, ‘LP · solicitar demonstração’, ‘Conteúdo · blog’. Cada card mostra páginas, motivo da identificação e estado rascunho. Painel lateral de prévia do grupo selecionado. Rodapé da seção com ‘Agora não’, ‘Criar selecionados’ e ‘Criar todos’. Deixar explícita a quantidade de fluxos escolhidos. Apresentar seleção em página, sem modal, com boa hierarquia e espaço.”

### C — Monitor de fluxo

“Crie dashboard CentralX Reports 1600 × 1000, Untitled UI React, português. Título ‘Monitoramento do fluxo’, domínio, versão publicada, período e atualização. Três áreas claramente rotuladas: Disponibilidade, Coleta, Resultados. Exibir estado vazio em Resultados com ‘Aguardando eventos’; não inventar tráfego. Mostrar canvas com cards maiores que comportem nome, caminho, estado HTTP e última verificação; setas estáticas de estrutura. Um card degradado com ícone e descrição, demais neutros. Indicador de cobertura ‘20 de 48 páginas verificadas’ como dado ilustrativo marcado. Drawer de detalhe com histórico de checks, URL, latência e ação Ver página. Barra superior com Atualizar e Configurar monitor. Tipografia tabular para números e legenda explícita para estados.”

### D — Mapa de calor do link

“Desenhe uma tela nova CentralX Reports chamada ‘Mapa de interação’, 1600 × 1100, Untitled UI, português. Topo: seletor de domínio, página, período, dispositivo e versão da captura. Tabs Cliques, Rolagem, Visibilidade. Área central mostra uma landing page genérica frontal com sobreposição de calor ilustrativa limitada aos CTAs e legenda clara ‘Demonstração visual’. Ao lado, ranking de elementos com cliques, sessões e exposição. Mostrar controle de intensidade, legenda de cores acessível e data da captura. Elemento selecionado ganha contorno e tooltip com nome técnico legível e destino sanitizado. Incluir aviso curto de compatibilidade entre captura e dispositivo. Rodapé com sessões analisadas e origem Super Tag. Nunca exibir informações pessoais, mapa aleatório sobre UI do produto ou números sem unidade.”

### E — Saúde de páginas e incidentes

“Crie tela CentralX Reports ‘Saúde das páginas’, desktop 1600 × 1000, padrão Untitled UI. Cabeçalho com domínio, cobertura e última verificação. Cards Disponíveis, Degradadas, Indisponíveis, Sem verificação, com números ilustrativos identificados. Tabela com URL, status textual e ícone, código HTTP, tempo de resposta, última checagem e fluxo. Página selecionada abre painel lateral com linha do tempo de falha e recuperação, redirecionamentos e detalhe técnico legível. Filtros simples, CTA Verificar agora. Distinguir visualmente ‘Erro do verificador’ de ‘Página indisponível’. Fundo branco, detalhes de cor apenas nos estados, padding confortável e números alinhados.”

### F — Revisão de publicação

“Desenhe página de revisão CentralX Reports, 1440 × 1000, Untitled UI em português. Título ‘Revisar publicação’. Resumo versão atual e rascunho; lista de páginas adicionadas, conexões alteradas, etapas removidas. Prévia do fluxo ao lado. Blocos de validação com erros bloqueantes, avisos de cobertura e evidências ausentes. CTA principal ‘Publicar versão’ desabilitado no exemplo por uma URL sem domínio autorizado; ação secundária ‘Voltar ao editor’. Conteúdo ilustrativo declarado. Sem modal, sem decoração, foco na consequência da publicação e recuperação por versão.”

## Ordem de execução e validação

1. P0: contratos de métricas, limites/cobertura, semântica de saúde, geometria de cards, histórico de edição e revisão de publicação.
2. P1: mapa de interações por elemento, fluxos adicionais com prévia, detalhe de página, navegação do canvas e comparações.
3. P1 dependente de dados: captura compatível e heatmap visual após instrumentação validada.
4. P2: alertas, colaboração, exports e análises comportamentais avançadas.

Validar cada fase com cenários reais: domínio sem sitemap, sitemap grande, links cíclicos, LP fora de padrão, ausência de tráfego, worker parado, timeout, redirect externo, 100 nós, URL longa, tablet, teclado e alterações simultâneas de rascunho. Nos heatmaps, testar coordenadas e versões com uma página controlada antes de qualquer interpretação de produção.

Não considerar este plano como implementação concluída. Próxima entrega recomendada: corrigir fundamentos P0 e produzir as referências A, C e D antes de expandir telas.
