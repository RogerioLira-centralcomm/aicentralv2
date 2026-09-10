"""Blocos determinísticos para prompts de mockups de formatos publicitários."""

from .creative_brand_analysis import format_copy_system_lines
from .creative_construct_params import locks_from_kv_items, normalize_kv_items

ANTI_AI_LOOK = """FORBID AI LOOK
No glowing rays, particle streams, neural-network lines, wifi magic,
lens flares, holographic grids or stock “family on a sofa with light trails”.
No synthetic skin sheen or invented sci-fi UI. Photographic advertising only."""

BRIEF_LOCK_RULES = """BRIEF LOCK
The campaign message, pack headline, offer and CTA are the only claims.
Do not invent a parallel story, product or benefit. Later scenes continue
this same ad; they are not variations of scene 1 and not a new composition."""

NATIVE_RENDER_RULES = """NATIVE ADVERTISING STILL
Render a photographic still of the campaign subject only.
Do not draw a portal, television, smartphone, tablet, browser chrome,
player chrome, icon bars, leader lines or typeset headline/CTA.
Leave a clean photographic field. Copy and CTA are composed later.
Do not invent extra chrome or a second advertising frame.
Social unfold pieces are the exception: when the format family is square_1x1,
story_9x16 or landscape_social, paint the complete locked advertisement
including verbatim headline, CTA and logo.
""" + ANTI_AI_LOOK


UNFOLD_LOCK_SYSTEM = """Você extrai os itens literais de um KV e das notas da campanha.
Não invente oferta, benefício, preço, CTA ou slogan. Se as notas trouxerem texto,
elas vencem qualquer leitura da imagem. Se um item não estiver visível, deixe
o texto vazio e status absent. Se a leitura for duvidosa, status uncertain.
Retorne somente JSON puro:
{"headline":"...","subhead":"...","cta":"...","other_lines":[],"has_logo":true,
 "items":{
   "logo":{"text":"","status":"seen|uncertain|absent"},
   "product_lockup":{"text":"...","status":"..."},
   "talent":{"text":"descrição curta da pessoa/produto","status":"..."},
   "headline":{"text":"...","status":"..."},
   "offer":{"text":"...","status":"..."},
   "benefits":{"text":"uma linha por benefício","status":"..."},
   "cta":{"text":"...","status":"..."},
   "legal":{"text":"...","status":"..."},
   "background":{"text":"cor ou campo","status":"..."}
 }}.
headline, subhead e cta são strings em português do Brasil ou vazias.
other_lines é uma lista de outras linhas visíveis, sem repetir headline/CTA.
has_logo é true só se houver marca gráfica visível. Não fabrique CTA."""


UNFOLD_PROMPT_SYSTEM = """Você é diretor de arte adaptando um KV aprovado para
OUTRO formato. O GPT Image 2 vai pintar a peça. Retorne JSON puro:
{"prompt_en":"...","rationale_pt":"...","checks":["..."]}.

O prompt_en deve ser inglês técnico de produção, nesta ordem exata:

LOCK
Quote every locked string verbatim. Do not rewrite, translate or omit.
KEEP
Preserve brand DNA, photography, logo mark and the KV as visual truth.
ADAPT
Change only geometry: crop, hierarchy, density and scale for the target size.
FORBID
No new claims, invented English slogans, portal/player chrome or a second CTA.

Inclua gpt_image_instruction da creative_line quando existir. Copy visível em
pt-BR literal. Adaptação de formato não é adaptação de cena da sequência."""


UNFOLD_SOCIAL_COMPLETE = """COMPLETE SOCIAL ADVERTISEMENT
Paint the finished advertising piece, including locked headline, supporting
line, CTA and logo, inside the target social rectangle.
The first attached image is the KV: treat it as visual truth, not mood.
Do not invent a device mockup, feed chrome, like-bar or extra UI.
Keep every locked string verbatim in Brazilian Portuguese."""


