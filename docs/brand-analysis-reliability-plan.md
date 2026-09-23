# Plano definitivo de confiabilidade da análise de marcas

Status: P0 e núcleo de P1/P2 implementados; runner de conjunto-ouro/shadow mode implementado; P3–P5 dependem de rotulagem humana, volume e rollout
Base de diagnóstico: Cemig, BDMG, Centralcomm, Banco Mercantil e UNIDAS
Pipeline atual: `brand-analysis-pipeline-v7-2026-09`

## Implementação realizada

O primeiro incremento de segurança já está aplicado:

- confiança dimensional ausente recebe fallback determinístico baseado na proveniência;
- proveniência verificada ou parcial sem confiança explícita recebe cálculo conservador;
- arquivos visuais inválidos são isolados sem interromper a análise web ou outros ativos;
- publicação automática é recusada abaixo do gate ou com versão de score incompatível;
- versões dos scores foram elevadas para `brand-readiness-v3-2026-09` e `brand-analysis-v3-2026-09`;
- fontes repetidas no histórico são deduplicadas por URL;
- completude do perfil, cobertura de evidências e prontidão para publicação passam a existir como métricas separadas;
- cada snapshot persiste os 39 metadados em `cadu_workspace_brand_identity_fields`, inclusive `not_found` e `blocked`;
- testes automatizados cobrem confiança ausente, ativo inválido, gate mínimo, versão de score e persistência por campo.
- a proveniência foi ampliada para identidade, público, mercado, campanhas, visual, presença e governança;
- o fallback do revisor central publica consenso somente quando os campos essenciais foram aceitos por todos os pareceres disponíveis;
- números contínuos sem formatação humana deixaram de ser aceitos como telefone público;
- uma migração aditiva passou a versionar categoria, origem, motivo, componentes de confiança e evidências por campo;
- snapshots passam a registrar pipeline, contrato, score e hash de evidências;
- as migrações da auditoria de marca foram ligadas ao fluxo controlado de deploy.

Os itens restantes exigem aplicação controlada da migração, shadow mode, conjunto ouro e rollout gradual; não devem ser ativados diretamente em produção sem os critérios definidos neste documento.

O comando read-only `scripts/brand_reliability_shadow.py` exporta a base do
conjunto-ouro e avalia snapshots sem alterar o perfil ativo. Por padrão ele
isola a versão vigente do pipeline; versões anteriores só entram quando
informadas explicitamente. A decisão é sempre `hold` se faltar amostra rotulada
ou qualquer SLO estiver fora do limite.

```bash
.venv/bin/python scripts/brand_reliability_shadow.py template --brand-id 29 --output output/brand-golden-template.json
.venv/bin/python scripts/brand_reliability_shadow.py evaluate --golden data/brand-golden.json --output output/brand-shadow-report.json
```

## 1. Objetivo

Transformar a auditoria de marcas em um pipeline automático, rastreável e seguro para publicação, com as seguintes garantias:

- pelo menos 99% das execuções encerradas automaticamente, sem ficar em estado indefinido;
- pelo menos 99% de precisão nos valores publicados como fatos;
- 100% dos campos aplicáveis com estado explícito, inclusive quando não houver evidência;
- 100% dos fatos publicados ligados a evidência reproduzível;
- nenhuma aprovação abaixo do gate vigente;
- nenhuma falha isolada de arquivo, modelo ou fonte capaz de apagar resultados válidos das demais etapas;
- custo controlado por reaproveitamento de coleta, execução incremental e repetição apenas do módulo defeituoso.

“100% completo” significa que todo campo foi processado e classificado. Não significa preencher todo campo com um valor. Quando a informação não existir, o resultado correto será `not_found`, `not_applicable`, `conflicting` ou `blocked`, nunca uma inferência apresentada como fato.

## 2. Indicadores oficiais

Os indicadores atuais devem ser separados. O nome genérico “cobertura” não poderá representar métricas diferentes.

