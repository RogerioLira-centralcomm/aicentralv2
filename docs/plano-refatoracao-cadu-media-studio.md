# Refatoração da entrada do Cadu Media Studio

## Resultado proposto

Transformar a entrada de uma parede de imagens em uma área operacional da marca: contexto persistente, acesso direto a Ajustar e Vídeo e biblioteca navegável. Manter Flask/Jinja, CSS e JavaScript vanilla. Este documento planeja a implementação; os arquivos da aplicação ainda não foram alterados.

**Mockup navegável:** [Cadu Media Studio — proposta de refatoração](../output/mockups/cadu-media-studio-refatoracao.html).

O mockup usa recortes visuais por CSS da captura fornecida, títulos de exemplo e o saldo mostrado na captura. Não representa consulta atual à API. Busca, filtros, navegação e rascunho em memória demonstram interação local; geração, envio de arquivos e cobrança não são executados. O rascunho é uma proposta, não um recurso confirmado do backend.

## Diagnóstico baseado no código

| Evidência | Consequência | Mudança planejada |
|---|---|---|
| `templates/parametros/modelagem_criativos.html`: duas galerias sucessivas, ferramentas no final | Vídeo e ferramentas ficam depois de uma longa parede de imagens | Entrada compacta com ações e biblioteca filtrável |
| `static/css/modelagem_criativos.css`: `.mc-cadu-takes li[data-ratio="16/9"]` ocupa duas colunas de quatro | Cada peça horizontal ocupa metade da tela | Miniaturas de altura controlada; três ou quatro colunas conforme espaço |
| `mc-cadu-home.js`: `items.slice(0, 12)` | Resultados além dos primeiros 12 não aparecem | Retirar truncamento silencioso e definir paginação conforme contrato real da API |
| `loadWall` e `loadClips` chamam `paintLibrary` vazio antes da resposta | Mensagem de biblioteca vazia aparece enquanto carrega | Estados loading, ready, empty e error independentes |
| Requisições de biblioteca e créditos não têm controle de resposta obsoleta | Uma resposta da marca anterior pode substituir a marca atual | AbortController e conferência da identidade da requisição |
| `boot` carrega a marca salva e também escuta `cadu:brand-ready` | Pode haver carregamento inicial duplicado | Inicialização única com contexto validado |
| Erro da imagem remove o item da galeria | Um resultado existente desaparece por falha da miniatura | Fallback de imagem, mantendo título e acesso ao resultado |
| `_mc_shell.html`: fluxos atuais, antigos e experimentais divididos entre Mais e Pesquisa | A navegação não explica claramente a função de cada área | Agrupar Produção, Biblioteca, Identidade e Recursos avançados |
| Folha compartilhada tem 14.252 linhas; tema local usa #0f766e e #eef0ec | Mudanças globais podem afetar editores; identidade diverge dos tokens CentralX | CSS específico do hub, escopo explícito e migração gradual |

Revisão realizada sobre código e captura, sem sessão autenticada do aplicativo. A ocorrência dos riscos de concorrência em produção não foi reproduzida; decorre da ausência de proteção nos caminhos revisados.

## Direção de produto e arquitetura da informação

1. Cabeçalho: Cadu Media Studio, seletor real de marca e créditos reais. Não mostrar um saldo padrão em falhas.
2. Navegação: Visão geral; biblioteca de peças e vídeos; ferramentas Ajustar e Vídeo; identidade da marca. Camadas, Formatos, Design System e Custo acessíveis em recursos avançados. Fluxos antigos e experimentais continuam acessíveis e separados.
3. Conteúdo: título operacional, identificação da marca e acessos Ajustar peça, Retomar peça, Montar vídeo e Perfil da marca.
4. Biblioteca: filtros Imagens/Vídeos, busca, resultado visível da filtragem e miniaturas uniformes. Prévia completa preserva o formato original; nunca alterar o arquivo criativo para preencher o card.
5. Acesso ao item: preservar parâmetros `run`, `clip` e `client` e reabrir a ferramenta existente. Não introduzir aprovação, colaboração ou publicação sem contratos reais.

A criação do zero não será a ação principal desta refatoração. O hub atual prioriza ajuste de criativos reais; a ferramenta de vídeo monta entre 2 e 30 cenas. O primeiro mockup exploratório foi corrigido para refletir esses fluxos. Persistência de rascunhos fica fora do primeiro release.

## Design do novo mockup

HTML/CSS/JS vanilla, primary #1E4D4F, superfícies brancas, fundo claro e bordas discretas. Título de página de 24px, corpo de 14–16px e metadados a partir de 12px. Escala de espaçamento 4/8/12/16/24/32px. A interface prioriza controles e biblioteca, sem banner promocional. O símbolo tipográfico do protótipo é provisório; na aplicação usar o ativo oficial aprovado do Cadu.

Desktop: navegação lateral compacta, contexto no alto, quatro acessos e três colunas de mídia. Mobile: navegação acessível por menu, ações em duas colunas e biblioteca em uma. O mockup simplifica a navegação mobile; a implementação deve incluir o menu, não apenas ocultar a lateral.

## Plano de execução

### 1. Registrar contratos e comportamento atual

- Mapear respostas de `/parametros/api/clients`, `/parametros/api/image-credits` e `/parametros/api/format-lab/swap/library?client_id=…&media=still|video`.
- Confirmar no handler real da biblioteca os campos, ordenação e suporte a paginação. A rota é consumida pelo hub, mas seu handler não foi auditado nesta revisão.
- Preservar a chave `cx-mc-desk-client`, a seleção `profile_id/id`, os eventos `cadu:brand-ready`, `cadu:brand-change` e `cadu:credits-refresh`.
- Registrar referências visuais e fluxos em Ajustar, Vídeo e Marcas antes de tocar no shell compartilhado.