UNFOLD_IMAGE_LOCK = """LOCK BLOCK FOR GPT IMAGE 2
Reproduce locked copy exactly. Do not rewrite, translate, shorten or invent
words. If a logo is present in the KV or brand references, keep that mark.
Do not add a second CTA or a new claim."""


UNFOLD_AB_SIMPLE = """Você escreve o prompt de uma variação A/B SIMPLES.
Só pode mudar cores da marca ou do anúncio. Mesmo recorte, mesmas zonas,
mesmo tamanho de tipo, mesmas posições. Não peça recorte, reposicionamento
nem still novo. Não reescreva texto, CTA ou logo.
Retorne JSON: {"prompt_en":"...","rationale_pt":"...","checks":["..."]}.
O prompt_en deve dizer explicitamente: recolor only; same crop; same type
size; same positions; locked copy and CTA and logo unchanged."""


UNFOLD_AB_MAX = """Você escreve o prompt de uma variação A/B MÁXIMA.
Pode recortar, reposicionar, mudar escala e restilizar a fotografia.
Não pode mudar wording, CTA nem a marca gráfica.
Retorne JSON: {"prompt_en":"...","rationale_pt":"...","checks":["..."]}.
O prompt_en pode pedir recrop, rebalance e restyle. Deve proibir rewrite
de copy, CTA ou logo. Liste as travas no bloco LOCK."""


MASTER_RENDER_RULES = """You are a senior advertising art director specialized in
premium digital media, rich media advertising, programmatic media formats,
mobile advertising, luxury branding and client-presentation mockups.

Create a CLIENT-PRESENTATION MOCKUP of the supplied interactive advertising format.
This is not a free-form campaign poster. The creative must clearly preserve the
structure, hierarchy and interaction model of the advertising format.

VISUAL PRESENTATION STANDARD
- Photorealistic, high-resolution advertising mockup.
- Physically correct device and screen proportions; never stretch or deform them.
- Premium studio presentation, controlled light and realistic soft shadows.
- Keep the advertising creative fully contained inside its placement.
- Do not add browser chrome or external UI unless the placement explicitly requires it.
- Use a large photographic area, few words, clear CTA and legible typography.
- Use consistent margins and realistic interaction cues.
- The static image must immediately explain how the interaction works.
- Avoid generic SaaS language, excessive cards and decorative UI.
- Do not show price unless explicitly requested."""


DEVICE_PRESENTATION_RULES = {
    "celular": """DEVICE PRESENTATION
- Use a realistic current-generation premium smartphone, perfectly front-facing.
- Preserve a mobile advertising area close to 1:2 / 300x600.
- Pure white studio background with a subtle shadow below the device.
- Do not crop, tilt, squash, widen or overlap the smartphone.""",
    "tablet": """DEVICE PRESENTATION
- Use one realistic premium tablet in landscape orientation.
- Keep the device front-facing, fully visible and physically proportional.
- Use a clean white studio background and restrained product shadow.""",
    "portal": """PLACEMENT PRESENTATION
- Use a deterministic desktop editorial portal shell around the advertising slot.
- Preserve a credible header, compact navigation, editorial grid and content rhythm.
- The portal is context only; the advertising unit remains the visual subject.
- Show the ad installed in its real reserved position inside the page.
- Do not place the portal ad inside a smartphone or isolated device frame.
- Do not copy a complete third-party page or real editorial content.""",
    "tv": """CTV PRESENTATION
- Use a physically correct 16:9 television or streaming interface.
- Preserve cinematic safe areas, a restrained navigation layer and content rail.
- Keep the advertising experience readable from a living-room viewing distance.
- Show the ad integrated into the CTV or streaming experience, not inside a phone.
- Do not turn the result into a poster detached from the CTV interface.""",
}


