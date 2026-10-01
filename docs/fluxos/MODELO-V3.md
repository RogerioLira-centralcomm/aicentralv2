# Fluxos v3 — Da dinâmica da campanha ao monitoramento

Este documento redefine o produto e o modelo de dados. Complementa o [PLANO-V2.md](PLANO-V2.md), que trata da mesa e da entrada, e o [CONTRACT.md](CONTRACT.md), que descreve o contrato atual (v2). Referências visuais: Funnelytics (editor e modo monitor).

## 0. Escopo e posicionamento

- O Fluxos continua **dentro do Reports**. Usa o que o Reports já tem: clientes, anunciantes, campanhas, importações, papéis de acesso (incluindo `viewer`) e a Super Tag.
- **Não há modelo comercial** nesta fase: nada de planos, cobranças, limites por pacote ou páginas de venda. O foco é a ferramenta e as funcionalidades para quem trabalha com campanhas.
- As imagens do Funnelytics são só referência de vocabulário e de leitura. O que vale é o problema do usuário.

## 1. Essência

> **Desenhar como uma campanha funciona (de onde vem o tráfego, por onde passa, o que conta como sucesso) e, no mesmo quadro, acompanhar o que realmente acontece.**

Hoje o Fluxos responde “quais páginas do site existem”. A ferramenta premium responde “como esta campanha deveria funcionar e como está funcionando”. Planejar e medir são o mesmo objeto: o desenho é o plano, e o monitor é o desenho com números.

## 2. Para quem e para quê

| Pessoa | Trabalho a fazer | O que a ferramenta precisa entregar |
|---|---|---|
| Planejador de mídia | Montar a jornada de uma campanha: canais, criativos, páginas de destino, follow-ups. | Começar de um objetivo ou de uma campanha, não de um mapa de páginas. Gerar os links com UTM de cada origem. |
| Analista | Saber se a campanha funciona e onde perde gente. | Números sobre o desenho: volume e taxa em cada conexão, saídas, comparação com o período anterior e com a meta. |
| Atendimento / cliente | Entender e aprovar o plano, acompanhar resultado. | Visão limpa para leitura, link de compartilhamento somente leitura, exportação. |

## 3. Diagnóstico do modelo atual

Verificado em `reports_flow.py`, `flowBlockRegistry.js` e `CONTRACT.md`.

| # | Problema | Consequência |
|---|---|---|
| D1 | `stage` (`entry`, `exploration`, `intent`…) é gravado por página, por heurística, ao importar do “Explorar site”. | A mesma página não pode ser entrada para um canal e exploração para outro. As faixas ENTRADA/INTENÇÃO/EXPLORAÇÃO descrevem páginas, não a jornada. |
| D2 | Origem é só uma plataforma (`source: 'meta'`), sem regra de atribuição. | Não separa “Meta · campanha X” de “Meta orgânico” nem dois e-mails diferentes. |
| D3 | Entrada (`isEntry`) e conversão (nó `conversion` com `path`) são marcas em páginas. | Meta não é um conceito do fluxo; não há valor, janela nem mais de uma meta. |
| D4 | A conexão do editor tem só `label: 'Próximo'` e `variant`. | A métrica existe apenas no endpoint de jornada, longe do desenho. |
| D5 | Um nó por página, com limite de 200 nós. | Um site com 499 páginas em 17 grupos não cabe. |
| D6 | O fluxo nasce de um site, não de uma campanha. | Perde-se o vínculo com orçamento, canais e metas do plano de mídia. |
| D7 | **Só existe o que já existe no ar.** Nó medido sem `path` válido é rejeitado com 400 (`reports_flow.py` ~516), publicar exige ao menos um passo medido (`no_measured_steps`) e criar um fluxo exige um domínio. | Não dá para planejar uma campanha antes de as páginas serem criadas, que é o caso mais comum. A ferramenta só serve depois do trabalho de produção, quando o planejamento já passou. |
| D8 | “Publicar” faz duas coisas ao mesmo tempo: congela o desenho e liga a medição. | Quem quer só aprovar o plano é bloqueado por pendências de medição que ainda não fazem sentido. |

## 3.1 Princípio corrigido

> **Um fluxo nasce como plano. As páginas, os eventos e as origens podem existir só no desenho. A medição liga nó a nó, conforme as peças ficam prontas.**

**Um fluxo que nunca será medido é um uso completo, não um rascunho incompleto.** Muitos planos servem só para entender e combinar com o time como a campanha funciona: por qual canal cada anúncio entra, como as páginas se dividem, que testes A/B existem e como a atribuição vai ser lida. Esses fluxos não pedem domínio, tag nem pendência de medição, e não devem ser tratados como atrasados.

