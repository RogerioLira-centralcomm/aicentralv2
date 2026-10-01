# Reports — Página 360: visão expandida do monitoramento

Data: 01/10/2026. Estado: proposta para decisão. Nada deste documento está implementado, exceto o que está marcado como "já existe".
Complementa `reports-editor-monitoring-excellence.md` (29/09) e `reports-flows-editor-monitoring-ux-2026-09-30.md`; não repete o que lá já está decidido
(canvas React Flow, geometria dos cards, saúde HTTP, editor). O foco aqui é o que acontece **quando se clica numa página monitorada**.

## 1. A ideia

Hoje o monitor mostra o mapa do fluxo e um card por página com estado e poucos números. A proposta é transformar a **página** em objeto de
primeira classe: ao abrir uma página monitorada, o usuário vê numa só tela de onde vem o tráfego, quanto custa, o que as pessoas fazem nela,
onde clicam, quantas convertem e se ela está no ar. E, pela primeira vez, ligar o gasto do Google Ads a essa página até a venda.

Seis blocos, na ordem em que o usuário lê:

| Bloco | Pergunta que responde | Fonte |
|---|---|---|
| 1. Números | Quantas pessoas, quanto tempo, quantas convertem? | Super Tag |
| 2. Origem paga | Qual campanha, quanto gastou, quanto custa cada conversão? | Google Ads (motor v2) |
| 3. Mapa de conversão | Por onde as pessoas passam até converter, e onde saem? | Super Tag + fluxo + webhook de CRM |
| 4. Mapa de interação | O que clicam, até onde rolam, o que veem? | Super Tag |
| 5. Saúde | A página está no ar e rápida? | Monitor HTTP |
| 6. Ações sugeridas | O que eu faço agora? | Cruzamento dos blocos acima |

## 2. O que já existe (verificado no código)

- **Super Tag** (`cadu-supertag-v1.js`, tabela `cadu_reports_supertag_events`): `page_view`, `click`, `whatsapp_click`, `form_submit`, `visibility`,
  `scroll_depth`, `custom_event`, `conversion`, `heartbeat`; guarda sessão, visitante, `referrer_host`, atribuição (JSON), tamanho do viewport,
  retenção de 90 dias e só com consentimento. Clique grava `x`/`y` em milésimos do **viewport**, mais `element_id`. Rolagem grava quartis (25/50/75/100).
  Visibilidade grava `element_id` e razão visível.
- **Monitor HTTP** por fluxo (`reports_flow_monitor.py`), presença e sessões ativas, transições observadas, relatório histórico por etapa.
- **Webhook de conversões** (`/ingest/conversions`): `lead`, `qualified_lead`, `sale`, atribuídos por `visitor_id` ou campanha.
- **Motor Google Ads v2** (nesta entrega): campanhas, grupos, palavras-chave com Índice de Qualidade, termos de pesquisa, dispositivo,
  orçamento/lances, palavras negativas e **páginas de destino** (`landing_page_metrics`), todos com `page_host` + `page_path` para cruzar com a Super Tag.
  Os dados já chegam e ficam guardados; nenhuma tela os lê ainda.

## 3. Os blocos em detalhe

### 3.1 Números da página

Janela, fuso e versão sempre visíveis; comparação com o período anterior equivalente.

- Visitantes únicos, sessões, visualizações, entradas (primeira página da sessão), saídas (última), tempo ativo mediano (por `heartbeat`),
  alcance de rolagem (% de sessões que passaram de 25/50/75/100), cliques por sessão.
- Conversões e taxa: **sempre com denominador**. "—" quando não medido, "0" só quando medido e zero.
- Quebras: origem (`referrer_host`/UTM), dispositivo (largura do viewport), campanha, novo × recorrente.
- Amostra mínima: abaixo de um limite, mostrar "amostra insuficiente" em vez de percentuais.

Não exige coleta nova. É consulta e tela.

### 3.2 Origem paga