FOUR_VARIATION_BOARD = """VARIATION PRESENTATION
Create ONE wide client-presentation image containing exactly FOUR identical devices
arranged horizontally in one row. All devices must have identical dimensions, angle,
vertical alignment, lighting and shadows. Leave equal spacing. Do not crop or overlap
any device. Keep exactly the same campaign design and interaction mechanism across all
four states. Only the supplied content or revealed scene may change."""

MULTI_FORMAT_BOARD = """MULTI-FORMAT PRESENTATION
Create ONE wide client-presentation board containing exactly FOUR advertising mockups.
Use the native presentation environment required by each placement: editorial portal
for desktop/display inventory, a 16:9 television or streaming shell for CTV inventory,
and a smartphone only for formats explicitly modeled as mobile. If all four formats
share one channel, repeat that same native environment consistently. If the board
compares channels, each mockup may use its corresponding native environment while
keeping one shared brand system, typography, lighting and art direction.
Each mockup demonstrates a DIFFERENT interactive advertising format from the same
campaign. The interaction mechanism may change between mockups, but the campaign
design must not. Make each mechanism immediately understandable:
1. immersive 360-degree or panoramic discovery
2. fixed-card or carousel selection
3. architectural image with premium clickable hotspots
4. drag-to-compare or pull-to-reveal interaction
Do not create four unrelated campaign styles. Do not merge the four mechanisms into
one screen. Do not default every format to a smartphone. Label each format through its
interaction cue, not through technical UI."""


FORMAT_MECHANISM_RULES = {
    "quiz": """FORMAT MECHANISM: INTERACTIVE QUIZ
Show one concise question, two to four comfortable answer targets and a progress
indicator. The answers must clearly look tappable. Keep the quiz inside the fixed
advertising unit. Do not turn it into a dashboard, form builder or landing page.""",
    "reveal": """FORMAT MECHANISM: PULL TO REVEAL
Represent the interaction in progress. A tactile foreground layer must be visibly
dragged to reveal a second visual layer. Show realistic material, overlap, edge,
shadow, directional cue and partial reveal. Do not render a simple static poster.""",
    "hotspot": """FORMAT MECHANISM: INTERACTIVE HOTSPOTS
Place restrained circular markers directly over one hero image. Connect each marker
to a short translucent label with a fine line. Keep the result premium and clearly
interactive. Do not turn it into a map application or dashboard.""",
    "flip": """FORMAT MECHANISM: FIXED PRODUCT CARD / FLIP
Keep one clearly bounded central card at exactly the same size and position. Show a
subtle front/back or carousel cue. Product photography, name and requested information
belong inside the card. Do not transform the card into a free-form layout.""",
    "compare": """FORMAT MECHANISM: DRAG COMPARISON
Show two aligned image states divided by one clear draggable handle. Preserve the
same framing on both sides and make the comparison interaction understandable.""",
    "video": """FORMAT MECHANISM: INTERACTIVE VIDEO
Show one primary video area with a restrained play/progress affordance and one clear
CTA. Avoid controls or navigation unrelated to the advertising unit.""",
    "static": """FORMAT MECHANISM: FIXED ADVERTISING UNIT
Respect the exact placement geometry, safe area, hierarchy and outer frame. Do not
expand the unit into a landing page.""",
}


STRICT_NEGATIVE_RULES = """STRICT NEGATIVE RULES
Do not:
- distort, crop or invent another device design
- use a smartphone when the placement context is portal, display, CTV or streaming
- change device size or campaign layout between variations
- transform the ad into a landing page, dashboard, chart or free-form poster
- add prices unless explicitly requested
- add fake browser UI, excessive cards, excessive copy or arbitrary icons
- add unrelated brand elements or navigation
- change the interaction mechanism
- ignore the supplied structural reference

The objective is to demonstrate the advertising FORMAT to a client, not merely to
generate an attractive campaign image."""