| Indicador | Definição | Meta |
|---|---|---:|
| `run_completion_rate` | Execuções encerradas como `published`, `partial`, `blocked` ou `failed_terminal` | >= 99% |
| `field_processing_rate` | Campos aplicáveis com estado explícito | 100% |
| `published_fact_precision` | Fatos publicados confirmados no conjunto ouro | >= 99% |
| `published_provenance_rate` | Valores publicados com evidência válida | 100% |
| `unsafe_publication_rate` | Publicações em desacordo com o gate | 0% |
| `empty_confidence_rate` | Campos processados sem confiança calculada | 0% |
| `false_contact_rate` | Telefones, e-mails e endereços falsos publicados | < 0,1% |
| `stable_rerun_rate` | Campos invariáveis preservados sem mudança de fonte | >= 98% |
| `isolated_retry_rate` | Falhas recuperadas sem repetir todo o pipeline | >= 95% |
| `manual_review_rate` | Execuções que realmente exigem decisão humana | <= 1% após calibração |

## 3. Estados canônicos

Todo campo deve terminar em exatamente um estado:

| Estado | Significado | Pode publicar? |
|---|---|---:|
| `verified` | Evidência direta, válida e suficiente | Sim |
| `probable` | Evidência forte, mas parcialmente inferida | Apenas como hipótese identificada |
| `partial` | Informação incompleta ou pouco sustentada | Não |
| `conflicting` | Fontes válidas divergem | Não |
| `not_found` | Coleta concluída sem resultado | Não, mas conta como processado |
| `not_applicable` | Campo não se aplica à marca | Não, mas conta como processado |
| `invalid` | Valor ou evidência em formato inválido | Não |
| `blocked` | Risco conhecido de publicação incorreta | Não |

Estados do run:

| Estado | Definição |
|---|---|
| `collecting` | Fontes e ativos em coleta |
| `extracting` | Extrações determinísticas e por modelo em andamento |
| `normalizing` | Candidatos sendo reconciliados com evidências |
| `reviewing` | Conflitos materiais sendo avaliados |
| `published` | Todos os campos publicáveis foram promovidos |
| `partial` | Campos seguros publicados e demais campos classificados |
| `blocked` | Nenhum conjunto mínimo seguro pôde ser publicado |
| `failed_terminal` | Falha técnica irrecuperável, com motivo e checkpoint preservados |

`insufficient_evidence` deixa de ser um estado genérico. A insuficiência passa a existir por campo.

## 4. Arquitetura-alvo

```text
Entrada validada
  -> inventário de fontes
  -> coleta resiliente por fonte
  -> extração determinística
  -> extração semântica modular
  -> normalização por campo
  -> resolução visual
  -> cálculo determinístico de confiança
  -> detecção de conflitos
  -> revisão apenas dos conflitos materiais
  -> gate de publicação por campo
  -> snapshot imutável
  -> projeção para brand_profile
  -> monitoramento e revalidação incremental
```

Princípios:

1. Evidência é a fonte de verdade; modelos propõem candidatos.
2. Confiança é calculada pelo sistema, não declarada livremente pelo modelo.
3. A aprovação é por campo, não por documento inteiro.
4. O perfil ativo é uma projeção do último snapshot publicado.
5. Toda execução é reproduzível a partir de versão, entradas, fontes e hashes.
6. Uma falha local produz degradação local.
7. Reexecuções não podem regredir campos válidos sem evidência nova.

## 5. Categorias e política dos metadados

| Categoria | Campos | Evidência mínima para `verified` |
|---|---|---|
| Identidade | `name`, `sector`, `website_url`, `brand_summary`, `tone_of_voice` | Página oficial e trecho direto; nome e site também podem usar metadado canônico do domínio |
| Público | `target_audience`, `audience_segments`, `personas`, `archetype`, `ad_segments` | Público declarado ou repetição consistente em oferta e comunicação; persona e arquétipo permanecem hipótese salvo declaração explícita |
| Oferta e mercado | `products_services`, `differentiators`, `proof_points`, `competitors` | Produto/serviço em fonte oficial; diferencial precisa de prova; concorrente exige fonte externa verificável e justificativa |
| Campanhas | `campaigns`, `campaign_opportunities` | Campanha observada exige peça ou página nomeada; oportunidade gerada deve usar tipo próprio |
| Sistema visual | `logo_url`, `primary_color`, `secondary_color`, `color_palette`, `product_palettes`, `fonts`, `visual_motifs`, `mandatory_elements`, `forbidden_elements`, `creative_guidelines`, `visual_opinions` | Ativo first-party, manual, CSS recorrente ou consenso visual com titularidade resolvida |
| Presença pública | `contacts`, `addresses`, `digital_policies`, `social_links` | Valor explícito em página first-party e contexto humano compatível |
| Governança | `sources`, `evidence_ledger`, `field_provenance`, `confidence`, `quality_dimensions`, `review_evidence_summary`, `output_packages`, `analysis_metadata` | Gerados pelo pipeline e validados por schema |