Tabela "Campanhas que levam a esta página": gasto, cliques, conversões do Google Ads, custo por conversão, e ao lado as sessões e conversões
**observadas na página** pela Super Tag. A diferença entre as duas colunas é informação, não erro: mostrar lado a lado, nunca somar.

Limite honesto do Google Ads: a página de destino é conhecida por **campanha/grupo/anúncio**, não por palavra-chave ou termo de pesquisa.
Então a tela mostra "termos e palavras-chave dessas campanhas", sem afirmar que o termo X levou à página Y. Quando a campanha tem mais de uma
página de destino, o vínculo é apresentado como distribuição, com o aviso.

### 3.3 Mapa de conversão

Visual tipo Sankey, da esquerda para a direita: **origens → páginas → evento (formulário / WhatsApp) → lead → qualificado → venda**.

- Largura do fluxo = sessões únicas; cada passagem mostra volume e % de continuidade; a perda entre etapas é explícita ("saíram aqui").
- Filtros: período, campanha, dispositivo, novo × recorrente. Clicar numa faixa abre a lista das páginas e eventos daquele trecho.
- Etapas de CRM (qualificado, venda) só aparecem quando o webhook as entrega. Etapa sem dado fica cinza com "sem integração", sem inventar valor.
- Regras explícitas, exibidas na tela: janela de atribuição, reentrada na mesma sessão, deduplicação.
- Distinguir três coisas que hoje se confundem: **conversão do Google Ads**, **conversão observada** (Super Tag) e **venda confirmada** (CRM).
- Atribuição é associação, não causalidade; não declarar incremento sem experimento.

Base técnica: ordenação de eventos por sessão (já há), transições deduplicadas (planejado em 29/09) e vínculo visitante → campanha (já há no webhook).

### 3.4 Mapa de interação (mapa de calor)

Sequência honesta, porque a coleta atual não permite desenhar calor correto sobre uma captura de página inteira:

1. **Ranking por elemento** (já possível): cliques, sessões, cliques por sessão, destino do link. Entrega valor sem nenhuma coleta nova.
2. **Grade por viewport**: usa o `x`/`y` atual, deixando claro que é posição na primeira tela, por faixa de dispositivo. Útil para topo de página, não para a página toda.
3. **Contrato de coleta v2** (precisa de instrumentação): posição no documento, rolagem no clique, dimensões do documento e do viewport, identidade estável
   do elemento, versão do layout. Medir o custo em volume antes de ligar. Nunca capturar valor de campo; áreas marcadas ficam excluídas.
4. **Captura de referência** por URL × dispositivo × versão, com fila, proteção SSRF e retenção. Sem captura compatível, volta ao ranking, sem calor falso.
5. **Modos**: cliques, profundidade de rolagem, visibilidade/atenção. Legenda acessível, intensidade ajustável, data da captura, total de sessões.
6. Depois: cliques repetidos e cliques mortos, abandono por campo — exigem instrumentação própria; o limitador atual de 250 ms impede tratá-los como sequência.

### 3.5 Saúde

Já planejada em 29/09: disponibilidade, latência, redirecionamentos, incidentes confirmados, cobertura "N de M páginas". Aqui entra só como bloco
da Página 360, ao lado dos números, para correlacionar queda de conversão com indisponibilidade.

### 3.6 Ações sugeridas (o que fecha o ciclo)

É onde o cruzamento paga o investimento. Regras simples, auditáveis, cada uma com evidência e número, nunca texto genérico:

| Sinal | Sugestão |
|---|---|
| Termo de pesquisa com gasto relevante, zero conversão, que ainda não é negativo | Considerar negativar (lista com custo acumulado) |
| Campanha com cliques altos e página com saída alta ou rolagem baixa | Revisar página ou mensagem do anúncio |
| Palavra-chave com Índice de Qualidade baixo apontando para página lenta ou instável | Verificar experiência da página |
| Queda de conversão após alteração da página (versão do fluxo) | Comparar antes e depois |
| Cliques no Google Ads muito acima das sessões na página | Verificar marcação, redirecionamento ou bloqueio de consentimento |
| Página indisponível com campanha ativa gastando | Alerta imediato |

