# Auditoria do Studio — lançamento 11/10/2026

Data: 06/10/2026. Escopo: Cadu Studio (imagem, vídeo, camadas, editor, áudio, storyboard, biblioteca). Auditoria **somente leitura**: nenhum código do produto foi alterado, nenhuma migração rodou, nenhum dado foi gravado no banco e nenhuma API paga foi chamada.

## Veredito: **BLOQUEADOR** (1 item) + riscos altos

O Studio está funcionalmente sólido: 844 testes Python e 19 suítes de front passam. Um problema de cobrança, porém, quebra toda geração paga para contas sem plano com preço, **inclusive o plano Free criado no cadastro público (commit e7f3f1905)**. Nesse caso a chamada ao provedor acontece e é paga, mas o usuário recebe erro. Confirme com a consulta Q1 antes de corrigir.

## Testes executados

| Suíte | Resultado |
|---|---|
| `DB_HOST=127.0.0.1 DB_PORT=1 .venv/bin/python -m pytest -k "studio or creative or video or modeling or storyboard"` | **844 passed**, 0 falhas (65 s) |
| `node --test tests/frontend/mc-*.test.* creative-*.test.*` | 18/19 passam; `mc-studio-download.test.cjs` falhou só na execução em paralelo e **passou sozinho** (instável por timing, não regressão) |
| `tests/frontend/mc-studio-browser.cjs` | **quebrado antes desta auditoria**: `render-studio-fixture.py` renderiza `parametros/modelagem_criativos.html`, que agora estende `cadu_portals/base.html` e precisa de `portal_product`/`cadu/_product_nav.html`. A fixture está defasada. |

Navegador: o Studio exige sessão e banco, então não renderiza sem login. A verificação visual usou as capturas que as suítes Playwright geram com fixtures (`tests/frontend/.artifacts/studio/editor.png` e `library-layout.png`, em 1440 e 1280). O tema escuro está consistente, sem resíduo de Untitled e sem tema claro. O Browser pane não foi aberto, logo não há viewport para restaurar.

---

## Achados por severidade

### BLOQUEADOR

**B1. Toda cobrança do Studio depende do preço comercial do plano. Plano Free ou ausente gera erro depois de o provedor já ter sido pago.**
- `aicentralv2/cadu_credit_connector.py:158-161`: `charge_provider` chama `_commercial_token_price_usd()` sempre que o resultado traz `actual_cost_usd`/`usage.cost`, **mesmo quando `media_tokens` já foi informado**.
- `aicentralv2/cadu_credit_connector.py:44-64`: `commercial_token_price_brl` lança `ValueError("Preço comercial de Tokens Cadu indisponível…")` se `price_monthly <= 0` ou se não há plano ativo.
- `aicentralv2/creative_modeling_service.py:5995`: `_charge_studio_call` sempre preenche `actual_cost_usd`, e as imagens passam por esse caminho.
- Confirmado sem banco: com `commercial_token_price_brl` substituído por um stub que lança erro, `charge_provider(..., media_tokens=4000, provider_result={"actual_cost_usd":0.04})` também lança.
- O preço só é consultado **depois** da chamada ao provedor, e `authorize` só verifica saldo. Na prática:
  - imagem (`studio_create.py:1069`): render pago, arquivo salvo em `static/uploads/creative_generated/` (fica órfão) e erro `image_billing` para o usuário;
  - direções (`studio_create.py:570`): erro;
  - agente, storyboard e narração (`services/cadu_ai_connector.py:74`): erro, e a chave idempotente fica `failed`;
  - transcrição (`creative_media/studio.py:1197`): erro.
- O vídeo usa `charge_tokens` (valor fixo) e **não** é afetado.
- Cenário: conta nova do cadastro público com plano Free (`cadu_billing_catalog.FREE_PLAN`, sem preço) e 50 mil tokens de boas-vindas. Na primeira imagem paga, o provedor cobra, o cliente vê erro e o saldo não muda.
- Correção curta, em duas partes:
  1. Em `charge_provider`, não consultar o preço comercial quando `media_tokens is not None`.
  2. Na falta de preço, usar a taxa-base `CADU_USD_PER_CREDIT_TOKEN` (US$10/M) ou chamar `ensure_priced()` **antes** do provedor, dentro de `authorize`.

  Adicionar um teste com plano Free.

