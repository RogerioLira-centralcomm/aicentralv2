# Plano de evolução da Home do Cadu

## Objetivo

Reorganizar a Home do Cadu usando a eficiência da Home do Codex como referência de interação, sem copiar sua aparência. A entrega deve preservar a skin clara do Cadu, seus tokens, sua navegação lateral, seus componentes React e todo o comportamento existente de contexto, anexos, voz e intensidade do agente.

O resultado esperado é uma Home que responda imediatamente a três perguntas:

1. O que posso pedir?
2. Em qual projeto ou sessão vou trabalhar?
3. Que recursos e modo o Cadu usará?

## Diagnóstico das quatro capturas

### O que funciona melhor no Codex

- O título é curto, leve e subordinado ao campo de entrada.
- O composer é a peça dominante da página, com largura confortável e altura que convida a escrever.
- O placeholder descreve a ação, não a marca.
- A linha superior do composer pertence à mensagem; a linha inferior concentra ações e configurações.
- Projeto e plugins ficam fora da área principal de digitação e são reconhecíveis como contexto/ferramentas.
- O menu `+` é uma central de ações: anexar, planejar, criar e conectar recursos.
- Os controles são progressivamente revelados. A Home permanece simples até a pessoa pedir mais opções.

### Onde a Home atual do Cadu perde eficiência

- O título em duas linhas, com `clamp(36px, 4vw, 52px)`, compete com o objetivo real da tela: começar uma conversa.
- O subtítulo repete a função já comunicada pelo campo.
- `Pergunte ao Cadu…` fala do produto; não ajuda a pessoa a formular a tarefa.
- Projeto, intensidade, voz e envio ocupam a mesma faixa à direita. A composição parece apertada mesmo com espaço horizontal disponível.
- O `+` mistura anexos, prompts prontos, modo do agente, integrações futuras e destino dos anexos em um menu longo, com mais carga cognitiva do que o Codex.
- A escolha do projeto está visualmente tratada como mais um controle técnico, embora seja uma decisão estrutural de contexto.
- “Equilibrado” explica pouco quando aparece isolado. O conceito de intensidade existe, mas a pessoa precisa abrir o menu para entendê-lo.
- A Home usa um campo branco compacto de 76 px. Ele parece um formulário, não o início de uma área de trabalho.

## Direção de design

### Princípio central

Adotar a arquitetura do Codex, não sua estética: uma pergunta discreta, um composer de duas camadas e uma barra contextual clara. A personalidade continua sendo do Cadu por meio do fundo atmosférico, verde mineral, bordas suaves, tipografia e linguagem em português.

### Hierarquia proposta

```text
                         Em que vamos trabalhar?

    ┌──────────────────────────────────────────────────────────┐
    │ Descreva uma tarefa, decisão ou ideia…                    │
    │                                                          │
    │  +  Ações                                  Modo   Voz  ↑  │
    ├──────────────────────────────────────────────────────────┤
    │  Projeto: Sessão rápida                 Recursos e apps   │
    └──────────────────────────────────────────────────────────┘
```

- Título: apenas uma linha sempre que houver largura suficiente.
- Sem subtítulo fixo no desktop; o placeholder assume o papel de orientação.
- Composer dividido em corpo de mensagem, barra de ações e barra contextual.
- Barra contextual pode ser integrada ao mesmo contorno, mas usa fundo levemente diferente para comunicar uma camada de configuração.

### Tokens a preservar

- Fundo: manter o campo claro e atmosférico já usado na Home (`#edf3f3` e variações existentes).
- Superfície: `var(--cadu-surface)` / branco atual.
- Texto: `var(--cadu-ink)`.
- Texto secundário: `var(--cadu-muted)`.
- Acento e foco: `var(--cadu-accent)` e `var(--cadu-accent-strong)`.
- Linha: `var(--cadu-line)`; evitar introduzir cinzas do Codex.
- Tipografia: manter a família atual do produto. A mudança é de escala e peso, não de identidade.
- Raios: reutilizar os tokens atuais; diferenciar o contêiner principal dos controles menores.

### Escala sugerida