O sistema **sugere**; não altera nada no Google Ads (o script é somente leitura e deve continuar assim).

## 4. Lacunas de dados para fechar

| Lacuna | Impacto | Quando |
|---|---|---|
| Chave canônica de página (`host` + `path` normalizado) usada igual no Google Ads, Super Tag e fluxo | Sem ela o cruzamento falha em silêncio | Fase 0 |
| Dimensões e rolagem do documento no clique | Heatmap sobre captura | Fase 4 |
| Captura de referência versionada | Heatmap visual | Fase 4 |
| Vínculo explícito instalação/domínio ↔ campanha | Mapa de calor e números por campanha | Fase 0 |
| Retenção: eventos têm 90 dias; Google Ads v2 não tem política | Comparações longas | Fase 0 |
| Metas/valor de conversão por tipo | Receita e retorno por página | Fase 2 |
| Anúncios, geografia e conversão por ação no Google Ads | Detalhe além de campanha | Depois |

## 5. Fases

| Fase | Entrega | Depende de | Aceite |
|---|---|---|---|
| 0 — Fundamentos | Chave canônica de página, dicionário de métricas (definição, janela, denominador), vínculo domínio ↔ campanha, política de retenção | motor v2 em produção | Mesma página resolve para a mesma chave nas três fontes; testes com URLs com UTM, barra final, subdomínio |
| 1 — Página 360, números e origem paga | Blocos 3.1, 3.2 e 3.5 numa rota própria; abre pelo card do monitor | Fase 0 | Números conferem com consulta direta na base e com o Google Ads por campanha/dia; estados vazios honestos |
| 2 — Mapa de conversão | Bloco 3.3 | Fase 1; webhook de CRM para as etapas finais | Sessão sintética conhecida percorre o caminho esperado; perdas somam o total de entradas |
| 3 — Mapa de interação v1 | Ranking por elemento e grade de viewport (3.4, itens 1-2) | Fase 0 | Evento sintético cai no elemento certo; layouts móvel e desktop não se misturam |
| 4 — Heatmap visual | Contrato de coleta v2, captura de referência, modos (3.4, itens 3-5) | Fase 3 e decisão de armazenamento | Calor sobre captura compatível; sem captura, mostra ranking; nenhum dado pessoal na imagem |
| 5 — Ações sugeridas | Bloco 3.6, com regras e evidência | Fases 1-2 | Cada sugestão traz números e link para o dado de origem |
| 6 — Alertas | Incidente, queda de conversão com amostra mínima, coleta ausente; deduplicação e responsável | Fase 1 | Sem alerta repetido; log de notificações |

Ordem recomendada: **0 → 1 → 3 → 2 → 5**, deixando 4 para quando a instrumentação for validada. A Fase 1 já entrega a primeira versão útil
sem coleta nova, e a Fase 3 entrega o ranking de cliques que hoje só existe como tabela.

### Status de implementação (01/10/2026)

