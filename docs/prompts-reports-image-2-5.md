# Prompts GPT Image 2.5: ilustrações do Reports

Mesmo método do Planner e do Radar (`docs/prompts-radar-wizard-image-2-5.md`): a imagem é só cenário. **Título, perguntas, rótulos, números e ícones são compostos em React por cima**, então nenhuma cena tem letra e todas as telas de painel saem vazias.

São 24 imagens, em 5 blocos, geradas nesta ordem. A cena **P0 (base)** vem primeiro: ela fixa o traço e a cidade, e todas as outras usam P0 como referência de estilo.

## Como usar

| Item | Regra |
|---|---|
| Referências | **R1** logo do Reports (duplo chevron azul) · **R2** a cena P0 aprovada (a partir da cena 2) |
| Variações | Gere 2 ou 3 de cada cena e escolha. Em P0, gere 4: ela define o resto |
| Cor de destaque | O Reports usa o azul `#175CD3` (sidebar, links, gráficos). Se o azul do logo que você enviar for outro, troque o hex na regra comum antes de gerar P0 |
| Conferir | Sem texto nem número; só azul, preto e neutros; telas vazias; mesma cidade e mesmos personagens em todas |
| Onde vão | `aicentralv2/static/images/reports/illustrations/` (eu comprimo para WebP) |

O fio condutor do Reports é: **dado solto → painel que se organiza → leitura que vira decisão**. Os fios tracejados azuis ligam fontes (site, anúncio, planilha) a um painel central. Nada de mascote: o Reports é analítico, os personagens são pessoas.

## Regras comuns (cole no início de todo prompt; anexar R1 e, a partir da cena 2, R2)

```
Use o logo anexado (R1) como referência de marca: azul vivo (aprox. #175CD3) e preto (aprox. #101418). Se a cena de referência (R2) estiver anexada, mantenha exatamente o mesmo traço, a mesma proporção dos personagens e a mesma cidade estilizada.
Ilustração vetorial editorial em estilo flat moderno, formas geométricas arredondadas, contornos limpos, sombras só em blocos chapados, sem gradientes complexos. Paleta fechada: azul #175CD3, azul muito claro (#EFF4FF), azul médio (#B2CCFF) para fundos de apoio, preto, branco e cinzas. Nenhuma outra cor de destaque. Verde, âmbar e vermelho só aparecem como um único ponto pequeno (status ok / espera / atenção) quando o prompt pedir.
PROIBIDO na imagem: qualquer texto, letra, número, logotipo, marca ou legenda. Telas de notebook, monitor, celular e painel devem aparecer VAZIAS: apenas bloco liso azul-claro ou formas abstratas simples (círculos, pontos, barras, linhas suaves), sem conteúdo legível. Pessoas estilizadas, sem traços faciais detalhados, com diversidade de idades e tons de pele.
Formato indicado em cada cena. PNG, fundo opaco (não transparente).
```

Nos wizards (retrato 1200×1600) deixe **15% de margem livre no topo e 12% embaixo** (o código coloca título e legendas ali). Nas cenas de onboarding (paisagem 1600×1000) deixe **margem de 8%** nas bordas e o terço direito mais limpo, porque o texto fica ao lado.

---

## Bloco 0: Base (gere primeiro)

### P0: observatório de dados (`reports-base.png`, 1600×1000)

Cena mãe. Define cidade, personagens, painel central e fios tracejados.

```
[REGRAS COMUNS, sem R2]

Uma sala-observatório de dados vista de frente, com janelas grandes mostrando uma cidade estilizada em azul muito claro. No centro, um grande painel arredondado vazio (bloco liso azul-claro com apenas três barras e uma linha suave abstratas). Do painel saem fios tracejados azuis que descem até quatro objetos sobre uma bancada: um pequeno notebook (anúncios), uma miniatura de site em janela de navegador vazia, uma caixa de arquivo com planilha vazia e um funil de conversão simples. Duas pessoas estilizadas (uma de blazer azul #175CD3, outra de camiseta preta) conversam apontando para o painel. Plantas e uma xícara dão calor à cena. Luz suave vinda das janelas, sombras chapadas. Paisagem 1600×1000.
```

