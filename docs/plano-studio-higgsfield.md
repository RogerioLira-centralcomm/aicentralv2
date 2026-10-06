# Studio · Higgsfield como motor de criação e edição — plano

Data: 2026-10-02 · Situação: planejamento, nada implementado.

## 1. O que já existe

- **Credencial:** o provedor `higgsfield` já está em `services/integration_credentials.py`
  (segredo `api_key`; públicos `workspace_id` e `default_model`), gravado **criptografado (Fernet) no
  PostgreSQL**, com fallback para `HIGGSFIELD_API_KEY` no ambiente. Tela: `/parametros/integracoes`
  (`integration_settings_routes.py`, PUT `/api/integrations/higgsfield` + validação).
- **Uso atual:** só um payload de vídeo "pronto para Higgsfield" (`build_higgsfield_payload`,
  `prepare_higgsfield`) que não chama a API.
- **Motor atual do Studio:** gpt-image-2 (OpenAI direto, OpenRouter de redundância) para criar e editar;
  Seedance 2.5 via OpenRouter para vídeo. Plano de tamanho, máscaras, logo e tipografia por código já
  são independentes do provedor.

## 2. Credencial (antes de tudo)

1. A chave foi colada no chat: **gerar uma nova chave no Higgsfield e revogar a exposta**.
2. Cadastrar a nova em `/parametros/integracoes` → Higgsfield (fica criptografada no banco; não vai para o
   repositório nem para `.env` versionado).
3. O SDK `higgsfield-client` lê a credencial do ambiente (`.env.local` no exemplo). O adaptador vai
   passar a chave vinda de `integration_credentials` explicitamente, sem depender de `.env`.

## 3. Arquitetura

```
studio_create / editor / vídeo
        │  (tarefa: create | edit | video, tamanho do size_plan, referências)
        ▼
   image_router  ── capabilities por modelo (tamanhos, ratios, referências, máscara, preço)
     ├── openai (gpt-image-2)           ← atual
     ├── higgsfield (modelos a definir)  ← novo, via higgsfield_service
     └── openrouter (redundância)
```

- `services/higgsfield_service.py`: wrapper do `higgsfield_client` (submit + polling com timeout,
  cancelamento, erros normalizados como `OpenRouterError`, custo devolvido para cobrança).
- **Tabela de capacidades por modelo**: quais tamanhos/ratios aceita, se aceita imagem de referência,
  máscara de edição, texto legível, duração de vídeo. O `size_plan` passa a consultar essa tabela:
  tamanho exato quando o modelo aceita, enquadramento (`frame`) quando não — a máquina já existe.
- **Roteamento por tarefa com flag**: `CREATIVE_STUDIO_CREATE_ENGINE`, `..._EDIT_ENGINE`,
  `..._VIDEO_ENGINE` (padrão: o motor atual). Fallback automático para o motor atual em erro.
- **Jobs assíncronos**: vídeo (e modelos lentos de imagem) entram como job com polling na UI, em vez de
  segurar a requisição HTTP.

## 4. Onde o Higgsfield pode render mais

| Tarefa | Hoje | Hipótese com Higgsfield |
|---|---|---|
| Vídeo (Seedance 2.5) | OpenRouter | rota direta pelo Higgsfield, com áudio (exemplo enviado) |
| Edição com máscara | gpt-image-2 edit | modelos de edição/inpainting do catálogo Higgsfield |
| Criação de imagem | gpt-image-2 | modelos de imagem do catálogo (comparar fidelidade de layout e de texto) |

**Os modelos exatos do catálogo Higgsfield não estão confirmados** — a fase 0 lista o catálogo pela API
e registra ids, parâmetros e preços antes de qualquer escolha.

## 5. Avaliação antes de trocar o motor

Bancada A/B no lab de máscaras: mesmo briefing + mesma máscara + mesma marca em gpt-image-2 e nos
candidatos Higgsfield, em 6 formatos (feed 4:5, story, 1:1, LinkedIn, 300×250, 728×90). Critérios:
aderência ao layout, texto legível, respeito à margem, fidelidade de marca, custo e latência.
Decisão por tarefa (criar, editar, vídeo), não global.

## 6. Fases

| Fase | Entrega | Aceite |
|---|---|---|
| 0 · 0,5 dia | Nova chave cadastrada; SDK instalado; catálogo e preços listados | tabela de modelos no doc |
| 1 · 1 dia | `higgsfield_service` + validação na tela de integrações | "Validar" verde em `/parametros/integracoes` |
| 2 · 1,5 dia | Vídeo Seedance 2.5 pelo Higgsfield atrás de flag, job assíncrono | vídeo 5 s 16:9 e 9:16 gerado no Studio |
| 3 · 1,5 dia | Roteador de imagem + capacidades + bancada A/B | relatório A/B com 6 formatos |
| 4 · 1 dia | Ativar o vencedor por tarefa; cobrança por modelo | flags no padrão escolhido; débito correto |

## 7. Riscos e decisões

- **Créditos/orçamento:** o saldo do Studio está baixo; a bancada A/B gasta gerações reais nos dois
  provedores. Definir teto de gasto da avaliação.
- **Cota/limite** do Higgsfield (como os 5 img/min do gpt-image-2) — medir na fase 0.
- **Cobrança:** o débito do Studio usa estimativa por modelo (`_estimate`); cada modelo Higgsfield precisa
  do seu custo antes de ir para produção.
- Decisão: começar pelo **vídeo** (ganho claro e isolado) ou pela **edição**?
