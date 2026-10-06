# Planner como marketplace: Canais, Formatos, Audiências e o assistente de planejamento

Plano para análise. Nada foi implementado. Data: 2026-10-06.

## 1. Diagnóstico das duas telas atuais

| Tela | O que está bom | O que falha | Evidência |
|---|---|---|---|
| **Canais (lista)** | Filtro por categoria e busca funcionam; logo e categoria no card | Card é só texto: nenhuma imagem de anúncio, nenhum preço ou sinal de "dá para comprar"; "Alcance" aparece truncado ("Mensurável por ..."); 37 cards iguais, sem hierarquia; não há "adicionar ao plano" na lista | `Catalog.jsx` `CatalogCard`: só mostra imagem se `VISUAL_KINDS` inclui o tipo, e canais não são "visuais" |
| **Canal (detalhe, ex.: 99)** | Estrutura de seções existe (papel, público, compra, estratégias, formatos, exemplos, novidades) | Aba "Diferenciais / Quando usar / Formatos" com **uma página quase vazia**: "Ainda não há formatos cadastrados"; sem foto, sem exemplo de anúncio, sem preço; métricas pobres (só 2); nada leva ao formato, à audiência ou ao plano em contexto | `ChannelDetail.jsx`: galeria e exemplos só aparecem se `cadu_formato_exemplos` tiver `approved`; para a 99 não há nada |
| **Formatos** | Catálogo com famílias, filtro por canal e contagens vivas | Só texto, sem miniatura do formato renderizado (peça de exemplo) | `FormatShowcase.jsx` |
| **Audiências** | Facetas e relacionadas | Sem ligação visual com o canal onde a audiência vive | `AudienceShowcase.jsx` |

Causa raiz: **os dados já se relacionam** (`cadu_formatos.plataforma_slug`, `cadu_formato_exemplos`, `FORMAT_PLATFORM_CHANNELS`, audiências com `plataforma_id`), mas a interface trata cada módulo como lista isolada e não tem **conteúdo visual**. O gargalo é banco de imagens/exemplos, não código.

## 2. O que a referência (Aqui Ads) ensina

| Padrão da referência | Como aplicar no Planner |
|---|---|
| Card com **foto grande no topo** + selos (tipo, digital, distância) | Card de canal com **foto real de anúncio do canal** (acervo existente), logo sobreposto e selos de categoria e "mensurável" |
| **Métricas em trio** (exibições, alcance, frequência) com rótulo e ícone | Trio por canal: alcance, viewability/conclusão, CPM de referência |
| **Preço + período** em destaque ("R$ 264,96 / 2 semanas") | **Não copiar.** Não exibimos preço de venda nem custo: tudo é orçado/cotado. No lugar do preço, o card tem o botão **Solicitar cotação** (ou "Adicionar ao plano" para cotar depois) |
| Botão **"adicionar ponto"** no card + coração | "Adicionar ao plano" e "Salvar" direto na lista (já existe `selection` no código) |
| **Chips de filtro** no topo + "mais filtros" | Chips de categoria, objetivo, formato, faixa de investimento; painel de filtros avançados |
| **Alternador de exibição** (grade, lista, mapa) | Grade / Lista. Sem mapa. "Comparar" fica para a fase 4 |
| **Banner intercalado** na grade ("deixa que a gente cuida da arte") | Banner do Cadu: "Não sabe qual canal? Monte o plano com o Cadu" e "Precisa de criativo? Studio" |
| **Barra fixa "continuar"** | Barra do plano ativo: "3 canais, 5 formatos · Revisar plano" |
| Banner de cookies e rodapé | Não usar |
| Wizard em **tela dividida**: ilustração à esquerda, pergunta única à direita, cartões de resposta | Novo planejamento em passos, uma pergunta por vez |

## 3. O assistente: "Assistente de anúncios" é um bom nome?

Resposta curta: **para o Planner, não é o melhor.**

| Critério | "Assistente de anúncios" | Comentário |
|---|---|---|
| Clareza para anunciante pequeno (Aqui Ads) | Boa | Eles compram anúncio e querem montar um |
| Clareza para agência/mídia (nosso público) | Fraca | Agência planeja **mídia**; "anúncio" sugere criar a peça, o que é o Studio |
| Colide com outro módulo | Sim | Studio e Creative Lab já fazem criativo |
| Identidade da marca | Fraca | O produto já tem persona: **Cadu** |
| "Beta" na etiqueta | Útil | Combina com nossos recursos desligados por flag |

Opções:

| Opção | Onde usar | Veredito |
|---|---|---|
| **Planejar** | Botão e título da tela | **Decidido** |
| Assistente de planejamento | Subtítulo | Boa, mais neutra |
| Planejador Cadu | Item de menu | Boa, curta |
| Assistente de anúncios | Evitar | Confunde com criação de peça |