---

## Bloco 1: Wizard "Novo cliente e conta" (3 cenas, retrato 1200×1600)

Fluxo: cadastrar o anunciante (cliente) e a conta de mídia dele.

### Cena 1: cliente (`conta-1-cliente.png`)

Passo "Quem é o cliente?" (nome, marca do Workspace).

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada (blazer azul) abre uma pasta grande de cliente sobre uma mesa. Dentro da pasta, um cartão liso com um losango abstrato no lugar da marca e uma pequena moldura redonda vazia (logo do cliente). Ao fundo, uma estante com outras pastas de cores azul e cinza, cada uma com uma etiqueta lisa. A cidade estilizada em azul muito claro aparece pela janela. Retrato 1200×1600.
```

### Cena 2: conta de mídia (`conta-2-midia.png`)

Passo "Em que plataforma ele anuncia?" (Google Ads, Meta, outras).

```
[REGRAS COMUNS + R2]

A mesma pessoa, agora diante de uma parede com três portas arredondadas lado a lado, cada uma com uma moldura redonda vazia acima (uma para cada plataforma). Uma das portas está aberta e deixa ver um corredor de luz azul-claro; um fio tracejado azul liga essa porta à pasta do cliente que ela segura. Um pequeno ponto verde acima da porta aberta indica conexão. Retrato 1200×1600.
```

### Cena 3: revisão (`conta-3-revisao.png`)

Passo "Tudo certo?" (resumo antes de criar).

```
[REGRAS COMUNS + R2]

Duas pessoas estilizadas conferem uma prancheta grande com uma lista de três itens vazios, cada um com uma caixinha marcada em azul. Atrás delas, a pasta do cliente e a porta da plataforma já ligadas por um fio azul contínuo (não tracejado) ao painel central vazio. Clima de conclusão, uma pequena estrela azul acima do painel. Retrato 1200×1600.
```

---

## Bloco 2: Wizard "Conectar o Google Ads" (4 cenas, retrato 1200×1600)

Fluxo: fonte de dados do Google Ads, com a campanha que será medida.

### Cena 1: escolher a fonte (`gads-1-fonte.png`)

Passo "De onde vêm os dados?".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada diante de uma mesa de triagem com três bandejas arredondadas: uma com um pequeno megafone (anúncios), uma com um navegador vazio (site) e uma com um arquivo (planilha). A bandeja do megafone brilha em azul #175CD3 e é a única destacada; as outras ficam em azul muito claro. Do megafone sai um fio tracejado até o painel central vazio, ao fundo. Retrato 1200×1600.
```

### Cena 2: instalar o script (`gads-2-script.png`)

Passo "Cole o script no Google Ads".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada senta ao notebook, cuja tela mostra apenas um bloco liso azul-claro com linhas horizontais abstratas (código sem conteúdo legível). Ao lado, uma chave grande azul flutua sobre uma pequena caixa-cofre arredondada, simbolizando a chave de acesso. Um fio tracejado sobe do notebook até o painel central ao fundo. Retrato 1200×1600.
```

### Cena 3: escolher a campanha (`gads-3-campanha.png`)

Passo "Qual campanha acompanhar?".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada examina uma fileira de cartões grandes e arredondados, cada um com uma barra e um ponto abstratos (campanhas). Um dos cartões, levantado com uma moldura azul #175CD3, é o escolhido; a pessoa o marca com uma etiqueta azul lisa. Fios tracejados ligam o cartão escolhido ao painel central, ao fundo. Retrato 1200×1600.
```

### Cena 4: aguardando o primeiro envio (`gads-4-aguardando.png`)

Passo "Conectado. Esperando os dados".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada toma café ao lado de uma ampulheta grande e arredondada, com areia azul clara a cair. Atrás dela, o painel central vazio mostra um pequeno relógio abstrato e um fio azul vindo do megafone quase chegando ao painel. Um único ponto amarelo-âmbar pequeno acima do painel indica espera. Retrato 1200×1600.
```

---

## Bloco 3: Wizard "Adicionar site, fluxo e Super Tag" (5 cenas, retrato 1200×1600)

### Cena 1: o site (`site-1-dominio.png`)

Passo "Qual é o site?".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada de pé diante de uma grande janela de navegador flutuante e vazia (barra de endereço lisa, sem texto), com uma pequena casa abstrata no canto. Um globo azul-claro com meridianos suaves flutua ao lado. Um fio tracejado azul liga a janela ao painel central, ao fundo. Retrato 1200×1600.
```

