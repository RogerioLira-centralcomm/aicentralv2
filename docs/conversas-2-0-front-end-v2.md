# Cadu Conversas 2.0 — arquitetura do front-end

## Diretriz

Conversas 2.0 será um módulo de operação do Workspace. A conversa mostra sínteses curtas; o trabalho completo aparece no artefato editável. O módulo deve preservar a casca visual do Workspace, a sessão Python/Flask e os dados existentes no PostgreSQL.

O primeiro corte será funcional com dados mockados para todos os fluxos que não dependem da resposta do agente. As intenções do usuário devem funcionar como ações de interface: trocar contexto, trocar projeto, abrir conversa antiga, criar rascunho, abrir artefato, alterar intensidade, selecionar texto e aplicar uma edição simulada.

## Referência de qualidade de interface

As telas do Dify anexadas pelo produto são referência de acabamento e organização, não para copiar a aparência literalmente. O Cadu deve adotar a mesma disciplina estrutural:

- shell do aplicativo estável, com navegação lateral persistente;
- canvas central amplo para o trabalho principal;
- inspector lateral direito para configurações, resultados, fontes e ações;
- topbar compacta com estado, salvar, visualizar, compartilhar e publicar;
- controles densos, mas legíveis, com padding consistente;
- modais largos e focados para tarefas complexas;
- abas claras para separar configuração, execução, preview e código;
- estados ativos, selecionados, erro e salvamento automático muito visíveis;
- separadores e divisores usados para organizar, não para decorar;
- nenhuma mudança brusca de raio, padding, altura de campo ou linguagem de botão.

O objetivo é que Conversas, artefatos, relatórios e HTML pareçam partes do mesmo Workspace. A conversa é uma superfície do produto; o artefato aberto é outra superfície do produto; o modal é uma terceira superfície, todas governadas pelo mesmo sistema.

### Métricas iniciais de layout

- navegação primária: 248 px;
- inspector de artefato: 384–440 px, redimensionável;
- topbar: 52–60 px;
- controles compactos: 32–36 px de altura;
- campos de formulário: 36–40 px;
- modal padrão: 640–960 px conforme a tarefa;
- padding de shell: 16 px;
- padding de painel: 16–20 px;
- gap de controles: 8 px;
- gap de seções: 20–24 px;
- borda de superfície: 1 px com contraste discreto;
- foco: anel visível de 2 px, sem depender apenas da cor.

### Modal system

Modais devem seguir quatro tamanhos e uma mesma anatomia:

```text
┌──────────────────────────────────────────────┐
│ ícone  Título                         fechar  │
│        descrição curta                       │
├──────────────────────────────────────────────┤
│ tabs / modo / contexto                       │
│                                              │
│ conteúdo principal                           │
│                                              │
├──────────────────────────────────────────────┤
│ cancelar / ação secundária       ação primária│
└──────────────────────────────────────────────┘
```

- small: confirmação, renomear, selecionar projeto;
- medium: editar contexto, comparar versões, configurar ação;
- large: editor de esquema, preview HTML, relatório detalhado;
- full: artefato complexo ou canvas interativo.

O modal deve manter o contexto da origem visível no fundo, com overlay escuro, foco preso, Escape para fechar e confirmação antes de perder alterações.

## Uso de cada base open source

### assistant-ui

Usar somente como referência e, se a ilha React for ativada, como camada de primitives para:

- lista de threads;
- runtime de conversa;
- estado de streaming;
- composer com anexos;
- interromper e retomar uma execução;
- mensagens com partes e anexos.

Não usar o tema pronto nem a estrutura visual pronta. A sidebar, os tokens e os componentes visuais continuam sendo do Cadu.

### Vercel AI SDK UI

Usar somente na camada de transporte do módulo React, caso o streaming seja migrado para essa ilha:

- `useChat` ou adaptador equivalente para streaming;
- estados `ready`, `submitted`, `streaming` e `error`;
- file parts e mensagens multimodais;
- abort/retry.

O endpoint continuará sendo Flask. O SDK não será responsável por autenticação, persistência ou regra de negócio.

### Tiptap

Usar somente como um dos renderizadores internos de artefato, quando o resultado for textual:

- texto selecionável;
- edição inline;
- bubble menu “Editar com Cadu”;
- proposta de alteração com aplicar/descartar;
- undo/redo;
- blocos de título, parágrafo, lista e tabela;
- serialização para HTML/JSON persistível.