O erro de partida foi tratar o desenho como espelho do que está publicado. Na prática, o time de mídia desenha a jornada, depois pede as páginas ao time de produção, depois publica e só então mede. O Fluxos acompanha esse caminho inteiro, e o desenho é a especificação do que falta construir.

## 4. O que já existe e será reaproveitado

- Teste de conversão e proposta de blueprint (`reports_flow_probe.py`).
- Origem calculada por `utm_source` ou `referrer` (`reports_flow_metrics.origin_platform`).
- Jornada medida com `sessions`, `rate` e `observation` por conexão, com estados `measured`, `no_data`, `unmeasured` e `no_origin`.
- Descoberta de páginas com grupos, `campaign_id` nos nós, registro de blocos, layout ELK e Super Tag.

## 5. Modelo v3

### 5.1 Nós

| Papel | Tipo | Campos novos |
|---|---|---|
| **Origem** | `source` | `channel` (`traffic.meta`…), `match` (`utm_source`, `utm_medium`, `utm_campaign`, `referrer_host`, todos opcionais), `plan` (orçamento, volume esperado), `link` (URL com UTM gerada). |
| **Passo** | `page`, `page_group`, `event`, `form` | `page_group` tem `pattern` (ex.: `/audiencia/*`) e `member_count`. Substitui dezenas de nós. |
| **Meta** | `goal` | Definida em `config.goals[]`: `{id, name, rule, window_days, value}`. O nó só referencia `goal_id`. |
| **Lógica** | `condition`, `delay`, `segment`, `webhook` | Inalterados. |
| **Ponto de contato fora do site** | `touchpoint` (e-mail, SMS, ligação, reunião, pipeline, negócio perdido) | `measure` define de onde vem o número: `tag` (site), `import` (planilha ou CSV pelas importações do Reports) ou `manual`. |

Uma jornada de campanha raramente é só web: e-mail, SMS, ligação e CRM aparecem nas referências. Esses nós entram no desenho com o mesmo peso dos demais. Sem fonte de dados, ficam como “sem medição”, nunca como zero.

Remoções: `stage` e `isEntry` deixam de ser gravados e passam a ser derivados no servidor do grafo.

- Sem conexão de entrada: **entrada**.
- Tem caminho até uma meta: **caminho de conversão**.
- Folha que não é meta: **saída**.
- As faixas visuais são só fundo, calculadas a partir disso.

### 5.1.1 Nó planejado e especificação

Todo nó ganha `status`:

| `status` | Significado | `path`/`event_name` |
|---|---|---|
| `planned` | Existe só no desenho. | Opcional. Pode ter um endereço sugerido (`suggested_path`), que não é validado contra o site. |
| `in_production` | Alguém está criando. | Opcional. |
| `ready` | Pronto para ir ao ar; o endereço final está definido. | Obrigatório e validado como hoje. |
| `live` | No ar e vinculado à medição. | Obrigatório. |

Nó `planned` ou `in_production` **não entra na medição**, aparece com visual de rascunho (tracejado, selo “a criar”) e não gera pendência bloqueante.

Cada nó planejado carrega uma **especificação** (`spec`), que é o que o time de produção precisa para construir:

- **Página:** objetivo, endereço sugerido, título, mensagem principal, blocos de conteúdo, chamada para ação, campos do formulário, observações e referências visuais.
- **Evento / meta:** nome do evento, quando dispara, em que elemento.
- **Origem:** canal, público, criativos necessários, UTMs.
- **Ponto de contato:** mensagem, gatilho e momento do envio.
- **Responsável, prazo e status** de cada peça.

### 5.1.2 Vincular depois

Quando a página existe, o usuário (ou o sistema) **vincula** o nó planejado a um endereço real: `status` vai para `ready` e `path` é validado. O Explorar site e o teste de conversão já descobrem páginas; passam a sugerir “esta URL parece ser o nó X” por título, caminho e papel. Nada é vinculado sem confirmação.

### 5.1.3 Fluxo sem domínio

O domínio deixa de ser obrigatório na criação. Sem domínio, o fluxo fica em modo plano e só aceita nós `planned`. O domínio é definido (e a tag instalada) quando o primeiro nó vai para `ready`.

### 5.1.4 Divisão e teste

O nó `condition` passa a ter um modo **teste A/B**: duas ou mais variantes com a divisão planejada (por exemplo 50/50), o que se compara e o critério de vencedor. Cada saída leva a uma variante (página, criativo ou mensagem). No plano, a divisão aparece nas conexões; na medição, cada variante tem suas próprias taxas lado a lado.

