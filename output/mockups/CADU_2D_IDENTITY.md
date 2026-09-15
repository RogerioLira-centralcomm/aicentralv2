# Cadu — símbolos 2D de interface

## Correção da entrega anterior

Ícones anteriores eram recortes dos key visuals 3D. Esta entrega cria cinco masters 2D individuais com a ferramenta imagegen integrada (Image 2), usando a imagem original de arquitetura de marca como referência. PNG, sem gerar SVG ou desenhar o símbolo em CSS/canvas.

Os PNGs derivados são recortes e redimensionamentos dos masters gerados, não logos redesenhados por código. Master original preservado por família. Exportador: `scripts/export_cadu_2d_icons.cjs`. Tamanhos: 16, 20, 24, 32, 40, 48, 64, 96, 128, 192, 512 e 1024 pixels.

## Direção e prompt usado por família

Prompt comum (cada família teve uma chamada individual):

> Use case: logo-brand. Asset: ONE individual flat 2D PNG app symbol for Cadu [família], with genuine transparent background. The attached image is ONLY an identity geometry reference, NOT a layout to reproduce. Extract/reinterpret the exact Cadu symbol from the reference: TWO solid thick left-pointing chevrons side by side, first chevron at left in [cor], second at right in near-black #0B0F14. Both chevrons point LEFT, like <<. Preserve equal height, equal weight, broad flat horizontal top and bottom ends, clean crisp angular sides and small consistent separation as in the original main Cadu logo. Make a meticulous minimal software brand icon optically clear at 16px. Center the symbol alone inside square 1024x1024 canvas with 18% safe space on every side; width around 64%, height around 64%. Flat solid color fills, hard geometry, antialiased edges, no extrusions, NO 3D, NO gradients, no lighting, no shadows, no scenery, no tiles, no border, no lettering, no wordmark, no text, no labels, no mockup, no multiple assets or contact sheet. The image must contain only the two left-pointing chevrons. Deliver a genuinely transparent raster PNG.

| Família | Cor de marca solicitada | Cor de ação UI | Superfície UI |
|---|---|---|---|
| Workspace | #009F8A | #007D6D | #E9F6F3 |
| Media Studio | #7456E8 | #6344CF | #F1EDFC |
| Connect | #1976E9 | #1363C5 | #EAF2FD |
| Skills | #E87922 | #A94D08 | #FFF2E7 |
| Smart Planner | #18B978 | #087D4D | #E8F7EF |

Cor exata em tokens CSS; o bitmap é uma geração de imagem e pode ter variação sutil no preenchimento. Cada exportação preserva sua origem raster, sem prometer geometria vetorial matematicamente idêntica entre gerações. Revisar os masters antes de um registro formal de marca.

Planner e Skills tiveram uma segunda chamada de edição: usar o master transparente do Studio como referência, preservar geometria/enquadramento e mudar somente o chevron violeta para #18B978 / #E87922, preservando alpha real e proibindo fundo quadriculado pintado. As primeiras variantes sem alpha foram rejeitadas e não integram os assets do projeto. Dimensão nativa dos masters selecionados: 1254 × 1254; as 12 dimensões de exportação são verificadas automaticamente.

## Aplicação

- Símbolo 2D de 20–24px no chrome; 16px para favicon/listas; nomes em texto acessível.
- Símbolo pequeno acompanhado de nome no seletor para não depender somente de cor.
- PNG com transparência verdadeira, sem checkerboard pintado como fundo.
- Fundo navy usa placa branca para proteger o chevron Ink; não aplicar filtro invert ou fabricar uma versão negativa.
- Key visuals 3D continuam em onboarding, apresentações e materiais promocionais, nunca substituindo favicon.
- Layout, foco, botões, campos e status compartilham os tokens da família no catálogo navegável.

## Localização

`output/mockups/brand-assets/icons-2d/{workspace,studio,connect,skills,planner}/`

Catálogo: `cadu-family-design-system.html`, com link individual por `#workspace`, `#studio`, `#connect`, `#skills`, `#planner`.

CentralX → Parâmetros → Protótipos Cadu agrupa cada produto, cada design system, planos, saldo, fontes, conta, apresentações e a lista completa dos HTMLs existentes. Caminhos relativos mantêm os materiais sob a rota administrativa quando abertos por lá. Sem deploy nesta etapa.

Validação: 60 PNGs com dimensões e alpha verificados; 20 páginas de identidade (5 famílias × 4 larguras) sem overflow, imagens quebradas ou erro JavaScript; cinco símbolos no seletor de produtos. Cinco testes administrativos aprovados, incluindo renderização do catálogo completo. Prévia visual conjunta: `brand-assets/icons-2d/family-preview.png`. Reproduzir com `tests/cadu_identity_browser.cjs` e `tests/test_cadu_prototype_routes.py`.