def normalize_locks(value):
    data = value if isinstance(value, dict) else {}
    other = data.get("other_lines") or []
    if not isinstance(other, list):
        other = []
    merged = locks_from_kv_items(data.get("items") or data, data)
    if not merged["headline"]:
        merged["headline"] = str(data.get("headline") or "").strip()
    if not merged["subhead"]:
        merged["subhead"] = str(data.get("subhead") or "").strip()
    if not merged["cta"]:
        merged["cta"] = str(data.get("cta") or "").strip()
    if not merged["other_lines"]:
        merged["other_lines"] = [str(item).strip() for item in other if str(item).strip()]
    if data.get("has_logo") is True:
        merged["has_logo"] = True
    merged["items"] = normalize_kv_items({**data, "items": merged.get("items")})
    return merged


def unfold_image_lock(locks=None):
    locks = normalize_locks(locks)
    lines = [UNFOLD_IMAGE_LOCK, "LOCK"]
    if locks["headline"]:
        lines.append(f'Headline verbatim: "{locks["headline"]}"')
    if locks["subhead"]:
        lines.append(f'Supporting line verbatim: "{locks["subhead"]}"')
    if locks["cta"]:
        lines.append(f'CTA verbatim: "{locks["cta"]}"')
    for extra in locks["other_lines"]:
        lines.append(f'Keep verbatim: "{extra}"')
    if locks["has_logo"]:
        lines.append("Keep the existing logo mark. Do not redraw a different brand.")
    lines.append("Do not rewrite, translate or omit locked copy.")
    return "\n".join(lines)


def unfold_ab_instruction(level, locks=None):
    locks = normalize_locks(locks)
    if str(level or "") in {"ab_max", "max", "maximum"}:
        body = (
            "Maximum A/B variation: you may recrop, rebalance, resize type "
            "blocks and restyle photography. You may not change wording, CTA "
            "or the logo mark."
        )
    else:
        body = (
            "Simple A/B variation: recolor only, using the brand palette or "
            "the ad's existing hues. Same crop, same type size, same positions."
        )
    return f"{body}\n\n{unfold_image_lock(locks)}"


def paints_full_copy(family, flow_kind=None, engine=None):
    if str(engine or "") == "construct":
        return False
    return (
        str(flow_kind or "") == "unfold"
        and family in {"square_1x1", "story_9x16", "landscape_social"}
    )


def native_scene_prompt_suffix(
    geometry, copy=None, flow_kind=None, locks=None, engine=None
):
    """Restrições determinísticas da peça nativa, sem device/portal."""
    geometry = geometry if isinstance(geometry, dict) else {}
    copy = copy if isinstance(copy, dict) else {}
    size = geometry.get("size") or ()
    budget = geometry.get("budget") or {}
    family = geometry.get("family") or "native"
    target = (
        f"{size[0]}x{size[1]}px"
        if len(size) == 2
        else geometry.get("target_size") or "native rectangle"
    )
    if paints_full_copy(family, flow_kind, engine):
        lines = [
            UNFOLD_SOCIAL_COMPLETE,
            f"Target canvas: {target}.",
            f"Family: {family}.",
            unfold_image_lock(locks or copy),
        ]
        return "\n".join(lines)
    lines = [
        NATIVE_RENDER_RULES,
        f"Target canvas: {target}.",
        f"IAB family: {family}.",
    ]
    if budget.get("summary"):
        lines.append(f"Element budget: {budget['summary']}.")
    if copy.get("headline"):
        lines.append(f"Headline will be composed later: {copy['headline']}.")
    if copy.get("cta"):
        lines.append(f"CTA will be composed later: {copy['cta']}.")
    lines.append(BRIEF_LOCK_RULES)
    lines.append(ANTI_AI_LOOK)
    return "\n".join(lines)