### 5.2 Conexões

`{id, from, to, kind, plan?}`, com `kind` em:

- `attribution`, de origem para passo: sessões cuja origem casa com `match` e cuja primeira página é o passo.
- `navigation`, entre passos: transição observada.
- `trigger`, de passo para evento ou meta.

A métrica não é gravada: vem do endpoint de jornada, com `sessions`, `rate`, `observation` e, novo, `previous` (período anterior) e `plan` (meta planejada).

### 5.3 Documento

`config.goals[]`, `config.origins_catalog[]` (canais usados no fluxo) e `config.plan` (período, orçamento total, objetivo da campanha). `schema_version: 3`. A leitura converte v2 para v3 (`migrate_v2_to_v3`) e a gravação projeta para v2 enquanto houver clientes antigos, como já ocorre entre v1 e v2.

## 6. Experiência premium

### 6.0 Planejar antes de existir

O caminho natural do usuário é:

1. **Planejar:** desenhar origens, páginas, eventos e metas, todos `planned`. Nenhum domínio é exigido.
2. **Especificar:** abrir cada peça e descrever o que precisa existir (5.1.1). Modelos por tipo de página reduzem o trabalho.
3. **Aprovar o plano:** “Publicar plano” congela uma versão do desenho para aprovação. Não liga medição.
4. **Produzir:** o time recebe a **folha de produção** (abaixo) e atualiza o status de cada peça.
5. **Vincular:** a cada página no ar, vincular o endereço real.
6. **Ativar medição:** só quando houver ao menos um nó `ready` e a tag instalada. Aqui valem as pendências de medição de hoje.
7. **Monitorar:** o plano segue no desenho, e o real aparece por cima.

**Duas ações de publicação separadas** (resolve D8):

| Ação | O que faz | Quando fica disponível |
|---|---|---|
| **Publicar plano** | Congela a versão e gera a folha de produção. | Sempre que houver ao menos um nó. |
| **Ativar medição** | Liga a Super Tag e começa a contar. | Quando houver nós `ready` e a tag instalada. Nós ainda `planned` ficam de fora, sem erro. |

**Folha de produção.** É o documento que sai do desenho: o que precisa ser criado, por quem e até quando.

- Uma seção por peça: páginas a criar, eventos a configurar, origens com seus links UTM, pontos de contato a escrever.
- Cada item mostra status, responsável, prazo e o que falta (por exemplo, “endereço definido”, “formulário com campos”, “evento nomeado”).
- Uma barra de progresso do conjunto (“7 de 12 peças prontas”) e a lista do que bloqueia a ativação da medição.
- Exportável em PDF e CSV, para entregar a quem produz fora do Reports, e imprimível a partir da própria tela.
- Atualiza sozinha: ao vincular uma página real, o item vira “no ar”.

**O desenho e o real convivem.** Se uma página vinculada deixa de existir ou muda de endereço, o nó mostra “página não encontrada” em vez de sumir da medição. Se há tráfego em páginas que não estão no desenho, o painel sugere incluí-las.

### 6.0.1 Modelos de fluxo

Modelos são o ponto de partida mais rápido, tanto para quem só planeja quanto para quem vai medir:

- **Do Reports:** modelos curados por objetivo (captação de leads, venda, evento, lançamento, institucional, recuperação), já com origens por canal, divisão de páginas, testes e meta, todos como nós planejados com a especificação preenchida.
- **Do time:** qualquer fluxo pode ser salvo como modelo do cliente (sem dados medidos, sem endereços reais) e reaproveitado em outra campanha.
- Ao aplicar um modelo, o usuário escolhe os canais que vai usar e o modelo remove o resto.

### 6.1 Começar pela campanha
O assistente “Novo fluxo” oferece quatro pontos de partida:
1. **Objetivo** (geração de leads, venda, evento, institucional): um modelo já com origens, páginas e meta típicas, **todas planejadas** e com a especificação preenchida como ponto de partida.
2. **Campanha existente**: traz canais, período e orçamento do plano de mídia (`campaign_id`).
3. **URL** (o teste de conversão atual): propõe páginas e eventos a partir do HTML.
4. **Vazio**, só para quem sabe o que quer.

### 6.2 Montar rápido
- Paleta com abas **Origens · Páginas · Ações · Outros**, busca e ícones por canal, como no Funnelytics.
- Barra flutuante sobre o nó selecionado (configurar, duplicar, medir).
- Arrastar da paleta para a mesa, conectar arrastando, `⌘K` para qualquer comando (já existe), desfazer/refazer e indicador “Rascunho · Salvo” (já existem).
- Grupos de páginas como um nó só, expansível.