Campos derivados devem ser marcados:

- `observed`: encontrado diretamente;
- `computed`: calculado deterministicamente;
- `inferred`: hipótese do modelo;
- `generated`: recomendação ou oportunidade criada pelo sistema;
- `human`: fornecido ou confirmado por uma pessoa.

## 6. Modelo de evidência

Cada afirmação deve apontar para um registro imutável de evidência:

```json
{
  "evidence_id": "ev_...",
  "source_url": "https://...",
  "canonical_url": "https://...",
  "source_type": "official_page|manual|css|image|social|external_market|human_upload",
  "authority": "first_party|regulator|trusted_third_party|unknown",
  "captured_at": "ISO-8601",
  "content_hash": "sha256:...",
  "excerpt": "trecho que comprova o valor",
  "asset_id": null,
  "market": "BR",
  "language": "pt-BR",
  "status": "valid|stale|invalid|conflicting"
}
```

Regras:

- deduplicar por URL canônica mais hash;
- preservar redirects e URL original;
- contar fontes distintas, não itens repetidos no array;
- guardar o trecho exato usado pelo campo;
- registrar expiração conforme o tipo da informação;
- nunca reutilizar uma URL sem trecho como prova;
- não tratar uma fonte externa como prova de identidade visual sem confirmação first-party.

## 7. Confiança determinística por campo

A pontuação deve ser calculada em escala de 0 a 1:

```text
confidence = clamp(
    authority * 0.30
  + directness * 0.25
  + corroboration * 0.15
  + freshness * 0.10
  + extractor_agreement * 0.10
  + format_validity * 0.10
  - penalties,
  0,
  1
)
```

| Componente | Regra resumida |
|---|---|
| `authority` | Manual/site oficial = 1; regulador = 0,95; terceiro confiável = 0,70; desconhecido = 0,20 |
| `directness` | Trecho afirma o valor = 1; associação indireta = 0,50; mera presença na página = 0,20 |
| `corroboration` | Duas ou mais fontes independentes e coerentes = 1 |
| `freshness` | Calculada por tipo de campo e data da captura |
| `extractor_agreement` | Extrator determinístico e semântico concordam = 1 |
| `format_validity` | Valor passa validadores específicos = 1 |

Penalidades obrigatórias:

| Situação | Penalidade ou teto |
|---|---:|
| Conflito entre fontes oficiais | -0,25 e estado `conflicting` |
| Somente inferência de modelo | teto 0,49 |
| Upload humano sem titularidade confirmada | teto 0,69 |
| Fonte externa sem confirmação first-party | teto 0,59 |
| Evidência sem trecho | confiança 0 |
| Campanha transitória usada como identidade | estado `blocked` |
| Formato inválido | estado `invalid` |

Faixas:

- `verified`: confiança >= 0,85;
- `probable`: 0,70 a 0,849;
- `partial`: 0,50 a 0,699;
- `blocked`: abaixo de 0,50 quando há valor candidato;
- `not_found`: nenhum candidato após coleta bem-sucedida.

O modelo pode sugerir os componentes, mas o backend valida limites, evidências e cálculo final.

## 8. Gate de publicação

A publicação deve ocorrer por campo.

Um campo será publicado automaticamente somente se:

1. tiver estado `verified`;
2. tiver confiança >= 0,85;
3. tiver pelo menos uma evidência válida;
4. cada evidência possuir URL ou ativo persistido e trecho/descrição verificável;
5. não estiver em conflito;
6. passar pelo validador específico do tipo;
7. tiver sido produzido pela mesma versão de contrato usada no gate;
8. não representar regressão em relação ao perfil ativo sem evidência mais nova ou mais forte.

Campos mínimos para uma marca operacional:

- `name`;
- `website_url` ou uma origem humana confirmada;
- `brand_summary`;
- `target_audience`;
- ao menos um `products_services`;
- ao menos uma evidência para cada campo publicado.

Logo, paleta e tipografia são gates para produção visual, mas não precisam impedir a publicação da identidade textual. O sistema deve expor duas prontidões separadas:

- `strategy_readiness`;
- `visual_production_readiness`.

## 9. Correções obrigatórias no fluxo atual

### 9.1 Confiança e proveniência

- Tornar obrigatório o objeto `confidence` na normalização.
- Rejeitar respostas que não passem pelo schema.
- Quando a resposta do modelo falhar, calcular confiança a partir das evidências já coletadas.
- Persistir uma linha por campo em `cadu_workspace_brand_identity_fields`.
- Proibir confiança zero implícita; zero deve conter `reason_code`.
- Cobrir todos os metadados, não apenas os 19 campos atuais de `field_provenance`.

### 9.2 Coleta

- Canonicalizar URLs e remover duplicidades.
- Registrar sucesso, bloqueio, timeout e erro por fonte.
- Implementar orçamento por domínio e prioridade.
- Isolar arquivos inválidos; a UNIDAS não poderia perder a análise web por causa de uma imagem.
- Manter checkpoint depois de cada fonte e módulo.
- Reaproveitar coleta quando URL, hash, versão e política de validade não mudarem.

### 9.3 Contatos e endereços

- Validar telefones brasileiros por DDD, quantidade de dígitos e tipo de número.
- Exigir rótulo semântico próximo: telefone, SAC, WhatsApp, central ou ouvidoria.
- Rejeitar CNPJ, CEP, datas, coordenadas, IDs e sequências presentes em URLs.
- Deduplicar números após normalização E.164.
- Validar e-mails e domínio.
- Separar múltiplos endereços em registros independentes.

### 9.4 Sistema visual

- Validar MIME pelos bytes, não apenas por extensão.
- Separar logo, favicon, parceiro, selo, plataforma e imagem promocional.
- Guardar titularidade e papel de cada ativo.
- Calcular recorrência de cor por ativo e superfície.
- Não identificar família tipográfica apenas pela aparência.
- Tratar upload humano como candidato prioritário, não como confirmação automática.
- Exigir resolução explícita quando upload e domínio oficial divergirem.

### 9.5 Revisores

- Revisores deixam de definir a confiança base.
- Eles recebem somente campos com conflito, baixa concordância ou alto risco.
- Falha de um revisor dispara retry daquele módulo.
- Falha do revisor central usa consenso determinístico; não reduz todo o dossiê a 0,35.
- `ready` não pode coexistir com bloqueio material sem explicação estruturada.
- `blocked_fields` deve usar objetos `{field, reason_code, evidence_ids}`, não texto livre.

### 9.6 Score e interface

- Substituir o score único por quatro indicadores:
  - completude do processamento;
  - cobertura de evidências;
  - prontidão estratégica;
  - prontidão visual.
- Nunca mostrar perfil antigo e auditoria nova sob o mesmo rótulo de cobertura.
- Exibir claramente `perfil ativo`, `última auditoria` e `alterações propostas`.
- Mostrar fontes canônicas distintas.
- Identificar oportunidades geradas separadamente de campanhas observadas.

## 10. Persistência e versionamento

### Tabelas

1. Completar `cadu_workspace_brand_identity_fields` com:

- `field_category`;
- `value_hash`;
- `value_origin`;
- `reason_code`;
- `confidence_components` JSONB;
- `evidence_ids` JSONB;
- `pipeline_version`;
- `contract_version`;
- `score_version`;
- `supersedes_field_id`;
- `expires_at`.

