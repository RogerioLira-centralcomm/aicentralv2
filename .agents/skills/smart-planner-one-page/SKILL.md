---
name: smart-planner-one-page
description: Gera e revisa a página única do Smart Planner no CentralX — folha de venda para cliente final com criativo no canal, dado de mercado, defesa, logos do CRM e marca apresentadora. Use when working on página única, one page, one-pager, Smart Planner canvas one_page, logos de cliente/agência, CentralComm como apoio, ou os anunciantes Montana Grill, BH Airport, BDMG e Minas Máquinas.
---

# Página única do Smart Planner

Folha de venda para **cliente final**. Agência não é o herói: se o briefing for de agência, escolha um anunciante específico dela e mostre canais úteis para esse anunciante.

Não use voz. Não use a marca "ONE PAGE". Não cite tabela PHP.

## Onde esta skill entra no fluxo

Este arquivo orienta o agente Codex durante revisão, implementação e QA. Ele não é
carregado diretamente pelo servidor em runtime.

O prompt realmente usado na geração é:

`aicentralv2/smart_planner/skills/planner_one_page_v2.md`

Ele é carregado por `generator._one_page_v2()` junto de `planner_truth_v1` e
`planner_estimation_v1`. O fluxo passa por:

```text
processor.py
  -> snapshot.py / build_evidence()
  -> generator.py / pesquisa de mercado
  -> planner_strategy_core_v1
  -> planner_one_page_v2 (esta regra de geração)
  -> one_page.py / cards, mídia e contrato
  -> images.py / assets
  -> editor.py + canvas.html / revisão interna
  -> public_view.py / publicação
```

Não confundir esta skill de orientação com o arquivo runtime `planner_one_page_v2.md`.
Quando uma regra mudar, os dois devem ser atualizados na mesma alteração.

## Anatomia da folha

O cabeçalho é uma camada editorial, não um card: logo e nome do cliente final;
logo da agência, quando houver no CentralX, aparece menor; a marca apresentadora
segue a regra abaixo.

Cada página única tem exatamente quatro cards editoriais, nesta ordem:

1. **Estratégia** — uma frase do projeto/canal para aquele anunciante.
2. **Expressão no canal** — direção visual estática para o canal herói. A geração de imagem acontece depois, por ação do usuário, e nunca bloqueia a geração dos documentos.
3. **Dado de mercado** — número ou leitura de mercado com origem. Sem evidência suficiente, omita o número e use uma leitura qualitativa útil; não mostre “A validar” ao cliente. O ecossistema de canais e a densidade do mix entram como subestrutura deste card, nunca como quinto card.
4. **Defesa** — por que aquele canal interessa ao cliente final.

O quadro público, contato, QR, logos de apoio e fundo são camadas de apresentação,
não novos cards editoriais. A página pública pode reorganizá-los em capítulos sem
alterar o contrato interno.

## Logos no CentralX

Buscar nesta ordem: `cx_clients.logo_url` / `logo_upload_path`, depois `cliente_web_info.logo_url` via `tbl_cliente`. Agência pelo vínculo `tbl_cliente_agencia` ou pelo nome no briefing.

Sem logo, mostre o nome. Não invente URL.

## Marca apresentadora

- **CentralComm como apoio** (padrão): logo pequeno no rodapé. A folha é do anunciante.
- **Outra marca como principal** (Serasa Ads, Amazon, Logan, ou marca do CRM): CentralComm **some** da folha. Regenerar o texto na voz dessa marca.

Persistir em `dados_detectados.presenter_brand`. Trocar a marca chama de novo a geração.

## Schema

Uma seção `id=one_page`. Cards nesta ordem:

| type | title típico | campos |
|---|---|---|
| `strategy` | Estratégia | `body` |
| `creative` | Criativo | `body`, `channel`, `surface` (`ctv`/`portal`/`app`/`display`), `image_url`, `image_prompt` |
| `market` | Mercado | `body`, `stat`, `stat_label` |
| `defense` | Defesa | `body` |

`meta`: `title`, `client`, `agency`, `campaign`, `presenter`.
`branding`: `client`, `agency`, `presenter` (`role`: `support` ou `principal`), `partners`, `hero` (cliente ou, se vazio, agência).
`theme`: `id`, `bg_url`, `ink`, `paper`, `accent`, `density[]`.
`share`: `public_token`, `url`, `path`.

Campos estruturados adicionais do plano:

- `one_page_v2.audience_model`: segmentos, faixa etária, gênero, classe social, região, bairro, universo e impacto. Todo número precisa de fonte; sem fonte, use `null` internamente e omita o dado da página pública.
- `one_page_v2.visual_data`: mostradores e barras somente para valores confirmados ou explicitamente estimados.
- `market` card: `channel_roles[]`, no máximo oito itens, com `id`, `label`, `logo`, `role`, `status` (`confirmed` ou `proposed`) e `count` somente quando confirmado.
- `public_design`: skin, tokens, referência CRM e hero com estado `draft`, `approved` ou `requested`.
- `asset_manifest[]`: assets de `creative`, `background`, `persona` e `place`, sempre com URL, prompt e status.
- `executive_contact`: contato normalizado; telefone ausente oculta o CTA de WhatsApp.

Planos antigos sem esses campos continuam válidos. O leitor deve usar fallback
seguro e nunca fazer backfill inventando informação.

Código extra: `theme.py` (família de mercado), `images.py` (GPT Image 2 / OpenRouter), `share.py` (link público + QR).

## Geração

1. Resolver cliente final e agência. Se só houver agência, só escolher um anunciante quando houver vínculo explícito no CRM, no briefing ou em fixture aprovada; caso contrário, parar em “anunciante a confirmar”.
2. Casar com um pitch conhecido ou redigir strategy / creative / market / defense.
3. Anexar logos reais. Se `presenter_brand != centralcomm`, omitir CentralComm e reescrever.
4. Pesquisar mercado antes da síntese quando não houver pesquisa persistida; preservar fonte, data e status de validação.
5. Modelar audiência sem inferir demografia ou alcance. Lacunas ficam como `null` e estado interno; não mostrar “A validar” ao cliente.
6. Preparar direção visual e prompt contextual. Não gerar imagem durante “Gerar documentos”. A imagem é criada depois por ação explícita do usuário e gravada no `asset_manifest` quando existir.
7. Não inventar verba, KPI, audiência, logo, praça, bairro ou canal.

Conteúdo capturado só entra nos prompts quando
`usar_conteudo_capturado_documentos=true`. Ele é apoio opcional, não verdade
confirmada, e nunca autoriza preço, inventário, fornecedor ou promessa comercial.

## Pontos de OOH recebidos no briefing

Quando o executivo colar uma lista de pontos ou enviar uma imagem cuja leitura
traga pontos de OOH, o Smart Planner deve guardá-la como `inventario_ooh` na
referência do briefing. A ordem e o texto de cada ponto são preservados. Isso
inclui OOH no plano, mas não autoriza inferir fornecedor, disponibilidade, preço,
alcance ou compra. A página única e o link público falam apenas em presença OOH;
o plano completo interno inclui o bloco `Pontos OOH informados`.

## Regras comerciais e de evidência

- Verba só aparece se confirmada na revisão ou no snapshot.
- Sem verba, não escrever investimento, percentual financeiro, CPM, alcance,
  impressões, CTR, conversões ou ROI como fato.
- Pesquisa de mercado complementa o briefing; nunca sobrescreve anunciante,
  agência, período, verba, canais ou objetivo confirmados.
- `confirmed` é dado da mesa e `proposed` é hipótese editorial. `a_validar` pode
  existir apenas como estado interno legado; nunca aparece como texto na página
  pública ou no PDF. Sem evidência, omita o número.
- Logos só vêm do catálogo/CRM. Imagem gerada nunca deve desenhar logo legível.
- Trocar skin altera apenas apresentação. Trocar marca apresentadora só regenera
  texto quando o usuário explicitamente pede uma marca principal.

## Performance, custo e QA

- Reutilizar `snapshot`, `market_research`, `strategy_core` e `one_page_v2` quando
  `material_hash` não mudou.
- Registrar custo real e tokens por chamada; a prévia em reais é interna, sem
  margem e fora do consumo comercial do Planner.
- A etapa `market` aparece no progresso e na prévia de custo quando executada.
- Validar os quatro cards, canais permitidos, confidencialidade e ausência de
  números inventados antes de publicar. Regras de OOH/Places validam afirmações
  comerciais completas, nunca palavras isoladas. “Intenção de compra”, “compras
  de imóveis” e “jornada de compra” são descrições válidas de público.
- Se o revisor encontrar linguagem comercial indevida, ele deve devolver o
  documento corrigido. A geração só para por quebra estrutural irrecuperável;
  não para por vocabulário que possa ser corrigido automaticamente.
- Testar pelo menos: BDMG, Confins, plano sem verba, plano sem logo, mais de oito
  canais, plano antigo sem os novos campos e ausência de telefone do executivo.

Código: `aicentralv2/smart_planner/one_page.py`, `logos.py`. Quadro: `templates/smart_planner/canvas.html` + `static/js/smart_planner/canvas.js`.

## Exemplos

Pitches iniciais e o briefing do João: [examples.md](examples.md).