### ALTO (corrigir antes de 11/10)

**A1. O Criar (`mc-studio-create.js`) e outras páginas clássicas usam `?v=83` fixo, e o nginx serve `/static/` como `public, immutable` por 30 dias.**
- `templates/cadu_studio/desk.html:26` (ramo `else`): `?v=83` não muda desde 15/09 (`0fc72b2c5`), mas `static/js/mc-studio-create.js` mudou em 05/10 (`10cdb562d`).
- `deploy/nginx-aicentralv2.conf:22-25`: `expires 30d; Cache-Control "public, immutable"`.
- O mesmo vale para `modelagem_criativos.js?v=58`, `mc-cadu-nav.js?v=8` e os CSS `?v=N`.
- Só Vídeo e Camadas usam `static_fingerprint` e o import map, e o teste `mc-video-import-map` cobre apenas esses dois.
- Cenário: um usuário interno que abriu o Criar nos últimos 30 dias recebe o JS antigo contra a API nova e pode ver erros de console ou de contrato. Os mesmos links valem para os demais usuários depois do próximo deploy.
- Correção: trocar todos os `?v=N` de `desk.html` por `?v={{ static_fingerprint(...) }}`.

**A2. Vídeo: a cobrança acontece antes do download e do empacotamento. Se o resto falhar, o cliente paga e não recebe vídeo.**
- `creative_media/worker.py:88-92`: `billing_fn(..., "video")` roda logo após `status == completed`, e só depois vêm o download (`download_video`), `_packs` (ffmpeg, overlay, mix de locução) e a persistência.
- Qualquer exceção nessas etapas marca o job como `failed` sem estorno, porque não existe caminho de estorno no ledger.
- Correção: cobrar depois de `persist` (a chave `studio-video:{public_id}:video` já é idempotente), ou criar um estorno no `except`.

**A3. Imagem: até três renders e a revisão por visão rodam, mas só um render é cobrado.**
- `creative_media/studio_create.py:996-1030`: a revisão automática fica ligada por padrão (`STUDIO_AUTO_REVIEW=1`, `MAX_ATTEMPTS=3`). Cada versão extra é um `generate_image` pago, e a revisão (`studio_review.py:324`, `chat_completion`) não é medida.
- O comentário em `studio_create.py:996` é explícito: só a versão entregue é cobrada.
- O mesmo vale para a correção de margem (`:990`) e o duplo passe (`TWO_PASS`, desligado).
- Na pior hipótese o custo real chega a cerca de 3x o valor cobrado, com a revisão por cima. A margem de 4x a 7x da venda absorve, mas fica fina.
- Decisão de produto. Opções: somar o `usage` de todas as tentativas em `_charge_studio_call`, ou limitar `STUDIO_AUTO_REVIEW_MAX_ATTEMPTS=2` no lançamento.

**A4. LLM e transcrição viram tokens pelo preço de venda do plano, sem margem. Mídia vira tokens pela taxa-base.**
- `cadu_tool_billing.py:350-357`, com `usd_per_credit_token` = preço comercial (`cadu_credit_connector.py:178-181`): tokens = custo ÷ preço de venda do token. A receita fica igual ao custo, ou seja, margem 1x.
- Imagem (`studio_costs.media_tokens_for_cost`) usa US$10/M e por isso carrega a margem da venda.
- Quatro caminhos usam o preço de venda: agente, storyboard, otimização de prompt e direções.
- Confirmar se é intencional. Se não for, passar `usd_per_credit_token=CADU_USD_PER_CREDIT_TOKEN` também para LLM. Fazer isso também resolve B1 nesses caminhos.

**A5. A transcrição não tem bloqueio de saldo antes do provedor.**
- `creative_media/studio.py:1188-1197`: `transcribe_upload(..., allow_long=True)` roda antes de qualquer `authorize`.
- Um arquivo longo é transcrito por inteiro (OpenAI/OpenRouter) mesmo com saldo zero, e depois o `charge` falha.
- Correção: `authorize(actor, transcription_credit_tokens(duração estimada ou máxima))` antes de transcrever.