Entrega: contrato mínimo de cliente, biblioteca e saldo, com cenários de erro documentados.

### 2. Substituir a composição do hub

- Refatorar `templates/parametros/modelagem_criativos.html` em cabeçalho/contexto, ações, filtros e biblioteca.
- Criar estilos com escopo `.mc-studio-home` em arquivo próprio; não acrescentar outra camada de sobrescritas ao fim da folha antiga.
- Reutilizar tokens oficiais e componentes de formulário existentes.
- Manter um único h1, landmarks e nomes acessíveis nos controles.
- Introduzir mudanças do shell compartilhado separadamente após validar as demais páginas consumidoras.

Entrega: nova estrutura visual servida na rota atual, com links reais e sem alterações nos motores de geração.

### 3. Refatorar o estado e carregamento em vanilla

- Separar acesso à API, estado da marca/biblioteca e renderização, em módulos pequenos compatíveis com a forma de carregamento do projeto.
- Estado mínimo: cliente ativo, mídia, busca, página/cursor quando suportado e estados independentes de biblioteca e créditos.
- Cancelar requisições anteriores e descartar respostas incompatíveis com o cliente atual. Limpar dados da marca anterior imediatamente ao trocar.
- Consumir o evento de contexto validado uma única vez; impedir chamadas duplicadas e listeners acumulados.
- Renderizar conteúdo textual com `textContent`, validar URLs e normalizar proporções permitidas. Preservar autenticação e permissões existentes.

Entrega: marca e resultados consistentes mesmo sob respostas fora de ordem.

### 4. Biblioteca e estados completos

- Implementar filtros e busca com escopo explícito: se forem locais, informar que pesquisam somente os itens carregados.
- Usar paginação do servidor quando disponível. Se não existir, definir evolução do endpoint antes de prometer busca global ou total de resultados.
- Mostrar skeleton no carregamento; vazio real com ação contextual; erro com Tentar novamente; mídia indisponível com acesso ao item preservado.
- Tratar marca inexistente/removida, ausência de perfil, saldo indisponível, biblioteca vazia e falha parcial entre imagens e vídeos.
- Usar lazy loading, dimensões reservadas e thumbnails existentes. Não carregar os arquivos de produção como miniaturas quando houver alternativa.

Entrega: biblioteca sem perdas silenciosas de itens, com retomada do trabalho.

### 5. Verificar e liberar gradualmente

- Testes focados: troca rápida A→B com resposta A atrasada; ausência de dupla carga inicial; saldo obsoleto; erro de thumbnail; mais de 12 itens; erro de biblioteca com recuperação.
- Confirmar os links de imagem e vídeo com os identificadores originais e a marca selecionada.
- Verificação visual em 1440, 1024, 768 e 390px; teclado, foco, seletor de marca, filtros e estados.
- Verificar regressões em Ajustar, Vídeo, Marcas e nos menus do shell compartilhado.
- Disponibilizar a nova composição sob flag temporária se o mecanismo de flags do projeto permitir; caso contrário, separar o commit do hub para reversão simples.
- Remover estilos antigos do hub somente após confirmar que não são usados por outras telas.

Entrega: novo hub validado com opção de retorno, sem perda do histórico existente.

## Critérios de aceite

- Marca ativa, ação Ajustar e acesso ao Vídeo identificáveis no primeiro viewport.
- Nenhum resultado ou saldo de outra marca após a troca de contexto.
- Loading nunca se apresenta como ausência de conteúdo.
- Falha de thumbnail não oculta o resultado.
- Histórico além de 12 itens acessível por estratégia explícita de navegação.
- Links existentes retomam corretamente cada execução e clipe.
- Nenhuma nova promessa de geração, aprovação ou persistência sem implementação.
- Navegação por teclado e mobile utilizáveis; nenhuma regressão nos editores existentes.

## Ordem sugerida

Entregar primeiro o novo hub com os contratos atuais e estados corrigidos. Depois evoluir busca/paginação do backend se necessário. Por último migrar o shell das demais ferramentas. A refatoração visual pode ser completa sem substituir simultaneamente os motores de imagem, vídeo e créditos.

## Execução realizada

O hub foi implementado no template da rota existente, com `cadu-studio-home.css` isolado, `mc-studio-library.js` para estado e `mc-cadu-home.js` para apresentação. A navegação compartilhada recebeu validação de respostas de contexto/créditos, sem alterar o HTML dos editores.

A API de biblioteca foi confirmada em `creative_format_lab/swap_session.py`: retorna todos os itens da marca ordenados por `created_at`, sem paginação. A nova interface pesquisa a coleção retornada inteira e amplia a exibição em lotes de 12 com Mostrar mais. Não houve mudança no backend.

Validação: cinco testes de estado passaram; teste de navegador passou com o template real sobre layout-base mínimo e APIs simuladas, incluindo quatro larguras, troca de marca, resposta atrasada de créditos e recuperação de erros. O contrato Jinja dos templates passou. O teste legado amplo `CreativeFormatLabDeskTest.test_mesa_registrada_no_shell` está bloqueado por uma expectativa de cache `v=83` no editor, enquanto o arquivo compartilhado, alterado por outro trabalho em andamento, já usa `v=84`; essa expectativa fora do escopo não foi alterada.

Limites: sem deploy e sem validação autenticada em produção; geração de imagem/vídeo e shell completo dos editores não foram exercitados no navegador. Mudanças simultâneas de vídeo e editor foram preservadas. Reprodução dos testes em `tests/frontend/README.md`.
