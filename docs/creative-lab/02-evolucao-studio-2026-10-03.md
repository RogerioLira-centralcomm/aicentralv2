# Evolução do Studio e do Lab — 3 e 4 de outubro de 2026

Registro do que mudou na geração de imagens do Cadu Studio, do que foi medido no Creative Lab e do que foi
descartado. **Regra da casa:** toda mudança no fluxo de geração passa primeiro por A/B no Lab (mesmos cenários,
`scripts/lab_ab.py`) e só vai ao Studio com ganho medido.

## Fluxo atual de uma peça

1. **Diretor** (Haiku 4.5 via OpenRouter; GPT-5 nano e gpt-4o-mini de reserva) — escreve a direção e **edita a cópia
   pelo tamanho** (`studio_playbook.copy_budget`): só corta palavras do pedido; oferta, número, preço e cupom nunca
   saem; a marca sai primeiro porque o logo a identifica. Se passar do orçamento, uma revisão curta (Haiku) encaixa.
   Quando o Studio aplica o texto, o diretor descreve só a imagem.
2. **Uma chamada ao modelo de imagem** (GPT Image 2 / 2.5) com prompt enxuto: layout (máscara, quando houver), cena,
   ofício de anúncio (um foco, área do texto calma, luz comercial, cor da marca na cena, telas abstratas), margem,
   formato. Peça com texto por código não recebe regras de texto e a cena perde as frases que citam a cópia.
3. **Composição por código** nos formatos display (todos os IAB e de portal): layout escolhido **depois** da cena
   (texto onde a imagem está calma; layouts espelhados quando o modelo inverte os lados; painel que cobriria o sujeito
   é trocado), painel reto e rente às bordas na cor da marca (não pinta onde o fundo já é liso), **oferta como herói**
   na cor de destaque, chamada em caixa alta, apoio só se couber com 9 px ou mais, CTA que nunca é cortado, logo
   oficial por último.
4. **Revisor** — olho rápido (Haiku, relatório curto ~3 s) + TypeSafe julgando (~0,3 s). Rejeita: texto errado, logo
   redesenhado, corte, identidade alterada, referência ignorada, margem (só do que o modelo desenha), números que o
   pedido não tem, texto pintado pelo modelo numa peça com texto por código. Correção por **edição** da última versão,
   ciente de paleta, logo e CTA da peça; entrega a de maior nota. Studio: até 3 versões só quando rejeita. Lab: até 5,
   buscando nota 90.
5. **Variações 2+** editam a primeira peça pronta (mesma campanha, outra tomada).

## Medições (Lab, GPT Image 2.5, mesmos cenários v3 com referências reais)

| Etapa | Nota média | Aprovadas de 1ª | Custo/peça |
|---|---|---|---|
| Uma chamada, prompts antigos | 67,7 | 1/6 | US$ 0,042 |
| Rascunho baixo + acabamento | 67,0 | 2/6 | US$ 0,085 |
| Uma chamada, prompt enxuto + layout pela cena + revisor de números | 71,8 | 4/6 | US$ 0,041 |
| Idem, simulando o Studio (até 3 versões) | 78,3 | — | ~US$ 0,045 |
| Texto por código também em feeds e stories (11 cenários, pares completos) | +9,8 nos sociais | — | — |

Ruído: a mesma peça varia ±10 pontos entre rodadas; decisões só com vários cenários e, de preferência, mais de uma
rodada.

## Descartado (e por quê)

- **Rascunho em qualidade baixa + acabamento por edição** (`CREATIVE_STUDIO_TWO_PASS`, desligado): mesma nota pelo
  dobro do custo. O acabamento preserva o rascunho, e o custo vem das imagens de entrada (referências), não da
  qualidade de saída.
- **Detectar texto do modelo pela posição** das caixas do olho: falso positivo em 2 de 6 peças limpas; as caixas
  estimadas pelo LLM são imprecisas (o mesmo vale para a margem de elementos desenhados por código, que não é mais
  medida).
- **Qwen Image 3 Pro e Recraft V4.1** fora do recorte do Lab (lentos ou nota baixa; ilustração raramente é pedida).
- **Métrica antiga de paleta** (área total da imagem): punia fotos boas; trocada por presença da cor da marca (ΔE Lab).

## Chaves

| Variável | Padrão | Efeito |
|---|---|---|
| `CREATIVE_STUDIO_DISPLAY_TYPESET` | 1 | Texto por código nos formatos display |
| `CREATIVE_STUDIO_SOCIAL_TYPESET` | 0 | Texto por código em feed, story e LinkedIn (aguardando A/B com o compositor novo) |
| `CREATIVE_STUDIO_TWO_PASS` | 0 | Rascunho + acabamento (descartado) |
| `CREATIVE_STUDIO_DIRECTOR_MODEL` | anthropic/claude-haiku-4.5 | Diretor |
| `CREATIVE_REVIEW_MODEL` | anthropic/claude-haiku-4.5 | Olho do revisor (Studio e Lab) |
| `STUDIO_AUTO_REVIEW_MAX_ATTEMPTS` | 3 | Versões no Studio enquanto o revisor rejeita |

## Como medir uma mudança

```bash
.venv/bin/python scripts/lab_ab.py --runs 240,238,236,234,232,230,228,226,220,218,216 \
    --arm 'A={"typeset_social": false}' --arm 'B={"typeset_social": true}' --attempts 3 --workers 2
```

Cada lado é um conjunto de atributos do `LabModeling`. Nada é gravado no banco; as imagens ficam em `output/lab-ab`.
Rodar em segundo plano (11 cenários × 2 lados levam ~20 min; o limite da OpenAI derruba execuções com muitos
paralelos).

## Formatos e referências

41 formatos no catálogo (todos os IAB, a partir de 16 px), 233 referências de composição (conjuntos por forma:
quadrado 11, vertical 9, horizontal 10, compactos 5, micro 5). Logo sempre inteiro e com respiro; painéis contêm
título e CTA.

## Pendências

- Ligar `CREATIVE_STUDIO_SOCIAL_TYPESET` depois do A/B com o compositor novo.
- Fonte de título pesada (Anton, Montserrat Black — licença OFL) precisa de autorização para baixar.
- 2 candidatas em paralelo com escolha pelo revisor: medir no Lab (estimativa +2 pontos, custo dobra, tempo não).