**A6. Direções: o saldo é verificado de novo depois do provedor.**
- `studio_create.py:566` chama `credits.authorize` dentro de `charge()`, já depois da chamada paga. Se o saldo caiu nesse meio-tempo (outra geração concorrente), o resultado é descartado e o custo fica perdido.
- O mesmo vale para `ledger.charge`: o `InsufficientToolCredits` em `cadu_tool_billing.py:279` aparece depois de qualquer provedor.
- Correção: remover a segunda verificação e, no `charge`, permitir saldo negativo controlado ou reservar o valor antes.

### MÉDIO (pode esperar, com monitoramento)

- **M1. A locução não usa ElevenLabs.** `creative_media/settings.py:21` define `TTS_MODEL = google/gemini-3.1-flash-tts-preview` via OpenRouter, com voz `Charon` (`worker.py:521-524`). Não há integração ElevenLabs no código. A cobrança da locução é pela **estimativa** do orçamento (`animate.py:648-651`, `usage: {}`). Isso diverge da decisão registrada; confirmar com o dono.
- **M2. O fallback de vídeo para Kling é cobrado pelo `total` de tokens do outro modelo** (`worker.py:233-251` + `animate.py:653`), com orçamento feito para Seedance. Validar a razão tokens/custo com Q5.
- **M3. Vídeo cobrado 1:1 por `usage.total` do provedor** (`animate.py:653`), não pelo custo em USD. Se o token de vídeo do OpenRouter custar mais que US$10/M, a margem some; se custar menos, a margem é a diferença. Validar com Q5. Se `usage` vier sem tokens, a cobrança cai na estimativa.
- **M4. Mídia gerada e referências são arquivos estáticos públicos** em `static/uploads/creative_generated|creative_references` (`creative_modeling_storage.py:28-31, 231`). O nome é um uuid4 (não adivinhável), mas não há escopo por client_id nem expiração, e o cache é `public, immutable` por 30 dias. Clipes, frames e áudios do editor estão bem escopados por `_scope(client_id)` e `send_file` (`studio_media.py:117-143`). Para o Vultr: hoje a gravação é em disco local dentro de `root_path/static/uploads` (imagens) e `instance/creative_media` (vídeo). Um deploy que substitua o diretório da app apaga as imagens, e não há limpeza de disco.
- **M5. Upload de vídeo transcodificado de forma síncrona na requisição** (`studio_media.py:94-103`): ffmpeg com timeout de 240 s, perto dos 300 s do gunicorn e do nginx, com workers `sync`. Dois uploads simultâneos prendem workers. Limites corretos: 150 MB, 5 min, `format_whitelist`, `protocol_whitelist`.
- **M6. Timeout de vídeo de 15 min** (`worker.py:198`): o provedor pode concluir e cobrar depois desse prazo, o custo fica sem cobrança e não há cancelamento no provedor.
- **M7. Áudio barrado por direito autoral** (`worker.py:37-47`): mensagem amigável, sem cobrança (status diferente de `completed`). OK. Falta confirmar se o OpenRouter cobra a geração barrada.
- **M8. Copy de unidade**: a UI do vídeo ainda diz "gasta poucos **créditos**" (`library-layout.png`), enquanto a unidade é tokens. O seletor de proporção aparece truncado em "16:" no editor em 1440.
- **M9. Teste instável**: `mc-studio-download.test.cjs` falha sob carga paralela (timer). Rodar a suíte com `--test-concurrency=1` no CI.
- **M10. Fixture do navegador quebrada**: `render-studio-fixture.py`, ver a seção de testes.

### BAIXO

- Referências a Skills no Studio, só anotadas e não alteradas: `creative_media/studio_agent.py`, `creative_format_lab/{catalog,engineer,mockup,pipeline,storyboard}.py` importam `creative_skills`/`cadu_skills`.
- `create_image` não reivindica a chave antes do render (`studio_create.py:1209`). Um duplo envio com o mesmo `request_id` gera dois renders e uma única cobrança. A rota do storyboard reivindica via `history.claim_image`.
- Os jobs órfãos são retomados depois de 10 min (`repository.py:263`), e um reenvio interrompido na etapa `submit` é bloqueado para evitar cobrança duplicada (`worker.py:73-74`). Bom.
- Idempotência, chave por cliente e usuário, e reivindicação antes do provedor nos caminhos de LLM (`cadu_ai_connector.py`): corretas.

---

