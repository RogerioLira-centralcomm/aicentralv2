# Cadu Skills — arquitetura inicial

## Contrato de URLs e navegação

- Skill aberta do Cadu: `/skills/<slug>` — pública, indexável e estável.
- Skill catalogada de terceiros: `/skills/diretorio/<slug>` — pública, indexável e estável.
- Skill premium personalizada: `/skills/s/<token>` — acessível somente por link, não enumerável, revogável e limitada a visualização ou execução autenticada.

O slug público não muda quando o título editorial muda. Links premium usam token aleatório e somente o hash é armazenado. A navbar global nasce em `output/mockups/cadu-platform.html`; cada aplicação mantém sua própria sidebar e pode operar em URL independente.

## Decisão de produto

O Cadu Skills terá duas superfícies claramente separadas:

1. **Marketplace público:** catálogo, busca, categorias, página detalhada, exemplos limitados, origem e explicação de instalação. Não exige login e não executa modelos.
2. **Studio de Skills:** criação, personalização por cliente/marca/projeto, teste ao lado, versionamento e publicação. Exige login, plano mensal ativo e saldo de créditos.

O marketplace cria descoberta. O Studio entrega valor recorrente. Não haverá teste grátis de modelo escondido na área pública.

## O que aproveitamos em vez de começar do zero

### Dentro da CentralX

- O Smart Planner já separa planejamento em 11 instruções: verdade da campanha, estratégia, estimativas, one page, defesa, mídia, execução, consistência, canvas e imagem.
- `planner_full_media_v2` já determina fechamento de percentuais/verba, justificativa por canal, fases do voo e projeções.
- `crm_v3_canais.py` já fornece o catálogo vivo de canais com grupo, tipo, alcance, viewability, mínimo, formatos, segmentações e diferenciais.
- `creative_skills/loader.py` já implementa o princípio certo: carregar só as skills necessárias à intenção, nunca o catálogo inteiro.
- `openrouter_service.py` já suporta `openai/gpt-4o-mini` e credenciais OpenAI/OpenRouter.
- `cadu_client_plans` já guarda limites e consumo mensal de tokens/imagens. Deve ser fonte de elegibilidade, mas não substitui um ledger por execução.

### Padrões do mercado

- O formato aberto `SKILL.md` é simples, portável e favorece instruções curtas com referências carregadas sob demanda.
- Skills maduras separam instrução, scripts determinísticos, referências e assets. Conhecimento vivo não deve ser colado em um prompt monolítico.
- Compartilhamento de equipe funciona melhor com uma versão publicada e imutável; rascunhos continuam editáveis e publicações posteriores criam novas versões.
- O catálogo pesquisado no skills.sh traz muita amplitude, mas pouca garantia editorial. A vantagem do Cadu deve ser curadoria, contexto brasileiro de mídia e dados próprios da agência.

