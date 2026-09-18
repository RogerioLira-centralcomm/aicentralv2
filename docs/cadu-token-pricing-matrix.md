# CADU · matriz de custos, margem e cobrança

Documento-base para revisar os planos comerciais e os valores mostrados nos e-mails.

## Regra central

O Cadu deve separar quatro números:

1. **Custo técnico real**: custo informado pelo provedor, em USD, mais mídia/serviços externos.
2. **Margem operacional**: calculada sobre o preço comercial dos créditos vendidos, depois de impostos e custos fixos; não é aplicada como multiplicador oculto no débito.
3. **Tokens cobrados**: unidade comercial consumida pelo cliente.
4. **Preço do plano**: preço mensal dividido pelo limite mensal de tokens do plano ativo.

Fórmula:

```text
custo técnico BRL = (custo técnico USD × câmbio registrado) + custos externos BRL
tokens técnicos = tokens de entrada + tokens de saída
tokens cobrados = tokens técnicos arredondados + equivalentes de custos externos, quando houver
preço unitário do plano = preço mensal do plano ÷ tokens mensais do plano
valor de referência = tokens cobrados × preço unitário do plano
margem bruta estimada = (valor de referência − custo técnico BRL) ÷ valor de referência
```

O e-mail deve exibir o valor de referência e o equivalente profissional somente quando houver dados suficientes. Nunca usar um valor fixo de fallback como preço comercial.

## Matriz inicial revisada

| Produto / agente | Atividade | Custo técnico usado | Margem operacional inicial | Cobrança recomendada | Equivalente humano |
|---|---|---:|---:|---:|---|
| Workspace | Conversa, síntese ou decisão curta | tokens reais do provedor | 4× | tokens reais × 4 | sem equivalente direto ou minutos estimados |
| Workspace | Importação e indexação de fonte | tokens processados + armazenamento | 1,2× | tokens processados × 1,2 | leitura/indexação assistida; não converter em horas automaticamente |
| Workspace | Análise de marca — imagem | custo real do provedor + Firecrawl quando usado | 4× | consumo medido, com teto informado antes da execução | análise estratégica/visual; usar faixa de horas, não número absoluto |
| Workspace | Revisão de módulo da marca | tokens reais do provedor | 4× | consumo medido | revisão de direção e identidade |
| Planner | Briefing e plano de mídia | tokens reais do agente | 4× | estimativa antes da execução e acerto após o uso | horas de planejamento, com faixa por profundidade |
| Planner | Revisão e melhoria do plano | tokens reais do agente | 4× | consumo incremental | horas de revisão estratégica |
| Planner | Documento derivado do plano | tokens reais do agente | 4× | consumo incremental | horas de redação/estruturação |
| Studio | Direção textual para peça | tokens reais do provedor | 4× | consumo medido | minutos de direção/criação |
| Studio | Imagem — geração/variação | custo real do provedor de imagem | 6× | tokens de mídia + tokens de execução | horas de direção e produção |
| Studio | Vídeo | custo real de vídeo + TTS, quando houver | 6× | tokens de mídia + tokens de execução | dias de produção, conforme duração e formatos |
| Studio | Edição, conversão ou handoff | custo técnico real, se houver | 2× | consumo incremental | minutos/horas estimados pelo escopo |
| Reports | Leitura de campanha e consolidação | tokens reais + custo de conectores | 4× | consumo medido | sem equivalente direto quando houver muitas fontes |
| Connect | Importação, sincronização e relatório | tokens reais + custo do conector | 4× | consumo medido por operação | operação analítica; não prometer horas equivalentes |
| Skills | Execução de skill textual | tokens reais do agente | 4× | consumo medido | tempo do especialista somente quando configurado |
| Projects | Organização, fontes e contexto | tokens de indexação + armazenamento | 1,2× | tokens processados | trabalho de organização, sem equivalência fixa |

## Por que a tabela muda

