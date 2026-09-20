# Cadu Workspace — Dock Inteligente e Home Adaptativa

## Decisão de produto

O Workspace não terá uma sidebar de navegação tradicional nem uma tela separada de “Recentes”. A dock é uma área de continuidade operacional: concentra marcas fixadas, recursos usados recentemente e itens arrastáveis para as superfícies de trabalho.

O chat é a superfície de comando. Planner, Studio, Reports, projetos e arquivos são superfícies de visualização e edição acionadas pelo chat, pelo contexto ou por um item da dock.

## Estrutura de navegação

```text
Chrome global escuro
├── Agência / troca de conta
├── Busca global
├── Notificações
└── Conta

Dock inteligente estreita
├── Cadu mark
├── Nova conversa
├── Marcas e projetos fixados
├── Itens transitórios usados recentemente
├── Uso de créditos
└── Avatar

Área de trabalho
├── Home global: chat + continuidade
├── Marca: contexto e abas da marca
└── Projeto: contexto e abas do projeto
```

As abas horizontais não existem na Home global. Elas aparecem apenas depois que uma marca ou projeto foi aberto. A Home é uma entrada; marca e projeto são contextos de trabalho.

## Dock: itens e comportamento

| Grupo | Comportamento | Representação |
|---|---|---|
| Cadu | Volta para Home global | Somente o mark oficial |
| Nova conversa | Abre a Home com composer focado | Botão circular `+` |
| Marca fixada | Clique abre a Home da marca; arrastar para o chat seleciona a marca | Logo circular, sem ícone de pasta |
| Projetos fixados | Ficam associados à marca; clique abre a Home do projeto; arrastar define contexto do chat | Badge numérico na marca e menu/stack contextual, nunca duplicar logo da marca |
| Item transitório | Recurso usado recentemente pode permanecer na dock por uma sessão ou até ser dispensado | Miniatura/ícone de 28–32px |
| Uso | Mostra só o percentual em anel | Tooltip: `Utilização de créditos` |
| Avatar | Abre conta e preferências | Sempre no fim da dock |

Não usar divisórias visuais, textos de navegação nem efeitos decorativos de hover. O feedback acontece por estado ativo, tooltip, foco de teclado, cursor e destino de arraste.

## Recentes: não é uma seção de navegação

`Recentes` não é uma tela nem uma seção fixa da sidebar. É uma coleção de recursos transitórios, semelhante a uma pilha de itens disponíveis para reutilização.

Um recurso entra na dock quando foi:

- aberto, criado ou atualizado pelo usuário;
- usado em uma conversa;
- criado no Studio;
- incluído em um plano, briefing ou relatório;
- anexado ou promovido a fonte do projeto.

O recurso pode ser arrastado para uma superfície que aceite seu tipo:

| Origem | Destino | Resultado |
|---|---|---|
| Imagem | Chat | Anexa como imagem e oferece uso como referência ou arquivo do projeto |
| Arquivo/PDF | Chat | Anexa e pergunta o destino: fonte, anexo ou apenas consulta |
| Conversa | Chat | Cita/continua a conversa sem abrir nova tela |
| Plano | Chat | Adiciona o plano como contexto ou pede alteração nele |
| Item do Studio | Chat | Anexa ativo gerado, com origem e versão |
| Ação do agente | Chat | Converte em contexto de execução para investigar, aprovar, alterar ou cancelar |
| Item de projeto | Chat | Atualiza automaticamente marca e projeto ativos |

Abrir um item não significa navegar para uma nova tela. O padrão é abrir uma visualização adequada: artifacts dentro de Conversas, preview no Studio, painel de recursos no projeto ou documento em modo leitura/edição.

## Regras de contexto

| Estado | Faixa de contexto | Abas |
|---|---|---|
| Nenhum contexto | `Cadu Workspace` + `Escolher contexto` | Nenhuma; Home global |
| Marca | Logo horizontal + nome da marca + `Todos os projetos` | Visão, Projetos, Campanhas, Arquivos, Agentes, Insights |
| Projeto | Marca / projeto + status | Conversa, Plano, Recursos, Produção, Relatórios, Atividade |

Arrastar uma marca ou projeto para o composer troca o contexto antes da mensagem ser enviada. O composer mostra um chip removível do contexto resolvido.

## Conta e configuração de atalhos

O avatar abre o único menu de conta. Ele inclui perfil, equipe, créditos, plano, integrações, preferências e `Personalizar dock`.

`Personalizar dock` abre uma superfície de gestão com:

- marcas e projetos fixados;
- ordem por arrastar e soltar;
- limite recomendado por grupo;
- itens transitórios mantidos ou removidos;
- restauração das sugestões automáticas;
- preferências de densidade e tooltips.

Arrastar para a dock fixa o item; remover da dock só remove o atalho, nunca o recurso original.

## Personalização por atividade

O sistema sugere atalhos pelo uso, mas não altera fixações explícitas sem consentimento.

| Perfil inferido | Sugestões na Home |
|---|---|
| Mídia | Planos em revisão, campanhas, relatórios e alertas |
| Criação | Produções recentes, briefings, ativos de marca e Studio |
| Redação | Briefings, documentos, revisões e aprovações |
| Planejamento | Cenários, pesquisas, planos e premissas pendentes |
| Atendimento/Gestão | Marcas, projetos ativos, aprovações e decisões pendentes |

## Componentes React

| Componente | Responsabilidade |
|---|---|
| `CaduDock` | Layout e regras de visibilidade da dock |
| `DockBrandShortcut` | Logo, estado ativo, badge de projetos e drag source |
| `DockTransientItem` | Item recente com tipo, miniatura e ciclo de vida |
| `DockUsageRing` | Percentual compacto e tooltip de créditos |
| `ShortcutManagerDialog` | Fixar, remover, ordenar e restaurar atalhos |
| `WorkspaceContextBar` | Estado global, marca ou projeto |
| `ContextualTabs` | Abas que dependem de marca/projeto |
| `RecentResourceFeed` | Continuidade na Home, não navegação lateral |
| `AgentActionDrop` | Ação arrastável/clicável que injeta contexto no chat |
| `ArtifactPreview` | Visualização sem forçar troca de página |

## Contrato mínimo de dados

```ts
type DockItem = {
  id: string;
  kind: 'brand' | 'project' | 'file' | 'image' | 'conversation' | 'plan' | 'artifact' | 'agent_action';
  title: string;
  brandRef?: string;
  projectRef?: string;
  previewUrl?: string;
  isPinned: boolean;
  lastUsedAt?: string;
  dragPayload: { type: string; id: string; brandRef?: string; projectRef?: string };
};
```

## Fases de entrega

1. Implementar dock mínima: logo, nova conversa, marcas fixadas, uso e avatar.
2. Criar contexto global/marca/projeto e mover as abas para contextos selecionados.
3. Criar `Personalizar dock` no menu da conta e persistência de fixações.
4. Implementar itens transitórios e drag/drop entre dock, chat, Studio e Planner.
5. Ligar sugestões de atalhos ao perfil de uso com explicação e controle do usuário.
