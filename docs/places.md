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

Publicados: aeroportos Confins (CNF), Congonhas (CGH), Santos Dumont (SDU), Galeão (GIG); shoppings Diamond Mall (DMM) e Iguatemi São Paulo (IGT); parques e eventos Ibirapuera (IBI) e Expominas (EXP). Shoppings e eventos entram com texto e mapa; as fotos do hero saem depois.

Passageiros ANAC 2025:

- Congonhas 24.583.610 (24,6 mi)
- Galeão 17.836.134 (17,8 mi)
- Confins 13.183.039 (13,2 mi)
- Santos Dumont 6.184.233 (6,2 mi; o book V2 tinha 4,9 mi, defasado)

Bacia residencial (Censo 2022, recorte oficial — não é presença no terminal):

- Confins: 212 mil / ~620 hab/km² — municípios Confins + Lagoa Santa + Vespasiano
- Congonhas: 153 mil / ~8,6 mil hab/km² — distritos Campo Belo + Moema
- Santos Dumont: 96 mil / ~10,8 mil hab/km² — bairros Centro, Glória, Catete e Flamengo (IPP)
- Galeão: 211 mil / ~5,2 mil hab/km² — RA Ilha do Governador (IPP / IBGE)

4 semanas físicas = anual ÷ 13 (estimate). Endereçáveis em apps e portais ≈ únicos (×0,62) × 0,38. Pontos não se somam. Halo não é presença no terminal. Pistas do SDU não são zona comercial. Internacional do CNF (~4–5%) fica 8–14 mil endereçáveis, a validar.

O índice público é um diretório em três colunas (Aeroportos, Shoppings, Parques e eventos), com foto no card. O header abre um mega menu com as mesmas colunas. Sem mapa, o status vira `mapping`.

## Dois visuais

- Dentro do CentralX: `base_erp` e tokens `--cx-*`
- Fora: site CentralComm — Nunito / Nunito Sans, canvas `#F7F8FA`, nav `#080808`, lima `#4AFF6B`, verde AA `#167A3A`, ouro `#F5A623`

## Payload

`metrics` (inclui `addressable`), `catchment`, `geo`, `points` (nome obrigatório; lat/lng pode faltar até o geocode), `offer`, `research`, `zones`, `audiences`, `media`, `pipeline`, `costs` (entradas OpenRouter e `total_usd`), `methodology`. Cada número leva `source` e `source_status` (`official | estimate | to_validate`).

A API do estúdio devolve a mesma ficha em `fiche` (identity, metrics, catchment, offer, points, images, pipeline) e o pacote visual em `images` (`spec.model`, `spec.resolution`, `hero_url`, `points[].url`, `errors`). `media` guarda `image_model`, `image_resolution` e `images[]`. `pipeline` lista os passos (`research → finalize → refine → geocode → polish → images`), modelos e avisos (ponto militar, avenida corrigida, coordenada faltando).

A one-page pública é uma folha, não um site: hero com a foto do place, mapa satélite (Esri) com o círculo do recorte e a ficha daquele ponto. Índice usa a foto hero com o código IATA por cima. Sem galeria, cards de oferta nem seção de bacia — o Censo entra numa linha (“mora no entorno, não é presença no terminal”). Internacional do CNF leva o selo “A validar”. As fotos vêm do OpenRouter por aeroporto: Confins e SDU no GPT Image 2; Congonhas no Nano Banana Pro 1K; Galeão no Seedream 5 Lite 2K. Importação: pesquisa (Sonar) → finalize (GPT-5) → refine da ficha gerada → geocode curto → polish da one-page.

Endereçáveis em 4 semanas (estimate, não somar):

- Confins terminal 350 m: 190–280 mil · embarque 250 m: 95–140 mil · internacional 200 m: 8–14 mil · estacionamento 400 m: 70–110 mil · MG-010 1,2 km: 80–130 mil
- Congonhas T1 300 m: 380–560 mil · embarque 250 m: 180–260 mil · apps 250 m: 160–230 mil · pátios 350 m: 120–180 mil · Campo Belo 800 m: 90–150 mil · Moema 1 km: 80–140 mil
- Santos Dumont terminal 250 m: 95–150 mil · embarque 200 m: 70–110 mil · VLT 300 m: 60–95 mil · Centro 800 m: 55–90 mil · Glória 900 m: 40–70 mil
- Galeão T2 400 m: 260–390 mil · embarque 250 m: 140–210 mil · internacional 300 m: 80–130 mil · estacionamento 400 m: 100–150 mil · Vinte de Janeiro 1 km: 70–120 mil · Jardim Guanabara 1,2 km: 55–95 mil

## Estúdio interno

Lista em tabela: código, place, cidade, status, passageiros, endereçáveis, pontos, fotos, custo de IA e link copiável.

Uma trilha no cadastro: Lugar → Bacia → Pontos → Arte → Publicar. Fechar a ficha pesquisa a região, fecha o texto e já entra os pontos (com ou sem coordenada). As fotos saem uma a uma — hero, mapa, depois cada ponto — com fila na tela de arte. Cinco imagens no mesmo request estouram o timeout.

Fluxo: buscar o lugar → fechar ficha → pontos entram sozinhos → gerar fotos → publicar o link. A one-page é para agência ou cliente final que vai comprar.