| Fase | Estado | Onde |
|---|---|---|
| 0 — Fundamentos | Feita (vínculo manual dispensado; retenção dos lotes em 30 dias) | `reports_page_identity.py`, `reports_page_metrics.py` (dicionário de métricas) |
| 1 — Página 360 | Feita (números, origem paga, saúde, dicionário) | `GET /connect/api/v2/reports/pages/overview`, rota `/connect/app/pages`, `PageDetail.jsx`; o inspetor do monitor ganhou "Ver detalhes da página" |
| 3 — Mapa de interação v1 | Feita: grade 10×10 da primeira tela e ranking de elementos marcados, por dispositivo | `GET /connect/api/v2/reports/pages/interactions`, seção "Mapa de interação" em `PageDetail.jsx` |
| 2 — Mapa de conversão | Feita: Sankey origem → página → próximo passo → resultado no site, mais faixa de CRM (lead, qualificado, venda) | `GET /connect/api/v2/reports/pages/conversion-map`, `sankeyLayout.js`, seção "Mapa de conversão" em `PageDetail.jsx` |
| 5 — Ações sugeridas | Feita: 7 regras determinísticas com evidência, em ordem de prioridade | `reports_page_suggestions.py`, `GET /connect/api/v2/reports/pages/suggestions`, seção "Ações sugeridas" |
| 4 — Heatmap visual | Feita: contrato de coleta v2 (posição no documento), calor da página inteira em faixas e **calor sobre a captura real da página** (cliques e rolagem), por dispositivo | `cadu-supertag-v1.js` (+ `.min.js`), `reports_supertag.py`, `reports_page_captures.py`, abas "Página inteira" e "Sobre a captura" do Mapa de interação |
| 6 — Alertas | Feita: central de alertas, 3 regras confirmadas, deduplicação, responsável, silêncio, histórico; e-mail desligado por padrão | `reports_alert_rules.py`, `reports_alerts.py`, `AlertsCenter.jsx`, migration `add_reports_alerts_v1.sql`, executor encaixado no worker do monitor |

Decisões tomadas ao implementar: o vínculo página ↔ campanha vem **da URL de destino dos anúncios** (sem tabela manual); a Página 360 é uma rota
própria e o card do monitor leva até ela (painel lateral fica para depois); o período vai de 1 a 90 dias porque os eventos da Super Tag expiram em
90 dias, então a comparação com o período anterior só existe até 45 dias; amostra abaixo de 30 sessões mostra aviso, não esconde os números.
Limites da fase 3, vindos da coleta atual: só elementos marcados com `data-cadu-element` têm nome; `x`/`y` são relativos ao viewport no momento do clique (não ao documento); a taxa "clicaram entre os que viram" só existe com `data-cadu-track`; layouts de dispositivos diferentes nunca são misturados sem aviso. O calor da página inteira e sobre captura foi entregue na fase 4.
Fase 2: o próximo passo é o primeiro evento após a primeira visualização da página (outra página, formulário ou WhatsApp); sem evento, a sessão conta como "saiu" (30 min sem atividade) ou "em andamento". As colunas somam o mesmo total de sessões. O CRM é ligado por `visitor_id` em até 30 dias depois da primeira visualização; conversões do CRM sem visitante só entram em campanha (não em página) e a tela diz quantas chegaram sem essa identificação. Conversão ou lead anteriores à primeira visualização não contam.
Fase 5: regras e limites fixos, listados na própria tela em "Como decidimos" (página fora do ar com custo, termo candidato a negativa, campanha com cliques e sem conversão, saída alta com pouca rolagem, cliques do Google Ads muito acima das sessões, Índice de Qualidade baixo com página instável, queda de conversão). Termo só vira candidato a negativa se o snapshot de palavras negativas daquela conta já chegou (senão a tela avisa que não dá para saber) e se nenhuma negativa ativa de campanha, grupo ou lista compartilhada já o bloqueia, respeitando exata, frase e ampla. Termos com status diferente de "nenhum" (já adicionados ou excluídos) nunca são sugeridos. A relação palavra-chave → página não existe no Google Ads, então as sugestões falam de campanhas, não de uma palavra levando a uma página.
Fase 4: cada clique passa a levar `dx`/`dy` (milésimos da largura e da altura do documento) e `dh` (altura em px), todos juntos ou nenhum; tags antigas em cache continuam válidas e só alimentam a visão da primeira tela. A tela mostra a cobertura ("X% dos cliques têm posição na página inteira") e, sem captura, deixa claro que não há imagem da página; com captura, o calor aparece sobre ela (ver abaixo).
Capturas (fase 4): uma por cliente, página canônica e dispositivo (celular 390 px, tablet 820 px, computador 1440 px), da página inteira via Firecrawl. Só acontecem quando alguém com permissão de edição pede, porque usam créditos do provedor; nova captura no mesmo item só após 30 s e no máximo 2 simultâneas. O destino é sempre uma página do domínio autorizado do site, com checagem de disponibilidade e de redirecionamentos; a imagem baixada precisa ser HTTPS em host público, sem seguir redirecionamentos, com limite de 12 MB, e é reencodada em WebP (largura até 720 px, altura até 16 000 px, nunca ampliada). Servida por rota autenticada; o arquivo não tem URL pública. Armazenamento atual: disco do servidor em `instance/reports-page-captures` (configurável por `REPORTS_PAGE_CAPTURE_DIR`; vários servidores precisam compartilhar o volume), com limpeza de arquivos com mais de 120 dias a cada nova captura. O armazenamento está atrás da interface `CaptureStore`: para mover para um serviço externo basta implementar `read_state`, `write_state`, `save_image`, `image_file`, `try_lock` e `prune` e apontar `get_store()` para ele. A sobreposição é proporcional à altura da página, então uma página que mudou depois da captura pode não coincidir (a tela avisa e oferece capturar de novo). A camada de rolagem mostra a % das sessões que chegaram ao fim de cada quarto da página.
Fase 6: um alerta só abre após confirmação (2 falhas seguidas do monitor; Super Tag sem eventos há 6 h ou mais depois de uma base de 50 eventos; queda de 30% ou mais na conversão da sessão, 7 dias contra 7, com amostra confiável). Cada um é atualizado em vez de duplicado, fecha sozinho na recuperação (reincidência abre um alerta novo e o histórico fica) e pode ser reconhecido, assumido ou silenciado por 1 h, 24 h ou 7 dias. A avaliação roda no worker `reports-flow-monitor-loop` (leve a cada 5 min, pesada a cada 1 h) sem serviço novo. O e-mail só sai com `REPORTS_ALERT_EMAILS=1` (destinatário: o responsável, ou os administradores do cliente), no máximo um por alerta a cada 24 h e só para prioridade alta ou média; cada decisão de enviar ou não fica no histórico do alerta.
Validado em Postgres real com dados sintéticos e em navegador com APIs simuladas; ainda não visto com dados de produção.

