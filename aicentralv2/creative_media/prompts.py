"""Prompt do still achatado. Sem garantia literal de tipo ou fala."""

from __future__ import annotations

MOTION = {
    "live": "Gentle parallax, light shift and product sheen. Keep layout locked.",
    "camera": "Slow camera move (push-in or tilt). No whip pans.",
    "people": "Natural micro-movements only. Preserve facial identity. No lip-sync.",
    "product": "Light and camera around the product. Do not deform packaging or labels.",
    "transition": "Interpolate toward the last frame. Hold the last second as an end card.",
    "free": "Restrained advertising motion described by the user note.",
}

INTENSITY = {
    "subtle": "Keep motion subtle and usable for a static ad that came alive.",
    "moderate": "Clear but controlled motion.",
    "expressive": "More energy, still coherent. No morphing limbs or extra people.",
}

AUDIO = {
    "silence": "No voiceover, no music, no sound effects.",
    "ambient": "Soft room tone or environment only. No speech.",
    "music": "Light music bed matching the note. No lyrics that invent a brand name. No speech.",
    "voice": "Optional spoken atmosphere guided by the voice note. Do not promise exact wording.",
    "voiceover": "No speech. Soft room tone or light music bed only. A separate exact voiceover will be mixed later.",
}

DISPLAY_SURFACES = frozenset({"display_square", "display"})


def format_surface(piece_ratio: str) -> str:
    raw = str(piece_ratio or "").strip()
    if raw == "1:1":
        return "display_square"
    if raw in {"4:3", "3:4"}:
        return "display"
    if raw in {"16:9", "21:9"}:
        return "ctv"
    if raw == "9:16":
        return "story"
    if raw == "4:5":
        return "feed"
    return "display"


def build_prompt(plan: dict) -> str:
    motion = MOTION.get(plan.get("motion_preset") or "live", MOTION["live"])
    intensity = INTENSITY.get(plan.get("motion_intensity") or "subtle", INTENSITY["subtle"])
    audio = AUDIO.get(plan.get("audio_mode") or "silence", AUDIO["silence"])
    note = str(plan.get("motion_note") or "").strip()
    voice = str(plan.get("voice_note") or "").strip()
    music = str(plan.get("music_note") or "").strip()
    extra = []
    if note:
        extra.append(f"User motion note: {note}")
    if music and plan.get("audio_mode") == "music":
        extra.append(f"Music direction: {music}")
    if voice and plan.get("audio_mode") == "voice":
        extra.append(f"Voice orientation (not a verbatim script): {voice}")
    extras = "\n".join(extra)
    plate = _plate_copy(plan)
    surface = plan.get("format_surface") or format_surface(
        plan.get("piece_ratio") or plan.get("aspect_ratio")
    )
    mode = str((plan.get("source") or {}).get("mode") or "")
    if mode == "transition_ab":
        hold = (
            "Interpolate from the first plate to the last plate. "
            "Hold the final second as a clean end card matching the last plate. "
            "Do not introduce new visual information in the last frame."
        )
    elif mode == "storyboard":
        hold = (
            "Treat the supplied references as an ordered storyboard. "
            "Advance through them in sequence. Do not jump or invent extra beats. "
            "Hold the final second as a clean end card matching the last still."
        )
        beats = ((plan.get("script") or {}).get("beats") if isinstance(plan.get("script"), dict) else None) or []
        if beats:
            lines = []
            for index, beat in enumerate(beats, start=1):
                if not isinstance(beat, dict):
                    continue
                lines.append(
                    f"{index}. {beat.get('purpose') or 'beat'}: {beat.get('visual') or ''} "
                    f"Motion: {beat.get('motion') or ''} Hold: {beat.get('hold') or ''}"
                )
            if lines:
                hold = hold + "\nBeats:\n" + "\n".join(lines)
    elif mode == "extend_video":
        hold = (
            "Continue the supplied clip. Do not restart the story or recast the opening. "
            "Keep identity, wardrobe, product and layout. Hold the last second as an end card."
        )
    else:
        hold = _hold_copy(surface)
    return f"""Animate the supplied visual plate from a finished Brazilian advertising creative.

{_surface_copy(surface, plan)}
{plate}
Do not add people, products or extra limbs.

Preserve people, faces, wardrobe, products, package geometry, brand colors and composition.

Motion:
{motion}

Intensity:
{intensity}

Duration:
{plan.get("duration")} seconds.

{hold}

Audio:
{audio}
{extras}
""".strip()


def _surface_copy(surface, plan):
    ratio = plan.get("piece_ratio") or plan.get("aspect_ratio") or "16:9"
    if surface == "display_square":
        return (
            f"This is a finished square display unit ({ratio}), not a film and not a social restack. "
            "Keep the approved composition: headline, dates, venue, artist names, tagline, "
            "footer lockup and logos stay exactly where they are. Do not restack into "
            "visual-on-top and headline-in-a-lower-band. Motion lives in decoration "
            "(flags, paper, light, fabric), never in letters."
        )
    if surface == "display":
        return (
            f"This is an in-banner display unit ({ratio}). Keep the IAB rectangle. "
            "Do not reframe into a poster or a 16:9 film. Lock every visible letter and mark."
        )
    if surface == "story":
        return (
            f"This is a vertical story unit ({ratio}). Keep safe areas. "
            "Do not crop faces or type into the UI chrome zones."
        )
    if surface == "feed":
        return (
            f"This is a feed still ({ratio}). Keep the approved crop. "
            "Do not convert it into a square or a story."
        )
    return (
        f"This is a landscape video plate ({ratio}). Keep cinematic framing. "
        "Do not convert it into a square display."
    )


def _hold_copy(surface):
    if surface in DISPLAY_SURFACES:
        return (
            "This is a display loop. First and last frames must match the approved still. "
            "Do not introduce new visual information. Do not rewrite names, dates, prices or logos. "
            "People may breathe; they must not walk out of their marks or lip-sync."
        )
    return (
        "Keep reserved empty areas usable. Hold the final second as a clean end card. "
        "Do not introduce new visual information in the last frame."
    )


def _plate_copy(plan):
    mode = str((plan.get("source") or {}).get("mode") or "")
    if mode == "extend_video":
        return (
            "This is a video continuation. Preserve the people, faces, wardrobe, products and brand "
            "already in the clip. Do not replace, rewrite or invent letters, logos, prices or UI."
        )
    if mode == "storyboard":
        return (
            "These are flattened stills in storyboard order. Typography, logos and prices may be baked in. "
            "Do not replace, rewrite or invent letters, logos, prices, buttons, watermarks or UI."
        )
    if mode in {"protected_scene", "transition_ab"} and (
        (plan.get("source") or {}).get("snapshot")
        or (plan.get("source") or {}).get("snapshot_a")
        or (plan.get("source") or {}).get("snapshot_b")
    ):
        return (
            "Protected typography, logos, prices and buttons were removed from the supplied plates. "
            "Do not recreate letters, logos, prices, buttons, watermarks or UI in the empty reserved areas. "
            "Keep those reserved areas empty and stable so overlays can be composited later."
        )
    return (
        "This is a flattened still. Typography, logos, prices and packaging may already be baked in. "
        "Do not replace, rewrite or invent letters, logos, prices, buttons, watermarks or UI."
    )
