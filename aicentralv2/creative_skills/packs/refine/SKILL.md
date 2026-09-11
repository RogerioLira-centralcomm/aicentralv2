---
name: creative-refine
pack: refine
triggers:
  - intent refine
  - intent adapt
expected_inputs:
  - existing spec or HTML
  - brand_context
expected_outputs:
  - classified issues
  - focused patches
failure_conditions:
  - redesign
  - changing interaction without approval
---

# Refine Pack

Do not redesign the creative.

On storyboard pass 2, ask only: is this the best 15s concept for this brand and these inputs?
Adjust copy, beat order and set/action notes. Do not invent a film. Do not draw player chrome.

Keep user locks and the chosen brand key visuals. Improve weak lines; do not replace a locked headline.

Reject generic hooks ("sua história", "viva o momento"), e-commerce CTAs, website menus, copy that fails at TV distance, and brand that lives only in the footer.

On HTML, review hierarchy, spacing, scale, legibility, alignment, balance, CTA, brand presence, density, consistency.

P0 = breaks format. P1 = major visual issue. P2 = noticeable refinement. P3 = optional polish.
Apply P0 and P1 first.
Never change interaction mechanics without approval.
