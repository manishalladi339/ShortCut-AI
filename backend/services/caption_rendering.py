"""Compile caption cues into an ASS subtitle document with deterministic styling."""
from __future__ import annotations

from models.render_plan import RenderPlan


def _ass_time(seconds: float) -> str:
    centiseconds = max(0, round(seconds * 100))
    hours, remainder = divmod(centiseconds, 360000)
    minutes, remainder = divmod(remainder, 6000)
    secs, cs = divmod(remainder, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{cs:02}"


def _escape_ass_text(text: str) -> str:
    # Prevent user text from being interpreted as ASS override tags.
    safe = text.replace("\\", r"\\")
    safe = safe.replace("{", "(").replace("}", ")")
    safe = safe.replace("\r\n", "\n").replace("\r", "\n").replace("\n", r"\N")
    return safe.strip()


def _base_font_size(height: int) -> int:
    return max(24, min(96, round(height * 0.036)))


def _animation_tags(
    *,
    animation: str,
    x: int,
    y: int,
    height: int,
    cue_duration_ms: int,
) -> str:
    """Return ASS tags for supported cue-level animations.

    These animations intentionally operate at cue level. Word-by-word karaoke
    requires word timing provenance and is handled separately in future work.
    """
    value = animation.strip().lower()
    if value in {"", "none", "static"}:
        return f"\\pos({x},{y})"

    cue_duration_ms = max(1, cue_duration_ms)
    intro_ms = min(220, max(80, cue_duration_ms // 4))
    outro_ms = min(140, max(60, cue_duration_ms // 6))

    if value == "pop":
        return (
            f"\\pos({x},{y})"
            r"\fscx82\fscy82"
            + f"\\t(0,{intro_ms},\\fscx100\\fscy100)"
            + f"\\fad(50,{outro_ms})"
        )

    if value in {"slide_up", "rise"}:
        offset = max(18, min(72, round(height * 0.025)))
        start_y = min(height - 1, y + offset)
        return (
            f"\\move({x},{start_y},{x},{y},0,{intro_ms})"
            + f"\\fad(70,{outro_ms})"
        )

    if value == "fade":
        return f"\\pos({x},{y})\\fad({intro_ms},{outro_ms})"

    # Unknown style data must not create unpredictable ASS output.
    return f"\\pos({x},{y})"


def _cue_override(
    *,
    style: dict,
    width: int,
    height: int,
    cue_duration_ms: int,
) -> str:
    base_size = _base_font_size(height)
    size_scale = float(style.get("size_scale", 1.0))
    size_scale = max(0.5, min(2.0, size_scale))

    preset = str(style.get("preset") or "default").lower()
    if preset == "social":
        size_scale *= 1.08
    font_size = max(12, min(160, round(base_size * size_scale)))

    position = str(style.get("vertical_position") or "default").lower()
    y_ratio = {
        "higher": 0.76,
        "default": 0.86,
        "lower": 0.92,
    }.get(position, 0.86)
    x = round(width / 2)
    y = round(height * y_ratio)

    if preset == "minimal":
        border = 1
        spacing = 0
    elif preset == "social":
        border = 3
        spacing = 0.4
    else:
        border = 2
        spacing = 0
    shadow = 0

    animation = str(style.get("animation") or "none")
    animation_tags = _animation_tags(
        animation=animation,
        x=x,
        y=y,
        height=height,
        cue_duration_ms=cue_duration_ms,
    )

    return (
        r"{\an2"
        + animation_tags
        + f"\\fs{font_size}"
        + f"\\bord{border}"
        + f"\\shad{shadow}"
        + f"\\fsp{spacing:.2f}"
        + "}"
    )


def build_ass_document(plan: RenderPlan) -> str:
    """Return a complete ASS document honoring supported ProjectState caption styles."""
    base_size = _base_font_size(plan.height)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {plan.width}
PlayResY: {plan.height}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,{base_size},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,2,0,2,40,40,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    lines = [header.rstrip()]
    for cue in plan.captions:
        start_sec = (
            cue.start * plan.timebase_denominator / plan.timebase_numerator
        )
        duration_sec = (
            cue.duration * plan.timebase_denominator / plan.timebase_numerator
        )
        end_sec = start_sec + duration_sec
        override = _cue_override(
            style=cue.style or {},
            width=plan.width,
            height=plan.height,
            cue_duration_ms=max(1, round(duration_sec * 1000)),
        )
        text = _escape_ass_text(cue.text)
        lines.append(
            "Dialogue: 0,"
            f"{_ass_time(start_sec)},{_ass_time(end_sec)},"
            f"Default,,0,0,0,,{override}{text}"
        )

    return "\n".join(lines) + "\n"
