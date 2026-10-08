# Prompts GPT Image 2.5: ilustrações de Marcas e Projetos (Workspace)

Substituem as ilustrações atuais de estados vazios de **Marcas** e **Projetos** (`static/images/cadu/project-states/*.png`, `brand-states/analysis-states.png`, SVG do `BrandState`). Seguem o mesmo padrão dos prompts do Planner/Radar (`docs/prompts-radar-wizard-image-2-5.md`) e usam o **logo do Workspace** (duplo chevron teal + preto, `static/images/cadu/products/cadu-icon.png`).

A imagem é só cenário. **Título, texto, botões e números são compostos em React por cima**; por isso as cenas não têm letras e as telas saem vazias.

## O que NÃO muda

A **animação de auditoria** (órbitas em volta da logo da marca, barra de etapas e a celebração com fogos) fica como está: `cadu-ds-brand-orbit*`, `cadu-ds-brand-audit-mark`, `AuditCelebration` e `BrandState type="processing"` em `WorkspaceBrand.jsx`. Nenhum prompt abaixo a substitui.

## Como usar

| Item | Regra |
|---|---|
| Referências a anexar | **R1** logo do Workspace (`cadu-icon.png`) · **R2** a primeira cena gerada aprovada (anexar nas demais, para manter traço e paleta) |
| Variações | 2 ou 3 de cada cena; escolher uma |
| Conferir | Sem texto, letra ou número. Só teal do logo, preto, branco, teal claro e cinzas. Logo aparece uma vez por cena, como objeto |
| Onde vão | `aicentralv2/static/images/cadu/states/` em WebP (comprimir; ver nomes abaixo) |
| Formato | Paisagem 4:3, 1200×900, fundo opaco `#FAFAFA`, objeto central com 10% de margem livre; no código a imagem entra com 200–280 px de altura |

## Regras comuns (colar no início de todo prompt; anexar R1, e R2 depois da primeira cena)

```
Use o logo anexado (R1) como marca: o duplo chevron em teal (aprox. #00A590) e preto (aprox. #090D13). Em cada cena o logo aparece UMA vez, como objeto físico (azulejo, etiqueta, placa ou selo com o duplo chevron), nunca como texto.
Ilustração vetorial editorial em estilo flat moderno, formas geométricas arredondadas, contornos limpos e uniformes, sombras só em blocos chapados, sem gradientes complexos, sem 3D realista. Composição centrada, um objeto principal e 3 a 5 elementos de apoio, ar ao redor.
Paleta fechada: teal do logo (#00A590), teal escuro (#0B5A52), teal muito claro (#E3F5F2), preto (#090D13), branco e cinzas (#F2F4F5, #D5DADD). Nenhuma outra cor de destaque; no máximo um toque pequeno de âmbar (#E9A63B) para sinalizar atenção, só quando o prompt pedir.
PROIBIDO na imagem: qualquer texto, letra, número, logotipo de terceiros ou legenda. Telas, cartões, painéis e documentos aparecem VAZIOS: apenas blocos lisos, linhas cinza e formas abstratas (círculos, barras, pontos). Pessoas, quando houver, são estilizadas, sem traços faciais, com tons de pele variados.
Formato paisagem 4:3, 1200×900, PNG, fundo opaco #FAFAFA (não transparente).
```

## Marcas

### M1. Marca nova, sem informações (`marca-nova.png`)
Tela: `BrandState type="new"` ("Ainda não há informações suficientes"). CTA no código: **Preparar análise** / **Adicionar informações**.
```
[REGRAS COMUNS]

Uma grande etiqueta de marca em branco, em formato de cartão arredondado com um furo de cordão, apoiada num suporte de exposição. Em volta, peças soltas ainda por organizar: um quadrado de cor teal, um círculo preto, um pequeno bloco de texto feito de três linhas cinza, uma lupa e um fio tracejado ligando a lupa à etiqueta. O logo do Workspace aparece como selo teal e preto no canto inferior do suporte. Sensação de começo: tudo arrumado e à espera.
```

### M2. Análise concluída sem dados suficientes (`marca-sem-dados.png`)
Tela: `BrandState type="new"` com histórico. CTA: **Nova análise** / **Adicionar informações**.
```
[REGRAS COMUNS]

Uma lupa grande sobre uma página de site abstrata (barra de navegação e blocos cinza) vista de cima; sob a lupa a página está quase vazia, com só um círculo e duas linhas curtas. Ao lado, uma pilha pequena de cartões em branco e uma seta circular fina indicando tentar de novo. Um pequeno toque âmbar num ponto de interrogação feito só de forma (um arco e um ponto, sem ser letra). O logo do Workspace como azulejo teal e preto sobre o cartão de cima.
```

