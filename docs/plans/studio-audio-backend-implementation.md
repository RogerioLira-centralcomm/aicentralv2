# Cadu Studio Áudio — contrato e implementação de backend

Estado: plano técnico. A interface `/audio` é uma prévia React; importar, editar o roteiro, mover/aparar/dividir clipes e preparar propostas funcionam localmente. Reproduzir a composição, gerar, transcrever, salvar e exportar ainda exigem os serviços abaixo. A interface do cliente deve falar em atividade, resultado, tempo e tokens — nunca em fornecedores ou modelos.

## Princípios de produto

- Uma sessão de áudio pertence a uma conta e, opcionalmente, a um projeto/marca já disponível no seletor do Studio. A troca de projeto deve carregar outra sessão ou pedir para guardar o rascunho atual; jamais atribuir silenciosamente uma edição a outra marca.
- Roteiro, agente, biblioteca e timeline compartilham a mesma revisão de sessão. Uma geração cria um novo asset/clipe, não destrói a versão anterior. Desfazer/refazer usa eventos ou snapshots de revisão.
- Nenhum processamento pago começa sem orçamento visível e autorização do usuário. Todo custo de LLM, fala, música, transcrição, separação, processamento e renderização cobrável passa pelo tokenizador. O servidor nunca aceita custo/tokens enviados pelo cliente como fonte de verdade.
- Operações gratuitas locais (mover, aparar, dividir, mute, solo, ganho simples, editar texto) não devem debitar tokens. O cliente pode mostrar “sem custo de IA” quando a operação for determinística.

## Modelo persistente

Estender `cx_studio_projects`/sessões existentes ou criar tabelas equivalentes com migrações, seguindo os padrões do repositório:

1. `audio_sessions`: `id`, `account_id`, `client_id`, `project_id nullable`, `title`, `duration_ms`, `sample_rate`, `revision`, `document JSONB`, `created_at`, `updated_at`. `document` contém blocos de roteiro, faixas, clipes, automação, playhead inicial e configurações de saída. IDs estáveis em todos os elementos.
2. `audio_assets`: `id`, `session_id`, `project_id`, `kind` (voice/music/effect/ambient/upload/render), `storage_key`, `mime`, `size_bytes`, `duration_ms`, `sample_rate`, `channels`, `sha256`, `waveform_key`, `transcript_key`, `origin_job_id`, `created_at`. URLs assinadas, sem URL externa arbitrária como identidade do asset.
3. `audio_jobs`: `id`, `session_id`, `revision`, `activity`, `status`, `idempotency_key`, `request JSONB`, `result JSONB`, `error_code`, `created_at`, `updated_at`. Estados `quoted → authorized → queued → running → succeeded|failed|cancelled`.
4. `audio_revisions`/eventos: `session_id`, `revision`, `actor`, `operation`, `before/after` ou patch, `created_at`. Checagem de concorrência por `If-Match`/`revision`.
5. Ledger do tokenizador existente: reserva, captura e estorno relacionados a `job_id` único. Armazenar custo real por unidade técnica e conversão para tokens com versão da tabela de preços.

Validar documento no servidor: clipes dentro da duração, `source_offset_ms >= 0`, limites de ganho, automação ordenada, faixa/asset pertencentes à conta e versão conhecida. Preservar os arquivos originais; cortes e fades são não destrutivos até o render.

## API proposta (`/studio/api/audio`)

| Rota | Objetivo |
| --- | --- |
| `GET/POST /sessions` | Listar por projeto; criar sessão pessoal ou vinculada ao projeto. |
| `GET/PATCH /sessions/{id}` | Ler/salvar documento com revisão otimista e permissões de conta/projeto. |
| `POST /sessions/{id}/assets/upload-init` e `/upload-complete` | Upload direto controlado, validação de MIME/tamanho/hash, inspeção assíncrona. |
| `GET /sessions/{id}/assets` | Biblioteca, duração, canais e URLs temporárias de escuta/waveform. |
| `POST /sessions/{id}/quotes` | Orçar atividade e retornar `quote_id`, faixa de tokens, expiração e condições. |
| `POST /sessions/{id}/jobs` | Confirmar `quote_id`, reservar tokens e enfileirar com `Idempotency-Key`. |
| `GET /sessions/{id}/jobs/{job_id}` | Estado, progresso, erro seguro e asset/patch de resultado. |
| `POST /sessions/{id}/agent/proposals` | Receber pedido textual, contexto da revisão e escopo; devolver payload estruturado e orçamento, sem executar. |
| `POST /sessions/{id}/agent/proposals/{id}/apply` | Validar revisão/escopo; aplicar patch local gratuito ou criar job pago autorizado. |
| `POST /sessions/{id}/preview` e `/exports` | Render de trecho ou mix final; custo e formato aprovados antes de enfileirar. |