- Os multiplicadores comerciais antigos (8×/12×) foram removidos do débito dos clientes.
- A margem passa a ser analisada sobre o preço dos pacotes e planos, preservando a métrica real de entrada/saída.
- Mídia visual e vídeo permanecem mais caros porque têm custo externo variável e maior risco de repetição.
- O preço em reais deve ser calculado pelo plano comercial ativo, não por `R$ 8,00` fixos por crédito.
- A margem deve ser medida por atividade e mês, usando consumo real, e não presumida apenas pelo limite do plano.

## Parâmetros que devem substituir os legados

```text
CADU_TEXT_MARGIN_MULTIPLIER=4
CADU_RAG_TOKEN_MARGIN=1.2
CADU_MEDIA_MARGIN_MULTIPLIER=6
CADU_CONNECT_MARGIN_MULTIPLIER=4
CADU_ANALYZER_IMAGE_MARGIN_MULTIPLIER=4
CADU_ANALYZER_VIDEO_MARGIN_MULTIPLIER=6
```

Os valores acima são uma matriz inicial para o teste. Antes de publicar planos, comparar por pelo menos 30 dias:

- custo médio real por atividade;
- p95 de tokens e retries;
- margem bruta por agente;
- atividades deficitárias;
- consumo médio por organização;
- quantidade de usuários e suporte envolvido.

## Exemplo de leitura para e-mail

```text
Consumo: 18.400 tokens
Preço de referência: preço mensal do plano ÷ tokens mensais
Valor de referência: 18.400 × preço unitário do plano
Custo técnico interno: registrado após a execução
Equivalente profissional: faixa estimada, quando aplicável
```

O e-mail não deve chamar custo interno de “economia” nem apresentar margem como desconto para o cliente.

## Simulação dos casos reais

Premissas usadas nesta rodada: câmbio de teste de R$ 5,50/USD, GPT Image 2 publicável a US$ 0,22 por chamada, vídeo Seedance em 720p 16:9 a 24 fps, tarifa de US$ 0,0000107 por token técnico e sem multiplicador comercial no débito.

### Imagem e edição

| Caso | Chamadas estimadas | Custo técnico | Tokens técnicos medidos |
|---|---:|---:|---:|
| Imagem grande + 4 refações | 5 | US$ 1,10 · R$ 6,05 | 880.000 |
| Edição com 2 referências + 5 refações | 6 | US$ 1,32 · R$ 7,26 | 1.056.000 |

As duas referências entram como contexto da chamada; não foram cobradas como duas gerações adicionais. Se o provedor cobrar processamento de imagem de entrada separadamente, esse componente deve ser somado ao custo real antes do fechamento.

### Vídeo por duração e número de cenas

| Duração | 4 cenas · custo técnico | 4 cenas · tokens técnicos | 30 cenas · custo técnico | 30 cenas · tokens técnicos |
|---:|---:|---:|---:|---:|
| 5 s | R$ 6,36 | 1.848.960 | R$ 6,36 | 1.848.960 |
| 10 s | R$ 12,71 | 3.697.920 | R$ 12,71 | 3.697.920 |
| 15 s | R$ 19,08 | 5.546.880 | R$ 19,08 | 5.546.880 |
| 20 s | R$ 25,42 | 7.395.840 | R$ 25,42 | 7.395.840 |

Os valores de 30 cenas são uma simulação conservadora em que cada cena vira uma geração completa. Para o produto, devemos separar:

- **cena de storyboard**: ainda não é um vídeo gerado e deve ter cobrança muito menor;
- **cena gerada**: cada cena efetivamente chama o modelo de vídeo;
- **montagem final**: edição, transição, áudio, locução e transcodificação.

Sem essa separação, o plano fica artificialmente caro e o cliente paga storyboard como se fosse produção final.

## Análise de marca — reconstrução da última execução

A última execução registrada no fluxo do Workspace não é uma única chamada. O fluxo completo faz:

1. leitura textual da marca pelo site;
2. leitura visual, quando há logo/captura/imagem disponível;
3. três pareceres: evidências, estratégia e direção criativa;
4. Firecrawl para a página analisada;
5. opcionalmente busca de ativos e pesquisa de mercado.

### Cenário completo observado no código