### 6.3 Origem com UTM
Ao configurar uma origem, o sistema gera o link marcado (`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`) com cópia em um clique e uma planilha para o time de mídia. Assim o plano e a medição usam as mesmas regras.

### 6.4 Plano versus real
- Cada origem e conexão aceita uma meta planejada: volume, taxa e custo.
- No monitor: realizado, planejado e desvio, com cor semântica (acima, na meta, abaixo).
- Aba **Previsão**: projeta o resultado do período a partir do ritmo atual, e só aparece com dados suficientes.

### 6.5 Achar o vazamento
Na referência, o valor do monitor é apontar onde a jornada perde gente, em vez de só mostrar números.
- **Saída explícita:** cada nó com perda relevante ganha um nó de saída tracejado com o total e o percentual (“1,1 mil saíram · −24%”).
- **Chip de continuidade** em cada conexão (“38% continuam”), com cor semântica.
- **Painel “Vazamentos”:** lista ordenada pelas maiores perdas absolutas, com o passo, o volume, a taxa e a comparação com o período anterior. Clicar leva ao nó.
- **Direção do tráfego:** as conexões medidas animam o sentido do fluxo (pontos em movimento) e a espessura acompanha o volume. A animação respeita `prefers-reduced-motion`.
- **Indicador de dados:** “Dados ao vivo” ou “atualizado há N min”, com o estado de cada fonte (tag, importação, manual).
- Cada vazamento só é apontado quando há amostra mínima definida no contrato; abaixo disso aparece “amostra pequena”.

### 6.6 Monitorar sobre o mesmo desenho
- Alternar **Desenho · Números · Previsão**, sem trocar de tela.
- Cada conexão mostra taxa e volume; cada nó, pessoas; cada meta, conversões e valor.
- Período com comparação (anterior ou ano), filtros por dispositivo e origem, e destaque do maior ponto de saída.
- Estado “sem dados” sempre distinto de zero (regra já existente).
- Alertas: queda de volume, origem sem tráfego, conexão sem medição.

### 6.7 Compartilhar dentro do Reports
Quem tem papel `viewer` no Reports abre o fluxo em modo leitura, sem editar. Exportação em imagem e PDF com a legenda, comentários nos nós e histórico de versões com autor e data. Link público sem login fica como etapa posterior, só se o time pedir.

### 6.8 Padrão de qualidade
- 200 nós e 300 conexões com 60 fps de pan e zoom (orçamento de desempenho verificado no harness).
- Navegação completa por teclado e leitor de tela nos nós e conexões.
- Estados vazio, carregando, erro e parcial desenhados para todas as telas.
- Tema escuro e claro, com contraste mínimo AA.

## 7. Fases

| Fase | Entrega | Aceite |
|---|---|---|
| **1. Modelo** | Contrato v3, `migrate_v2_to_v3`, `status` por nó (nós planejados sem `path`), domínio opcional na criação, metas no fluxo, etapa e entrada derivadas, `page_group`. | Os fluxos existentes abrem iguais em v3 (todos `live`); um fluxo sem domínio e sem páginas é salvo; um grupo `/audiencia/*` vira um nó com 331 páginas. |
| **2. Plano e folha de produção** | Cenário “e se”, modelos curados, especificação por nó, “Publicar plano” e “Ativar medição” separados, folha de produção com status, responsável e prazo, exportação em PDF e CSV, vincular página real. | Um fluxo 100% planejado é publicado como plano e gera a folha; ao vincular uma página, o item muda para “no ar” e a medição daquele nó liga. |
| **3. Origem e UTM** | `match` por origem, gerador de links, atribuição por origem na jornada. | Duas campanhas Meta separadas no mesmo fluxo recebem sessões distintas. |
| **4. Mesa premium** | Paleta por abas com busca, barra flutuante, conexões tipadas com chip de taxa e volume, nós de contato fora do site. | O modo Números mostra taxa e volume em cada conexão, e um nó de e-mail ou ligação aceita dados importados. |
| **5. Plano × real e vazamentos** | Metas planejadas por origem e conexão, desvio, comparação de período, painel “Vazamentos” e nós de saída. | Cada origem exibe planejado, realizado e desvio; o maior vazamento do fluxo de teste aparece em primeiro no painel. |
| **6. Começar pela campanha** | Modelos por objetivo e importação de campanha. | Um fluxo completo nasce de uma campanha em menos de 2 minutos. |
| **7. Compartilhar** | Modo leitura para `viewer`, exportação, comentários, versões. | Um usuário `viewer` abre o fluxo e não consegue editar nem apagar. |
| **8. Alertas e previsão** | Previsão e alertas. | Alertas disparam em dados de teste e nunca com “sem dados”. |

