# Cadu Chat — base visual para chat, artefatos e Image 2

Status: briefing de direção e inventário inicial. Serve como referência para protótipos e implementação; não substitui os tokens oficiais nem altera a interface.

## Objetivo

Refinar o chat React do Cadu e suas entregas editáveis para parecerem uma única ferramenta de trabalho: conversa escaneável, perguntas respondíveis sem esforço e artefatos que assumem o espaço de leitura quando abertos. A direção visual deve funcionar em tema claro e escuro, manter a identidade Cadu e evitar a aparência de um template genérico de chat com cartões repetidos.

## Inventário confirmado

- Aplicação React principal: `frontend/conversations-v2/App.jsx`; montagem e provider de tema em `frontend/conversations-v2/main.jsx`.
- Conversa, estados vazios, respostas, perguntas e ação de abrir artefatos: `frontend/conversations-v2/components/Conversation.jsx` e `ResponseBlocks.jsx`.
- Sugestões iniciais contextuais: `frontend/cadu-design-system/components/WorkspacePromptSuggestions.jsx`. São geradas para contexto pessoal, projeto ou marca; o componente entrega até três sugestões.
- Artefatos: `frontend/conversations-v2/components/ArtifactPane.jsx`; tipos existentes incluem documento, nota, resumo, plano, pesquisa, HTML interativo, imagem, planilha, reunião, recursos, marca e projeto.
- Tokens e temas: `frontend/cadu-design-system/tokens.css`; regras extensas e sobreposições de chat/sugestões em `frontend/cadu-design-system/styles.css`.
- Superfície React empacotada servida pelo template Flask. `aicentralv2/static/cadu_workspace/conversations/react/app.css` e `app.js` são artefatos compilados; mudanças devem começar nos fontes `frontend/` e seguir o build já usado pelo projeto.
- Existe também legado não React em `aicentralv2/static/cadu_workspace/conversations/chat.js` e `chat.css`; não usar como fonte primária do redesign React.

## Comportamento visual atual a considerar

- O chat está intencionalmente escuro no tema de conversas (`data-cadu-skin="conversations"`), inclusive quando `data-cadu-theme="light"`; esse bloqueio aparece nos tokens. Workspace usa provider travado em claro, enquanto modo standalone usa o provider travado em escuro.
- O painel de artefato é uma área de leitura/editável que abre ao lado da conversa no desktop, com largura redimensionável, abas/histórico de versões e layout de superfície separada em telas menores.
- Mensagens do usuário aparecem alinhadas à direita em verde escuro. Respostas do Cadu ficam sem balão, com bloco de resposta, fontes, perguntas, ações e eventual link de artefato.
- Perguntas estruturadas chegam via `ResponseBlocks`; respostas legadas podem virar perguntas obrigatórias. Sugestões iniciais e perguntas dentro da resposta são componentes diferentes e devem compartilhar linguagem, não necessariamente formato.
- Parte dos estilos usa valores hex inline e utilitários de modo escuro. Para habilitar os dois temas de verdade será necessário migrar cores de superfície/texto/borda/estado para tokens semânticos e revisar CSS específico dos artefatos.

## Referência oficial do logo

Preferir o ícone compacto oficial do produto, já fornecido no bootstrap como `bootstrap.caduMark`:

- Principal para chat/avatar/marca: `aicentralv2/static/images/cadu/products/cadu-icon.png`.
- Ícone de instalação/Workspace: `aicentralv2/static/images/cadu/brand-icons/workspace-192.png`.
- `aicentralv2/static/images/cadu/products/cadu-hub.png` é um arquivo existente, mas não assumi que seja a marca recomendada para superfícies do chat.
- Nunca pedir ao Image 2 para redesenhar, reinterpretar ou escrever o logo. Tratar a referência anexada como marca exata e preservá-la. Se a composição precisar de um logo no produto, renderizar o asset original via HTML/CSS depois da geração.

## Direção de design proposta

**Ideia:** “mesa de trabalho do Cadu” — o chat é uma superfície de decisão; artefatos parecem folhas de trabalho bem compostas, e perguntas parecem controles de próxima ação.

**Paleta de partida** (validar contra a identidade de marca antes de fechar tokens):

| Papel | Claro | Escuro |
|---|---|---|
| Fundo de conversa | `#F4F7F6` | `#0B1517` |
| Superfície | `#FFFFFF` | `#122124` |
| Superfície elevada | `#F0F5F3` | `#192C2E` |
| Texto principal | `#18312F` | `#E8F2EF` |
| Texto secundário | `#5F7772` | `#9DB2AD` |
| Acento Cadu | `#087765` | `#55D8C6` |
| Linha | `#D7E3DF` | `rgba(181,218,211,.16)` |

A paleta escura atual de `tokens.css` já fornece um ponto de partida válido para contraste e identidade. Não converter artefatos HTML gerados automaticamente para o tema do chat sem uma decisão por tipo: páginas publicáveis podem ter sua própria identidade visual; editores de documento, painéis e perguntas devem seguir o tema ativo do produto.

