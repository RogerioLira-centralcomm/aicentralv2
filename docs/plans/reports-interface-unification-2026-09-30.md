# Reports — plano de adequação visual e interação

Data: 30/09/2026. Escopo: todo o Reports, com prioridade para painéis flutuantes e Flow Studio.
Status: proposta de execução; não representa interface já implementada.

## 1. Direção aprovada pelas referências

Referências recebidas: painel de confirmação com formulário; configurações com navegação e aviso contextual; formulário amplo com resumo lateral; relatório responsivo com gráfico e tabela.

Traduzir essas referências para o Reports: superfícies claras, tipografia precisa, ícones consistentes, espaçamento generoso entre seções e controles compactos. Manter a identidade azul do Reports. Não copiar nomes, números, perfis, imagens de pessoas ou serviços fictícios das referências.

O refinamento vem da composição: um cabeçalho, uma hierarquia de ações, seções legíveis e estados claros. Evitar empilhar cards para separar cada campo ou cada número. Bordas delimitam controles e superfícies; espaço organiza o conteúdo.

## 2. Diagnóstico do código atual

- `ReportsActionButton.jsx` já envolve o botão Untitled, porém infere cor e tipo por classe/onClick. A migração deve tornar a intenção explícita e usar `type="button"` como padrão seguro; submissão deve ser declarada.
- O kit local em `frontend/reports-v1/untitled-kit` contém botão, input, textarea, select nativo, tooltip e ilustração Documents. Não há evidência local de todos os templates completos das referências. Inventariar a disponibilidade e licença antes de importar outros componentes; não substituir por imitações com nomes de Untitled.
- `ReportsDrawer.jsx` usa React Aria, mas não oferece contrato compartilhado para corpo rolável, rodapé persistente, estado de salvamento e proteção de alterações.
- `FlowInspector`, `FlowCatalog`, `FlowBlueprint`, `FlowStudioAssist` e painéis do monitoramento usam estruturas particulares.
- `ReportsTabs` usa botões; precisa padronizar aparência e associação tab/tabpanel. `PageChrome` ainda contém selects próprios.
- `flow-workspace.css` tem 24 ocorrências de `!important`. Auditar junto com `styles.css`, `flow-canvas.css` e `flow-monitor-workspace.css`, substituindo regras antigas ao migrar cada componente.
- `main.jsx` concentra páginas e estados; separar gradualmente por superfície durante a migração, preservando rotas e contratos.
- Permanecem dois defeitos funcionais conhecidos: reconexão de arestas agregadas pode gravar ID de grupo como etapa; mover um grupo não marca seus membros como editados. Corrigir antes da migração visual.

## 3. Sistema visual proposto

Usar tokens semânticos existentes do Untitled; valores abaixo são alvos de desenho a reconciliar com o tema local.

| Elemento | Padrão |
|---|---|
| Cor | superfície #FFFFFF; fundo #F9FAFB; texto #101828; secundário #475467; borda #EAECF0; ação #155EEF |
| Tipografia | família sans já adotada no kit; página 24/32 semibold; painel 18/28 semibold; corpo/campos 14/20; apoio 12/18 |
| Espaçamento | escala 4, 8, 12, 16, 24, 32; campos separados por 16–20; seções por 24 |
| Header | 64 px, alinhado com a área da marca; uma única linha estrutural no desktop |
| Inputs | 40 px padrão; 36 px apenas em barras densas; label persistente e ajuda abaixo |
| CTAs | 36 px desktop; alvos de toque pelo menos 44 px; primário único por contexto |
| Bordas | 1 px; não somar borda do wrapper à borda do input; foco visível independente |
| Raios | controles 8 px, painéis 16 px; sem card envolvendo cada seção |
| Elevação | sombra suave em superfícies flutuantes, sem sombra em cada campo |
| Ícones | Untitled, 16/20 px; marcas oficiais para plataformas; tooltip e nome acessível em icon buttons |
| Movimento | 120–180 ms ao abrir/fechar; respeitar redução de movimento; atividade animada somente com evidência recente |

Modo escuro: preparar tokens e contraste nesta migração; implementação visual completa em etapa própria, após consolidar o modo claro. Não anunciar suporte antes da validação.

## 4. Contrato único de painéis

Criar `ReportsPanelShell` com variantes de comportamento, mantendo a mesma aparência:

1. **Painel flutuante do canvas:** não modal, afastado 16 px das bordas úteis, permite continuar explorando o fluxo. Inspector à direita; explorador à esquerda.
2. **Drawer de tarefa:** modal apenas quando a tarefa exige foco e confirmação; overlay leve, foco contido e retorno ao acionador.
3. **Página de formulário:** conteúdo extenso, várias seções ou navegação própria. Resumo lateral opcional para decisões que realmente precisam dele.

Estrutura comum:

```
┌ ícone contextual                 fechar ┐
│ Título                                 │
│ Descrição curta, quando necessária      │
│ abas opcionais                         │
├ corpo com rolagem própria               │
│ label                                  │
│ campo                                  │
│ ajuda ou erro                           │
│                                        │
│ próxima seção com espaço               │
├ estado opcional   Cancelar   Ação       │
└────────────────────────────────────────┘
```

- Largura: explorador 304 px; inspector 360 px; tarefa 400–440 px. Larguras limitadas pela viewport.
- Cabeçalho e rodapé permanecem visíveis; somente o corpo rola. Evitar scrollbar no painel externo e interno simultaneamente.
- Formulários explícitos: Cancelar/Salvar; editores com autosave: indicar salvando/salvo/falha e permitir tentar novamente, sem segundo botão Salvar redundante.
- Fechar por Escape no painel ativo; clicar fora não descarta formulário sujo. Confirmação somente quando houver risco real de perda.
- Apenas um painel por lado. Não empilhar drawers. Ao abrir outra tarefa, preservar ou resolver o estado anterior.
- No canvas, calcular espaço livre antes de ajustar o enquadramento. Não alterar zoom a cada evento de atualização.
- Painéis não modais não prendem o foco; drawers modais prendem e devolvem o foco. Atalhos do canvas ignoram campos em edição.
- Carregamento, erro, vazio e falta de acesso pertencem ao corpo do painel e preservam contexto e ação de retorno.

## 5. Mapeamento de todas as áreas

| Área | Composição e mudanças | Formulário/detalhe |
|---|---|---|
| Navegação global | Logo e seletor de soluções, conta principal clara, item ativo discreto, perfil real e créditos legíveis | Menu de conta; não confundir conta principal com anunciante/conta de mídia |
| Visão geral | Período no topo, faixa de métricas, gráfico principal e tabela; início guiado quando sem fontes | Drawer curto para conectar; processo extenso em página |
| Clientes e anunciantes | Tabela com busca e ações; marca Workspace opcional explícita | Drawer criar/editar; detalhe completo em página |
| Contas | Ícone de plataforma, anunciante, conexão e última sincronização; erros acionáveis | Drawer para metadados; conexão em fluxo próprio |
| Campanhas | Toolbar única, filtros ativos, colunas úteis, detalhe navegável | Criação extensa em página; edição rápida em painel |
| Relatórios | Lista com período, atualização e ações; editor com seções e prévia | Página para criar/configurar; painel para filtros |
| Importações | Seleção, mapeamento, revisão, resultado; progresso e erros por linha | Página com etapas, sem modal longo |
| Dados de mídia | Fontes e saúde de sincronização; instalação separada dos dados | Painel de fonte; instruções extensas em página |
| Super Tag — sites | Favicon com fallback, domínio, saúde real, última atividade; linha abre detalhe | Conectar em drawer curto; configuração extensa no detalhe |
| Super Tag — detalhe | Resumo, atividade, páginas, fluxos e instalação em abas claras | Inspector de evento e configuração contextual |
| Fluxos — lista | Nome, site, publicação, coleta e atualização; modelos com prévia claramente demonstrativa | Criar em painel ou página conforme quantidade de escolhas |
| Flow — edição | Canvas ocupa área útil; rail, catálogo e inspector compartilham shell; menus pequenos | Resumo/Configuração no inspector; avançados recolhidos |
| Flow — montagem automática | Etapas de progresso, proposta, evidência, seleção e aplicar | Mesmo painel; prévia preserva rascunho; nenhum modal sobre outro |
| Flow — monitoramento | Mesmo mapa e posições; período, atualização, sessões e conversões; métricas distinguem ausência de dado de zero | Clique na etapa/ligação abre painel de evidências |
| Eventos | Busca, filtros e origem; separar recebidos e definição de personalizados | Detalhe em painel; formulário com ajuda e validação |
| Link Tester | Campo de URL, progresso e resultados por problema; ações objetivas | Resultados em página, detalhe em painel |
| Acessos | Pessoas, papel e escopo; estados convite/revogação/compartilhamento | Drawer de convite; confirmação somente para ação destrutiva |
| Recursos compartilhados | Mesmo desenho do monitor; escopo e modo leitura claros | Sem CTAs indisponíveis de edição |
| Relações com Workspace | Vínculos opcionais; indisponível continua removível para responsável Reports | Painel de associação com busca; sem obrigar criar projeto |
| Notificações e histórico | Linha temporal com ícone, ator quando disponível, data e ação | Painel único, grupos por data; confirmar componente/entrada existentes antes de expandir escopo |

