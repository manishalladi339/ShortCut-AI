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
    duration_ms: int,
) -> str:
    animation = animation.lower().strip()
    if animation in {"", "none", "static"}:
        return f"\\pos({x},{y})"

    if animation in {"fade", "fade_in", "fade-in"}:
        fade_ms = min(140, max(40, duration_ms // 6))
        return f"\\pos({x},{y})\\fad({fade_ms},{fade_ms})"

    if animation in {"pop", "punch", "bounce"}:
        first = min(110, max(45, duration_ms // 6))
        second = min(max(first + 40, 120), max(first + 40, duration_ms // 3))
        second = min(second, duration_ms)
        return (
            f"\\pos({x},{y})"
            r"\fscx88\fscy88"
            + f"\\t(0,{first},\\fscx108\\fscy108)"
            + f"\\t({first},{second},\\fscx100\\fscy100)"
        )

    if animation in {"slide_up", "slide-up", "rise"}:
        slide_ms = min(180, max(70, duration_ms // 4))
        start_y = min(height - 8, y + max(28, round(height * 0.035)))
        return (
            f"\\move({x},{start_y},{x},{y},0,{slide_ms})"
            f"\\fad({min(70, slide_ms)},{min(90, max(40, duration_ms // 8))})"
        )

    # Unknown/untrusted values are rendered statically rather than interpreted.
    return f"\\pos({x},{y})"


def _cue_override(
    *,
    style: dict,
    width: int,
    height: int,
    duration_sec: float,
) -> str:
    base_size = _base_font_size(height)
    size_scale = float(style.get("size_scale", 1.0))
    size_scale = max(0.5, min(2.0, size_scale))
    font_size = max(12, min(160, round(base_size * size_scale)))

    position = str(style.get("vertical_position") or "default").lower()
    y_ratio = {
        "higher": 0.76,
        "default": 0.86,
        "lower": 0.92,
    }.get(position, 0.86)
    x = round(width / 2)
    y = round(height * y_ratio)

    preset = str(style.get("preset") or "default").lower()
    if preset in {"social", "bold"}:
        border = 3
        font_size = min(160, round(font_size * 1.08))
        extra = r"\b1\blur0.35"
    elif preset == "minimal":
        border = 1
        extra = r"\b1"
    else:
        border = 2
        extra = r"\b1"

    animation = str(style.get("animation") or "none")
    duration_ms = max(1, round(max(0.001, duration_sec) * 1000))
    motion = _animation_tags(
        animation=animation,
        x=x,
        y=y,
        height=height,
        duration_ms=duration_ms,
    )

    return (
        r"{\an2"
        + motion
        + f"\\fs{font_size}"
        + f"\\bord{border}"
        + r"\shad0"
        + extra
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
            duration_sec=duration_sec,
        )
        text = _escape_ass_text(cue.text)
        lines.append(
            "Dialogue: 0,"
            f"{_ass_time(start_sec)},{_ass_time(end_sec)},"
            f"Default,,0,0,0,,{override}{text}"
        )

    return "\n".join(lines) + "\n"