### M3. Análise não concluída (`marca-falha.png`)
Tela: `BrandState type="failed"`. CTA: **Nova análise**; texto pede corrigir a fonte.
```
[REGRAS COMUNS]

Um cabo/conector de link partido ao meio, cada ponta com um plugue arredondado, sobre uma base com uma seta circular de tentar de novo. Uma pequena placa de aviso âmbar com um triângulo (só forma) presa ao cabo. Ao fundo, um navegador abstrato vazio. Nada de pessoa nem de rosto triste: tom calmo, de "corrija e tente de novo". O logo do Workspace como selo no canto da base.
```

### M4. Marca sem radar (`marca-radar-vazio.png`)
Tela nova "Radar da marca", sem nenhum run. CTA: **Rodar radar**.
```
[REGRAS COMUNS]

Uma antena parabólica/radar elegante sobre um pequeno pedestal, com três arcos de sinal concêntricos em teal saindo dela, ainda sem nenhum ponto detectado. Perto do pedestal, o cartão arredondado de uma marca (losango abstrato) ligado à antena por um fio tracejado. Pontos cinza vazios espalhados em volta, esperando acender. O logo do Workspace como placa de metal no pedestal.
```

### M5. Radar sem novidades (`marca-radar-sem-novidade.png`)
Radar já rodou, nada novo acima do limite.
```
[REGRAS COMUNS]

A mesma antena de radar da cena M4, agora ao lado de um relógio/agenda abstrato (círculo com dois ponteiros) e uma lista de verificação com três itens já marcados em teal. Os arcos de sinal estão calmos e uma pequena lua/estrela teal sugere "tudo em dia". Sem pontos de alerta. O logo do Workspace como adesivo na agenda.
```

### M6. Biblioteca da marca vazia (`marca-biblioteca-vazia.png`)
Seção de ativos (logos, referências, criativos).
```
[REGRAS COMUNS]

Uma pasta/caixa de arquivo aberta, em teal escuro, com molduras vazias saindo dela: uma moldura quadrada (logo), uma retangular larga (criativo), uma pequena com um sol e montanha simples (imagem) e uma paleta de três círculos (teal, preto, cinza). Uma seta suave de upload apontando para dentro da caixa. O logo do Workspace como selo na frente da caixa.
```

### M7. Marca sem projetos vinculados (`marca-sem-projetos.png`)
Trilho e seção "Projetos". CTA: **Criar ou vincular projeto**.
```
[REGRAS COMUNS]

Um cartão de marca (losango abstrato) à esquerda e uma pasta de projeto vazia à direita, separados por um fio tracejado com um elo/clipe aberto no meio, pronto para fechar. Pequenos blocos de papel flutuando perto da pasta. O logo do Workspace como etiqueta na aba da pasta.
```

### M8. Lista de marcas vazia (`marcas-lista-vazia.png`)
`WorkspaceBrands` sem nenhuma marca. CTA: **Nova marca**.
```
[REGRAS COMUNS]

Uma prateleira ou estante com várias etiquetas de marca (cartões com losango, círculo e quadrado abstratos); só a primeira etiqueta está preenchida e as demais estão em contorno tracejado, indicando espaço para novas marcas. Um botão redondo teal com um sinal de mais (só forma) ao lado da prateleira. O logo do Workspace como placa na lateral da estante.
```

## Projetos

### P1. Para começar (`projeto-comecar.png`)
Cartão "Conheça e complete este projeto" na Visão geral.
```
[REGRAS COMUNS]

Uma pasta de projeto aberta como um mapa: quatro marcos pequenos ligados por uma trilha tracejada (um documento, um ponto de interrogação em forma de arco, uma lista de verificação, um guia dobrado), terminando numa bandeirinha teal. O logo do Workspace como selo no centro da pasta. Clima acolhedor de "por onde começar".
```

### P2. Atividade vazia (`projeto-atividade-vazia.png`)
```
[REGRAS COMUNS]

Uma linha do tempo vertical com pontos vazios (contornos cinza) e um único ponto teal preenchido no topo, ao lado de cartões de evento em branco com linhas cinza. Um relógio pequeno e uma folha de calendário em branco. O logo do Workspace como selo no ponto teal do topo.
```

### P3. Tarefas vazias (`projeto-tarefas-vazias.png`)
```
[REGRAS COMUNS]

Um quadro de tarefas com três colunas vazias (cabeçalhos como barras de cores teal claro, cinza e preto) e cartões em branco encaixados. Uma caneta/lápis grande e uma caixa de seleção redonda com visto teal em primeiro plano. O logo do Workspace como prendedor de papel no canto do quadro.
```

### P4. Fontes vazias (`projeto-fontes-vazias.png`)
Substitui `library-empty.png` e as telas Arquivos/Biblioteca/Indexação sem itens. CTA: **Adicionar fonte**.
```
[REGRAS COMUNS]

Uma caixa de entrada de arquivos em teal escuro, vazia, com quatro ícones de tipo flutuando acima prontos para cair dentro: um documento dobrado, uma imagem, um elo de link e uma onda de áudio, todos em blocos lisos sem conteúdo. Uma seta suave de entrada. O logo do Workspace como placa frontal da caixa.
```