## 6. Regras de honestidade dos números

- Toda métrica mostra período, fuso, fonte e denominador; total exato disponível quando abreviado.
- "Tempo real" só para o que é de fato quase imediato (presença); o Google Ads chega diariamente e a tela diz isso, com a data da última atualização.
- Não somar mídia, site e CRM. Mostrar lado a lado, com a definição de cada um.
- Sem dado, sem número: "—", "sem integração" ou "amostra insuficiente".
- Prévias e capturas ilustrativas sempre identificadas como tais.

## 7. Privacidade e limites

Consentimento e retenção atuais permanecem. Sem valores de formulário. Destinos de link sem parâmetros sensíveis. Capturas de página só de URLs públicas
do domínio autorizado, com proteção SSRF. A leitura do Google Ads é somente leitura.

## 8. Decisões (resolvidas em 01/10/2026)

1. Ordem executada: 0 → 1 → 3 → 2 → 5 → 4 → 6; todas as fases estão implementadas.
2. Página 360 é rota própria (`/connect/app/pages`); o card do monitor leva até ela.
3. Capturas no disco do servidor por enquanto (120 dias), atrás de `CaptureStore` para migrar a um serviço externo.
4. O Sankey usa lead, qualificado e venda do CRM, ligados por `visitor_id`.
5. Imagens de referência por GPT Image 2 ficaram fora: o calor usa a captura real da página.

## 9. Pendências conhecidas (fora do plano)

- Vínculo manual domínio ↔ campanha: dispensado, o vínculo vem da URL de destino dos anúncios. A retenção dos lotes do Google Ads está feita (30 dias, `prune_chunk_runs`).
- Mover as capturas para um serviço externo (nova implementação de `CaptureStore`).
- Ajustar limiares das regras de sugestão e alerta com dados reais após o primeiro deploy.
- Rodar uma captura real (Firecrawl cobra créditos) e ver a Página 360 com dados de produção.
