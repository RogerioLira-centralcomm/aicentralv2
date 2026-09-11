---
name: advertising-create
pack: create
triggers:
  - intent create
  - intent adapt
  - campaign_slug
expected_inputs:
  - brand_context
  - campaign_model
  - format skill
expected_outputs:
  - CreativeFormatSpec
  - scene copy
  - image prompts
failure_conditions:
  - free-form poster
  - changing format mechanic
  - ignoring Marcas payload
---

# Creative Generation Pack

Create new advertising executions while respecting a defined format.

Before creating anything determine:

- brand (full Marcas payload)
- campaign
- audience
- format
- interaction
- canvas
- platform
- storytelling
- number of variations

This is advertising-format generation, not free-form poster creation.
Always preserve the mechanics of the selected format.

Regulators for this 15s experiment:

- scene_count: 4 or 5
- duration: 15
- density: low | tv
- hook_tension: 0–1
- cast_lock, product_lock, scenography
- offer_lock from dropped creatives
- brand forbidden / mandatory / tone from Marcas

Output a concept storyboard, not a finished film. Brand must live in every frame (color, type, tone) even when the mark is off. Set logo_visible per scene: last scene always on and centered; opening scenes may be with or without the logo.

Write specific 15s copy. Refuse generic hooks ("sua história", "conheça", "saiba mais" as headline), e-commerce urgency, price, installment, and website menus. Prefer the campaign model's headlines, set_note and action_note when they exist.

User edits win: if the human locked offer, headline, support, CTA or a brand key-visual, keep them. Selected Marcas images are the campaign key visual — describe the still around that photo, do not invent a different product.

## Brand payload is mandatory input

Use every field coming from Modelagem / Marcas:

- name, sector, tone_of_voice
- primary/secondary colors and color_palette
- logo and brand_assets (logo, reference, creative)
- brand_summary, target_audience, ad_segments
- campaign_opportunities, products_services, differentiators, proof_points
- visual_motifs, mandatory_elements, forbidden_elements
- creative_guidelines, fonts
- creative_line (signature, composition_rules, copy_patterns, gpt_image_instruction)
- brand_dna

Do not invent a brand system when Marcas already has one.

## Variation rule

Keep constant: layout, format, interaction, component positions, CTA hierarchy.
Change: photography, product, headline, scene, visual treatment.

## Raster vs HTML

- Photography / editorial → image generation or brand raster assets
- Interface / CTA / text → HTML
- Complex visual background → raster
- Interaction → HTML/JS