| Etapa | Quantidade | Unidade Firecrawl | Regra de custo |
|---|---:|---:|---:|
| Leitura textual | 1 | — | custo real do provedor |
| Leitura visual | 1 | — | custo real do provedor visual |
| Parecer de evidências | 1 | — | custo real do provedor |
| Parecer de estratégia | 1 | — | custo real do provedor |
| Parecer de direção criativa | 1 | — | custo real do provedor |
| Scrape do site | 1 ou mais páginas | 1 por página | US$ 0,0025 por crédito Firecrawl |
| Busca de ativos | opcional | 2 créditos para até 10 resultados | US$ 0,0025 por crédito |
| Pesquisa de mercado | opcional | 2 créditos para até 10 resultados | US$ 0,0025 por crédito |

No cenário completo mais provável — uma página, busca de ativos e pesquisa de mercado — o Firecrawl representa 5 créditos de provedor, ou US$ 0,0125 antes da margem. O restante depende do uso real de tokens retornado pelos cinco chamados de modelo.

### Estimativa operacional antes do acerto

Como o último registro detalhado de uso não está disponível nesta execução local, a faixa de planejamento deve ser:

| Cenário | Tokens de modelo estimados | Firecrawl convertido | Faixa operacional inicial |
|---|---:|---:|---:|
| Site sem imagem e sem pesquisas extras | 4.000–8.000 | 400–800 tokens | 4.400–8.800 tokens |
| Site + leitura visual + ativos | 6.000–12.000 | 1.200–2.000 tokens | 7.200–14.000 tokens |
| Auditoria completa com mercado e 3 pareceres | 10.000–20.000 | 2.000–3.000 tokens | 12.000–23.000 tokens |

Esses números são teto de planejamento, não preço final. O valor correto para o e-mail deve vir da soma de `tokens_cobrados` das cinco chamadas e das linhas Firecrawl idempotentes do `job_id`.

### Recomendação comercial

- Auditoria simples: faixa de 5 mil a 9 mil tokens.
- Auditoria completa: faixa de 12 mil a 23 mil tokens.
- Revisão de um módulo aprovado: cobrar somente o novo parecer, não repetir a auditoria inteira.
- Reprocessamento após falha: reutilizar evidências já pagas e cobrar apenas etapas novas.
- O e-mail deve mostrar “consumo desta análise” e não “preço fixo da análise”.

## Custo técnico mensal por cenário

Esta simulação usa **4 clientes e 1 campanha por cliente/mês**. O custo abaixo é antes de margem e antes de preço comercial do plano.

### Premissas de volume

| Atividade | Volume por cliente/mês | Premissa de custo técnico |
|---|---:|---:|
| Análise completa de marca | 1 | 17.500 tokens de modelo + Firecrawl completo |
| Projeto e organização inicial | 1 | 3.000 tokens + 1 scrape Firecrawl |
| Conversas de trabalho | 12 | 2.000 tokens por conversa |
| Imagem grande | 1 fluxo | 1 imagem final + 4 refações = 5 chamadas GPT Image 2 publicável |
| Edição com referências | 1 fluxo | 2 referências + 5 refações = 6 chamadas GPT Image 2 publicável |
| Vídeo | 1 fluxo | 10 segundos, 4 cenas, 720p, sem locução |

Premissas financeiras: US$ 1 = R$ 5,50; custo de texto de referência = US$ 0,00001 por token; GPT Image 2 publicável = US$ 0,22 por chamada; vídeo Seedance = tarifa atual de 720p/16:9/24 fps; Firecrawl = US$ 0,0025 por crédito.

### Custo real por cliente e por atividade

| Atividade | Custo modelo/provedor | Firecrawl | Custo técnico total |
|---|---:|---:|---:|
| Análise completa de marca | R$ 0,96 | R$ 0,07 | **R$ 1,03** |
| Projeto e organização inicial | R$ 0,17 | R$ 0,01 | **R$ 0,18** |
| 12 conversas | R$ 1,32 | R$ 0,00 | **R$ 1,32** |
| Imagem grande + 4 refações | R$ 6,05 | R$ 0,00 | **R$ 6,05** |
| Edição + 2 referências + 5 refações | R$ 7,26 | R$ 0,00 | **R$ 7,26** |
| Vídeo de 10 s + 4 cenas | R$ 12,71 | R$ 0,00 | **R$ 12,71** |
| **Total por cliente/campanha** | **R$ 28,47** | **R$ 0,08** | **R$ 28,55** |

