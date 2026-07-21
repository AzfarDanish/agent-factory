"""Coloring page domain rules — complexity, constraints, age validation.

This module encodes what a valid coloring page is: black line art on white
background, no fills, no shading, clear closed shapes. It does NOT generate
images or prompts — it only validates and constrains.
"""

from enum import Enum
from typing import Literal


class AgeGroup(str, Enum):
    TODDLER = "toddler"
    CHILD = "child"
    TEEN = "teen"
    ADULT = "adult"


class Style(str, Enum):
    SIMPLE = "simple"
    DETAILED = "detailed"
    MANDALA = "mandala"
    CARTOON = "cartoon"
    REALISTIC = "realistic"


# Max closed shapes per age group
COMPLEXITY_LIMITS: dict[AgeGroup, int] = {
    AgeGroup.TODDLER: 5,
    AgeGroup.CHILD: 10,
    AgeGroup.TEEN: 25,
    AgeGroup.ADULT: 999,  # unbounded
}

# Line width ranges in pixels (thicker = more visible, easier to color within)
LINE_WIDTH_RANGES: dict[AgeGroup, tuple[int, int]] = {
    AgeGroup.TODDLER: (4, 6),
    AgeGroup.CHILD: (3, 5),
    AgeGroup.TEEN: (2, 4),
    AgeGroup.ADULT: (1, 3),
}

# Which styles are allowed per age group
ALLOWED_STYLES: dict[AgeGroup, list[Style]] = {
    AgeGroup.TODDLER: [Style.SIMPLE, Style.CARTOON],
    AgeGroup.CHILD: [Style.SIMPLE, Style.CARTOON, Style.DETAILED],
    AgeGroup.TEEN: [Style.SIMPLE, Style.DETAILED, Style.CARTOON, Style.MANDALA],
    AgeGroup.ADULT: [Style.SIMPLE, Style.DETAILED, Style.MANDALA, Style.CARTOON, Style.REALISTIC],
}

# Style descriptions for prompt engineering
STYLE_DESCRIPTIONS: dict[Style, str] = {
    Style.SIMPLE: "Very simple shapes, thick outlines, minimal details, large open areas to color",
    Style.DETAILED: "Moderate detail level, clear outlines, a mix of large and small areas",
    Style.MANDALA: "Intricate symmetrical patterns, many small repeating sections, meditative",
    Style.CARTOON: "Playful rounded shapes, expressive characters, thick friendly lines",
    Style.REALISTIC: "More natural proportions, finer lines, detailed textures while keeping closed shapes",
}


class ColoringPageError(ValueError):
    """Raised when a coloring page request violates domain rules."""


def validate_age_group(age_group: str) -> AgeGroup:
    """Validate and normalize age group string."""
    try:
        return AgeGroup(age_group.lower())
    except ValueError:
        valid = [a.value for a in AgeGroup]
        raise ColoringPageError(f"Invalid age_group '{age_group}'. Must be one of: {valid}")


def validate_style(style: str, age_group: AgeGroup) -> Style:
    """Validate style is allowed for the given age group."""
    try:
        s = Style(style.lower())
    except ValueError:
        valid = [st.value for st in Style]
        raise ColoringPageError(f"Invalid style '{style}'. Must be one of: {valid}")

    allowed = ALLOWED_STYLES[age_group]
    if s not in allowed:
        allowed_names = [st.value for st in allowed]
        raise ColoringPageError(
            f"Style '{style}' not allowed for age group '{age_group.value}'. "
            f"Allowed: {allowed_names}"
        )
    return s


def get_complexity_limit(age_group: AgeGroup) -> int:
    """Return max recommended closed shapes for the age group."""
    return COMPLEXITY_LIMITS[age_group]


def get_line_width_range(age_group: AgeGroup) -> tuple[int, int]:
    """Return (min, max) line width in pixels."""
    return LINE_WIDTH_RANGES[age_group]


def get_style_description(style: Style) -> str:
    """Return a prose description of the style for prompt engineering."""
    return STYLE_DESCRIPTIONS[style]


def validate_prompt(prompt: str) -> str:
    """Validate and normalize a raw prompt string."""
    stripped = prompt.strip()
    if len(stripped) < 3:
        raise ColoringPageError("Prompt must be at least 3 characters")
    if len(stripped) > 500:
        raise ColoringPageError("Prompt must be 500 characters or fewer")
    return stripped


def validate_quantity(quantity: int) -> int:
    """Validate the number of requested variations."""
    if not isinstance(quantity, int) or quantity < 1 or quantity > 10:
        raise ColoringPageError("Quantity must be an integer between 1 and 10")
    return quantity


def validate_request(
    prompt: str,
    age_group: str,
    style: str,
    quantity: int = 1,
) -> dict:
    """Validate a complete coloring request. Returns normalized dict or raises."""
    valid_prompt = validate_prompt(prompt)
    valid_age = validate_age_group(age_group)
    valid_style = validate_style(style, valid_age)
    valid_qty = validate_quantity(quantity)

    return {
        "prompt": valid_prompt,
        "age_group": valid_age.value,
        "style": valid_style.value,
        "quantity": valid_qty,
    }