Fontes de pesquisa: [skills.sh](https://www.skills.sh/), [Agent Skills — Claude](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview), [Agent Skills — Anthropic Engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills), [Awesome Agent Skills](https://github.com/VoltAgent/awesome-agent-skills).

## Primeira skill: Planejamento de mídia Cadu

```text
aicentralv2/cadu_skills/
└── media-planning/
    ├── SKILL.md
    ├── references/
    │   ├── channels.csv          snapshot gerado do banco
    │   ├── channel-data.md       contrato e regras de atualização
    │   └── brand-context.md      campos da personalização
    └── scripts/
        └── export_channels.py    exportação determinística
```

O `SKILL.md` contém somente o método de planejamento e as invariantes. O CSV é referência factual e substituível. Dados de marca/projeto entram como contexto de execução, sem criar uma cópia integral da skill a cada cliente.

## Modelo de domínio proposto

| Entidade | Função | Campos essenciais |
| --- | --- | --- |
| `skill_definitions` | identidade estável da skill | `id`, `slug`, `owner`, `visibility`, `status` |
| `skill_versions` | publicação imutável | `skill_id`, `version`, `manifest`, `system_prompt`, `model`, `credit_cost`, `published_at` |
| `skill_customizations` | camada cliente/marca/projeto | `skill_version_id`, `client_id`, `brand_id`, `project_id`, `context_json`, `created_by` |
| `skill_shares` | link público revogável | `customization_id`, `token_hash`, `permission`, `expires_at`, `revoked_at` |
| `skill_runs` | execução auditável | `id`, `customization_id`, `user_id`, `model`, `status`, `input`, `output`, `usage`, `created_at` |
| `credit_ledger` | verdade financeira append-only | `id`, `client_plan_id`, `run_id`, `kind`, `amount`, `idempotency_key`, `created_at` |

`kind` no ledger: `reserve`, `capture`, `release`, `refund`, `monthly_grant`, `adjustment`. Nunca debitar apenas incrementando um contador depois da chamada: duas requisições simultâneas poderiam gastar o mesmo saldo.

## Personalização por cliente, marca e projeto

A personalização deve ser uma camada de contexto sobre uma versão publicada:

- **Cliente:** segmento, objetivos de negócio, praças, políticas e fontes autorizadas.
- **Marca:** posicionamento, tom, produtos, públicos, identidade, palavras obrigatórias/proibidas e ativos.
- **Projeto:** briefing, verba, período, metas, aprovações, canais permitidos e entregáveis.
- **Skill:** modelo, custo, limites de entrada, prompts iniciais e contrato de saída.

Na UI, a agência escolhe a skill-base, informa esses campos, pré-visualiza a composição e publica. O link compartilhado mostra descrição, versão, responsável e exemplos; a execução continua exigindo um usuário autorizado e créditos do cliente proprietário.

## Laboratório pago

Modelo inicial fixo: `openai/gpt-4o-mini`, via o serviço já existente. O navegador nunca escolhe ou envia o model ID.

Fluxo transacional:

1. validar sessão, cliente e plano ativo;
2. validar permissão sobre a skill/customização;
3. calcular custo fixo da versão e bloquear se saldo insuficiente;
4. criar `skill_run` e reservar créditos na mesma transação;
5. executar o modelo com limite de entrada/saída;
6. capturar a reserva em sucesso; liberar em falha técnica;
7. registrar tokens e custo do provedor para auditoria, sem alterar retroativamente o preço em créditos mostrado ao usuário.

O teste deve oferecer 3 a 5 prompts curtos e um campo limitado. Antes de enviar, a interface mostra “Este teste usa N créditos” e o saldo restante. Sem saldo, o botão fica bloqueado com ligação para planos/recarga.

## Segurança e compartilhamento

- Tokens públicos ficam apenas como hash no banco; o valor bruto aparece uma vez na URL.
- Links podem ser revogados, expirar e ter permissão `view` ou `run`.
- `view` pode ser público; `run` sempre pede login e vínculo com um plano elegível.
- Prompts, respostas e arquivos herdam o `client_id`; nenhuma busca pode atravessar clientes.
- Versões publicadas são imutáveis para que um link de equipe não mude silenciosamente.

## Entregas em fases

### Fase 1 — fundação (agora)

- formato nativo `SKILL.md`;
- skill inicial de planejamento de mídia;
- exportador e snapshot dos 34 canais ativos;
- documentação de arquitetura e contratos.

### Fase 2 — marketplace público

- catálogo inicial de 100 referências pesquisadas;
- detalhe de cada skill e destaque da Skill do Cadu;
- busca, filtros e SEO; nenhuma chamada de modelo.

### Fase 3 — Studio autenticado

- editor de personalização por cliente/marca/projeto;
- versionamento e link compartilhável;
- prompts de demonstração com `gpt-4o-mini`.

### Fase 4 — créditos e publicação

- ledger, reserva/captura/estorno e idempotência;
- limites por plano e auditoria;
- publicação interna para toda a agência e futura instalação direta.

## Critérios para avançar

- confirmar se créditos serão uma unidade nova ou conversão visível dos `tokens_monthly_limit` atuais;
- definir quem pode publicar uma skill para toda a agência;
- definir se links públicos podem mostrar dados de marca ou somente uma versão sanitizada;
- validar o snapshot de canais com Comercial antes de tratá-lo como fonte oficial.