def apply_render_mode_to_prompt(
    prompt, render_mode, geometry, copy=None, flow_kind=None, locks=None,
    engine=None,
):
    text = str(prompt or "").strip()
    if render_mode == "native":
        suffix = native_scene_prompt_suffix(
            geometry, copy, flow_kind, locks, engine
        )
        marker = "COMPLETE SOCIAL ADVERTISEMENT" if paints_full_copy(
            (geometry or {}).get("family"), flow_kind, engine
        ) else "NATIVE ADVERTISING STILL"
        if marker not in text:
            text = f"{text}\n\n{suffix}".strip()
    if flow_kind == "unfold" and "LOCK BLOCK FOR GPT IMAGE 2" not in text:
        text = f"{text}\n\n{unfold_image_lock(locks)}".strip()
    return text


def _value(data, key, fallback=""):
    value = data.get(key) if isinstance(data, dict) else None
    return value if value not in (None, "") else fallback


def compose_format_mockup_prompt(
    format_data,
    client=None,
    reference_type="full_mockup",
    presentation_mode="single",
    campaign_content=None,
    has_references=False,
    has_brand_references=False,
):
    """Monta um prompt por camadas, sem templates livres vindos do cliente."""
    placement = format_data.get("placement_spec") or {}
    viewport = placement.get("viewport") or {}
    slot = placement.get("slot") or {}
    context = placement.get("context") or "portal"
    presentation_context = {
        "ctv": "tv",
        "streaming": "tv",
        "smart_tv": "tv",
        "mobile": "celular",
        "display": "portal",
        "desktop": "portal",
    }.get(context, context)
    behavior = (format_data.get("behavior_spec") or {}).get("type") or "static"

    sections = [
        MASTER_RENDER_RULES,
        DEVICE_PRESENTATION_RULES.get(
            presentation_context, DEVICE_PRESENTATION_RULES["portal"]
        ),
    ]
    if presentation_mode == "four_horizontal":
        sections.append(FOUR_VARIATION_BOARD)
    elif presentation_mode == "multi_format_board":
        sections.append(MULTI_FORMAT_BOARD)
    sections.extend(
        [
            "\n".join(
                [
                    "FORMAT TEMPLATE",
                    f"Name: {_value(format_data, 'name_pt', 'Advertising format')}",
                    f"Mechanic: {_value(format_data, 'mechanic', behavior)}",
                    f"Context: {context}",
                    (
                        "Technical viewport: "
                        f"{viewport.get('width', 1280)}x{viewport.get('height', 800)}"
                    ),
                    (
                        "Reserved slot: "
                        f"x {slot.get('x', 0)}%, y {slot.get('y', 0)}%, "
                        f"width {slot.get('width', 100)}%, "
                        f"height {slot.get('height', 100)}%"
                    ),
                    f"Output aspect ratio: {_value(format_data, 'aspect_ratio', '16:9')}",
                    f"Safe area: {_value(format_data, 'safe_area', {})}",
                    f"Responsive rules: {_value(format_data, 'responsive_rules')}",
                    f"Background guidance: {_value(format_data, 'background_guidance')}",
                    f"Foreground guidance: {_value(format_data, 'foreground_guidance')}",
                ]
            ),
            FORMAT_MECHANISM_RULES.get(behavior, FORMAT_MECHANISM_RULES["static"]),
        ]
    )

    if reference_type == "background":
        sections.append(
            "OUTPUT SCOPE\nGenerate the environment only. Keep the advertising slot "
            "empty, neutral and clearly reserved. Do not place a finished ad in it."
        )
    elif client:
        profile = client.get("brand_profile") or {}
        palette = [
            f"{item.get('hex')} ({item.get('usage') or 'brand use'})"
            for item in (profile.get("color_palette") or [])
            if isinstance(item, dict) and item.get("hex")
        ]
        brand_lines = [
            "BRAND CONTEXT",
            f"Brand: {_value(client, 'name')}",
            f"Sector: {_value(client, 'sector')}",
            f"Voice: {_value(client, 'tone_of_voice')}",
            f"Primary color: {_value(client, 'primary_color')}",
            f"Secondary color: {_value(client, 'secondary_color')}",
            (
                "Price policy: show price only when explicitly requested."
                if client.get("price_policy") == "show_price"
                else "Price policy: do not show price."
            ),
        ]
        if palette:
            brand_lines.append("Observed palette: " + "; ".join(palette[:6]))
        if profile.get("creative_guidelines"):
            brand_lines.append(
                f"Creative direction: {profile['creative_guidelines']}"
            )
        for key, label in (
            ("visual_motifs", "Recurring visual motifs"),
            ("mandatory_elements", "Mandatory brand elements"),
            ("forbidden_elements", "Brand restrictions"),
        ):
            values = profile.get(key)
            if isinstance(values, list) and values:
                brand_lines.append(f"{label}: " + " | ".join(map(str, values[:6])))
        sections.append("\n".join(brand_lines))
        creative_line = profile.get("creative_line") or {}
        if isinstance(creative_line, dict) and creative_line.get(
            "signature_summary"
        ):
            learned = [
                "LEARNED CREATIVE LINE",
                f"Signature: {creative_line['signature_summary']}",
            ]
            for key, label in (
                ("composition_rules", "Composition"),
                ("imagery_rules", "Imagery"),
                ("typography_rules", "Typography"),
                ("graphic_devices", "Graphic devices"),
                ("must_preserve", "Must preserve"),
                ("avoid", "Avoid"),
            ):
                values = creative_line.get(key)
                if isinstance(values, list) and values:
                    learned.append(f"{label}: " + " | ".join(map(str, values[:6])))
            if creative_line.get("gpt_image_instruction"):
                learned.append(str(creative_line["gpt_image_instruction"]))
            learned.extend(
                format_copy_system_lines(
                    creative_line.get("copy_system"), english=True
                )
            )
            learned.append(
                "Reuse only the visual system. Never reuse previous offers, "
                "prices, claims or campaign copy."
            )
            sections.append("\n".join(learned))
    else:
        sections.append(
            "BRAND CONTEXT\nUse a fictional neutral brand with no recognizable "
            "logo, trademark, price or unsupported claim."
        )

    if campaign_content:
        sections.append(f"CAMPAIGN CONTENT AND VARIATIONS\n{campaign_content}")
    if has_references:
        sections.append(
            "STRUCTURAL REFERENCE RULES\nUse input references only as the structural "
            "advertising-format template. Preserve proportions, hierarchy, card/slot "
            "dimensions, header and CTA locations, outer-frame relationship and the "
            "interaction metaphor. Replace only campaign, colors, photography and copy. "
            "Do not redesign the format."
        )
    if has_brand_references:
        sections.append(
            "BRAND REFERENCE RULES\nApproved brand images are attached as identity "
            "evidence, not as layout templates. Match their palette, materials, "
            "lighting and logo treatment. Reproduce the logo faithfully without "
            "redrawing or restyling it, and never copy their layout, offers or copy."
        )
    sections.append(STRICT_NEGATIVE_RULES)
    return "\n\n".join(section.strip() for section in sections if section)


def build_inherited_scene_prompt(visual_bible, description, cta_text, position):
    """Direção inicial da cena a partir do storyboard, sem chamada extra de LLM."""
    lines = [f"INHERITED CAMPAIGN SYSTEM — scene {position}"]
    if visual_bible:
        lines.append(f"Visual bible: {visual_bible}")
    if description:
        lines.append(f"Scene direction: {description}")
    if cta_text:
        lines.append(f"CTA: {cta_text}")
    lines.append(BRIEF_LOCK_RULES)
    lines.append(ANTI_AI_LOOK)
    lines.append(
        "Preserve this visual system across the sequence. Later scenes adapt "
        "only the storyboard delta; do not restart the campaign."
    )
    return "\n".join(lines)
