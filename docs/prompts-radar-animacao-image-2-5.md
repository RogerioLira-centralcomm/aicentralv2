# Radar: 3 cenas para a ilustração animada de espera (GPT Image 2.5)

A espera do Radar é um **quadrado padronizado no meio da tela**, como a marca no centro da análise de marcas: o mascote do Planner num disco claro, com três órbitas finas girando em volta. O disco e as órbitas são desenhados pelo código. Falta só a arte do mascote: **3 cenas quadradas, uma por fase da busca**, cada uma com um objeto diferente na mão.

| Fase da busca | Cena | Objeto na mão | Arquivo |
|---|---|---|---|
| Procurando o que está em alta | 1 · Buscando | Binóculo | `radar-anim-1-buscando.png` |
| Conferindo as fontes | 2 · Conferindo | Lupa, com um cartão e um check | `radar-anim-2-conferindo.png` |
| Montando os ângulos | 3 · Ângulos | Três cartões em leque, com uma lâmpada | `radar-anim-3-angulos.png` |

O plano anterior (cidade inteira, antena, balões) era complicado demais para o gerador e foi descartado. Aqui é só o mascote, no centro, sem cenário.

## Regras (poucas e fixas)

| Item | Regra |
|---|---|
| Formato | **Quadrado 1024×1024**, PNG |
| Fundo | **Transparente**. Se a ferramenta não entregar transparência, peça fundo branco puro (`#FFFFFF`) e eu removo |
| Mascote | **O mesmo da referência**, de corpo inteiro, **no centro**, ocupando cerca de **60% da largura**, com margem livre em volta |
| Mesma posição nas 3 | Mascote no mesmo lugar e do mesmo tamanho em todas. **Só o objeto na mão muda.** É isso que faz a troca parecer movimento |
| Cenário | Nenhum: sem chão, sem cidade, sem outros elementos. Só uma sombra suave embaixo do mascote |
| Texto | Nenhum: nem letras, nem números, nem logotipos |
| Estilo | O da referência: 3D macio, corpo preto, olho único, mãos verdes, chevron no peito. Cores de destaque só o verde-esmeralda |

## Como gerar (3 passos, sempre por edição)

Anexe o mascote oficial (`aicentralv2/static/images/planner/illustrations/mascote-planner.webp`) como referência. Não peça do zero: o mascote sairia diferente.

1. **Cena 1:** edite o mascote oficial (prompt abaixo).
2. **Cena 2:** edite a **cena 1**.
3. **Cena 3:** edite a **cena 1** (não a cena 2, para não acumular erros).

### Cena 1 · Buscando

Anexar: o mascote oficial.

```
Edite a imagem anexada, que é o mascote do Planner. Entregue uma imagem QUADRADA de 1024×1024 com FUNDO TRANSPARENTE.
Coloque o mascote no centro, de corpo inteiro e IDÊNTICO ao original: mesmo corpo preto, mesmo olho único verde, mesmas mãos verdes, mesmo chevron no peito, mesmo estilo 3D macio. Ele ocupa cerca de 60% da largura da imagem, com margem livre em volta.
Troque o megafone da mão direita por um binóculo preto com lentes verde-esmeralda, levantado à frente do olho, como quem procura algo ao longe.
Sem cenário, sem chão, sem texto, sem outros objetos. Apenas uma sombra suave embaixo do mascote.
```

### Cena 2 · Conferindo

Anexar: a cena 1.

```
Edite a imagem anexada. Mantenha EXATAMENTE igual o mascote, a posição, o tamanho, o enquadramento e o fundo transparente. Mude somente o objeto:
troque o binóculo por uma lupa grande de aro preto e lente com um brilho verde-esmeralda, segurada na mesma mão. À direita do mascote, flutuando, um cartão branco pequeno com três barras cinza (sem letras) e um selo de check verde-esmeralda grande no canto.
Mais nada. Sem cenário, sem texto.
```

### Cena 3 · Ângulos

Anexar: a cena 1.

```
Edite a imagem anexada. Mantenha EXATAMENTE igual o mascote, a posição, o tamanho, o enquadramento e o fundo transparente. Mude somente o objeto:
troque o binóculo por três cartões brancos pequenos abertos em leque, segurados na mesma mão, cada um com um ícone verde-esmeralda simples (um alvo, um balão de conversa e uma seta subindo) e sem texto. Acima da cabeça do mascote, uma lâmpada pequena acesa, em verde-esmeralda.
Mais nada. Sem cenário, sem texto.
```

## Conferência antes de me enviar

| Item | Como conferir |
|---|---|
| Mesmo lugar | Sobreponha as 3 imagens: o corpo do mascote deve coincidir |
| Quadrado | 1024×1024, mascote no centro, sem cortar mão nem objeto |
| Fundo | Transparente (ou branco puro) |
| Sem extras | Sem chão, cenário, texto, letras ou números |
| Mascote | Um único olho, corpo preto, mãos e chevron verdes, igual nas 3 |

## Entrega e como o código usa

Salve os 3 PNG em `aicentralv2/static/images/planner/illustrations/`. Eu converto para WebP 512×512 com transparência, até 60 KB cada.

| Elemento | Onde |
|---|---|
| Mascote no quadrado, com fade entre as cenas conforme a etapa em execução | `frontend/planner/RadarAnimation.jsx` |
| Disco e três órbitas girando (8, 10 e 12 s, uma no sentido contrário) | `frontend/planner/planner.css`, seção "Animação de espera do Radar" |
| Quando aparece | No meio da tela durante a busca, e no fluxo "Completar o perfil da marca" |
| Terminada a busca | Vira um selo pequeno ao lado do resumo, parado |
| Movimento reduzido | Sistemas com "reduzir movimento" veem só o mascote, parado, sem órbitas |
| Sem os arquivos novos | O próprio mascote do Planner ocupa o quadrado. Já funciona assim hoje |