## Corrigir antes de 11/10
1. **B1**: preço comercial ausente ou Free quebra toda cobrança do Studio depois do provedor.
2. **A1**: versões manuais `?v=N` com cache imutável no `desk.html`.
3. **A2**: cobrar o vídeo só depois de persistido, ou estornar.
4. **A5**: bloqueio de saldo antes da transcrição.
5. Decidir **A3** e **A4**, que afetam a margem; no mínimo, `STUDIO_AUTO_REVIEW_MAX_ATTEMPTS=2`.

## Pode esperar
A6, M1–M10 e os itens baixos. Para o Vultr (M4): centralizar a gravação em um único `storage` com backend S3-compatível e URLs assinadas.

---

## Consultas SELECT (somente leitura) para validar a produção

Os nomes de colunas seguem o código (`cadu_tools_token_usage`, `cadu_plan_definitions`, `cadu_client_plans`, `cx_media_jobs`). Ajuste se o esquema de produção divergir; a memória registra que a produção diverge do esquema do repo.

```sql
-- Q1 (B1): o plano Free tem preço? price_monthly = 0 confirma o bloqueador
SELECT id, slug, price_monthly, tokens_monthly_limit FROM cadu_plan_definitions ORDER BY price_monthly;

-- Q2 (B1): clientes que usam o Studio sem plano ativo com preço
SELECT DISTINCT u.id_cliente
  FROM cadu_tools_token_usage u
  LEFT JOIN cadu_client_plans cp ON cp.id_cliente = u.id_cliente AND cp.plan_status = 'active'
  LEFT JOIN cadu_plan_definitions pd ON pd.id = cp.id_plan_definition
 WHERE u.ferramenta ILIKE '%studio%'
   AND (pd.id IS NULL OR COALESCE(pd.price_monthly,0) <= 0
        OR COALESCE(pd.tokens_monthly_limit, cp.tokens_monthly_limit, 0) <= 0);

-- Q3 (B1/A6): falhas de cobrança já ocorridas
SELECT etapa, status, COUNT(*), MAX(created_at)
  FROM cadu_tools_token_usage
 WHERE ferramenta ILIKE '%studio%'
   AND (metadata->>'error' ILIKE '%Preço comercial%' OR metadata->>'error' ILIKE '%Saldo insuficiente%')
 GROUP BY 1,2;

-- Q4: reivindicações órfãs (pending antigas)
SELECT etapa, COUNT(*), MIN(created_at)
  FROM cadu_tools_token_usage
 WHERE status = 'pending' AND created_at < NOW() - INTERVAL '30 minutes'
 GROUP BY 1;

-- Q5 (M2/M3/A3/A4): tokens cobrados vs custo interno por etapa e modelo (margem efetiva)
SELECT etapa, modelo, COUNT(*),
       SUM(tokens_cobrados) AS tokens,
       SUM(custo_interno)   AS custo_usd,
       ROUND(SUM(tokens_cobrados) * 0.00001 / NULLIF(SUM(custo_interno),0), 2) AS razao_vs_base_10usd_m
  FROM cadu_tools_token_usage
 WHERE ferramenta ILIKE '%studio%' AND status = 'charged' AND charged_at > NOW() - INTERVAL '30 days'
 GROUP BY 1,2 ORDER BY custo_usd DESC NULLS LAST;

-- Q6 (A2): vídeos cobrados cujo job terminou em falha
SELECT j.public_id, j.status, j.error_message, u.tokens_cobrados, u.charged_at
  FROM cx_media_jobs j
  JOIN cadu_tools_token_usage u ON u.idempotency_key = 'studio-video:' || j.public_id || ':video'
 WHERE j.status = 'failed' AND u.status = 'charged';

-- Q7 (M6/M7): jobs de vídeo por status e motivo (timeout, direito autoral)
SELECT status, LEFT(error_message, 80) AS motivo, COUNT(*)
  FROM cx_media_jobs WHERE created_at > NOW() - INTERVAL '30 days'
 GROUP BY 1,2 ORDER BY 3 DESC;

-- Q8: jobs presos (running/provider_* sem atualização)
SELECT public_id, status, stage, updated_at FROM cx_media_jobs
 WHERE status IN ('running','provider_pending','provider_running') AND updated_at < NOW() - INTERVAL '20 minutes';
```
