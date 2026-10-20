# Leads v3 — conexão com pauta real, escrita humana e envio medido

Plano de 2026-10-20. Decisões do usuário: envio pela Brevo com um clique depois de revisar; remetente é o
e-mail do próprio executivo (reply-to na caixa dele); abertura avisa com selo na Operação e notificação no
CentralX; resposta continua marcada à mão.

## Diagnóstico (por que saiu genérico)

- O passo 2 da cadência "Marketing e mídia" pede "apresentar a CentralComm e propor 20 minutos". É pitch
  no topo; o objetivo do passo vence a regra de topo do prompt.
- O contexto de mercado é um texto solto do `perplexity/sonar`. Não vira gancho com número e fonte que o
  passo possa usar, então o modelo enche com "campanhas incríveis" e "insights valiosos".
- O prompt de mensagem (`gpt-4o`) não tem regras contra tom de IA.
- O "Foco" é texto livre e vazio; nada sugere.
- O webhook da Brevo só atualiza `cadu_email_log`; `cadu_lead_mensagem_eventos` já tem `aberto`/`clicado`
  mas nada grava.

## Fase 1 — Pauta: dossiê de ganchos (Perplexity via OpenRouter)

- `gerar_contexto_mercado` passa a `perplexity/sonar-pro` e devolve JSON: lista de ganchos
  `{fato, numero?, fonte_url, data, angulo (mídia/marketing/comunicação), etapa (topo|meio), tipo}`.
  Tipos: movimento da empresa, campanha própria, concorrente, dado do setor (Kantar, IAB, Cenp, Comscore),
  mudança de liderança, tendência de mídia. Só fatos dos últimos 12 meses, com URL; sem fonte, descarta.
- Ganchos guardados por lead (tabela `cadu_lead_ganchos`, com `usado_em` por contato para não repetir).
- Painel do lado direito: lista de ganchos com fonte e data; o executivo marca, descarta ou edita.
- "Foco" passa a ser sugerido pela IA a partir dos ganchos + papel das pessoas (topo, meio, tom, evitar);
  o executivo aceita ou edita.

## Fase 2 — Perguntar ao mercado (pesquisa livre)

- Caixa "Perguntar ao mercado" no lead (já com empresa e setor no contexto) e solta na Operação.
- `sonar-pro` por padrão; `sonar-deep-research` como opção "pesquisa profunda" (mais lenta e cara).
- Resposta com fontes; botão "Salvar como gancho" leva o trecho para o dossiê.
- Custo por chamada registrado por executivo (para ver uso).

## Fase 3 — Cadência por funil, com foco em topo e meio

Novo modelo (substitui o seed atual sem apagar inscrições existentes):

| Etapa | Toques | Regra |
|---|---|---|
| Topo | 3–4 (LinkedIn conexão, e-mail com dado, WhatsApp/LinkedIn com tendência, e-mail com movimento do concorrente) | Um gancho diferente por toque; nenhum pedido de reunião; termina em pergunta de opinião |
| Meio | 2–3 (diagnóstico curto, case do segmento, pergunta sobre o desafio) | Convite para conversa específica de 15 min só aqui |
| Fundo | 1 (proposta de próximo passo) | Só no fim ou depois de resposta |

Cada passo declara o tipo de gancho que consome; se não houver gancho daquele tipo, a tela pede para
pesquisar antes de gerar.

## Fase 4 — Escrita humana

- Regras no prompt: frases curtas; nenhum adjetivo de elogio ("incrível", "inovador"); nada de
  "espero que esteja bem", "estou ansioso", "insights valiosos"; um único fato com número e de onde veio;
  uma pergunta só; 50–90 palavras no e-mail de topo; primeiro nome; minúsculas no assunto quando natural.
- Checagem pós-geração: lista de frases proibidas; se aparecer, reescreve uma vez.
- Corpo enviado como texto puro (HTML mínimo só para o pixel de abertura), sem logo nem rodapé de marketing.
- Preferência por executivo: assinatura curta e flag "Enviado do meu iPhone" / "Enviado do meu Galaxy" /
  nenhuma.
- Linha de saída discreta ("se não fizer sentido, me avisa que eu paro") e respeito ao opt-out (LGPD).

## Fase 5 — Envio pela Brevo e medição

- Botão "Enviar" (ao lado de "Abrir no Gmail"): manda pela Brevo com `sender` = e-mail do executivo,
  `replyTo` = mesmo e-mail, tag `leads-v3`, e grava `enviado` com `provedor_message_id` em
  `cadu_lead_mensagem_eventos`; marca o passo como feito.
- Pré-requisito: domínio `centralcomm.media` autenticado na Brevo (SPF/DKIM/DMARC) e cada executivo
  cadastrado como remetente. Limite diário por executivo para proteger a reputação.
- Webhook `/api/brevo/webhook`: além do ledger atual, grava `entregue`/`aberto`/`clicado`/`bounce`/`optout`
  no lead. Abertura por proxy (Apple MPP) entra marcada como `proxy` e não conta como abertura real.
- Aviso: selo no passo e no lead ("abriu 2x · há 10 min") e o lead sobe na fila do dia; notificação no
  CentralX para o executivo dono (não há tabela geral para usuários internos; criar
  `cadu_user_notifications` + toast com polling leve).
- Análise: por cadência e por passo — enviados, entregues, abertos (reais), cliques, respostas; por gancho
  usado (qual tipo de pauta abre mais).

## Ordem e verificação

1 → 4 → 3 → 5 → 2. Testes sem rede para prompt, parser de ganchos, checagem de frases e mapeamento de
eventos da Brevo. Migrações em Postgres local antes (o `.env` aponta para o banco de produção).