2. Criar `cadu_workspace_brand_evidence` para evidências normalizadas.

3. Criar `cadu_workspace_brand_snapshots` para snapshots imutáveis e decisão final.

4. Manter `brand_profile` como projeção de leitura rápida, nunca como única fonte de verdade.

### Versionamento

Toda decisão deve registrar:

- `pipeline_version`;
- `contract_version`;
- `score_version`;
- modelos e versões;
- hash dos prompts;
- hash das entradas;
- hash das evidências;
- data do gate;
- motivo de publicação ou bloqueio.

Uma reavaliação deve sempre usar explicitamente uma versão de score. Resultados produzidos por regra antiga não podem aparecer como aprovados pela regra atual.

## 11. Recuperação e idempotência

- Cada estágio grava um checkpoint transacional.
- A chave de idempotência inclui marca, entrada, versão e estágio.
- Retry reaproveita estágios concluídos.
- Um worker antigo não pode sobrescrever snapshot mais novo.
- Mudança de fonte invalida somente os campos dependentes dela.
- Mudança de prompt ou score reavalia sem repetir coleta.
- Mudança de contrato executa migração explícita.
- Falha após publicação não reverte o perfil ativo.

## 12. Testes

### Testes unitários

- confiança e penalidades;
- transições de estado;
- canonicalização de URL;
- deduplicação de fontes;
- validadores de telefone, e-mail, endereço, cor e ativo;
- gate por campo;
- prevenção de regressão;
- versionamento e reavaliação.

### Testes de contrato

- todas as respostas dos modelos validadas por JSON Schema;
- ausência de `confidence` deve produzir fallback determinístico;
- campos desconhecidos devem ser rejeitados ou preservados em área de extensão;
- `blocked_fields` deve apontar para campos válidos e códigos conhecidos.

### Testes de integração

- site completo sem upload;
- site mais upload válido;
- upload inválido com site válido;
- site indisponível com ativos válidos;
- revisor indisponível;
- normalizador indisponível;
- conflito entre upload e site;
- duas execuções concorrentes;
- reavaliação com score novo;
- análise incremental após mudança de uma página.

### Conjunto ouro

Construir no mínimo 100 marcas:

- 40 com manual e identidade pública;
- 30 com site completo, sem manual;
- 20 com presença incompleta;
- 10 casos adversariais.

Cada marca terá verdade de referência por campo, evidência aceita, evidência rejeitada e motivo.

## 13. Observabilidade

Dashboard por versão de pipeline:

- conclusão por estágio;
- duração e custo por estágio;
- taxa de JSON inválido por modelo;
- campos por estado;
- confiança média e distribuição;
- fontes por autoridade;
- retries e fallbacks;
- campos publicados, bloqueados e regredidos;
- falsos positivos confirmados;
- divergência entre execuções;
- runs com score ou contrato incompatível;
- percentual de dados sem evidência persistida.

Alertas:

- confiança vazia > 0;
- aprovação abaixo do threshold > 0;
- publicação sem evidência > 0;
- erro do mesmo estágio > 2% em 15 minutos;
- diferença superior a 20% entre execuções sem mudança de fonte;
- queda de precisão no conjunto ouro;
- tabela de campos sem registros após run concluído.

## 14. Rollout

### Fase 0 — Congelar regressões

Prazo sugerido: 2 dias.

- bloquear aprovação abaixo do gate;
- impedir confiança vazia;
- isolar arquivos inválidos;
- separar os indicadores na interface;
- adicionar testes para Cemig, BDMG, Banco Mercantil e UNIDAS.

Critério de saída: nenhuma aprovação contraditória e nenhuma execução perdida por falha isolada de ativo.

### Fase 1 — Evidência e confiança por campo

Prazo sugerido: 5 dias.

- implementar schema de evidência;
- preencher `cadu_workspace_brand_identity_fields`;
- implementar score determinístico;
- ampliar proveniência para todos os campos;
- criar snapshots imutáveis.

Critério de saída: 100% dos campos processados possuem estado, confiança, motivo e evidência ou justificativa de ausência.

### Fase 2 — Pipeline resiliente

