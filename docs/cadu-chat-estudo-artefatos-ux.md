# Cadu Chat — estudo de artefatos e padrão de navegação

Escopo: inventário do renderizador React em `frontend/conversations-v2/components/ArtifactPane.jsx`, itens de resultado do chat e catálogo de ações existentes. Este estudo orienta a evolução visual sem converter todos os artefatos em documentos do mesmo formato.

## Tipos e comportamento

| Tipo | Visualização atual | Ação de maior valor | Ações secundárias a expor |
|---|---|---|---|
| Documento, briefing, nota, resumo executivo, plano, cenário, pesquisa | Leitor rico; alternância para edição | Editar / visualizar | Tema, baixar Markdown/TXT/HTML, mover de projeto, versões, mudar lado |
| Pauta e resumo de reunião | Campos semânticos editáveis | Editar o registro | Baixar, indexar/salvar no projeto, versões, mudar lado |
| Página HTML | iframe isolado | Publicar / copiar link | Abrir no navegador, baixar, mover, despublicar, mudar lado |
| Imagem | Prévia centrada e metadados | Editar no Studio | Analisar, marcar área, recortar, remover fundo, adaptar formato, otimizar, abrir original, baixar |
| Mapa do projeto | Mapa arrastável/zoom e recursos por grupo | Abrir/organizar recurso | Mover recurso, abrir editor, baixar, zoom |
| Referência/link lido | Prévia/embed ou resumo seguro | Abrir a referência | Resumir, salvar referência, preparar pauta quando for reunião |
| Arquivo/recurso conectado | Cartão com destino e estado de edição | Abrir arquivo | Criar cópia editável, baixar, ver no projeto |
| Identidade de marca | Identidade, sinais, cores, fontes e projetos | Visitar site | Reavaliar auditoria |
| Perfil de projeto | Contexto, métricas, instruções e marcas | Ler contexto | Navegar para o projeto conforme links disponíveis |
| Biblioteca | Grupos de materiais, lista/carrossel e drag | Abrir material | Arrastar para composição; ações do item variam por recurso |
| Entrega estruturada genérica | Resumo e campos editáveis | Editar conteúdo | Salvar, indexar, versões, baixar |

As ações de persistência (salvar, indexar, anexar ao projeto) ficam no rodapé por terem impacto de fluxo e estado. Fechar/alternar aba, editar/visualizar, publicar e menu de ações pertencem ao cabeçalho. Ações próprias da imagem ou do link continuam contextuais ao tipo.

## Achados de consistência

- As abas já selecionam ícones pelo tipo, mas o fallback é o mesmo arquivo para quase todos; o título é abreviado por palavras e fica visualmente parecido com uma aba tradicional de navegador.
- A lista de abas apresenta um título e um botão “×” sem estrutura de label reaproveitável. Há espaço para espelhar o truncamento com fade usado nos títulos de conversa/projeto da sidebar.
- O cabeçalho mostra texto em “Editar”, “Ações”, “Publicar” e um controle separado de fechar. Em painéis estreitos esses rótulos competem com o título.
- O menu secundário é uma lista textual longa para imagem e uma lista menor para documentos; sem ícones, exige leitura sequencial e não mostra rapidamente a categoria da ação.
- Há famílias com linguagem própria que deve continuar clara: documentos são legíveis/editáveis; HTML é uma página isolada; imagem é mídia; link/arquivo é referência conectada; mapa e biblioteca são navegação de recursos; identidade e perfil são contexto.
- Títulos completos devem permanecer disponíveis por `title`/tooltip e acessibilidade, mesmo quando a representação visual termina em fade.

## Padrão proposto

1. Abas baixas e compactas, título original numa única linha com fade no limite direito; ícone identifica tipo; ícone de fechar aparece no hover/foco e continua acessível por nome.
2. A barra do painel reserva espaço ao título; edição e publicação são controles compactos com ícone + tooltip, e o menu “Mais ações” é um botão de ícone (`ellipsis`/menu) com nome acessível.
3. Menu mantém rótulos curtos e adiciona ícone consistente por verbo: editar, publicar/externo, tema, download, projeto, histórico, mover lado, fechar. Ícone nunca substitui o nome no menu.
4. Não comprimir os controles de metadado da imagem, o rodapé de indexação ou decisões de projeto no menu: são contexto/status, não ferramentas ocasionais.
5. Ícones precisam ter semântica transversal, affordance de foco e tooltip; não usar emojis, pictogramas CSS improvisados ou combinações diferentes do mesmo verbo.

## Revisão visual por largura

- Desktop largo: título do artefato, tipo/estado e controles no mesmo cabeçalho; abas aceitam rolagem horizontal.
- Desktop estreito: títulos das abas usam fade, fechar reduz a largura disponível sem sobrepor o nome; ferramentas primárias ficam compactas.
- Mobile: faixa de abas tocável e rolável, alvo mínimo confortável; voltar à conversa permanece com texto; menu contextual usa largura da viewport e mantém os mesmos nomes.
- Claro/escuro: ícone, foco, estado ativo e hover têm contraste semanticamente equivalente; a mudança de tema do documento não altera o tema do chrome do painel.

## Próximas decisões de produto

- Confirmar a taxonomia de ícones para todos os tipos e a ação primária contextual de HTML, imagem, link, biblioteca, marca e perfil.
- Avaliar ação de edição do mapa/biblioteca e salvamento de referências depois da revisão do fluxo completo; este estudo não inventa ações que o componente não oferece.
- Fazer revisão visual ao vivo das famílias e larguras após aplicar o padrão de abas e cabeçalho; o mockup GPT Image 2 serve apenas como direção, não substitui checagem funcional.
