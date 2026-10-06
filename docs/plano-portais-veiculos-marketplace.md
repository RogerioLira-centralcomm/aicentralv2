# Portais e veículos como marketplace, com prints reais

Plano para análise. Nada foi implementado. Data: 2026-10-06. Regra de partida: **print real do portal, nunca imagem criada do zero**, sempre com data e fonte.

## 1. Diagnóstico (dados lidos do banco em 2026-10-06)

| Fato | Valor |
|---|---|
| Portais cadastrados (`cadu_planner_portals`) | **1.074** |
| Premium nacionais | 100 |
| Regionais | 974 (jornalismo online por região) |
| Com visitas mensais | **0** |
| Com leitura do site (`last_crawled_at`) | **0** |
| Com favicon | **0** |
| Com `ads.txt` lido | **0** |
| Captura de tela no código | **não existe** (sem Playwright, sem Chromium; há o CLI `firecrawl` na máquina) |

Hoje a vitrine é uma lista de linhas sem imagem e com métricas vazias ("Sem fonte"). Para um marketplace falta o visual (print), os números e a ligação com formatos e audiências.

## 2. Visão da vitrine

| Elemento | Especificação |
|---|---|
| Card | **Print da home** (acima da dobra, 16:9) com data da captura; favicon/logo; nome e domínio; escopo (Premium nacional / Regional · UF); 3 números (acessos/mês, tempo médio, formatos de anúncio detectados); botão Adicionar ao plano |
| Grade e lista | Grade com prints; lista densa para comparar |
| Filtros (uma linha, sem quebra) | Busca; Escopo; Estado; Categoria; "Só com print"; "Só programático" |
| Ordenação | Premium primeiro, depois por acessos; "Mais recentes" pela data do print |
| Agrupamento | Premium nacionais em destaque no topo; regionais por região |
| Banner "Planejar" | Igual ao de Canais |
| Barra do plano | Já existe |

### Ficha do portal

| Bloco | Conteúdo |
|---|---|
| Carrossel | Prints reais: home, uma página de notícia e uma página com espaço de anúncio visível; cada um com **data e URL** |
| Métricas com ícone | Audiência pública (com fonte), acessos/mês, tempo médio, páginas lidas |
| Espaços de anúncio | Os slots detectados na página (topo, lateral, in-article) marcados sobre o print |
| Programático | Status de `ads.txt`, vendedores e sinais (campos já existem) |
| Evidências públicas | Já existe |
| Formatos compatíveis | Formatos de Display, Native e Vídeo com **Adicionar** (liga com a vitrine de Formatos) |
| Plano ao lado | Coluna "No seu plano" (já existe) |

## 3. Como obter os prints

| Etapa | Opção | Observação |
|---|---|---|
| Captura | `firecrawl scrape --screenshot` (CLI já instalado) ou Playwright/Chromium em um worker | Decidir uma: firecrawl é rápido de integrar; Playwright dá controle (aceitar cookies, esperar anúncios) |
| Tamanho | 1440×900 acima da dobra (home) e página inteira recortada em 1440×2400 | Salvar WebP 85 |
| Anúncios | Esperar o carregamento e **não** mascarar nem editar o que aparece | Print fiel; se o anúncio da hora for de outra marca, é o que o portal mostrou |
| Cookies e popups | Fechar banner de consentimento antes do print; sem login | Falha vira "sem print" e entra na fila de revisão |
| Armazenamento | Disco primeiro (como já fazemos com capturas do Reports), depois serviço externo | Caminho: `static/images/portais/prints/{id}/{data}-home.webp` |
| Registro | Nova tabela `cadu_planner_portal_prints` (portal_id, tipo, url, arquivo, capturado_em, status) | Migração em `ORDER.txt`; sem mexer em `cadu_planner_portals` |
| Atualização | Nova captura a cada 30 dias para premium, 90 para regionais | Manter a anterior para histórico |
| Revisão | Tela interna simples: aprovar ou descartar cada print antes de ir ao cliente | Evita captura quebrada ou imprópria |

## 4. Riscos e regras

| Risco | Tratamento |
|---|---|
| Direitos sobre a imagem do site de terceiros | Uso interno de planejamento, com data e fonte; **validar com o jurídico** antes de abrir ao cliente |
| Print mostrando conteúdo sensível ou anúncio inadequado | Fila de aprovação humana |
| `robots.txt` e termos de uso | O módulo de leitura já respeita robots; manter o mesmo para o print |
| Carga em sites pequenos | Fila com limite e intervalo por domínio |
| Dados de audiência vazios | Mostrar "sem fonte"; não preencher com estimativa |
| 1.074 portais é muito | Começar pelos 100 premium nacionais |

## 5. Fases

| Fase | Entrega | Tamanho |
|---|---|---|
| 0 | Decidir a ferramenta de captura e validar o uso com o jurídico | pequeno |
| 1 | Captura dos **100 premium nacionais** (home), tabela de prints e tela de aprovação | médio |
| 2 | Card com print, grade/lista, filtros em uma linha e banner (reaproveita componentes de Canais) | médio |
| 3 | Ficha com carrossel de prints, espaços de anúncio e formatos compatíveis | médio |
| 4 | Métricas reais (acessos, tempo médio) a partir de uma fonte confiável; `ads.txt` em lote | alto |
| 5 | Regionais, atualização automática mensal e histórico de prints | alto |

## 6. Decisões que preciso de você

| # | Pergunta | Recomendação |
|---|---|---|
| 1 | Ferramenta de captura | Começar com `firecrawl` (já instalado); migrar para Playwright se precisar de mais controle |
| 2 | Quem aprova os prints | Time comercial, numa tela interna, antes de ir ao cliente |
| 3 | Jurídico: prints de sites de terceiros na vitrine | Validar antes da fase 2 |
| 4 | Fonte dos números de audiência | Definir (a base atual não tem nenhuma); sem ela o card mostra só o print e os formatos |
| 5 | Começar pelos 100 premium nacionais | Sim |