Cada fase termina em produção com a anterior intacta. A Fase 1 muda pouco o que o usuário vê, mas é a que corrige D7: sem ela, nada do planejamento antes das páginas existe. A Fase 2 é a que entrega o novo jeito de trabalhar.

## 8. Riscos e decisões em aberto

| Risco / decisão | Tratamento |
|---|---|
| Migrar `stage` e `isEntry` pode alterar a leitura de fluxos publicados. | Derivar em paralelo, comparar com os valores gravados nos fluxos existentes e só então remover os campos. |
| A atribuição por primeira página não cobre sessões com várias origens. | Documentar o modelo (primeiro toque no período) e expor a regra na legenda. |
| O vínculo com o plano de mídia depende de onde ficam orçamento e canais hoje. | Confirmar a fonte antes da Fase 6; as fases 1 a 5 não dependem dela. |
| Nó planejado sem `path` quebra consumidores que assumem caminho (descoberta, métricas, Super Tag, validação de identidade). | Mapear os usos de `path` antes da Fase 1 e filtrar por `status` nos pontos de medição; cobrir com testes de contrato. |
| O fluxo planejado e o real divergem com o tempo. | Mostrar a divergência (página sumiu, tráfego fora do desenho) em vez de esconder; nunca apagar um nó vinculado sem aviso. |
| A folha de produção vira um documento paralelo, fora do Reports. | Ela é uma visão do próprio desenho, sempre gerada do estado atual; a exportação é só uma cópia. |
| Meta com valor monetário exige o valor chegar na Super Tag. | Aceitar valor fixo por meta na Fase 1; valor dinâmico fica para depois. |
| Dados de fora do site chegam atrasados ou incompletos. | Cada nó mostra a fonte e a data da última atualização; sem dado vira “sem medição”. |
| Importação de e-mail ou CRM exige mapear colunas. | Reaproveitar o fluxo de importação do Reports (mapa de colunas e sugestões) em vez de criar outro. |

## 8.1 Lacunas em relação à referência (análise de 01/10/2026)

Acrescentadas às fases conforme a prioridade:

| Lacuna | Fase |
|---|---|
| Cenário “e se”: visitas por origem, taxas por conexão e valor da meta, recalculando o fluxo inteiro | 2 |
| Modelos curados e modelos do time | 2 e 6 |
| Teste A/B no nó de divisão | 4 |
| Notas e molduras soltas, seleção múltipla, alinhar e distribuir, busca de nó | 4 |
| Vista em tabela da jornada (também para acessibilidade e CSV) | 4 |
| Explorar o que vem antes e depois de um nó, com botão para incluir no desenho | 5 |
| Filtros por dispositivo, origem e UTM na jornada; conversão entre dois passos quaisquer | 5 |
| Pessoas por passo no período, com a linha do tempo de cada jornada | 5 |
| Tendência por nó e marcos de publicação na linha do tempo | 5 |
| Modo apresentação e explicação de cada número | 4 e 7 |

## 9. Como saberemos que melhorou

- Fluxos criados **antes** de a primeira página existir, e quantos chegam a `live`.
- Tempo entre “Publicar plano” e “Ativar medição”.
- Peças com especificação preenchida na hora da publicação do plano.
- Tempo para montar o primeiro fluxo medido: de uma sessão de trabalho para minutos.
- Fluxos com pelo menos uma origem com UTM e uma meta definidas.
- Fluxos monitorados semanalmente por pessoas diferentes do criador.
- Redução de nós de página importados em massa (substituídos por grupos).

## 10. Progresso

| Data | Entrega | Commit |
|---|---|---|
| 01/10/2026 | Fase 1a: situação do passo (planejado, em produção, pronto, no ar), especificação para produção, passos planejados fora de toda a medição, aviso de conversão só planejada, passo novo da paleta nasce planejado. | `30f679ee`, `734d1fb6` |

Decisão registrada: planejar é uma escolha explícita. Um passo antigo sem situação e sem URL continua bloqueando a publicação (com a opção de marcá-lo como planejado), para nenhum passo sair da medição sem que a pessoa perceba.

Pendente na Fase 1: domínio opcional na criação (exige migração do registro de fluxo e da tag), metas no fluxo com etapa e entrada derivadas do grafo, e `page_group`.
