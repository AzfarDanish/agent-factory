"""Prompt engineering templates, style presets, and coloring page design rules.

These templates produce prompts optimized for generating proper coloring pages:
thick black lines, white background, closed shapes, no shading, large open areas.
"""

from src.core.coloring_domain import (
    AgeGroup, Style, get_style_description, get_line_width_range,
)

# ── CORE COLORING PAGE INSTRUCTION ──

BASE_INSTRUCTION = (
    "Black and white coloring page suitable for children. "
    "Pure white background ONLY. No colors, no shading, no gradients, no gray areas. "
    "Every element MUST have thick, bold, unbroken black outlines. "
    "All shapes MUST be fully closed — no open lines, no incomplete paths. "
    "Large open white spaces inside each shape for coloring. "
    "No filled areas, no solid black sections larger than 2px. "
    "No shadows, no highlights, no texture. "
    "Clean, simple, unmistakable line art."
)

# ── AGE GROUP MODIFIERS ──

AGE_GROUP_MODIFIERS: dict[AgeGroup, str] = {
    AgeGroup.TODDLER: (
        "SUPER SIMPLE design with very thick lines (4-6px). "
        "Maximum 5 large, chunky shapes. Huge open areas. "
        "Round, soft shapes — no sharp corners or complex curves. "
        "A single large central subject, nothing in background. "
        "Easy for a toddler to recognize and color without going outside lines."
    ),
    AgeGroup.CHILD: (
        "Simple, friendly design with thick lines (3-4px). "
        "10-15 closed shapes with clearly separated sections. "
        "Cute, approachable subject with big eyes and soft features. "
        "Minimal background elements. Fun and engaging. "
        "Perfect for a child age 5-10 to color independently."
    ),
    AgeGroup.TEEN: (
        "Moderate detail with medium lines (2-3px). "
        "Mix of large and small sections for varied coloring experience. "
        "More intricate details in some areas while keeping clean lines. "
        "Stylized but recognizable subject matter."
    ),
    AgeGroup.ADULT: (
        "Intricate design with fine lines (1-2px). "
        "Many small sections and detailed patterns. "
        "Suitable for advanced coloring with fine-tip tools. "
        "Complex but every shape remains fully closed."
    ),
}

# ── STYLE-SPECIFIC INSTRUCTIONS ──

STYLE_INSTRUCTIONS: dict[Style, str] = {
    Style.SIMPLE: (
        "Basic geometric shapes. Round forms. Minimal parts. "
        "No small details, no fine line work."
    ),
    Style.DETAILED: (
        "Moderate complexity. Mix of small and large sections. "
        "Some pattern details while keeping main shapes bold."
    ),
    Style.MANDALA: (
        "Radially symmetrical design. Repeating geometric patterns. "
        "Circles, petals, and concentric rings. Meditative."
    ),
    Style.CARTOON: (
        "Playful, exaggerated features. Big round eyes. Friendly smile. "
        "Rounded corners, soft curves. Expressive and warm. "
        "Large clearly defined body sections."
    ),
    Style.REALISTIC: (
        "Natural proportions while keeping it suitable for coloring. "
        "Clean outlines defining each anatomical part clearly. "
        "No photographic style — simplified real-world shapes."
    ),
}

# ── SUBJECT-SPECIFIC GUIDES ──

SUBJECT_GUIDES: dict[str, str] = {
    "animal": (
        "Large head with big eyes. Simple body with 3-4 main sections "
        "(head, torso, limbs). Friendly expression. No fur texture — "
        "use smooth shapes instead."
    ),
    "person": (
        "Large round head. Simple facial features with big eyes and smile. "
        "Body in 4 sections (head, torso, arms, legs). "
        "Simple clothing with 2-3 color zones."
    ),
    "nature": (
        "Large central element (tree, flower, sun) with bold shapes. "
        "Leaves and petals as separate closed shapes. "
        "Clouds as rounded puffy outlines."
    ),
    "vehicle": (
        "Side or simplified front view. Large main body shape. "
        "Round wheels. Windows as separate closed shapes. "
        "No perspective distortion — flat 2D view."
    ),
    "food": (
        "Large single item centered on page. Clearly divided sections "
        "(e.g., pizza slices, burger layers). Round friendly shapes."
    ),
    "fantasy": (
        "Recognizable creature with simplified features. "
        "Wings as separate large shapes. Big eyes. "
        "No complex scales or intricate patterns."
    ),
    "object": (
        "Front-facing view centered on page. 3-5 main sections. "
        "Clean outlines with no perspective distortion."
    ),
}

DEFAULT_SUBJECT_GUIDE = (
    "Centered composition on white background. Large main subject "
    "filling 60-80% of frame. 5-10 clearly separated sections to color. "
    "Thick outlines throughout."
)

# ── NEGATIVE PROMPTS (what to explicitly exclude) ──

BASE_NEGATIVE = (
    "shading, gradients, colors, filled areas, color blocks, "
    "gray areas, half-tones, shadows, highlights, lighting, "
    "3D rendering, perspective, depth of field, blur, "
    "text, letters, words, numbers, labels, "
    "watermarks, signatures, logos, brand marks, "
    "photorealism, photographic, realistic textures, "
    "fur detail, scales, complex patterns, overlapping lines, "
    "unclosed paths, open shapes, incomplete lines, "
    "background scenes, multiple subjects, cluttered composition, "
    "messy lines, sketch lines, rough edges, pencil texture, "
    "cross-hatching, stippling, dots, noise, grain, "
    "fine details that are too small to color between lines"
)