Decisão: manter **"Novo planejamento"** no menu e chamar o modo guiado apenas de **"Planejar"** (sem "com o Cadu"). Sem "anúncios" no nome.

## 4. Visão: marketplace onde tudo se encaixa

```
        Audiência ──vive em──▶ Canal ──vende──▶ Formato ──ilustrado por──▶ Exemplo (anúncio real)
            ▲                    │                 │
            └──── plano ◀────────┴─────────────────┘   (carrinho único: "Meu plano")
```

Regra de produto: **toda ficha mostra e leva aos três vizinhos**. Canal → seus formatos e audiências. Formato → canais onde roda e exemplos. Audiência → canais onde está e formatos que a alcançam. O carrinho é o plano ativo, sempre visível.

### 4.1 Lista de Canais (nova)

| Elemento | Especificação |
|---|---|
| Cabeçalho | Título, busca, chips de categoria com contagem, "Mais filtros", alternador Grade / Lista |
| Card | Foto 16:9 real do canal, logo sobreposto, selos (categoria, mensurável); nome; 1 linha de papel no plano; trio de métricas; botão **Adicionar ao plano**; coração. **Sem preço** |
| Canal sem foto real | Não há fallback gerado. Canal sem foto vai para a lista de pendências de acervo (seção 5) e usa o card compacto com logo, sem área de foto vazia |
| Banner intercalado | A cada 8 cards: chamada "Planejar" para o assistente |
| Barra fixa inferior | Itens no plano + "Revisar plano" (reaproveitar `selection`) |
| Comparar | **Fase 4**, fora do escopo inicial |

### 4.2 Ficha do Canal (nova)

| Bloco | Conteúdo | Fonte atual |
|---|---|---|
| Hero | Foto grande ou carrossel, logo, selos, trio de métricas, **Adicionar ao plano** fixo (sem preço) | `hero_image_url`, `gallery` |
| Navegação interna fixa | Visão geral · Formatos · Audiências · Exemplos · Como comprar · Novidades (âncoras com contagem) | já há `sections` em `DetailLayout` |
| Visão geral | Papel no plano, diferenciais, quando usar (playbook em cartões) | `roles`, `diferenciais`, `segmentacoes` |
| Formatos | Grade de miniaturas **com a peça renderizada**, dimensões, tipo, botão adicionar | `formats` + exemplos |
| Audiências | Cartões das audiências do canal com tamanho e perfil | **novo**: consulta por `plataforma_id` |
| Exemplos | Galeria de anúncios reais, legenda com marca e formato; clique abre ampliado | `ad_examples`, `concepts` |
| Como comprar | Modelo de compra, prazo, mensuração, brand safety e **"Solicitar cotação"**. Sem valores | já existe, remover `investimento_minimo` da tela |
| Relacionados | "Quem usa 99 também usa Uber, iFood" | **novo**: coocorrência em planos |

### 4.3 Formatos e Audiências

| Módulo | Mudança |
|---|---|
| Formatos | Miniatura da peça com a proporção correta; filtro por canal já existe; ficha mostra "canais onde roda" com logos e exemplos |
| Audiências | Card com tamanho, perfil e **canais onde está**; ficha leva a canais e formatos |

## 5. Dados: o que falta e como resolver

| Lacuna | Impacto | Solução | Esforço |
|---|---|---|---|
| Canais sem exemplo aprovado (99 está vazio) | Ficha vazia | Fila de curadoria: buscar anúncios reais públicos por canal, revisar, aprovar em `cadu_formato_exemplos` | Alto, contínuo |
| Sem imagem de capa por canal | Card sem foto | Usar o acervo real; listar canais sem imagem para completar (`imagem_path`, `hero_image_url`) | Médio |
| Valores comerciais aparecendo na interface | Promessa de preço indevida | Remover `investimento_minimo` e qualquer valor da lista, ficha e cards; botão "Solicitar cotação" | Baixo |
| Ligação audiência ↔ canal | Navegação cruzada | Consulta por `plataforma_id`; revisar o mapeamento `FORMAT_PLATFORM_CHANNELS` | Baixo |
| Direitos de imagem | Risco jurídico | Só usar imagens reais aprovadas com `source_url`; sem imagem gerada por IA na interface | Regra |

**Decisão tomada:** sem mocks de IA e sem fallback gerado. A interface só usa imagens reais.

## 6. Fases

