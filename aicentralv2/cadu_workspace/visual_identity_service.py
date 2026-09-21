"""Geração versionada de visuais do Workspace com cobrança idempotente."""

from ..cadu_credit_connector import CaduCreditConnector, CreditActor
from ..cadu_family import repository
from ..creative_modeling_generation import CreativeGenerationClient
from ..creative_modeling_storage import CreativeAssetStorage


def build_visual_identity_prompt(prompt, visual_type):
    """Compile the Workspace request into a stable GPT Image 2 contract.

    This follows the Studio prompt rules: explicit source of truth, references
    treated as contracts, no invented logo/copy, and output-specific safe areas.
    """
    request = ' '.join(str(prompt or '').split())[:6000]
    kind = str(visual_type or 'background').strip().lower()
    if kind in {'icon', 'avatar'}:
        output = """Create a premium project or brand avatar/icon for the Cadu Workspace.
The icon is a compact identity asset, not a logo redesign and not a UI screenshot.
Use only the supplied brand/project identity as source of truth: preserve official
logo geometry, symbol proportions, distinctive colors and recognizable visual cues
when they are provided. If no official mark is provided, create an original,
non-textual abstract symbol derived from the supplied identity; never invent a
legal wordmark, slogan or unrelated monogram. Use one clear focal symbol, simple
silhouette, controlled detail, generous internal safe margin and strong legibility
at 24px, 32px, 48px and 96px. Make the foreground readable on both a light and a
dark surface. Keep the background simple, opaque and compatible with a rounded
mask. No text, letters, numbers, UI, cards, mockups, people, watermark or third-
party logo. Output one centered square asset with no border and no cropped mark."""
    else:
        output = """Create a premium hero background for a Cadu Workspace brand or
project detail page. This is a background layer, not a poster, advertisement or
interface. Use the supplied brand/project identity as the source of truth and
translate its approved colors, materials, shapes and visual language into a
subtle, original atmosphere. Keep the upper and side edges gently active while
preserving a large calm negative-space field for the page title, metadata and
actions. Any organic lines, abstract forms or brand-derived vector motifs must be
thin, low-opacity and clearly subordinate to content. Use a restrained fade or
overlay that terminates in the page surface color, with readable contrast in both
light and dark UI themes. No text, letters, numbers, logos, icons, buttons, cards,
dashboard chrome, people, watermark, strong gradient, neon, sci-fi effects,
particles, light trails or high-contrast focal object. Do not place important
detail behind the title or actions. Output a wide, clean, reusable background."""
    return "\n\n".join((output, f"Literal Workspace request (source of truth): {request}"))


def generate_visual(*, client_id, user_id, version_id, prompt, visual_type,
                    aspect_ratio='16:9', references=None):
    """Gera um visual e só cobra depois que o provider devolve uma imagem válida."""
    client_id, user_id = int(client_id), int(user_id)
    compiled_prompt = build_visual_identity_prompt(prompt, visual_type)
    result = CreativeGenerationClient().generate_image(
        prompt=compiled_prompt,
        input_references=references or [],
        aspect_ratio=aspect_ratio,
        quality='low',
        resolution='1K',
        output_format='png',
        background='opaque',
        model='openai/gpt-image-2',
    )
    encoded = result.get('b64_json') or result.get('image_base64')
    if not encoded:
        raise ValueError('O provedor não retornou a imagem gerada.')
    image_path = CreativeAssetStorage().save_generated_base64(encoded, output_format='png')
    actor = CreditActor.from_values(client_id, user_id)
    charge = CaduCreditConnector().charge_provider(
        actor=actor,
        idempotency_key=f'workspace-visual:{version_id}',
        app='Workspace visual identity',
        stage=visual_type,
        provider_result=result,
        model=result.get('model') or 'openai/gpt-image-2',
        fallback_cost_usd=0.04,
        metadata={'version_id': str(version_id), 'visual_type': visual_type,
                  'provider_route': (result.get('response_metadata') or {}).get('route')},
    )
    updated = repository.update_visual_identity_version(
        client_id, version_id, status='ready', image_url=image_path,
        token_usage=(charge or {}).get('charged_tokens') if isinstance(charge, dict) else 0,
    )
    return {'version': updated, 'charge': charge, 'provider': result.get('response_metadata') or {}}