### Cenário A — 1 pessoa, 4 clientes, 1 campanha por cliente

| Atividade mensal | Quantidade | Custo técnico unitário | Total mensal |
|---|---:|---:|---:|
| Análises de marca | 4 | R$ 1,03 | R$ 4,12 |
| Projetos/contextos | 4 | R$ 0,18 | R$ 0,72 |
| Conversas | 48 | R$ 0,11 | R$ 5,28 |
| Imagens grandes | 4 | R$ 6,05 | R$ 24,20 |
| Edições com referências | 4 | R$ 7,26 | R$ 29,04 |
| Vídeos de 10 s / 4 cenas | 4 | R$ 12,71 | R$ 50,84 |
| **Custo técnico mensal antes da margem** | — | — | **R$ 114,20** |

O custo médio técnico por cliente é **R$ 28,55**. A pessoa concentra a operação, mas o número de usuários não multiplica o custo enquanto o volume de atividades permanecer igual.

### Cenário B — 3 pessoas, 4 clientes, 1 campanha por cliente

| Atividade mensal | Quantidade total | Divisão média por pessoa | Custo técnico mensal |
|---|---:|---:|---:|
| Análises de marca | 4 | 1,33 | R$ 4,12 |
| Projetos/contextos | 4 | 1,33 | R$ 0,72 |
| Conversas | 48 | 16 | R$ 5,28 |
| Imagens grandes | 4 | 1,33 | R$ 24,20 |
| Edições com referências | 4 | 1,33 | R$ 29,04 |
| Vídeos de 10 s / 4 cenas | 4 | 1,33 | R$ 203,40 |
| **Custo técnico mensal antes da margem** | **68 execuções principais** | — | **R$ 114,20** |

O custo técnico continua **R$ 114,20/mês** porque a produção é a mesma. O cenário com três pessoas só aumenta custo de equipe, permissões, suporte ou consumo adicional se esses itens forem realmente utilizados.

### Sensibilidade do vídeo

| Vídeo por cliente | Custo técnico unitário | Total para 4 clientes |
|---|---:|---:|
| 5 s · 4 cenas | R$ 6,36 | R$ 25,44 |
| 10 s · 4 cenas | R$ 12,71 | R$ 50,84 |
| 15 s · 4 cenas | R$ 19,08 | R$ 76,32 |
| 20 s · 4 cenas | R$ 25,42 | R$ 101,68 |
| 10 s · 30 cenas | R$ 12,71 | R$ 50,84 |

Os valores de vídeo são o maior fator de custo. Antes de precificar planos, devemos validar se as quatro ou trinta cenas são gerações completas ou apenas quadros de storyboard.

## Reports — processamento atual e preço sugerido

O fluxo atual do Reports tem duas fases:

- upload/importação da fonte: não consome créditos;
- ação **Sugerir métricas**: envia uma imagem para `openai/gpt-5-nano`, com teto de 3.200 tokens por fonte, reserva o teto técnico de 3.200 tokens e liquida o uso real medido, sem multiplicador comercial.

Com a mesma base de custo usada nesta simulação:

| Operação | Custo técnico antes da margem | Margem atual no código | Preço implícito atual | Margem revisada | Preço sugerido |
|---|---:|---:|---:|---:|---:|
| Importar fonte | R$ 0,00 | — | R$ 0,00 | — | R$ 0,00 |
| Sugerir métricas · 1 fonte | R$ 0,18 | tokens medidos | custo técnico medido | 4× comercial | R$ 0,70 |

O preço sugerido não precisa ser cobrado individualmente: pode ser absorvido pelo plano mensal. O limite de 3.200 tokens é um teto de reserva, não necessariamente o consumo real; o e-mail e o extrato devem mostrar o valor liquidado.