Planos, cobrança e configurações globais: se acessados pelo shell de outro produto, reutilizar a superfície existente; não criar módulo duplicado no Reports só porque aparece na referência.

## 6. Flow Studio: refinamento específico

- Header: voltar, marca/seletor, nome editável, Editar/Monitorar, salvamento e Publicar; ações secundárias em menu. Avaliar perfil/créditos compacto conforme espaço, sem duplicar sidebar global no editor.
- Explorador: abas Páginas/Origens/Eventos; busca sem dupla borda; grupos com contagem e seleção; ícones de localizar/adicionar com tooltip.
- Inspector: ícone e título no cabeçalho; Resumo/Configuração; URL, evento e status em seções. Campos avançados recolhidos e exemplos concretos.
- Nós de origem compactos com logo/título; páginas com preview real ou placeholder honesto; conversões com símbolo e métrica. Evitar transformar tudo no mesmo card grande.
- Arestas agrupadas identificadas como agregados, sem reconectar diretamente IDs visuais; detalhar membros quando necessário.
- Organizar da esquerda para a direita, desfazer e ajuste à área livre disponíveis. Grupos movidos preservam autoria.
- Monitoramento mantém layout da edição; pontos em movimento indicam atividade recente comprovada, com legenda e pausa. Conexão operacional, coleta recente e usuário online são estados distintos.
- Nunca misturar dados de períodos, sites ou clientes. Skeleton inicial e estado de dado desatualizado não mostram número fictício.

## 7. Formulários, tabelas e conteúdo

Formulários: label, requerido, ajuda, erro no mesmo padrão; agrupamento por significado; validação ao sair/enviar; foco no primeiro erro; resumo para múltiplos erros. Preservar valores após falha. Botões de submissão mostram progresso e impedem duplicação.

Tabelas: título/contagem + toolbar com busca, filtros e ação; uma superfície. Seleção em lote só quando houver ação real. Cabeçalho claro, linhas com separador discreto, densidade consistente, paginação e estados vazios. Em viewport estreita, priorizar colunas e permitir scroll local da tabela.

Filtros: período visível e filtros avançados em popover/painel; chips removíveis; Limpar; Aplicar quando há edição em lote. Rótulos sempre descrevem o contexto atual. Não esconder filtros ativos.

Estados: novo usuário recebe sequência curta para conectar dados; coleta pendente explica o requisito; sem resultado permite limpar filtros; erro oferece tentar novamente; acesso negado não revela dados privados. Ilustração pequena e relevante nos estados de início/vazio, sem competir com gráficos reais.

Texto: PT-BR consistente; verbos concretos como Conectar site, Criar fluxo, Aplicar proposta, Publicar alterações. Não expor identificadores técnicos no título; manter em detalhes copiáveis quando úteis.

## 8. Responsividade

- 1440–1920: dois painéis permitidos quando sobra área útil de canvas ≥640 px.
- 1024–1366: um painel aberto por vez se a soma reduzir demais o canvas; ações secundárias vão ao menu.
- 768: navegação recolhida, tabelas com prioridade de colunas; painel ocupa largura limitada disponível.
- 390–430: painel em tela inteira, header/rodapé persistentes; monitoramento legível; edição por seleção/toque, com ações alternativas ao drag. Não anunciar paridade de edição móvel antes de validar.
- Verificar altura 600/768/900, zoom do navegador 200%, teclado virtual e safe areas. Nenhum CTA de confirmação fora da tela.

