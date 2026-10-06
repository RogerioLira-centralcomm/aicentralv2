# Prompts GPT Image 2.5: ilustrações do Radar

Estas ilustrações acompanham `docs/radar-v2-plano.md`. Seguem o mesmo padrão das cenas do wizard "Planejar" (`docs/prompts-gpt-image-mockups-planner.md`). A imagem é só cenário. **Título, perguntas, rótulos, ícones e números são compostos em React por cima**, por isso as cenas não têm nenhuma letra e as telas dos dispositivos saem vazias.

## Como usar

| Item | Regra |
|---|---|
| Referências | **R9** logo do Planner (duplo chevron verde-esmeralda + preto) · **R11** uma das cenas atuais do Planejar (ex.: `planejar-praca.webp`) para manter o traço · **R12** mascote (`mascote-planner.webp`) |
| Variações | Gere 2 ou 3 de cada cena e escolha |
| Conferir | Sem texto nem número; só verde-esmeralda, preto e neutros; mascote com o mesmo olho único em todas |
| Onde vão | `aicentralv2/static/images/planner/illustrations/` (eu comprimo para WebP) |

O fio condutor do Radar é: **antena/radar que varre → sinais que acendem → lupa que confere → alvo/agenda que vira plano**. Os passos 1 a 5 contam essa história na mesma cidade estilizada do Planejar.

## Regras comuns (cole no início de todo prompt; anexar R9, R11 e R12)

```
Use o logo anexado (R9) como referência de marca: verde-esmeralda vivo (aprox. #1DBF73) e preto (aprox. #101418). Mantenha o mesmo traço, proporção de personagens e cidade estilizada da cena de referência (R11). O mascote (R12) tem corpo preto, um chevron verde-esmeralda e UM único olho; mantenha-o idêntico.
Ilustração vetorial editorial em estilo flat moderno, formas geométricas arredondadas, contornos limpos, sombras só em blocos chapados, sem gradientes complexos. Paleta fechada: verde-esmeralda, preto, branco, verde-esmeralda muito claro (#E3F8EE), cinzas. Nenhuma outra cor de destaque.
PROIBIDO na imagem: qualquer texto, letra, número, logotipo, marca ou legenda. Telas de celular, TV, painel, notebook e radar devem aparecer VAZIAS: apenas bloco liso verde-esmeralda ou formas abstratas simples (círculos, pontos, barras), sem conteúdo legível. Pessoas estilizadas, sem traços faciais detalhados, com diversidade de idades e tons de pele.
Formato retrato 1200×1600, com 15% de margem livre no topo e 12% embaixo (o código coloca título e legendas ali). PNG, fundo opaco (não transparente).
```

## Wizard "Configurar Radar" (5 cenas, painel esquerdo)

### Cena 1: marca (`radar-1-marca.png`)

Passo "De quem é este radar?". A cena mostra o Radar reunindo o que já se sabe da marca.

```
[REGRAS COMUNS]

Uma pessoa estilizada (blazer verde-esmeralda) em pé diante de um grande painel de cortiça com cartões lisos presos por alfinetes verdes: um cartão com um losango de marca abstrato, outro com silhuetas de pessoas (público), outro com três pequenos prédios lado a lado (concorrentes) e fios tracejados ligando os cartões a um ponto central. O mascote está sentado no topo do painel, olhando para o ponto central. Ao fundo, a cidade estilizada em verde-esmeralda muito claro.
```

### Cena 2: tema (`radar-2-tema.png`)

Passo "O que você quer encontrar?" (lentes: sazonalidade, concorrência, tendências, regulação…).

```
[REGRAS COMUNS]

Uma pessoa estilizada segurando uma lente grande e redonda de aro preto diante dos olhos; através da lente, uma parte da cidade aparece realçada em verde-esmeralda vivo, enquanto o resto fica em cinza-claro. Flutuando ao redor, quatro ícones geométricos simples e sem texto: um calendário em grade, um balão de conversa, uma seta subindo e um pequeno martelo de juiz. O mascote espia por cima do ombro da pessoa.
```

### Cena 3: onde e quando (`radar-3-praca-janela.png`)

Passo "Onde e em que janela?".

```
[REGRAS COMUNS]

Vista aérea da cidade estilizada em blocos (prédios, ruas, parque) com três pinos de localização verde-esmeralda e preto. Sobre a cidade, um grande arco de relógio sem números, desenhado como um semicírculo fino de traço preto, com uma faixa preenchida em verde-esmeralda marcando uma janela de tempo. Um painel urbano vazio e um ponto de ônibus no primeiro plano. Sem mapa realista, sem nomes.
```

### Cena 4: fontes (`radar-4-fontes.png`)

Passo "Onde o Radar deve olhar?" (notícias, buscas, redes, governo, calendário, concorrentes, base do projeto).

```
[REGRAS COMUNS]

No centro, uma antena de radar parabólica preta com prato verde-esmeralda sobre um prédio baixo, emitindo ondas concêntricas finas em verde-esmeralda claro. Ao redor, nas pontas das ondas, seis objetos simples e sem texto que representam fontes: um jornal dobrado liso, uma lupa, um celular com balões vazios, um prédio com colunas clássicas (governo), um calendário de mesa sem números e uma pasta de arquivos. Pontos de sinal acendem em alguns deles. O mascote opera um pequeno painel de botões redondos ao pé da antena.
```

