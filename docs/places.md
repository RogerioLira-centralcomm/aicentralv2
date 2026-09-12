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

4 semanas físicas = anual ÷ 13 (estimate). Endereçáveis em apps e portais ≈ únicos (×0,62) × 0,38. Pontos não se somam. Halo não é presença no terminal. Pistas do SDU não são zona comercial. Internacional do CNF (~4–5%) fica 8–14 mil endereçáveis, a validar.

Shoppings e áreas de evento existem como tipo. Sem mapa, o status vira `mapping`. SP e RJ têm mais pontos a mapear.

## Dois visuais

- Dentro do CentralX: `base_erp` e tokens `--cx-*`
- Fora: site CentralComm — Nunito / Nunito Sans, canvas `#F7F8FA`, nav `#080808`, lima `#4AFF6B`, verde AA `#167A3A`, ouro `#F5A623`

## Payload

`metrics` (inclui `addressable`), `catchment`, `geo`, `points` (lat/lng, `radius_m`, reach, formatos, públicos), `offer`, `research`, `zones`, `audiences`, `media`, `methodology`. Cada número leva `source` e `source_status` (`official | estimate | to_validate`). A one-page pública não usa hero gerado no índice: o cartão é o código IATA. Internacional do CNF leva o selo “A validar”.

Endereçáveis em 4 semanas (estimate, não somar):

- Confins terminal 350 m: 190–280 mil · embarque 250 m: 95–140 mil · internacional 200 m: 8–14 mil · estacionamento 400 m: 70–110 mil · MG-010 1,2 km: 80–130 mil
- Congonhas T1 300 m: 380–560 mil · embarque 250 m: 180–260 mil · apps 250 m: 160–230 mil · pátios 350 m: 120–180 mil · Campo Belo 800 m: 90–150 mil · Moema 1 km: 80–140 mil
- Santos Dumont terminal 250 m: 95–150 mil · embarque 200 m: 70–110 mil · VLT 300 m: 60–95 mil · Centro 800 m: 55–90 mil · Glória 900 m: 40–70 mil

## Estúdio interno

Abas: Lugar (Nominatim), Importar (Perplexity + GPT-5 para fechar a ficha), Pontos (lat/lng + mapa), Imagens (GPT Image 2: hero, mapa e interiores de cada ponto), Publicar.

Fluxo: buscar o lugar → salvar ou finalizar importação → GPT-5 fecha linha de venda, bacia e pontos → gerar imagens → publicar o link. A one-page é para agência ou cliente final que vai comprar.
