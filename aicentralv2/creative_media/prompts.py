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
    hold = (
        "Interpolate from the first plate to the last plate. "
        "Hold the final second as a clean end card matching the last plate. "
        "Do not introduce new visual information in the last frame."
        if (plan.get("source") or {}).get("mode") == "transition_ab"
        else (
            "Keep reserved empty areas usable. Hold the final second as a clean end card. "
            "Do not introduce new visual information in the last frame."
        )
    )
    return f"""Animate the supplied visual plate from a finished Brazilian advertising creative.

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


def _plate_copy(plan):
    mode = str((plan.get("source") or {}).get("mode") or "")
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