| Fase | Entrega | Depende de | Tamanho |
|---|---|---|---|
| 0 | Aprovar mockups (arquivo de prompts) e decisões da seção 8 | você | pequeno |
| 1 | Card novo de canal (foto real, sem preço) + chips + alternador grade/lista + barra do plano | fase 0 | médio |
| 2 | Ficha do canal com navegação interna, formatos com miniatura, bloco de audiências | fase 1 | médio |
| 3 | Ligar o acervo de imagens reais existente a cada canal (capa, galeria, exemplos) e listar canais ainda sem imagem | paralelo | médio |
| 4 | Formatos e Audiências no mesmo padrão; relacionados; comparar canais | fase 2 | médio |
| 5 | "Planejar": wizard dividido, uma pergunta por passo, reaproveitando `OBJECTIVES` e o formulário atual | fase 0 | médio |
| 6 | Verificação em tela (1280, 1440, 1920, mobile) e testes de contrato | todas | pequeno |

Arquivos principais: `frontend/planner/Catalog.jsx`, `details/ChannelDetail.jsx`, `details/DetailLayout.jsx`, `FormatShowcase.jsx`, `AudienceShowcase.jsx`, `PlansPages.jsx` (novo planejamento), `aicentralv2/cadu_planner/catalog.py` e `channels.py`. O bundle em `static/cadu_planner/react/app.js` é gerado, então precisa de rebuild.

## 7. Riscos

| Risco | Mitigação |
|---|---|
| Working tree compartilhado e sujo (vários arquivos modificados fora deste tema) | Commits pequenos só com os arquivos da fase |
| Imagens pesadas na lista (37+ cards) | `loading="lazy"`, WebP, proporção fixa |
| Valor comercial exposto por engano | Nenhum campo de preço ou custo nas telas do cliente; teste de contrato que falha se `investimento` aparecer |
| Canal sem foto real deixa a grade irregular | Card compacto sem área de foto e lista de pendências de acervo |
| Regra de módulos ES e cache imutável (import map com hash) | Seguir o procedimento já registrado para o bundle |

## 8. Decisões tomadas

| # | Pergunta | Decisão |
|---|---|---|
| 1 | Nome do assistente | **"Planejar"** |
| 2 | Mocks de IA como fallback | **Não.** Só imagens reais do acervo |
| 3 | Preço na lista | **Não mostrar preço de venda nem custo.** Tudo é orçado/cotado; no lugar, "Solicitar cotação" |
| 4 | Por onde começar | **Canais e ficha (fases 1 e 2)** |
| 5 | Comparar canais | **Depois (fase 4)** |

---

## 9. Formatos: o que a Aqui Ads faz melhor e como superar

### 9.1 Por que a vitrine deles funciona

| O que eles fazem | Por que funciona | Como estamos hoje |
|---|---|---|
| **Cada card desenha o formato em escala**: retângulo na proporção real, setas e cotas "largura 256 px / altura 1024 px" | O usuário entende o formato em 1 segundo, sem ler texto, e vê a diferença entre vertical, horizontal e quadrado | `CatalogCard` só mostra imagem para `audiencias` e `places` (`VISUAL_KINDS`). Formatos são texto: nome, tipo e finalidade |
| A peça exibida é uma arte-modelo da marca dentro do retângulo | Dá noção de como o anúncio fica | Só existe `extras.imagem_referencia` na ficha, e quase nunca preenchida |
| Selo de **ambiente** no card (Ruas, Shoppings, Aeroportos, Transportes) | O contexto de exibição vem antes do tamanho | Mostramos "família" apenas como título de grupo |
| Filtros por **ambiente de exibição, formato e tipo de mídia** + ordenar | Três eixos independentes | Temos busca, canal e família |
| **Selecionar vários** (checkbox em cada card, "selecionar todos", "0 itens selecionados") | Montar o plano em lote | Já existe `selection` (adicionar item a item), mas sem seleção múltipla visível na grade |
| Nome do formato + medida (L)x(A) na mesma linha, botão "ver detalhes" | Leitura rápida e comparável | Nome e chips sem a medida em destaque |
| Contagem "95 formatos encontrados" | Feedback imediato | Já temos, no cabeçalho |

Falha deles que **não devemos copiar**: card sem prévia mostra só um ícone ou imagem quebrada ("400x600px" quebrado na terceira linha), e o banner de cookies cobre o conteúdo.

### 9.2 A ideia central: prévia gerada a partir do dado

O campo `dimensoes` (ex.: "300x250", "1200x628 | 1200x1200") já existe em `cadu_formatos`. Em vez de depender de imagem, o front **desenha um SVG em escala** a partir dele. Funciona para os 100+ formatos no dia 1, sem curadoria.