**Tipografia:** preservar Inter/system existente nesta primeira rodada; usar hierarquia por tamanho, peso e largura de linha, evitando introduzir dependência de fonte antes de validar marca. Leitura principal limitada a cerca de 72 caracteres por linha; documentos podem ser mais largos conforme o tipo.

**Composição:** alinhamento de leitura à esquerda. No vazio, título/convite claro e três sugestões textuais distintas, leves e relacionadas a tarefas. Na conversa, sem cartão em volta de cada parágrafo. Perguntas agrupadas por contexto e cada decisão exibindo opções como controles, com estado selecionado e ação de continuar visíveis. Artefato deve ter cabeçalho funcional (tipo, título, salvar/versões/fechar), corpo com largura de leitura própria e fundo que o distinga sem parecer outra aplicação.

**Princípios:** hierarquia por função; densidade baixa no chat e alta o suficiente nos documentos de trabalho; acento teal reservado a ação/seleção; nenhum gradiente ornamental; borda e superfície como estrutura; foco teclado claro; movimento apenas para abrir/fechar ou confirmar ação; adaptação a mobile sem reduzir controles abaixo de alvos confortáveis.

## Prompt mestre — gerar referência de interface com GPT Image 2

Usar como prompt de imagem para produzir um mockup estático. Anexar `cadu-icon.png` como referência visual oficial do logo. Fazer uma geração por direção de tela/estado para evitar misturar telas no mesmo quadro.

> Create a high-fidelity product UI reference for the Cadu AI work chat, a Brazilian Portuguese professional assistant used to analyze projects, ask follow-up questions, and create editable work artifacts. Treat the attached Cadu icon as the exact official logo: preserve its silhouette, proportions and colors without redrawing it, adding text to it, or inventing a new mark. Show a real desktop chat workspace at 1440×1000, with a quiet, deliberate hierarchy and realistic Portuguese interface copy. The chat should read as a work surface, not a generic chatbot: readable left-aligned assistant answer, compact user message, one clearly grouped decision question with a few selectable options, and three lightweight task suggestions only in the empty-state variant. Include an adjacent editable artifact pane with a functional header and a well-typeset document preview. Use the Cadu teal identity as a restrained action color, precise spacing, accessible contrast, visible keyboard focus, fine structural dividers and purposeful typography. Keep the layout calm and editorially clear; use distinct hierarchy rather than repeating identical rounded cards. No gradients, no decorative blobs, no fabricated brand logos, no unreadable microcopy, no device mockup, no browser chrome, no watermark. [THEME: light / dark]. [STATE: empty chat / active conversation with question / artifact open]. This is a visual reference, not production code; prioritize realistic component geometry and legible Portuguese labels.

### Variações necessárias

1. **Claro, conversa vazia:** `THEME: light`, `STATE: empty chat`; mostrar contexto de projeto/marca opcional e três inícios de tarefa.
2. **Escuro, conversa ativa e pergunta:** `THEME: dark`, `STATE: active conversation with question`; mostrar opções escolhidas/não escolhidas, uma resposta do Cadu e fontes.
3. **Claro, artefato aberto:** `THEME: light`, `STATE: artifact open`; documento editável no painel e conversa contextual visível.
4. **Escuro, artefato aberto:** `THEME: dark`, `STATE: artifact open`; repetir a mesma estrutura da versão clara, sem mudar a hierarquia nem inventar outra marca.
5. Para comparar consistência, pedir a mesma tela nos dois temas; variar somente tokens de cor e estados que dependam de contraste.

## Brief para a próxima implementação

- Auditar todos os valores de cor inline em `Conversation.jsx`, `ResponseBlocks.jsx`, `ArtifactPane.jsx` e estilos React do chat; substituir cores da interface por tokens semânticos com pares claro/escuro.
- Tornar o seletor de tema disponível onde o chat React é usado e persistir por preferência existente, removendo o bloqueio global escuro da skin conversations somente depois que todos os estados essenciais tiverem tokens claros validados.
- Manter a identidade HTML artefato separada quando for saída publicável; aplicar tema do produto em editor/painel nativo, estado vazio, loading, erro, abas, controles e modais.
- Revisar visualmente em desktop e mobile: vazio, conversa ativa, pergunta de uma e múltiplas opções, erro recuperável, documento longo, imagem e HTML aberto.
- Os mockups GPT Image 2 são referências de proporção, agrupamento e direção, nunca fonte de texto/logos finais nem especificação pixel-perfect.

## Perguntas de validação de design

- O usuário entende imediatamente qual ação cada pergunta está pedindo?
- As sugestões parecem tarefas possíveis dadas a marca/projeto ativo, e não atalhos genéricos?
- O artefato parece parte do Cadu enquanto conserva identidade própria quando for um documento publicável?
- Claro e escuro mantêm a mesma hierarquia, estados e affordances?
- O logo exibido é sempre o arquivo oficial renderizado pelo produto?