### P5. Fontes sendo indexadas (`projeto-fontes-indexando.png`)
Substitui `indexing-processing.png`. Estado de processamento, sem animação nova.
```
[REGRAS COMUNS]

Documentos entrando por uma esteira curta em direção a uma lupa/leitor em teal, que os transforma em pequenos pontos ligados por fios (uma rede de conhecimento). Três documentos na esteira, dois já viraram nós teal ao fundo. Uma engrenagem pequena e um relógio de areia abstrato. O logo do Workspace como selo na máquina do leitor.
```

### P6. Entregas vazias (`projeto-entregas-vazias.png`)
CTA: **Criar no projeto**.
```
[REGRAS COMUNS]

Uma mesa de trabalho vista de frente com três molduras de entrega vazias: um quadro vertical (peça de imagem), um retângulo largo com triângulo de play liso (vídeo) e uma folha com gráfico de barras cinza (relatório/plano). Um carrinho/bandeja pequeno esperando receber as peças. O logo do Workspace como adesivo na bandeja.
```

### P7. Reports vazio (`projeto-reports-vazio.png`)
Substitui `views-empty.png`. Cobre campanhas, sites e fluxos do Reports.
```
[REGRAS COMUNS]

Um painel de gráficos vazio: eixos finos, três barras baixas cinza e uma linha pontilhada à espera de dados, ao lado de um alvo de campanha, uma janela de navegador abstrata (site) e um pequeno funil (fluxo). Elos tracejados em teal ligando esses três ao painel, ainda sem dados. O logo do Workspace como selo no canto do painel.
```

### P8. Planos vazios (`projeto-planos-vazio.png`)
Cartão "Planos" do resumo do projeto. CTA: **Criar plano de mídia**.
```
[REGRAS COMUNS]

Uma mesa de planejamento com uma planta/mapa de rotas (quadro com pinos e uma trilha tracejada ligando três paradas em forma de círculo, quadrado e triângulo), um calendário em branco e um bloco de notas. Uma bússola pequena em teal. O logo do Workspace como selo no canto do mapa.
```

### P9. Conversas vazias (`projeto-conversas-vazio.png`)
CTA: **Nova conversa**.
```
[REGRAS COMUNS]

Dois balões de conversa grandes e arredondados, um branco e um teal, vazios (só três pontinhos cinza no branco), diante de uma pasta de projeto aberta. Pequenas faíscas teal ao redor do balão teal sugerindo o assistente. O logo do Workspace como selo no balão teal.
```

### P10. Lista de projetos vazia (`projetos-lista-vazia.png`)
`WorkspaceProjects` sem projetos. CTA: **Novo projeto**.
```
[REGRAS COMUNS]

Um arquivo/gaveteiro com várias pastas; só a primeira pasta aparece preenchida (teal) e as demais em contorno tracejado, abertas para novos projetos. Um botão redondo teal com sinal de mais (só forma). O logo do Workspace como placa no topo do gaveteiro.
```

## Mapa de substituição

| Hoje | Passa a ser | Observação |
|---|---|---|
| `project-states/activity-empty.png` | `states/projeto-atividade-vazia` | P2 |
| `project-states/tasks-empty.png` | `states/projeto-tarefas-vazias` | P3 |
| `project-states/library-empty.png` | `states/projeto-fontes-vazias` | P4 (e Arquivos vazio) |
| `project-states/indexing-processing.png` | `states/projeto-fontes-indexando` | P5 |
| `project-states/deliveries-empty.png` | `states/projeto-entregas-vazias` | P6 |
| `project-states/views-empty.png` | `states/projeto-reports-vazio` | P7 |
| SVG do `BrandState` (tipos `new`/`failed`) | M1, M2, M3 | `<img>` no lugar do `<svg>` |
| `brand-states/analysis-states.png`, `workspace-cards/brand-review-loop.png` | remover se nada mais usar | conferir com `grep` antes |
| (novos) | M4–M8, P1, P8–P10 | sem equivalente hoje |

## Implementação (depois de aprovar as cenas)

1. Gerar com o mesmo caminho do Radar/portais (`svc._openai_generate_image`, `aspect_ratio` 4:3, qualidade média). Custo estimado: 10 + 8 cenas × 2 variações. **Pedir aval antes de gerar.**
2. Comprimir para WebP em `static/images/cadu/states/`.
3. Criar um componente `StateIllustration({name, alt})` em `cadu-design-system/components` e usar nos dois lugares (hoje `ProjectStateIllustration` aceita `project-states/<nome>.png`).
4. Remover os PNGs antigos que ficarem sem uso e conferir o peso das páginas (hoje cada PNG tem 130–420 KB).
5. Estados vazios sempre com um CTA primário e o texto de uma linha (regra de CTAs, seção 9.3 do plano).
