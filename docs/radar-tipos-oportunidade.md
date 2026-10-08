# Radar: três tipos de oportunidade (mídia, conteúdo, inteligência)

Plano de 2026-10-08. Responde à pergunta "como uma notícia vira plano de mídia?": nem toda vira. O Radar passa a dizer **o que cada ângulo permite fazer** e leva cada um ao destino certo.

## Decisões (do usuário, 2026-10-08)

- Três tipos: **mídia**, **conteúdo**, **inteligência**.
- **Datas** (sazonalidade, calendário) ficam em **inteligência**.
- **Eventos** dependem do evento: o modelo decide caso a caso (mídia, se há audiência/espaço a comprar; conteúdo, se há assunto; inteligência, se é só para saber).
- **Conteúdo** tem duas saídas: **salvar como pauta** ou **enviar o pedido pronto ao Cadu Chat**. Se o radar tem projeto (ou marca), o chat abre com esse projeto.
- O Radar **não gera conteúdo**; prepara o pedido.

## Os tipos

| Tipo | Quando | Campos que o modelo preenche | Ação |
|---|---|---|---|
| **Mídia** | Momento, público ou praça em que vale comprar espaço | objetivo (awareness, consideração, leads, vendas, tráfego), público, praças, período (janela em datas), mensagem-chave, **canais e formatos escolhidos do catálogo do Planner** com o motivo de cada um | **Criar planejamento**: plano com objetivo, período, geografia, itens do catálogo para revisar e briefing (tese, por que agora, fontes) |
| **Conteúdo** | Há assunto para a marca falar, sem necessariamente comprar mídia | tema, tese, mensagem, formatos (texto livre: artigo, carrossel, vídeo curto…), tom, fontes | **Salvar pauta** ou **Criar no Cadu Chat** (pedido montado, com projeto/marca do radar) |
| **Inteligência** | Serve para decidir: concorrência, regulação, preço, datas | o que aconteceu, impacto para a marca, o que observar, prazo | **Levar ao briefing de um plano** (novo ou existente) ou só acompanhar |

Concorrência é, em regra, inteligência. O modelo só marca como mídia quando há ação clara (defesa de marca, busca pelo nome do concorrente) e diz o porquê.

## O que muda

### 1. Pipeline (etapa `angles`)
- Prompt novo (V1.6): classificar cada ângulo em `tipo` e preencher só os campos do tipo.
- Para mídia, o prompt recebe a **lista de canais e formatos do catálogo** (id e nome) e só pode escolher dentre eles. A validação descarta ids que não existem.
- Gravação: `score_breakdown` ganha `type`, `objective`, `audience`, `places`, `period` (início/fim), `message`, `media` (`[{kind, id, name, why}]`), `content` (`{theme, formats, tone}`) e `impact`/`watch` (inteligência). Sem migração: é JSONB.
- **Medir no Lab antes** (regra da casa): A/B entre V1.5 e V1.6 em 4–6 temas reais (um de concorrência, um de data, um de evento). Critérios: classificação faz sentido, mídia sugerida existe no catálogo e combina com o tema, custo de tokens.

### 2. Tela do radar
- Ângulos agrupados: **Oportunidades de mídia**, **Pautas de conteúdo**, **Para saber**.
- Card de mídia: "Objetivo · Público · Praça · Período", mídia sugerida (chips com link para o catálogo), "Criar planejamento".
- Card de conteúdo: tema, tese, formatos, "Salvar pauta" e "Criar no Cadu Chat".
- Card de inteligência: o que aconteceu, impacto, o que observar, "Levar ao briefing".
- Execuções antigas (V1.5, sem `type`) continuam aparecendo como hoje, sem agrupamento.

### 3. Criar planejamento (mídia)
- `create_plan` passa a preencher objetivo, período e geografia do ângulo.
- Os canais/formatos sugeridos entram como **itens do plano** (`kind` + `resource_id`), marcados como sugestão do Radar para revisar.
- Briefing: tese, por que agora, notícias com link.

### 4. Pautas e Cadu Chat (conteúdo)
- **Salvar pauta**: usa o status `salva` que já existe em `cadu_radar_opportunities`. Lista de pautas: filtro "Pautas salvas" na vitrine e seção no radar.
- **Criar no Cadu Chat**: o link leva **só a referência** do ângulo: `?radar_angle=<id>&project_ref=…&brand_ref=…`. O prompt **não** vai na URL: é longo, e Planner e chat estão em subdomínios diferentes (`sessionStorage` não atravessa; a sessão do Flask é cookie de ~4 KB).
  - O backend do chat lê o ângulo (conferindo o cliente), monta o pedido (tema, tese, mensagem, formatos, tom, fontes com link) e o front envia sozinho, como já faz com `auto_send`.
  - Sem projeto, abre com a marca; sem nenhum, em contexto livre.
  - Se um dia for preciso mandar algo que não está gravado (ex.: vários sinais escolhidos), usar um handoff temporário no servidor (linha com validade, URL com token).

### 5. Inteligência
- **Levar ao briefing**: escolher um plano (ou criar um) e acrescentar ao briefing um bloco "Contexto do Radar" (o que aconteceu, impacto, fonte). Precisa de um endpoint que anexe ao briefing sem sobrescrever.

### 6. Vitrine
- O card do radar resume por tipo: "2 mídia · 1 pauta · 1 para saber".

## Ordem

1. Prompt V1.6 + validação contra o catálogo, rodando **só no Lab**; medir e trazer o resultado.
2. Com o resultado aprovado: gravação dos campos, tela agrupada, ações de conteúdo (pauta e chat).
3. Criar planejamento preenchido (objetivo, período, itens do catálogo).
4. Inteligência no briefing de um plano existente.
5. Resumo por tipo na vitrine.

## Riscos

- O catálogo é grande: mandar só os canais/formatos ativos e relevantes (filtrar por categoria antes) para não estourar tokens.
- Classificação errada (tudo vira "mídia"): o Lab mede isso; o prompt pede justificar o tipo.
- Itens do plano sugeridos podem parecer decisão já tomada: marcar como sugestão e exigir revisão.