Usar CSRF e sessão do Studio nas mutações, limites por conta, logs de auditoria e respostas de erro estáveis (`insufficient_tokens`, `stale_revision`, `asset_not_ready`, `invalid_scope`, `processing_failed`). Nunca devolver chave de fornecedor ao navegador.

## Contrato da timeline e processamento

- Clipe: `asset_id`, `track_id`, `timeline_start_ms`, `duration_ms`, `source_offset_ms`, `source_duration_ms`, `gain_db`, `fade_in_ms`, `fade_out_ms`, `speed=1`, `status`. Drag de corpo muda apenas início; drag de borda ajusta início/duração/offset sem extrapolar o arquivo. Divisão cria dois clipes referenciando o mesmo asset com offsets complementares. Separar move o clipe para outra faixa.
- Faixa: tipo, ordem, ganho, mute/solo e curvas de automação em tempo da sessão. Ducking de música deve ser curva editável, não apenas um único ganho global. Ondas são derivadas do arquivo real (picos por resolução), armazenadas para zoom e sincronizadas aos offsets.
- Prévia e export usam o mesmo motor de mixagem para evitar divergência. Reamostrar explicitamente, aplicar ganho/fades/automação, limitar pico e medir LUFS/true peak. Presets iniciais: WAV 48 kHz estéreo e MP3 320 kb/s; metas de loudness configuráveis por destino, sem normalização oculta.
- A locução nasce de bloco de roteiro com versão do texto, voz escolhida e duração alvo. Ao regerar, criar novo asset e oferecer substituir clipe mantendo posição ou inserir em nova faixa. Texto aprovado permanece intacto até o usuário aceitar revisão.

## Agente e tokenizador

O agente recebe um payload limitado: `session_id`, `revision`, `project/brand_context`, bloco ou intervalo selecionado, trechos relevantes do roteiro, metadados dos clipes, faixas/automação e intenção do usuário. Não incluir URLs privadas, arquivos completos nem histórico irrelevante no prompt. A resposta deve obedecer schema com `intent`, `scope`, `operations[]`, `assumptions`, `warnings`, `estimated_tokens`, `preview_available`; operações aceitas por allowlist (por exemplo `script.rewrite`, `voice.generate`, `track.automation`, `audio.denoise`, `transcript.create`). Revalidar cada operação no servidor antes de aplicar.

Fluxo pago: calcular orçamento servidor-side por atividade e insumos reais → apresentar tokens estimados ao usuário → confirmar `quote_id` → reservar saldo com chave idempotente → executar em fila → registrar consumo real (incluindo entrada/saída LLM e serviços de áudio) → capturar diferença/estornar reserva → anexar resultado à sessão. Falha, cancelamento ou timeout têm estorno/reconciliação; retries não debitam duas vezes. Guardar discriminação interna de custo e tokens, mas mostrar ao cliente só descrição da atividade e débito consolidado. Definir limites máximos de gasto e timeout por job.

## Ordem de entrega

1. Persistência/autorização de sessão e projeto, upload, leitura de áudio e waveform real; ligar seletor à sessão. Testes de isolamento entre contas e revisão concorrente.
2. Timeline não destrutiva persistida, preview do trecho e export real; testes de precisão de corte, offset, fades, automação, LUFS e formatos.
3. Orçamento/reserva/captura/estorno no tokenizador e fila de jobs; testes de idempotência, falha e saldo insuficiente.
4. Criação de voz, música, efeitos e transcrição, cada uma com quote e revisão de resultado. Não expor nomes de tecnologia na UI.
5. Agente contextual com payload estruturado, proposta revisável, aplicação segura e histórico; testes de comandos ambíguos, escopo incorreto e alterações de texto aprovado.

Critério de pronto: em desktop e tablet, o usuário abre um projeto no Studio, edita e salva roteiro/timeline, pré-escuta a composição, aprova um custo em tokens antes de qualquer job pago, acompanha processamento, compara revisões e exporta um arquivo cuja duração e medição correspondem à prévia. Nenhum fluxo depende de mock local para salvar ou cobrar.