### Cena 2: instalar a Super Tag (`site-2-supertag.png`)

Passo "Instale a Super Tag".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada coloca uma etiqueta em forma de pino (marcador de mapa) azul #175CD3, grande e brilhante, dentro de uma janela de navegador vazia, como quem fixa um sensor. Pequenas ondas concêntricas azul-claro saem do pino. Ao lado, uma colega confere a instalação num notebook de tela lisa. Retrato 1200×1600.
```

### Cena 3: desenhar o fluxo (`site-3-fluxo.png`)

Passo "Monte o caminho do visitante".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada desenha um mapa de caminho sobre uma lousa grande: quatro quadros arredondados vazios ligados por setas azuis (anúncio, página, formulário, conversão), com um ponto azul #175CD3 percorrendo o caminho. A lousa tem moldura clara e um pequeno funil desenhado no canto. Retrato 1200×1600.
```

### Cena 4: a conversão (`site-4-conversao.png`)

Passo "O que conta como resultado?".

```
[REGRAS COMUNS + R2]

Uma pessoa estilizada ergue um alvo grande, com o centro azul #175CD3, sobre o qual pousa uma bandeirinha azul. Aos pés dela, um pequeno formulário vazio e um botão arredondado liso, simbolizando o evento de conversão. Pequenas faíscas azul-claro ao redor do alvo. Retrato 1200×1600.
```

### Cena 5: revisão e publicar (`site-5-revisao.png`)

Passo "Publicar e começar a medir".

```
[REGRAS COMUNS + R2]

Duas pessoas estilizadas sobem juntas uma pequena escada azul até uma plataforma onde o painel central vazio está aceso; um foguete de papel azul decola ao fundo, entre as janelas da cidade. Três fios azuis contínuos ligam site, fluxo e Super Tag ao painel. Clima de lançamento. Retrato 1200×1600.
```

---

## Bloco 4: Onboarding "Conhecer o Reports" (8 cenas, paisagem 1600×1000)

Tela nova logo abaixo de **Visão geral**, interativa. Cada capítulo tem uma cena à esquerda e, ao lado, texto e uma ação que prepara o ambiente (criar o cliente, conectar a fonte, instalar a Super Tag). O terço direito de cada cena fica limpo para o texto.

### O1: boas-vindas (`onb-1-boas-vindas.png`)

```
[REGRAS COMUNS + R2]

A sala-observatório da cena base em plano mais aberto: as janelas amanhecem sobre a cidade, o painel central acende pela primeira vez e as duas pessoas estilizadas trocam um high-five. Um tapete de boas-vindas azul liso na entrada. Terço direito da imagem mais limpo (parede clara). Paisagem 1600×1000.
```

### O2: clientes e contas (`onb-2-clientes.png`)

```
[REGRAS COMUNS + R2]

Uma estante organizada com pastas de clientes, cada uma com uma moldura redonda vazia no topo e um pequeno cabo azul que desce até uma caixa de contas de mídia. Uma pessoa estilizada encaixa uma pasta nova na estante. Terço direito mais limpo. Paisagem 1600×1000.
```

### O3: mídia (`onb-3-midia.png`)

```
[REGRAS COMUNS + R2]

Uma bancada com um megafone, um pequeno gráfico de barras vazio em bloco liso e uma moeda azul grande, sugerindo investimento e resultado. Uma pessoa estilizada compara dois períodos com duas réguas azuis lado a lado. Terço direito mais limpo. Paisagem 1600×1000.
```

### O4: site e jornada (`onb-4-jornada.png`)

```
[REGRAS COMUNS + R2]

Um caminho sinuoso azul-claro atravessa a cidade estilizada, passando por uma janela de navegador vazia, um formulário e um alvo; um pequeno ponto azul #175CD3 percorre o caminho. Uma pessoa estilizada observa de cima de uma passarela com uma luneta. Terço direito mais limpo. Paisagem 1600×1000.
```