| Camada da prévia | Fonte | Quando usar |
|---|---|---|
| 1. Wireframe em escala com cotas | `dimensoes` (parse de LxA) | Sempre, é o piso |
| 2. Arte-modelo dentro do wireframe | `extras.imagem_referencia` ou peça gerada pelo Studio/GPT Image | Quando existir |
| 3. Foto real em contexto (celular, TV, painel, portal) | Exemplo aprovado em `cadu_formato_exemplos` | Na ficha e no hover |

Regras do wireframe: proporção real limitada a uma caixa fixa (altura máx. 180 px), cotas com seta, cor neutra com o verde da marca como preenchimento, moldura de dispositivo conforme o `tipo` (celular para vertical móvel, TV para 16:9 CTV, retângulo simples para display), múltiplos tamanhos viram "pilha" com os 3 primeiros e "+N". Medidas inválidas ou ausentes mostram ícone do tipo com legenda "sem medida cadastrada", nunca imagem quebrada.

### 9.3 Vitrine de Formatos (nova)

| Elemento | Especificação |
|---|---|
| Barra de filtros | Busca; **Ambiente de exibição**; **Formato** (família); **Tipo de mídia** (estático, vídeo, áudio, interativo); **Canal**; Ordenar (relevância, A-Z, maior, menor, mais usados); alternador Grade / Lista |
| Contadores vivos | Mantém a lógica atual de facetas que somam (cada filtro conta o que os outros deixam) |
| Card | Selo de ambiente/canal com mini logo; **wireframe em escala com cotas**; checkbox de seleção; nome; medida "(L)300 × (A)250 px" em destaque; tipo; botão **Adicionar ao plano** e **Ver detalhes** |
| Seleção em lote | "Selecionar todos · Limpar seleção · N selecionados" e barra fixa "Adicionar N formatos ao plano" |
| Lista | Linha densa com miniatura, medida, peso máximo, arquivos aceitos e canais: ideal para comparar especificações |
| Agrupar | Por família (como hoje), com opção "sem agrupar" |
| Comparar | Marcar até 4 e abrir tabela de especificações lado a lado |

### 9.4 Ficha do Formato (nova)

| Bloco | Conteúdo |
|---|---|
| Hero | Prévia grande em escala + mock em contexto (aba "Em escala" / "Em contexto") |
| Especificações | Tabela: dimensões (cada tamanho), peso máximo, formatos de arquivo, duração (vídeo/áudio), taxa de quadros, safe area; botão **Baixar template** (PSD/Figma/PNG com guia) |
| Boas práticas | "Faça / Evite" com 3 itens cada |
| Onde usar | Canais compatíveis com logos (já existe, ganha visual). Sem preço |
| Exemplos | Anúncios reais aprovados neste formato |
| Para criar a peça | Botão **Criar no Studio** já com o formato e as dimensões preenchidos (liga Planner a Studio) |

Dependências de dados novas: `peso_maximo`, `duracao`, `safe_area`, `template_url` em `dados_extras`; `ambiente` por formato (derivável do canal/família).

### 9.5 Melhorias extras além da referência

| Melhoria | Valor |
|---|---|
| **Checagem de compatibilidade**: ao adicionar um formato, avisar se o canal do plano não o aceita | Evita plano inconsistente |
| **Contagem de peças a produzir** no resumo do plano ("12 tamanhos, 4 vídeos") | Dimensiona o trabalho criativo |
| **Reaproveitar peça**: "este criativo 300×250 também serve em 3 canais do plano" | Economia de produção |
| Busca por medida: digitar "300x250" ou "9:16" | Rapidez para quem já conhece o tamanho |
| Estado de carregamento em esqueleto com a proporção reservada | Sem salto de layout |

### 9.6 Fases (acrescentadas)

| Fase | Entrega | Tamanho |
|---|---|---|
| 1b | Componente `FormatPreview` (SVG em escala + cotas; formato sem medida usa ícone do tipo) e uso no `CatalogCard` de formatos | pequeno |
| 2b | Filtros de ambiente, tipo de mídia e ordenação; seleção em lote; modo lista | médio |
| 3b | Ficha do formato: especificações completas, em escala/em contexto, template, "Criar no Studio" | médio |
| 4b | Compatibilidade no plano e contagem de peças | médio |

A fase 1b é a de maior retorno por menor custo e pode sair primeiro, antes mesmo dos canais, porque independe de curadoria de imagens.

### 9.7 Decisões adicionais (ainda em aberto)

| # | Pergunta | Recomendação |
|---|---|---|
| 6 | Começar pela prévia em escala dos formatos (fase 1b) antes de tudo? | Sim, é o ganho mais rápido |
| 7 | Seleção em lote entra já? | Sim, a base `selection` existe |
| 8 | Template baixável entra agora ou depende de produzir arquivos? | Depois, junto com os dados novos |
| 9 | Botão "Criar no Studio" a partir do formato | Sim, é o elo entre planejar e produzir |