## 9. Implementação em fases

### Fase 0 — segurança funcional e inventário
Corrigir os dois defeitos de grupos. Capturar baseline por rota e estado. Mapear todos os drawers, overlays e formulários. Confirmar componentes Untitled disponíveis/licenciados. Registrar contratos existentes de API e permissões.
Aceite: inventário fechado, regressões de grupos cobertas, nenhuma mudança de contrato involuntária.

### Fase 1 — componentes e tela piloto
Implementar PanelShell, header/body/footer, FormSection, StatusNotice, toolbar de tabela e variantes explícitas dos controles. Aplicar primeiro ao inspector de evento e ao painel de montagem automática: validam formulário, abas, progresso e rodapé.
Aceite: aparência comparada às referências, teclado/foco/scroll aprovados e ausência de bordas duplicadas. Biblioteca de exemplos com dados demonstrativos identificados.

### Fase 2 — editor e monitoramento
Migrar catálogo, blocos, inspector, montagem, validação, histórico e detalhes de métricas. Unificar regras de abertura e área disponível. Remover CSS antigo correspondente.
Aceite: drag, seleção, grupos, conexões, zoom, undo, autosave, publicação e troca de fluxo/cliente preservados.

### Fase 3 — navegação e operações
Migrar shell, visão geral, clientes, contas, campanhas, sites e eventos. Aplicar tabela/toolbar e estados de onboarding.
Aceite: mesma composição de headers, filtros e ações; nenhum header duplicado; mesma linguagem para a mesma ação.

### Fase 4 — processos extensos e administração
Migrar relatórios, importações, dados de mídia, Link Tester, acessos e vínculos Workspace. Refinar notificações/histórico onde disponíveis.
Aceite: tarefas longas em páginas, relações opcionais preservadas, permissões e estados de falha validados.

### Fase 5 — revisão e publicação
Comparação visual por rota, testes funcionais e de acessibilidade; build; revisão dos estilos removidos; commit na main; homologação e deploy somente com acesso operacional disponível.
Aceite: captura de evidência por tela/estado, sem erros de console, bundle atualizado e smoke test após deploy. Se regressão, reverter o commit de migração correspondente, sem reset destrutivo de dados.

## 10. Arquivos e limites de execução

Base: `ReportsDrawer.jsx`, `ReportsActionButton.jsx`, `ReportsTabs.jsx`, `ReportsFieldInput.jsx`, `ReportsNativeSelect.jsx`, `ReportsTextArea.jsx`, `PageChrome.jsx`, kit e tema.
Flow: `FlowInspector.jsx`, `FlowCatalog.jsx`, `FlowBlueprint.jsx`, `FlowStudioAssist.jsx`, `FlowCanvas.jsx`, `FlowMonitorWorkspace.jsx`, `usePanelLayout.js` e folhas CSS associadas.
Páginas: extrair de `main.jsx` gradualmente; manter `ReportsCustomers.jsx`, `ReportsRelationships.jsx`, `SharedReports.jsx` integrados ao padrão.

A adaptação visual não requer reset de banco nem migração de ownership. APIs só mudam se faltar informação comprovadamente necessária; documentar antes de implementar. Sem criar um segundo design system, sem adicionar overrides globais para consertar um único painel, sem usar imagens de IA como campos/tabelas/grid.

## 11. Checklist de aprovação final

- Todas as áreas da matriz têm estados de carregamento, vazio, sucesso, falha e acesso restrito quando aplicáveis.
- Um header por página; ações com hierarquia; ícones sem rótulo têm nome acessível.
- Labels associados aos campos; tabs associadas a painéis; contraste AA; foco visível e retorno de foco.
- Inputs e tabelas sem wrappers com bordas duplicadas; sem card por campo ou por seção sem necessidade.
- Painéis cabem em altura curta, preservam valores e não ocultam o CTA; mobile não acumula overlays.
- Fotos reais quando disponíveis, iniciais como fallback; favicons com fallback; nenhuma pessoa ou dado inventado.
- Performance de arraste em 200 nós comparada ao baseline; medir FPS/latência no mesmo ambiente, sem prometer 60 FPS universal.
- Zero regressão conhecida de autoria, isolamento por cliente, permissões ou persistência; os dois defeitos de grupos resolvidos antes de considerar a migração concluída.
