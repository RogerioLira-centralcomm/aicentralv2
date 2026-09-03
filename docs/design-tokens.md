# Design Tokens — CentralX (tema `centralcomm`)

## Tema DaisyUI

Aplicado via `data-theme="centralcomm"` em [`base_tailwind.html`](aicentralv2/templates/base_tailwind.html).

| Token DaisyUI | Hex | Uso |
|---------------|-----|-----|
| primary | `#1E4D4F` | Ações principais, avatares ativos |
| secondary | `#F3B71B` | Destaques secundários |
| accent | `#9CCF31` | Item selecionado (lista clientes) |
| neutral | `#3d4451` | Avatares alternativos |
| base-100 | `#ffffff` | Fundo cards |
| base-200 | `#F8F9FA` | Fundo seções |
| base-300 | `#DEE2E6` | Bordas |
| info | `#2094f3` | Badges informativos |
| success | `#28A745` | Sucesso / Hoje |
| warning | `#FFC107` | Atrasado / Amanhã |
| error | `#DC3545` | Erro / Alta prioridade |

Configuração em [`tailwind.config.js`](tailwind.config.js) e espelho em [`design-system.css`](aicentralv2/static/css/tailwind/design-system.css).

## Tipografia (escala oficial — mínimo 12px)

| Token | Tamanho | Uso |
|-------|---------|-----|
| xs | 12px | Labels, badges, timestamps |
| sm | 14px | Menu, corpo secundário |
| base | 16px | Corpo, inputs |
| lg | 18px | Subtítulos |
| xl | 20px | Valores em cards |
| 2xl | 24px | Títulos de página |

## Espaçamento

Escala recomendada: **4, 8, 12, 16, 24, 32** px (`p-1`, `p-2`, `p-3`, `p-4`, `p-6`, `p-8`).

## Contraste WCAG (texto sobre fundo)

| Par | Ratio estimado | OK 4.5:1 |
|-----|----------------|----------|
| primary `#1E4D4F` / white | ~8.5:1 | Sim |
| error `#DC3545` / white | ~4.6:1 | Sim |
| success `#28A745` / white | ~3.4:1 | Uso em badges com texto branco (UI component) |
| base-content `#1f2937` / base-100 | ~12:1 | Sim |
| neutral `#3d4451` / white | ~7:1 | Sim |

Badges DaisyUI usam `*-content` do tema para texto sobre fundo semântico.

## Regras

- Preferir classes semânticas DaisyUI: `badge-error`, `btn-primary`, `bg-base-200`.
- Evitar hex soltos e `bg-red-500` etc. nos templates `/teste-crm`.
- Avatares: `primary` ou `muted` (`#94a3b8`) — duas tons apenas.