Tiptap não é o sistema de artefatos. Ele é apenas o modo de edição de documentos textuais dentro desse sistema.

### BlockNote

Não usar na primeira implementação. Ele é uma alternativa caso os artefatos evoluam para um editor de páginas em blocos, com drag-and-drop e colaboração. Misturar BlockNote e Tiptap agora criaria dois modelos de documento.

### Motion

Não adicionar uma biblioteca de animação no primeiro corte. Usar CSS transitions/keyframes do Workspace para:

- abrir e fechar a sidebar de artefatos;
- mudar de conversa;
- revelar atividade do agente;
- mostrar proposta de edição;
- respeitar `prefers-reduced-motion`.

Se depois precisarmos de timelines complexas, introduzir Motion apenas na ilha React.

## Compatibilidade com o stack atual

O repositório atual já possui:

- Python/Flask;
- PostgreSQL e tabelas de conversas existentes;
- HTML server-rendered;
- JavaScript vanilla;
- Tailwind e CSS específico de Conversas;
- endpoints `/familia/api/...` e `/workspace/api/...`;
- histórico, anexos, profundidade, streaming e painel de artefatos parciais.

Por isso, o V2 começará como uma evolução compatível da página existente. A ilha React só entra quando o contrato visual e os estados mockados estiverem aprovados. Assim não criamos uma segunda casca do Workspace.

## Sistema de artefatos

Artefato é qualquer resultado de trabalho que pode ser aberto ao lado da conversa, inspecionado, acionado, editado, executado, salvo, versionado ou enviado para outro produto do Workspace. Não é sinônimo de documento.

### Tipos de artefato

| Tipo | Visualização principal | Ações principais |
|---|---|---|
| Texto / briefing | Editor rico | Editar seleção, aplicar sugestão, salvar, versionar |
| Relatório | Resumo + tabelas + gráficos | Filtrar, comparar período, exportar, adicionar ao projeto |
| HTML | Navegador renderizado em iframe seguro | Abrir preview, pedir alteração |
| Tabela / dados | Grade navegável | Filtrar, ordenar, copiar, exportar |
| Plano / cenário | Painel de decisão | Comparar, selecionar cenário, enviar ao Planner |
| Pesquisa | Fontes + síntese | Abrir fonte, citar, salvar insight, revisar evidência |
| Arquivo | Preview adequado ao formato | Baixar, abrir, vincular, substituir versão |
| Imagem / criativo | Preview visual | Abrir no Studio, comparar, salvar referência |
| Tarefa / decisão | Checklist ou registro | Confirmar, atribuir, transformar em projeto |

### Anatomia da sidebar de artefatos

```text
┌──────────────────────────────────────────────┐
│ Briefing de campanha          [⋯] [fechar]   │
│ criado agora · versão 3 · salvo automaticamente│
├──────────────────────────────────────────────┤
│ [Preview] [Variações] [Fontes]                │
├──────────────────────────────────────────────┤
│                                              │
│   preview específico do tipo de resultado    │
│   texto, relatório, gráfico, tabela ou HTML  │
│                                              │
├──────────────────────────────────────────────┤
│ Ações do resultado                           │
│ [Adicionar ao projeto] [Comparar] [Exportar] │
│ [Abrir no Planner] [Abrir no Studio]         │
└──────────────────────────────────────────────┘
```

### HTML interativo

Para resultados HTML, o usuário vê somente o navegador com o resultado renderizado dentro de um iframe isolado. HTML, CSS e JavaScript ficam encapsulados no artefato e não aparecem na interface principal.

- preview clicável em iframe sandbox;
- barra mínima de navegador: recarregar e abrir maior;
- ação principal: “Pedir alteração”;
- ação secundária: “Abrir preview”;
- novas alterações são pedidas pelo composer e geram uma nova versão.

O preview nunca é injetado diretamente no DOM principal. Scripts, origem, permissões, links externos, downloads e formulários passam por uma política de segurança própria do iframe.