STYLE_NEGATIVE: dict[Style, str] = {
    Style.SIMPLE: BASE_NEGATIVE + ", small details, thin lines, complex shapes",
    Style.DETAILED: BASE_NEGATIVE + ", tiny sections, microscopic details",
    Style.MANDALA: BASE_NEGATIVE + ", asymmetry, irregular borders, non-geometric",
    Style.CARTOON: BASE_NEGATIVE + ", scary elements, realistic proportions, violence",
    Style.REALISTIC: BASE_NEGATIVE + ", photographic style, blur, unfocused areas",
}


def _detect_subject(prompt: str) -> str:
    """Classify a raw prompt into a subject category for guide selection."""
    p = prompt.lower()
    subjects = {
        "animal": ["dog", "cat", "horse", "bear", "rabbit", "bird", "fish", "lion", "tiger", "elephant",
                     "giraffe", "monkey", "dolphin", "whale", "shark", "dinosaur", "dragon",
                     "fox", "wolf", "deer", "mouse", "pig", "cow", "chicken", "duck", "frog",
                     "turtle", "snake", "butterfly", "bee", "ladybug", "penguin", "owl",
                     "parrot", "animal", "pony", "kitten", "puppy", "bunny", "hamster", "pet"],
        "person": ["boy", "girl", "child", "kid", "man", "woman", "person", "people", "family",
                    "baby", "mom", "dad", "mother", "father", "sister", "brother",
                    "princess", "prince", "knight", "wizard", "fairy", "elf", "pirate",
                    "superhero", "scientist", "doctor", "teacher", "chef", "farmer"],
        "nature": ["tree", "flower", "garden", "forest", "sun", "rainbow", "mountain",
                    "ocean", "beach", "lake", "river", "rain", "snow", "weather",
                    "plant", "leaf", "rose", "tulip", "sunflower", "nature"],
        "vehicle": ["car", "truck", "bus", "train", "plane", "airplane", "boat", "ship",
                     "rocket", "bicycle", "motorcycle", "tractor", "helicopter", "submarine",
                     "ambulance", "fire truck", "police car"],
        "food": ["pizza", "cake", "ice cream", "cookie", "bread", "fruit", "apple",
                  "banana", "grape", "watermelon", "strawberry", "sandwich", "burger",
                  "fries", "pasta", "sushi", "donut", "cupcake", "candy", "food", "pancake",
                  "waffle", "juice", "milk", "cheese"],
        "fantasy": ["unicorn", "dragon", "mermaid", "fairy", "phoenix", "griffin",
                     "centaur", "pegasus", "witch", "wizard", "magic", "monster",
                     "alien", "robot", "ghost", "pumpkin", "castle", "knight", "princess"],
        "object": ["house", "building", "ball", "toy", "book", "gift", "present",
                    "hat", "shoe", "dress", "crown", "wand", "sword", "shield",
                    "chair", "table", "lamp", "clock", "camera", "phone"],
    }

    for category, keywords in subjects.items():
        for kw in keywords:
            if kw in p:
                return category
    return "general"


def build_refined_prompt(
    raw_prompt: str,
    age_group: AgeGroup,
    style: Style,
) -> str:
    """Build the full refined prompt for image generation.

    Combines: base instruction → age modifier → style guide → subject guide
    → theme specification → output constraints.
    """
    subject_type = _detect_subject(raw_prompt)
    subject_guide = SUBJECT_GUIDES.get(subject_type, DEFAULT_SUBJECT_GUIDE)
    style_guide = STYLE_INSTRUCTIONS[style]
    age_mod = AGE_GROUP_MODIFIERS[age_group]
    line_min, line_max = get_line_width_range(age_group)

    parts = [
        BASE_INSTRUCTION,
        f"Line thickness: {line_min}-{line_max} pixels wide, consistent throughout.",
        style_guide,
        age_mod,
        subject_guide,
        f"Theme: {raw_prompt}",
        "Single subject centered. No background details beyond essential context.",
        "Final image MUST be pure black lines on pure white background. No gray. No color.",
    ]

    return " ".join(parts)


def build_negative_prompt(style: Style) -> str:
    """Return the negative prompt for the given style."""
    return STYLE_NEGATIVE[style]


def build_system_prompt() -> str:
    """Build the system prompt for the DeepSeek reasoning worker."""
    return (
        "You are a professional coloring page designer specializing in children's coloring books. "
        "Your job is to transform user descriptions into precise, optimized prompts for an "
        "AI image generator that produces black-and-white line art coloring pages.\n\n"

        "DESIGN PRINCIPLES:\n"
        "1. Thick, consistent black outlines — no thin or broken lines\n"
        "2. Every shape MUST be fully closed — no open paths\n"
        "3. Large white areas inside shapes — easy to color without going outside lines\n"
        "4. Pure white background — no shading, gradients, or gray areas\n"
        "5. Age-appropriate complexity (toddler: ≤5 big shapes, child: ≤15, teen: ≤30, adult: unlimited)\n"
        "6. Simple, recognizable subjects with friendly, approachable features\n"
        "7. No text, letters, numbers, or words anywhere in the image\n\n"

        "OUTPUT FORMAT:\n"
        "Return ONLY valid JSON with these keys:\n"
        "- refined_prompt: string (the complete optimized prompt for image generation)\n"
        "- negative_prompt: string (what to explicitly exclude)\n"
        "- confidence: float 0.0-1.0 (how suitable this request is for a coloring page)\n\n"

        "EXAMPLES OF GOOD SUBJECTS:\n"
        "- A friendly cat sitting with a big smile and round eyes\n"
        "- A simple house with a roof, door, and two windows\n"
        "- A large sunflower with 6 petals in a circle\n\n"

        "EXAMPLES OF POOR SUBJECTS:\n"
        "- A detailed landscape with multiple elements (too complex for a single page)\n"
        "- Abstract patterns without recognizable forms (confusing for children)\n"
        "- Subjects with tiny overlapping details (impossible to color between lines)"
    )