### Cena 5: revisão e alerta (`radar-5-revisao.png`)

Passo "Pronto para procurar?", com o interruptor "Me avise quando houver novidade".

```
[REGRAS COMUNS]

Uma pessoa estilizada sentada à mesa, relaxada, com um notebook aberto (tela vazia com formas abstratas de cartões e um pequeno gráfico de quatro quadrantes, sem números). Ao lado, um sino de mesa verde-esmeralda com duas pequenas linhas de vibração, um relógio de parede sem números com três marcas verdes no aro (manhã, tarde, noite) e uma xícara preta com um chevron verde. O mascote segura uma lanterna apontada para o horizonte da cidade pela janela.
```

## Estados da tela Radar

### Busca rodando (`radar-scan.png`, substitui o placeholder do slot `radar-scan`, 480×320)

```
[REGRAS COMUNS]

Formato paisagem 1200×800, sem margens reservadas, fundo verde-esmeralda muito claro. Uma antena de radar preta com prato verde-esmeralda em primeiro plano, com um feixe de varredura em leque verde translúcido passando sobre uma cidade estilizada; três pontos de sinal acendem no caminho do feixe (um sobre um jornal liso, um sobre uma lupa, um sobre um celular). O mascote observa com binóculos ao lado da antena.
```

Se a animação for feita depois, o feixe gira em loop de até 2,4 s e os pontos acendem em sequência. Também é preciso entregar uma versão estática para `prefers-reduced-motion`.

### Antes da primeira busca (`radar-empty.png`, substitui o slot `radar-empty`, 480×320)

```
[REGRAS COMUNS]

Formato paisagem 1200×800, sem margens reservadas, fundo verde-esmeralda muito claro. O mascote no alto de um pequeno morro gramado, com uma luneta preta de detalhes verdes apontada para um horizonte de cidade calmo, com nuvens arredondadas e um único brilho verde-esmeralda no céu. Clima de "ainda não procuramos".
```

### Busca sem resultado (`radar-vazio-resultado.png`, 480×320)

```
[REGRAS COMUNS]

Formato paisagem 1200×800, sem margens reservadas, fundo verde-esmeralda muito claro. A antena de radar com o feixe passando por uma cidade tranquila, sem pontos de sinal acesos. O mascote coça a cabeça com uma mão e segura uma lupa com a outra. Tom leve, sem frustração.
```

## Alertas e Agentes

### Alertas sem nada configurado (`alertas-vazio.png`, 480×320)

```
[REGRAS COMUNS]

Formato paisagem 1200×800, sem margens reservadas, fundo verde-esmeralda muito claro. Um sino grande verde-esmeralda em repouso sobre uma pilha de três cartões lisos, um relógio sem números ao lado com três marcas verdes no aro e o mascote dando corda num pequeno despertador preto. Sem texto.
```

### Banner de Alertas (`alertas-banner.png`, 1680×560)

Aparece no topo de `/radar/alertas`. O título e o botão são compostos em HTML no terço esquerdo.

```
[REGRAS COMUNS]

Formato paisagem 1680×560. Deixe o terço esquerdo inteiro livre, só com fundo verde-esmeralda muito claro (o código põe o título ali). Nos dois terços da direita: uma linha do dia desenhada como um arco fino de sol nascente a sol poente sobre a cidade estilizada, com três pontos marcados no arco (manhã, meio-dia, fim de tarde); em cada ponto, uma pequena antena emite uma onda, e de uma delas desce um cartão liso com uma marca verde de check até um celular vazio na mão de uma pessoa estilizada.
```

### Agentes do Radar (`agentes-radar.png`, 1200×1600, cena do painel de criação do agente)

```
[REGRAS COMUNS]

Três versões do mascote, idênticas e lado a lado, cada uma com um pequeno acessório diferente (fones de ouvido, uma lupa, uma prancheta lisa), sentadas numa bancada em frente a uma parede de telas vazias com formas abstratas (pontos, barras, um gráfico de quatro quadrantes). Fios finos verde-esmeralda ligam cada mascote a uma pasta de arquivos aberta (as bases de consulta). Uma pessoa estilizada de pé ao fundo, de braços cruzados e sorrindo, supervisiona.
```

### O que o agente aprendeu (`agente-aprendeu.png`, 480×320)

```
[REGRAS COMUNS]

Formato paisagem 1200×800, sem margens reservadas, fundo verde-esmeralda muito claro. O mascote diante de uma balança de pratos: num prato, cartões lisos com uma marca verde de check; no outro, cartões lisos com um pequeno x cinza. Um ponteiro simples se inclina para o lado verde. Ao lado, um caderno aberto com linhas abstratas e um lápis.
```

## Como o código usa

| Imagem | Onde |
|---|---|
| `radar-1` a `radar-5` | Painel esquerdo do `RadarWizard.jsx`, uma por passo, com a mesma transição do Planejar |
| `radar-scan`, `radar-empty`, `radar-vazio-resultado` | `Illustration.jsx`: o slot passa a usar `<img>` e o placeholder sai. Atualizar a tabela em `docs/design/planner-illustrations.md` com a paleta nova |
| `alertas-vazio`, `alertas-banner` | Tela `/radar/alertas` |
| `agentes-radar`, `agente-aprendeu` | Fase 4 (Agentes) |