- Título desktop: 28–32 px, peso 600–650, `line-height` 1.15.
- Título mobile: 26–30 px.
- Placeholder/input: 15–16 px, contraste suficiente para leitura, mas claramente secundário ao texto digitado.
- Controles: 13–14 px; áreas clicáveis com mínimo de 40 × 40 px.
- Largura do conjunto: 720 px como base atual, podendo chegar a 760 px se os testes de sidebar mostrarem espaço.
- Altura vazia do composer: 104–116 px no desktop; 96–108 px no mobile.

## Copy recomendada

### Título

Usar uma frase estável na primeira versão:

`Em que vamos trabalhar?`

Motivo: é curta, orientada ao trabalho e combina com projeto, tarefa, ideia ou conversa livre. A rotação atual de 30 títulos adiciona variação sem ganho funcional e dificulta testes visuais e consistência de marca.

### Placeholder

Recomendação principal:

`Descreva uma tarefa, decisão ou ideia…`

Alternativa mais direta:

`O que você quer fazer?`

Evitar `Pergunte ao Cadu…`, pois a Home também inicia criação, análise, pesquisa e planejamento — não apenas perguntas.

### Contexto sem projeto

Manter `Sessão rápida`, pois já está implementado e comunica menor compromisso que “projeto”. No menu, explicar: `Conversa sem contexto de projeto`.

### Modo do agente

- Trigger compacto: `Equilibrado` com ícone e chevron.
- Cabeçalho do menu: `Como o Cadu deve trabalhar`.
- Opções atuais podem permanecer:
  - `Rápido` — resposta direta.
  - `Equilibrado` — analisa contexto e fontes.
  - `Profundo` — planeja e executa tarefas complexas.

## Arquitetura dos componentes React

### 1. `WorkspaceHome.jsx`

Responsabilidades após a mudança:

- Renderizar o título estável.
- Manter o estado de mensagem, projeto, marca, anexos e intensidade.
- Passar ao composer os recursos realmente disponíveis no bootstrap.
- Remover o subtítulo fixo.
- Não duplicar seleção de projeto fora do composer.

Mudanças propostas:

- Substituir `HOME_TITLES` por uma constante `HOME_TITLE` na primeira entrega.
- Manter `WorkspaceChatComposer` como ponto único de entrada.
- Preservar `HomeCreditAlert` imediatamente abaixo, sem fazer o alerta competir com o composer.

### 2. `WorkspaceChatComposer.jsx`

Transformar a marcação interna em três regiões explícitas:

- `ComposerMessageArea`: textarea, contexto de resposta, anexos e preview de link.
- `ComposerPrimaryActions`: adicionar, modo, voz e enviar.
- `ComposerContextBar`: projeto/sessão e recursos/apps.

Esses podem começar como componentes locais no mesmo arquivo. Extrair arquivos novos apenas quando a API estiver estabilizada.

### 3. `ComposerAddMenu` — novo componente local ou arquivo dedicado

O botão `+` deve abrir um menu curto e orientado a verbos:

Seção `Adicionar`:

- Arquivos e pastas.
- Imagem.
- Link ou referência.

Seção `Trabalhar`:

- Pesquisar na internet.
- Analisar criativo.
- Resumir reunião.
- Planejar trabalho — somente quando o modo/recurso estiver disponível.

Regras:

- Remover do menu principal a escolha da intensidade; ela já possui controle próprio.
- Remover do primeiro nível os itens “Em breve”. Recursos indisponíveis pertencem ao menu de apps/conexões.
- Exibir atalhos de teclado apenas se forem reais.
- Manter `role="menu"`, navegação por teclado, Escape e retorno de foco ao trigger.

### 4. `ComposerContextBar` — novo

Duas ações principais:

- À esquerda: projeto atual ou `Sessão rápida`.
- À direita: `Recursos` ou `Apps`, com contador/estado apenas quando houver conexão ativa.

O seletor de projeto reutiliza `ProjectSelector`, mas sua apresentação muda:

- Trigger com ícone, rótulo e chevron.
- Menu com `Sessão rápida` primeiro.
- Lista limitada inicialmente aos projetos recentes.
- Link final `Ver todos os projetos` se o catálogo exceder o limite.
- Busca apenas quando houver volume que justifique; não adicionar por padrão.

### 5. `ComposerResourcesMenu` — novo

Equivalente funcional ao menu de plugins do Codex, adaptado ao Cadu:

- Recursos nativos: pesquisa web, análise de criativo, resumo de reunião.
- Conectores disponíveis no bootstrap: Drive, documentos, automações etc.
- Estados: conectado, disponível para conectar, indisponível.
- A ação deve refletir capacidade real do backend; nenhum item decorativo ou falso.

Na primeira fase, o menu pode exibir apenas os recursos já funcionais. A infraestrutura para integrações futuras fica preparada, sem colocar botões desabilitados na Home.

### 6. `AgentModeMenu`

Manter o componente atual e melhorar:

- Copy descritiva consistente.
- `aria-label` deve usar “Modo do agente”, não “Intensidade”, se esse for o termo adotado na interface.
- Seleção ativa com check e não apenas cor.
- Menu alinhado à direita do trigger e contido no viewport.

## Comportamentos e estados

### Vazio

- Título e composer centralizados verticalmente um pouco acima do meio óptico.
- Botão enviar desabilitado.
- `Sessão rápida` selecionada.
- `Equilibrado` como modo padrão.

### Foco

- Uma única mudança de borda/anel no contêiner completo.
- Não aplicar foco visual concorrente em cada barra.
- Placeholder some naturalmente quando há texto; não usar label flutuante.

### Com texto

- Textarea cresce até o limite atual de 120 px.
- Depois do limite, scroll interno.
- A barra de ações permanece no rodapé do composer.

### Com anexos

- Chips ficam entre o textarea e a barra de ações.
- Destino do anexo é mostrado no chip ou em um popover contextual, não como uma seção permanente no menu `+`.
- Sem projeto, destinos de projeto não devem aparecer como escolhas desabilitadas; mostrar a opção somente depois de selecionar projeto.

### Com projeto

- O nome substitui `Sessão rápida` na barra contextual.
- Recursos dependentes do projeto aparecem no menu de recursos.
- O estado continua usando `context_mode: bound`; sessão livre continua usando `free`.

### Arrastar e soltar

- Preservar anexos por drop e contexto de projeto por payload.
- Realçar o contêiner completo, com mensagem curta específica para arquivo ou contexto quando possível.

### Voz

- Preservar reconhecimento em `pt-BR`.
- Estado ouvindo precisa de mudança de cor e animação discreta, respeitando `prefers-reduced-motion`.
- Falhas continuam anunciadas por `role="status"`.

### Carregamento e envio

- Preservar fila e interrupção em conversas.
- Na Home, envio leva para a nova conversa como hoje.
- Estado desabilitado precisa manter contraste perceptível, não apenas opacidade muito baixa.

## Responsividade

### Desktop, acima de 1180 px

- Largura ideal de 720–760 px.
- Título centralizado e com uma linha.
- Barra contextual completa com texto `Recursos`/`Apps`.

### Tablet, 761–1180 px

- Mesmo desenho, largura fluida.
- Truncar nomes longos de projeto.
- Reduzir rótulos secundários antes de remover controles.

### Mobile, até 760 px

- Preservar o chrome móvel existente.
- Título alinhado à esquerda, no máximo duas linhas.
- Composer com largura total e áreas de toque de pelo menos 44 px quando possível.
- Barra contextual pode quebrar em duas linhas ou trocar `Recursos e apps` por ícone + `Recursos`.
- Projeto e modo não devem desaparecer: são decisões essenciais.
- Menus abrem como popover amplo ou bottom sheet; nunca ultrapassam a altura visual disponível quando o teclado estiver aberto.

## Estratégia CSS

- Concentrar todas as regras específicas da Home em `WorkspaceHome.css`.
- Evitar adicionar novos overrides no final de `styles.css`, que já possui várias camadas históricas para a mesma Home.
- Introduzir classes semânticas para as três regiões do composer, reduzindo seletores baseados em `aria-label`.
- Usar tokens existentes e `color-mix` onde já suportado no projeto.
- Preservar o isolamento por `.is-workspace-home` para não alterar o composer da conversa.
- Após estabilizar, remover regras antigas da Home que tenham sido completamente substituídas; não deixar duas implementações competindo na cascata.

## Ordem de implementação

### Fase 1 — estrutura e hierarquia

- Fixar título e nova copy do placeholder.
- Remover subtítulo.
- Criar as três regiões do composer.
- Reposicionar projeto e recursos na barra contextual.
- Manter toda a lógica existente.

