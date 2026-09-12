# Places

Inventário comercial de lugares que viram audiência. Gestão no CentralX; one-page pública na marca CentralComm.

## Onde mora

- Menu Comercial → Propostas → Places
- Interno: `/places/`, `/places/novo`, `/places/<id>`
- Público: `/places/p`, `/places/p/<slug>`
- Prévia (logado): `/places/preview/<token>`

## Tabelas

Migration: `migrations/add_cx_places.sql` + `migrations/run_add_cx_places.py`

- `cx_places` — identidade, status, payload JSONB
- `cx_place_inquiries` — pedidos da one-page

## V1

Aeroportos publicados: Confins (CNF), Congonhas (CGH), Santos Dumont (SDU).

Passageiros ANAC 2025:

- Congonhas 24.583.610 (24,6 mi)
- Confins 13.183.039 (13,2 mi)
- Santos Dumont 6.184.233 (6,2 mi; o book V2 tinha 4,9 mi, defasado)

Bacia residencial (Censo 2022, recorte oficial — não é presença no terminal):

- Confins: 212 mil / ~620 hab/km² — municípios Confins + Lagoa Santa + Vespasiano
- Congonhas: 153 mil / ~8,6 mil hab/km² — distritos Campo Belo + Moema
- Santos Dumont: 96 mil / ~10,8 mil hab/km² — bairros Centro, Glória, Catete e Flamengo (IPP)

4 semanas = anual ÷ 13, sempre como estimativa. Zonas não se somam. Halo não é presença no terminal. Pistas do SDU não são zona comercial. Internacional do CNF fica ~4–5% do movimento; o alcance da zona CNF-03 permanece a validar.

Shoppings e áreas de evento existem como tipo. Sem mapa, o status vira `mapping`. SP e RJ têm mais pontos a mapear.

## Dois visuais

- Dentro do CentralX: `base_erp` e tokens `--cx-*`
- Fora: logo `cc_logo.png`, teal `#1E4D4F`, ouro `#F3B71B`, lima `#9CCF31`

## Payload

`metrics`, `catchment`, `geo`, `points`, `research`, `zones`, `audiences`, `media`, `methodology`. Cada número leva `source` e `source_status` (`official | estimate | to_validate`).

## Estúdio interno

Abas: Lugar (Nominatim), Importar (Perplexity + GPT-5 para fechar a ficha), Pontos (lat/lng + mapa), Imagens (GPT Image 2: hero, mapa e interiores de cada ponto), Publicar.

Fluxo: buscar o lugar → salvar ou finalizar importação → GPT-5 fecha linha de venda, bacia e pontos → gerar imagens → publicar o link. A one-page é para agência ou cliente final que vai comprar.
