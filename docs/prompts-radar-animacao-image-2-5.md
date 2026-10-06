# Radar: 3 cenas para a ilustração animada de espera (GPT Image 2.5)

A ilustração de espera do Radar passou a se mover como a da análise de marcas: três órbitas finas, com um ponto cada, giram em velocidades diferentes ao redor do centro, e um feixe de radar gira por cima. O que falta é a arte por trás: **3 cenas, uma para cada fase da busca**. O código troca de cena com um fade, conforme a etapa que está rodando.

| Fase da busca | Cena | Arquivo |
|---|---|---|
| Procurando o que está em alta | 1 · Buscando | `radar-anim-1-buscando.png` |
| Conferindo as fontes | 2 · Conferindo | `radar-anim-2-conferindo.png` |
| Montando os ângulos (e salvando) | 3 · Ângulos | `radar-anim-3-angulos.png` |

Enquanto os arquivos não existem, o código usa a arte atual (`radar-scan.webp`) nas três posições. Ao colocar os arquivos na pasta, a animação passa a usá-los sozinha.

## A regra que faz a animação funcionar: as 3 cenas são o MESMO quadro

O fade só parece uma animação contínua se a cidade, a antena e o enquadramento forem **idênticos** nas três imagens. Só mudam o que o mascote faz e o conteúdo dos três balões à direita. Por isso:

1. Gere a **cena 1** primeiro.
2. Gere as cenas 2 e 3 **editando a cena 1** (modo de edição, com a cena 1 anexada), pedindo para manter tudo e mudar só o que está descrito. Não gere do zero: a cidade sairia diferente.

## Âncora das órbitas (não mude)

As órbitas e o feixe são desenhados pelo código, centrados na **antena parabólica**, em **37% da largura e 43% da altura** da imagem. Mantenha o prato da antena exatamente nesse ponto nas três cenas.

**Não desenhe na imagem** anéis, ondas, órbitas, feixe de luz nem pontos orbitando: isso é do código, e o desenho duplicaria o efeito.

## Especificações

| Item | Regra |
|---|---|
| Tamanho | 1536×1024 (proporção 3:2), PNG, fundo opaco |
| Eu converto | WebP 960×640, até 120 KB |
| Pasta | `aicentralv2/static/images/planner/illustrations/` |
| Texto | Nenhum: nem letras, nem números, nem logotipos |
| Paleta | Verde-esmeralda `#1DBF73` e verde escuro, preto `#101418`, branco, verde-esmeralda muito claro `#E3F8EE`, cinzas. Nenhuma outra cor de destaque |
| Estilo | O mesmo das cenas do wizard do Radar: vetorial editorial flat, formas arredondadas, sombras só em blocos chapados |
| Mascote | Corpo preto, chevron verde-esmeralda no peito, **um único olho** com o "C". Igual em todas as cenas |

## Anexos de referência (em todas as gerações)

- **R1:** a arte atual do Radar (`radar-scan.webp`): é a referência de estilo e de composição.
- **R2:** o mascote (`mascote-planner.webp`).
- **R3:** o logo do Planner.

## Bloco comum (cole no início do prompt da cena 1)

```
Use as imagens anexas como referência. R1 define o estilo e a composição: cidade estilizada em verde-esmeralda muito claro e cinza, rio com ponte ao fundo, um prédio no primeiro plano à esquerda e uma grande antena parabólica preta com o prato verde-esmeralda. R2 é o mascote: corpo preto, chevron verde-esmeralda no peito, um único olho com a letra C, antena na cabeça. Mantenha o mascote idêntico.
Ilustração vetorial editorial em estilo flat moderno, formas geométricas arredondadas, sombras só em blocos chapados, sem gradientes complexos. Paleta fechada: verde-esmeralda (#1DBF73), verde escuro, preto (#101418), branco, verde-esmeralda muito claro (#E3F8EE) e cinzas.
Formato paisagem 1536×1024, câmera fixa, vista elevada de um telhado, enquadramento amplo.
COMPOSIÇÃO TRAVADA: o prato da antena parabólica fica com o centro a 37% da largura e 43% da altura da imagem, apontado para a direita. O mascote fica embaixo à esquerda, de pé sobre o telhado. A cidade e o rio ocupam o fundo e o lado direito. Os três balões circulares da cena ficam no terço direito da imagem, alinhados na diagonal, cada um ligado a um prédio por uma linha tracejada fina.
PROIBIDO: texto, letras, números, logotipos; qualquer onda, anel, órbita, feixe de luz ou ponto girando em volta da antena (isso é animado depois, por código); pessoas.
```

