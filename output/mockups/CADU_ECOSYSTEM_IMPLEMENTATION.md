# Cadu — plano técnico, visual e de componentes

## Direção consolidada

O Cadu não usa marca como decoração. O símbolo raster identifica o ambiente; a interface prioriza a tarefa. Não usar SVG como ativo de marca. Cada entrega de marca é uma imagem raster produzida em Image 2, em dimensões próprias para seu uso. CSS serve apenas para layout, estados e recortes responsivos.

O `Cadu/App` atual permanece em PHP, sem alteração nesta fase. Todo estudo está isolado em `output/mockups/`.

## Fase 0 — kit mestre e contratos de front-end

Entregáveis comuns às cinco famílias:

- `brand-primary`: assinatura raster horizontal em fundo claro e escuro.
- `app-icon-3d`: ícone quadrado 1024px para onboarding, apresentação e troca expandida de produto.
- `app-icon-2d`: ícone quadrado raster em 1024px, com exportações 512/192/180/64/32/16 para PWA, rede social e favicon.
- `product-key-visual`: imagem editorial 16:9 e corte 4:5; deve mostrar elementos reais do respectivo produto, não formas abstratas genéricas.
- `surface-kit`: exemplos reais de navegação, vazio, carregamento, erro, alerta, status, modal, tooltip, dropdown, dados e cartão de ação.
- `tokens`: navy `#10213B`, ink `#0B0F14`, paper `#F7F9FC`, line `#DCE3EC`; cada produto recebe uma cor de ação e uma superfície tonal acessível.

O seletor global usa ícones raster 2D de 20–24px. Ao trocar de produto, o front mantém a organização, a marca e o usuário como contexto de SSO visual; o backend futuro decide o acesso e redireciona para o subdomínio correto.

## Fase 1 — Cadu Hub

**Papel:** comando e contexto compartilhado.

- Cor: teal `#009F8A`; o logo Cadu atual permanece a origem da marca.
- Key visual: composição de briefing real, projetos, marcas, integrações MCP e trilha “pergunta → decisão → ação”; sem dashboards fictícios como fundo.
- Home: prompt central, projetos, conversas recentes, integração/contas pendentes e resumo do plano.
- Componentes: composer, chips de contexto, lista de conversas, projeto, cartão de integração, status de créditos, consumo e histórico financeiro.
- Onboarding: contexto da organização; primeiro projeto; conexão com Studio/Connect.

## Fase 2 — Cadu Media Studio

**Papel:** produção criativa com área de trabalho densa.

- Cor: violeta `#7456E8`.
- Key visual: kit real de produção da marca — logo, paleta, fontes, formatos, referências, peça, vídeo e variações; a imagem deve representar a biblioteca e a mesa, não um gradiente abstrato.
- Home: marca ativa, novos fluxos de criação, biblioteca, produção em andamento e atalhos para editores existentes.
- Chrome exclusivo: navbar horizontal de largura total; marca compacta, tabs, menus Criar/Editar/Recursos, status “salvo”, créditos, usuário, troca de marca e notificações.
- Componentes: asset tile, mídia em processamento, job, revisão, variant, formato, timeline compacta, inspector e barra de ferramentas.
- Onboarding: briefing → criação/ajuste → biblioteca → exportação. Editores densos continuam desktop-first.

## Fase 3 — Cadu Connect

**Papel:** operação multi-conta e preparação de dados.

- Cor: azul `#1976E9`.
- Key visual: cartões reais de contas/redes, arquivo de relatório, campanhas identificadas, IDs normalizados e estados de sincronização.
- Home: contas conectadas, saúde MCP, importação, último processamento, campanhas encontradas e tarefas de normalização.
- Componentes: account row, status OAuth/MCP, import dropzone, mapping de coluna, validação de IDs, fila de processamento, campanha e alerta operacional.
- Onboarding: conectar conta ou importar arquivo; validar leitura; escolher conta principal; abrir primeiro painel.

## Fase 4 — Cadu Skills

**Papel:** documentação aberta e guia de capacidades.

- Cor: laranja `#E87922`.
- Key visual: documentação real — páginas, prompt de exemplo, bloco de código, navegação de tópicos e relação com os produtos; não ilustração tecnológica genérica.
- Home: busca, categorias, skills em destaque, exemplos e rota clara para autenticar no Hub.
- Componentes: busca de documentação, sidebar de capítulos, breadcrumb, bloco de código, exemplo copiável, tabela de referência, callout e resultado de busca.
- Onboarding: descobrir; testar exemplo; levar a Skill ao ambiente autenticado.

## Fase 5 — Cadu Smart Planner

**Papel:** estratégia de mídia a partir do objetivo.

- Cor: verde `#18B978`.
- Key visual: briefing real com objetivo, audiência, canais, calendário, plano e handoff para Studio/Connect.
- Home: objetivo em destaque, marca, planos em curso, próximos passos e ponto de entrada de novo planejamento.
- Componentes: card de objetivo, canal, audiência, plano, orçamento, calendário, recomendação, etapa e handoff.
- Onboarding: objetivo; estrutura de plano; aprovação; transferência para produção ou operação.

## Fase 6 — brand book e HTML navegável

- Expandir `cadu-brand-system.html` para uma página de componentes navegável: assets raster de cada marca, fundos, cortes, tamanhos, estados e aplicações.
- Criar uma página inicial por produto e navegação entre HTMLs, com o mesmo seletor global.
- Cada home inclui onboarding de três passos, dispensável e lembrado apenas no front-end do protótipo.
- Validar em 1440, 1024, 768 e 390px; elementos de leitura respondem no mobile e mesas densas orientam continuidade no desktop.

## Ordem de produção de imagens

1. Validar o kit real de cada família: logo-base, exemplos de telas/elementos e uso pretendido.
2. Gerar o ícone 2D raster e o selo 3D raster por família.
3. Gerar key visual a partir de elementos reais do produto definidos nas fases acima.
4. Produzir os recortes 16:9, 4:5, 1:1 e 9:16 com área segura, sem texto incorporado.
5. Aplicar no brand book e nos primeiros acessos; nenhum asset é usado apenas como decoração.