Prazo sugerido: 5 dias.

- checkpoints por estágio;
- retries isolados;
- cache por hash;
- coleta incremental;
- consenso determinístico em falha de revisão;
- proteção contra worker antigo.

Critério de saída: pelo menos 99% das execuções do conjunto de validação terminam automaticamente.

### Fase 3 — Qualidade visual e dados públicos

Prazo sugerido: 5 dias.

- resolução de titularidade;
- validadores de contato e endereço;
- classificação visual por papel;
- distinção entre identidade e campanha;
- testes adversariais.

Critério de saída: zero falsos positivos críticos no conjunto ouro e precisão global >= 99%.

### Fase 4 — Shadow mode e migração

Prazo sugerido: 7 dias.

- executar pipeline novo sem publicar;
- comparar com produção;
- revisar divergências;
- recalibrar thresholds;
- migrar os perfis existentes;
- liberar publicação automática gradualmente.

Critério de saída: sete dias sem publicação insegura e métricas dentro do SLO.

### Fase 5 — Operação contínua

- 10% das marcas no gate novo;
- depois 25%, 50% e 100%;
- rollback por feature flag;
- revisão semanal de erros e mensal do conjunto ouro;
- revalidação automática por validade da evidência.

## 15. Backlog priorizado

### P0 — obrigatório antes de novas auditorias em escala

1. Validar `confidence` e criar fallback determinístico.
2. Corrigir aprovação abaixo do threshold.
3. Isolar falha de upload.
4. Persistir estado/confiança por campo.
5. Separar completude, evidência e prontidão.
6. Versionar decisões e reavaliações.
7. Corrigir contagem de fontes.

### P1 — necessário para 99% de automação

1. Checkpoints e retries por módulo.
2. Consenso semântico quando o revisor central falhar.
3. Validadores de contatos e endereços.
4. Snapshots imutáveis.
5. Coleta incremental e cache por hash.
6. Gate por campo e prevenção de regressão.

### P2 — qualidade e eficiência

1. Conjunto ouro e calibração contínua.
2. Observabilidade por versão e campo.
3. Expiração diferenciada de evidências.
4. Detecção automática de mudança no site.
5. Priorização adaptativa de fontes.

## 16. Critério definitivo de conclusão

O projeto estará concluído somente quando, em produção controlada:

1. pelo menos 10.000 execuções atingirem `run_completion_rate >= 99%`;
2. 100% dos campos tiverem estado explícito;
3. nenhuma publicação ocorrer sem evidência persistida;
4. nenhuma aprovação ocorrer abaixo do gate vigente;
5. `published_fact_precision >= 99%` no conjunto ouro e na amostra humana de produção;
6. a diferença entre reruns sem mudança de fonte ficar abaixo de 2%;
7. uma falha isolada de fonte, ativo ou modelo não apagar resultados válidos;
8. todas as decisões puderem ser reproduzidas por versão, hashes e evidências;
9. Cemig, BDMG, Centralcomm, Banco Mercantil e UNIDAS passarem novamente pelos cenários que hoje falham;
10. o rollout permanecer sete dias sem incidente crítico antes da ativação em 100%.

## 17. Resultado esperado nas cinco marcas de referência

| Marca | Resultado esperado após correção |
|---|---|
| Cemig | Identidade textual publicada; visual marcado como conflitante até resolução de logo/paleta; nenhuma confiança vazia |
| BDMG | Evidências existentes recalculadas por campo; perfil antigo separado da auditoria atual; nenhum bloqueio global causado por normalização vazia |
| Centralcomm | Fontes canônicas reconhecidas como páginas oficiais; visual parcial sem impedir identidade textual |
| Banco Mercantil | Aprovação antiga incompatível invalidada; somente campos `verified` permanecem publicados; telefones falsos removidos |
| UNIDAS | Ativo inválido rejeitado isoladamente; coleta web e análise textual concluídas normalmente |

Este plano substitui a busca por preenchimento integral pela garantia mais importante: todo dado publicado deve ser correto, rastreável, reproduzível e compatível com a versão vigente do sistema.