## Cena 1 · Buscando (`radar-anim-1-buscando.png`)

Gerar do zero, com o bloco comum.

```
[BLOCO COMUM]

CENA 1 · BUSCANDO. O mascote está de pé no telhado, à esquerda, com um binóculo preto nos olhos, olhando para a direita, em direção à cidade. A antena parabólica está apontada para a direita. No terço direito, três balões circulares com borda cinza fina e fundo branco, ainda vazios no sentido de "ainda procurando": dentro de cada um, um ícone cinza-claro simples, sem cor de destaque: um jornal dobrado, uma lupa e um celular. Nenhum selo verde nesta cena. Céu claro com duas nuvens pequenas.
```

## Cena 2 · Conferindo (`radar-anim-2-conferindo.png`)

Editar a cena 1. Anexar a **cena 1** e usar:

```
Edite a imagem anexada (cena 1). MANTENHA EXATAMENTE IGUAIS: a cidade, o rio, a ponte, o telhado, a antena parabólica (mesma posição e mesmo ângulo), o céu, o enquadramento e as cores. Mude somente isto:
1. O mascote não usa mais o binóculo. Agora segura, com uma das mãos, uma grande lupa de aro preto, olhando por ela para uma folha de papel branca que paira à frente dele, com linhas de texto abstratas (só barras cinza, sem letras).
2. Os três balões do terço direito agora têm borda e fundo verde-esmeralda e um pequeno selo de check branco no canto de cada um; os ícones internos (jornal, lupa, celular) ficam verde-escuro.
3. Acrescente, ao lado do terceiro balão, um quarto balão menor com o ícone de um elo de corrente (link) em verde-escuro, indicando "link aberto".
Sem texto, sem letras, sem números, sem ondas, anéis nem feixe de luz.
```

## Cena 3 · Ângulos (`radar-anim-3-angulos.png`)

Editar a cena 1 (não a cena 2, para evitar acumular erros). Anexar a **cena 1** e usar:

```
Edite a imagem anexada (cena 1). MANTENHA EXATAMENTE IGUAIS: a cidade, o rio, a ponte, o telhado, a antena parabólica (mesma posição e mesmo ângulo), o céu, o enquadramento e as cores. Mude somente isto:
1. O mascote não usa mais o binóculo. Agora está de frente para um pequeno quadro de montagem portátil sobre o telhado, onde prende quatro cartões retangulares brancos lado a lado, cada um com um pequeno ícone verde (um alvo, um balão de conversa, um calendário e uma seta subindo) e barras cinza abstratas no lugar do texto. Uma lâmpada acesa, em verde-esmeralda, paira sobre a cabeça do mascote.
2. Os três balões do terço direito viram três cartões pequenos, brancos, com borda verde-esmeralda, cada um ligado por uma linha tracejada ao quadro de montagem, como se o buzz alimentasse os ângulos. Dentro de cada cartão, um ícone verde simples: um jornal, uma lupa e um celular.
3. Um pequeno brilho de quatro pontas (estrela) em verde-esmeralda no céu, à direita.
Sem texto, sem letras, sem números, sem ondas, anéis nem feixe de luz.
```

## Conferência antes de me enviar

| Item | Como conferir |
|---|---|
| Mesmo quadro | Sobreponha as 3 imagens: a cidade, o rio e o prato da antena devem coincidir |
| Antena na âncora | O centro do prato está a 37% da largura e 43% da altura |
| Sem efeitos pintados | Nenhum anel, onda, feixe ou órbita desenhado em volta da antena |
| Sem texto | Nenhuma letra ou número, nem nos cartões nem nos balões |
| Mascote | Um único olho, corpo preto, chevron verde, igual nas 3 cenas |
| Paleta | Só verde-esmeralda, verde escuro, preto, branco e cinzas |

Se a antena sair um pouco fora da âncora em alguma cena, não precisa refazer: dá para ajustar o ponto das órbitas por cena. O que não dá para corrigir no código é uma cidade diferente entre as cenas.

## Como o código usa

| Elemento | Onde |
|---|---|
| As 3 cenas com fade, trocadas pela etapa em execução | `frontend/planner/RadarAnimation.jsx` |
| Órbitas, feixe e pulso (CSS) | `frontend/planner/planner.css`, seção "Animação de espera do Radar" |
| Quando aparece | Cabeçalho da busca em andamento e o fluxo "Completar o perfil da marca" |
| Movimento reduzido | Sistemas com "reduzir movimento" veem só a cena, parada, sem órbitas nem feixe |