Critério de saída: a Home já deve ter a leitura visual da referência em desktop e mobile, sem regressão funcional.

### Fase 2 — menus eficientes

- Separar menu de adicionar do menu de recursos/apps.
- Retirar modo do agente e itens futuros do `+`.
- Reorganizar destino de anexos.
- Melhorar descrição dos modos.

Critério de saída: cada menu tem um único propósito e nenhuma ação falsa.

### Fase 3 — estados, acessibilidade e polimento

- Teclado, Escape, retorno de foco e roving/foco dos itens.
- Estados de drop, voz, upload, erro e envio.
- Ajustes de contraste, truncamento e viewport com teclado móvel.
- `prefers-reduced-motion`.

Critério de saída: fluxo completo utilizável sem mouse e sem overflow em todos os breakpoints.

### Fase 4 — limpeza e consolidação

- Remover CSS substituído.
- Documentar API dos subcomponentes.
- Confirmar que Home e conversa continuam compartilhando lógica sem compartilhar layout indevidamente.

## Testes necessários

### Testes de estrutura

Atualizar `tests/frontend/cadu-conversations-v2-integration.test.cjs` para verificar:

- existência das três regiões do composer;
- placeholder novo;
- projeto dentro da barra contextual;
- modo fora do menu `+`;
- ausência dos itens “Em breve” na Home;
- preservação de `context_mode` livre e vinculado;
- preservação de upload, voz e envio.

### Testes visuais/layout

Atualizar `tests/frontend/cadu-workspace-layout.test.cjs` com cenários em:

- 1440 × 1000;
- 1180 × 820;
- 768 × 1024;
- 390 × 844;
- 360 × 800.

Asserções principais:

- sem overflow horizontal;
- composer não colide com sidebar/dock;
- título não excede duas linhas no mobile e uma linha em desktop largo;
- menus permanecem dentro do viewport;
- targets principais mantêm tamanho acessível;
- teclado visual móvel não encobre os controles essenciais.

### Testes funcionais

- enviar sessão rápida;
- enviar em projeto;
- trocar modo;
- anexar arquivo e imagem;
- alterar/remover destino do anexo;
- colar link e abrir preview;
- usar ditado e tratar navegador incompatível;
- arrastar arquivo e projeto;
- navegar e fechar menus apenas com teclado.

## Critérios de aceite do produto

- Em até dois segundos, uma pessoa identifica onde escrever, qual contexto está ativo e onde alterar o modo.
- O título não é o elemento dominante; o composer é.
- Projeto deixa de parecer uma configuração técnica escondida.
- `+` contém apenas ações de adição/trabalho relacionadas ao pedido.
- Recursos/apps têm entrada própria e representam somente capacidades reais.
- A skin continua inequivocamente Cadu: fundo, cores, tipografia, foco, ícones e tom de voz permanecem coerentes com o design system.
- Nenhum comportamento existente de upload, voz, link, contexto ou roteamento é perdido.
- Desktop e mobile passam nos testes de layout e teclado.

## Decisões que não exigem rediscussão

- React e os componentes atuais serão mantidos.
- Não haverá cópia do tema escuro do Codex.
- A dock e a sidebar do Cadu permanecem.
- A arquitetura `free`/`bound` permanece.
- `Equilibrado` permanece como padrão.
- A Home continuará sendo uma entrada para conversa, e não um dashboard de cards.

## Riscos e mitigação

- **Cascata CSS histórica:** isolar regras em `WorkspaceHome.css` e remover overrides substituídos na fase 4.
- **Menu `+` acoplado a muitas funções:** separar por responsabilidade antes de mudar lógica.
- **Diferença entre Home e conversa:** usar props/slots explícitos; não condicionar comportamento por CSS apenas.
- **Integrações ainda não disponíveis:** renderizar somente capacidades confirmadas no bootstrap.
- **Nomes longos de projetos:** truncamento com tooltip/nome acessível completo.
- **Viewport móvel com teclado:** usar as variáveis de viewport já existentes e testar com textarea expandido.

## Entrega recomendada

Executar em um único ciclo de produto, mas em quatro commits correspondentes às fases acima. A Fase 1 já produz o maior ganho perceptível; Fases 2 e 3 evitam que a nova aparência esconda os mesmos problemas de organização e acessibilidade.