### O5: relatórios (`onb-5-relatorios.png`)

```
[REGRAS COMUNS + R2]

Uma mesa com uma pilha de documentos vazios com cantos arredondados e um envelope azul sendo entregue por uma pessoa estilizada a outra, do outro lado da mesa. Um painel pequeno ao fundo mostra apenas formas abstratas. Terço direito mais limpo. Paisagem 1600×1000.
```

### O6: alertas (`onb-6-alertas.png`)

```
[REGRAS COMUNS + R2]

Um sino azul grande e arredondado pendurado sobre o painel central, com ondas suaves saindo dele. Uma pessoa estilizada recebe a notificação num celular de tela lisa e sorri, tranquila. Um único ponto vermelho pequeno junto ao sino, discreto. Terço direito mais limpo. Paisagem 1600×1000.
```

### O7: fontes de dados (`onb-7-fontes.png`)

```
[REGRAS COMUNS + R2]

Quatro conectores arredondados (plug) de formas diferentes alinhados numa régua de tomadas, cada um ligado por um cabo azul a um objeto: notebook de anúncios, janela de site, caixa de arquivos e uma pequena engrenagem de integração. Uma pessoa estilizada confere as conexões, com um ponto verde pequeno em cada tomada ativa. Terço direito mais limpo. Paisagem 1600×1000.
```

### O8: ambiente pronto (`onb-8-pronto.png`)

```
[REGRAS COMUNS + R2]

O painel central completo e aceso, com barras, uma linha e círculos abstratos em azul e azul-claro; as duas pessoas estilizadas e uma terceira comemoram com os braços para cima. Confete azul discreto. Uma pequena bandeira azul fincada na mesa. Terço direito mais limpo. Paisagem 1600×1000.
```

---

## Bloco 5: Estados vazios (3 cenas, 480×320)

### E1: nenhum cliente ainda (`empty-sem-cliente.png`)

```
[REGRAS COMUNS + R2]

Uma estante vazia com uma única pasta azul em branco encostada, e uma pessoa estilizada pequena, de braços abertos, convidando a começar. Formato 480×320, margem de 10%.
```

### E2: sem dados no período (`empty-sem-dados.png`)

```
[REGRAS COMUNS + R2]

Um painel pequeno vazio, com uma lupa azul grande sobre ele e uma ampulheta ao lado; fios tracejados soltos no ar esperando para se conectar. Formato 480×320, margem de 10%.
```

### E3: sem alertas (`empty-sem-alertas.png`)

```
[REGRAS COMUNS + R2]

Um sino azul calmo repousando sobre uma almofada, com um pequeno ponto verde ao lado e uma planta ao fundo, transmitindo tudo em ordem. Formato 480×320, margem de 10%.
```

---

## Como o código usa

| Imagem | Onde |
|---|---|
| `reports-base` | Referência de estilo (R2). Não vai para a interface |
| `conta-1` a `conta-3` | Painel esquerdo do wizard "Novo cliente e conta" em Clientes e contas |
| `gads-1` a `gads-4` | Wizard "Conectar o Google Ads" em Fontes de dados → Conexões e chaves |
| `site-1` a `site-5` | Wizard "Adicionar site, fluxo e Super Tag" em Site & Jornada |
| `onb-1` a `onb-8` | Tela nova "Conhecer o Reports", logo abaixo de Visão geral |
| `empty-*` | Estados vazios da Visão geral, de Clientes e contas e de Alertas |

## Ordem sugerida de geração

1. **P0**, 4 variações. Aprovar uma e usá-la como R2.
2. Bloco 1 (3 cenas): valida que o estilo se mantém em retrato.
3. Blocos 2 e 3 (9 cenas).
4. Bloco 4 (8 cenas).
5. Bloco 5 (3 cenas).

Se algo sair com texto, tela cheia de conteúdo ou outra cor de destaque, regenere só aquela cena com a mesma regra comum e uma linha extra: "Remova todo texto e deixe a tela lisa".
