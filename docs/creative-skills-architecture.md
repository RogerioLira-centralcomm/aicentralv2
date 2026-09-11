# Arquitetura de skills — Mesa de Formato CTV

O lab de CTV não é um gerador genérico de imagem. Cada etapa carrega só as skills necessárias. A identidade visual vem da mesa [Marcas](/parametros/modelagem-criativos/marcas): perfil, auditoria, linha criativa e assets.

## Princípio

STRUCTURE > FORMAT > INTERACTION > BRAND > AESTHETICS

Conflito: pedido do usuário > skill de formato > fidelidade visual > regras da marca > UX > estética.

## Routing

| Intent | Packs | Formato |
|--------|--------|---------|
| create / storyboard | create + refine | video-15 ou ctv-qr |
| reconstruct | reconstruct, implement, validate | + referência |
| adapt | create, refine, implement, validate | mesmo formato, outra marca |
| refine | refine, validate | output existente |
| html | implement, validate | spec aprovada |

O orquestrador nunca carrega o catálogo inteiro.

## Responsabilidades

- **orchestrator** — classifica intent e formato; monta o bundle.
- **create** — conceito 15s, 4 ou 5 cenas, a partir do payload de Marcas + knobs.
- **refine** — segunda passagem: o melhor roteiro para estas informações.
- **implement** — preenche o protótipo HTML; IDs estáveis; CSS variables da marca.
- **validate** — render Chromium + patch, nunca rewrite.
- **video-15 / ctv-qr** — planta técnica do anúncio horizontal.

## Payload de Marcas usado no lab

name, sector, tone, cores, logo, website, brand_summary, target_audience, ad_segments, campaign_opportunities, products_services, differentiators, proof_points, visual_motifs, mandatory/forbidden, creative_guidelines, fonts, creative_line, brand_dna, brand_assets, analysis_metadata.

Arquivos soltos na mesa entram como foto de cena (fundo do HTML) e como referência do QA, junto com as referências de Marcas. O logo da marca vai para `--logo`, não para o fundo.

## Campanhas-modelo (piloto criação)

- `tim-controle-ctv` — Video 15s
- `vivara-presente-ctv` — Video 15s, composição C
- `rededor-cuidado-ctv` — Video 15s + QR

Se a marca existir em `cx_clients`, o modelo recebe o DNA real. Qualquer outra marca de Marcas gera 4 cenas a partir de oportunidades, produtos e provas do perfil.

## Visual QA

1. Render 1920×1080
2. Comparar referência vs HTML
3. Devolver patch por `layer_id`
4. No máximo 3 tentativas

## Três testes piloto

1. **Criação** (desta fase): Tim / Vivara / Rede D’Or — brief texto → HTML + PNG.
2. **Adaptação**: mesmo formato, outra marca de Marcas.
3. **Reconstrução**: screenshot → HTML → diff → patch.

## Exemplo de trace

```
orchestrator  create
create        spec
video-15      video-linear-15
refine        melhor roteiro
implement     4 ou 5 cenas
Chromium      done
validate      QA
```