Esse comportamento segue o modelo de arquivos com preview renderizado e vista de código documentado para o visualizador de arquivos do ChatGPT. [OpenAI Docs — trabalhar com arquivos](https://developers.openai.com/pt-BR/docs/artifacts-viewer)

### Ações contextuais

As ações não são iguais para todos os artefatos. O componente recebe uma lista declarativa:

```js
{
  id: 'artifact-report-01',
  type: 'report',
  renderer: 'report',
  tabs: ['preview', 'data', 'sources'],
  actions: [
    'add_to_project',
    'compare_period',
    'export',
    'create_decision'
  ],
  editable: false,
  sourceRefs: ['report-august', 'media-plan-v4']
}
```

O resultado pode ser editável, acionável, executável, comparável ou apenas visualizável. A interface deve comunicar qual desses comportamentos está disponível.

Cada artefato deve mostrar uma ação principal e no máximo duas secundárias. O restante fica em um menu discreto. Não exibir todas as possibilidades ao mesmo tempo.

```text
Imagem       Editar no Studio   Gerar variação       ⋯
HTML         Pedir alteração    Abrir preview        ⋯
Relatório    Ver relatório      Comparar             ⋯
Briefing     Editar             Adicionar ao projeto ⋯
Plano        Revisar            Abrir no Planner     ⋯
```

## Coluna principal de Conversas

A coluna central não deve competir com o artefato. Ela funciona como uma linha de trabalho curta e contínua.

### Linguagem visual da conversa

O chat do Cadu não deve parecer um mensageiro social. Não usar avatares, bolhas repetidas ou uma linha de horário em cada mensagem.

- mensagens do usuário ficam alinhadas à direita, com tratamento discreto;
- respostas do Cadu ficam alinhadas à esquerda, sem avatar e sem moldura pesada;
- a marca Cadu aparece no header e nos estados do sistema, não como avatar repetido;
- o nome do autor só reaparece quando houver mudança clara de autor ou de etapa;
- horários ficam ocultos por padrão;
- horário aparece apenas em revisão, histórico detalhado, auditoria ou atividade expandida;
- mensagens consecutivas do mesmo autor são agrupadas em um único fluxo;
- respostas simples são texto puro;
- blocos visuais só aparecem quando há decisão, confirmação, atividade, resultado ou ação necessária.

Exemplo de fluxo preferencial:

```text
Você
Analise o briefing e indique o que precisa ser revisado.

Cadu
Encontrei três pontos para revisar: público, canais e KPI.
Abra o briefing ao lado para ver os detalhes.

[Abrir briefing] [Revisar público] [Comparar versões]
```

Em vez de:

```text
[avatar] Você 10:14   mensagem em uma bolha
[avatar] Cadu 10:15   outra bolha
[avatar] Cadu 10:15   outra bolha
```

### Quando mostrar horário

Mostrar horário somente quando ele ajuda a entender o trabalho:

- revisão de uma decisão;
- linha do tempo de execução;
- comparação entre versões;
- atividade que demorou ou foi retomada;
- histórico expandido solicitado pelo usuário.

O horário deve ser secundário, pequeno e não competir com a mensagem.

### Padrão visual de retorno

A referência visual aprovada estabelece uma sequência simples para as respostas:

1. indicador discreto de execução, como “Trabalhou por 22 s”, expansível;
2. resultado textual principal, sem card decorativo;
3. explicação curta em linguagem de usuário;
4. links para arquivos, documentos ou artefatos relacionados;
5. faixa de alteração no rodapé quando um arquivo foi criado ou modificado.

```text
Trabalhou por 22 s  ›

Refinei as interações no documento.

O chat agora segue estas regras:
texto simples e direto, sem repetir o conteúdo inteiro do artefato.

[Abrir documento] [Revisar resultado]

Documento atualizado
conversas-2-0-front-end-v2.md
                            [Desfazer] [Revisar]
```

O link de arquivo deve parecer um objeto real do Workspace, com nome, tipo e ação clara. Não deve virar um card de resumo dentro da mensagem.

### Desfazer, revisar e versionamento

Toda alteração de arquivo ou artefato deve retornar uma faixa contextual, sem interromper a conversa:

- “Documento atualizado”;
- nome e tipo do arquivo;
- “Desfazer” para reverter imediatamente a última alteração;
- “Revisar” para abrir o resultado no inspector;
- “Ver histórico” quando houver mais de uma versão.

No primeiro corte, o desfazer pode ser limitado à última alteração da sessão. A estrutura deve nascer preparada para versionamento futuro por artefato, com `version_id`, `parent_version_id`, `created_by`, `created_at` e `change_summary`.

Git não deve aparecer para o usuário comum. A interface deve falar em versão, alteração e desfazer.

### Google Drive, Docs e Sheets

Links externos usados pelos agentes devem entrar no modelo de artefatos conectados:

- Google Drive: arquivo ou pasta vinculada, com nome, tipo, proprietário, data e permissão;
- Google Docs: documento aberto em preview ou edição, com referências usadas na resposta;
- Google Sheets: tabela visualizável, com aba, intervalo, filtros e célula de origem;
- links do Drive devem ser fontes clicáveis e também poder virar artefatos do projeto;
- o Cadu deve mostrar quando está usando uma cópia sincronizada, uma referência externa ou conteúdo importado;
- alterações externas exigem confirmação explícita;
- a conversa pode resumir e comparar o conteúdo sem perder o link de origem.

```text
Encontrei o orçamento na planilha do projeto e comparei com o briefing.

[Orçamento 2027 · Google Sheets] [Abrir fonte]
[Ver comparação] [Salvar no projeto]
```

O artefato interno deve guardar a proveniência: URL original, arquivo, aba/intervalo ou trecho usado, data de sincronização e permissões aplicáveis.

### Header

- título editável da conversa;
- breadcrumb Cliente → Projeto → Objeto;
- seletor de projeto/contexto;
- estado do Cadu: disponível, trabalhando, aguardando confirmação ou erro;
- intensidade: Foco, Análise ou Pesquisa profunda;
- menu de ações da conversa: compartilhar, renomear, arquivar e iniciar nova conversa.

O header deve ter entre 56 e 64 px, sem transformar cada ação em um card.

### Mensagens

- usuário e Cadu aparecem como mensagens leves;
- respostas do Cadu começam com síntese de até três linhas;
- detalhes extensos viram artefato no inspector direito;
- atividades aparecem como linha compacta expansível;
- ações surgem somente quando aplicáveis;
- geração de imagem aparece como resultado de conversa com preview, não como uma tela separada.

### Geração de imagem dentro da conversa

Quando o usuário pedir uma imagem, o fluxo será:

1. o Cadu identifica a intenção `image_generate`;
2. prepara o prompt usando o contexto atual, marca e projeto;
3. chama a API interna de geração do Studio;
4. mostra progresso curto no chat;
5. abre o resultado no inspector de artefatos;
6. oferece `Editar no Studio`, `Gerar variação`, `Ajustar imagem` e `Adicionar ao projeto`;
7. permite pedir novas versões no mesmo composer.

O chat não precisa reproduzir todos os controles do Studio. O inspector mostra o resultado, referências, prompt resumido, versões e ações. A edição avançada continua disponível pelo Studio quando necessário.

O contrato visual do resultado deve ser:

```text
Imagem gerada
[preview visual]
2 versões · contexto Reserva · salvo no projeto
[Editar no Studio] [Gerar variação] [Adicionar ao projeto]
```

No primeiro mock, a chamada pode ser simulada, mas o objeto precisa usar o mesmo formato da futura resposta da API: `artifact_id`, `type=image`, `preview_url`, `source_prompt`, `versions`, `project_ref` e `actions`.

### Composer

O composer é o principal controle da tela:

- altura mínima de 72 px;
- cresce somente conforme o texto, até um limite controlado;
- anexos aparecem acima do texto dentro do mesmo shell;
- Enter envia e Shift+Enter quebra linha;
- paste de texto e imagem;
- drag-and-drop sobre o shell;
- botão de interrupção durante streaming;
- seletor de intensidade integrado, mas discreto;
- ações de imagem e artefato no menu `+`;
- foco visível e recuperação de erro sem perder o texto digitado.

O composer nunca deve ocupar metade da tela, mesmo quando uma geração estiver em andamento.

### Anotação e revisão

O usuário deve conseguir marcar uma área do artefato e pedir uma mudança contextual:

1. seleciona texto, célula, bloco, gráfico ou área do preview;
2. abre “Editar com Cadu” ou “Explicar este resultado”;
3. o Cadu cria uma proposta localizada;
4. a sidebar mostra antes/depois;
5. o usuário aplica, descarta ou pede outra versão.

Em HTML, a seleção pode apontar para um elemento/linha/trecho de código. Em relatório, pode apontar para uma métrica ou gráfico. Em imagem, pode apontar para uma área visual e encaminhar para o Studio.

## Casca da tela

## Sidebar principal aprovada

A sidebar do último mockup será tratada como a referência principal do front-end V2. Ela deve permanecer sólida mesmo quando o canvas central mudar entre conversa, relatório, HTML ou outro artefato.

### Estrutura

```text
┌──────────────────────────────┐
│  Cadu     Workspace       ⋯  │  identidade
├──────────────────────────────┤
│  +  Nova conversa             │  ação primária
│  ⌕  Buscar conversas          │  busca global
├──────────────────────────────┤
│  Início                       │
│  Projetos                     │  navegação Workspace
│  Docs                         │
│  Marcas                       │
├──────────────────────────────┤
│ Conversas                     │  seção ativa
│  Fixadas                      │
│  ├ Estratégia de lançamento   │
│  └ Planejamento Q3            │
│                              │
│ Hoje                         │
│  ├ Lançamento Reserva 2027    │  ativa
│  ├ Campanha Always On         │
│  └ Roteiro de mídia           │
│                              │
│ Ontem                        │
│  ├ Análise de concorrência    │
│  └ KPIs e mensuração          │
│                              │
│ Últimos 7 dias               │
│  └ Reposicionamento Nike      │
├──────────────────────────────┤
│ Equipe       Planos     Ajuda │  utilidades
│ ──────────────────────────── │
│ uso de créditos               │
│ avatar · nome · e-mail        │
└──────────────────────────────┘
```

### Regras de interação

- largura padrão de 248 px;
- não usar cards individuais para cada conversa;
- conversa ativa usa apenas fundo, linha de foco e texto mais forte;
- cada item pode mostrar projeto, horário e indicador de execução sem criar outro bloco;
- grupos Hoje, Ontem e Últimos 7 dias são divisores de leitura, não cards;
- Fixadas fica acima da timeline e aceita reordenar;
- busca filtra título, projeto e conteúdo sem sair da sidebar;
- botão Nova conversa permanece sempre acessível;
- hover revela ações de renomear, fixar e arquivar;
- menu contextual abre modal pequeno e consistente;
- em telas menores, a sidebar vira drawer, preservando a mesma hierarquia;
- a sidebar não deve desaparecer quando a sidebar de artefato abrir: são superfícies independentes.

### Estados visuais

- normal: texto secundário e fundo transparente;
- hover: superfície azul-marinho discreta;
- ativa: linha lateral ciano, fundo #162238 e texto principal;
- trabalhando: ponto animado ciano ao lado do horário;
- não lida: título com peso maior e ponto de status;
- fixada: ícone de pin discreto, nunca uma cor adicional dominante;
- arquivada: aparece apenas no filtro/entrada “Arquivadas”.

### O que não levar para a sidebar

- preview de artefato;
- gráficos;
- cards de KPI;
- sugestões contextuais;
- controles de intensidade;
- configurações técnicas;
- múltiplos níveis de navegação aberta;
- textos longos de descrição.

O papel da sidebar é localizar e trocar de conversa. O papel do canvas é conversar. O papel do inspector direito é mostrar o resultado e suas ações.

```text
Workspace Cadu
└── Conversas 2.0
    ├── Sidebar principal
    │   ├── Nova conversa
    │   ├── Busca
    │   ├── Fixadas
    │   ├── Recentes por data
    │   ├── Conversas por projeto
    │   └── Arquivadas
    ├── Barra superior
    │   ├── Título da conversa
    │   ├── Cliente / projeto / objeto
    │   ├── Seletor de intensidade
    │   └── Estado da execução
    ├── Chat central
    │   ├── Mensagens curtas
    │   ├── Atividades
    │   ├── Sugestões
    │   └── Composer
    └── Sidebar de artefato
        ├── Preview por tipo
        ├── Editor textual quando aplicável
        ├── Preview HTML + código
        ├── Dados / tabelas / gráficos
        ├── Fontes e proveniência
        ├── Versões e comparação
        ├── Ações de negócio
        └── Anotação + aplicar / descartar
```

## Dados mockados do primeiro corte

Os mocks devem ter o mesmo formato esperado pela API, para serem substituídos sem reescrever os componentes.

```js
{
  conversations: [
    { id, title, projectId, projectName, updatedAt, pinned, activeRun, artifactCount }
  ],
  projects: [
    { id, clientName, name, status, artifactCount, lastActivity }
  ],
  context: {
    client: { id, name },
    project: { id, name },
    object: { id, type, title }
  },
  artifacts: [
    { id, type, renderer, title, status, sections, sources, version, tabs, actions, editable }
  ],
  messages: [
    { id, role, text, createdAt, activity, artifactId, suggestions }
  ]
}
```

## Fluxos mockados que precisam funcionar

### 1. Histórico de conversas

- carregar conversas antigas da base quando o endpoint estiver disponível;
- fallback para mock quando a API não responder;
- filtrar por título, projeto e conteúdo demonstrado;
- agrupar por Hoje, Ontem e Mais antigas;
- marcar conversa ativa;
- fixar, renomear, arquivar e criar nova conversa em estado local mockado.

### 2. Seletor de projeto

- buscar projetos;
- selecionar cliente → projeto → objeto;
- atualizar o breadcrumb;
- atualizar o texto de contexto;
- demonstrar aviso quando trocar de projeto alterar o escopo;
- manter a conversa e trocar somente o `current_context`.

### 3. Controle de intensidade

Três estados visuais e funcionais:

- Foco: resposta curta e direta;
- Análise: síntese com evidências;
- Pesquisa profunda: mostra atividade e fontes mockadas.

O controle altera a apresentação e o payload preparado para o backend, mas não precisa chamar o agente no primeiro corte.

### 4. Intenções de trabalho

As ações abaixo devem abrir estados mockados:

- criar projeto;
- revisar briefing;
- comparar versões;
- transformar resposta em documento;
- adicionar ao projeto;
- abrir fontes;
- editar trecho selecionado;
- continuar conversa interrompida;
- tentar novamente;
- interromper geração.

### 5. Sistema de artefatos

- clicar em qualquer resultado abre a sidebar direita sem abandonar a conversa;
- o renderer muda conforme o tipo: texto, relatório, HTML, tabela, pesquisa, plano, arquivo ou imagem;
- cada artefato mostra somente o preview e as ações necessárias para aquele tipo;
- briefing/documento mostra campos Confirmado, Premissa e Pendente;
- relatório mostra resumo, dados, fontes e comparação;
- HTML mostra apenas navegador renderizado em iframe isolado e “Pedir alteração”;
- tabelas permitem filtrar, ordenar e copiar;
- resultados de pesquisa mostram fonte, evidência, data e ação de salvar insight;
- selecionar texto, célula, gráfico ou elemento abre “Editar com Cadu”;
- a ação cria uma proposta de alteração mockada localizada;
- “Aplicar” atualiza apenas a parte selecionada;
- “Descartar” restaura a versão anterior;
- salvar cria uma nova versão e altera o estado para “Salvo automaticamente”.

### 6. Composer

- textarea/contenteditable estável;
- Enter envia;
- Shift+Enter quebra linha;
- paste de texto e imagem;
- drag-and-drop;
- anexos aparecem no próprio composer;
- remover anexo antes do envio;
- estado enviando;
- estado interromper;
- estado erro com tentar novamente;
- nunca deixar o composer crescer até ocupar a tela inteira.

## Contrato de integração posterior

O front-end mockado deve chamar uma camada única:

```js
conversationRepository.list()
conversationRepository.get(id)
conversationRepository.create(payload)
conversationRepository.updateContext(id, context)
conversationRepository.sendMessage(payload)
conversationRepository.stopRun(runId)
conversationRepository.listProjects(query)
artifactRepository.get(id)
artifactRepository.save(id, payload)
artifactRepository.applySuggestion(id, suggestion)
```

No mock, essas funções usam estado local. Na integração, elas apontam para os endpoints Flask/PostgreSQL existentes.

## Ordem de construção

1. Consolidar a casca visual e tokens escuros do mockup 4.
2. Trazer a sidebar de conversas do mockup 1.
3. Ligar histórico existente e fallback mockado.
4. Implementar contexto e seletor de projeto.
5. Implementar intensidade e estados de execução.
6. Implementar composer robusto.
7. Implementar o sistema de renderers de artefatos.
8. Implementar HTML Preview/Código com sandbox e atualização mockada.
9. Implementar anotação localizada e aplicar/descartar.
10. Só depois ligar o streaming real e avaliar a entrada da ilha React.

## Critério de sucesso

O usuário deve conseguir abrir uma conversa antiga, trocar o projeto, mudar a intensidade, abrir um artefato, selecionar um trecho, simular uma alteração, aplicar ou descartar a edição e continuar na mesma conversa — tudo sem sair da tela de Conversas.
