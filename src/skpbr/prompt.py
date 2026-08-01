"""Deterministic English Prompt encoding used by SKPBR v0.1."""

from __future__ import annotations

import re

import numpy as np


ARCHETYPES = (
    "bare_metal",
    "rusted_metal",
    "plastic_rubber",
    "paint_coating",
    "automotive_paint",
    "marble",
    "porous_stone",
    "concrete_asphalt",
    "masonry_plaster",
    "ceramic",
    "engineered_composite",
)
ARCHETYPE_INDEX = {name: index for index, name in enumerate(ARCHETYPES)}

BASIC_COLORS: dict[str, tuple[float, float, float]] = {
    "red": (0.72, 0.035, 0.020),
    "blue": (0.025, 0.14, 0.68),
    "green": (0.035, 0.43, 0.13),
    "yellow": (0.80, 0.70, 0.09),
    "orange": (0.72, 0.25, 0.025),
    "brown": (0.34, 0.14, 0.055),
    "black": (0.035, 0.040, 0.045),
    "white": (0.86, 0.85, 0.80),
    "gray": (0.47, 0.48, 0.49),
    "silver": (0.72, 0.74, 0.77),
    "gold": (0.75, 0.50, 0.11),
    "copper": (0.68, 0.27, 0.09),
    "purple": (0.39, 0.075, 0.55),
    "pink": (0.78, 0.25, 0.43),
    "beige": (0.73, 0.63, 0.47),
}
COLOR_NAMES = tuple(BASIC_COLORS)
COLOR_ALIASES: dict[str, tuple[str, ...]] = {
    "red": ("red",),
    "blue": ("blue",),
    "green": ("green",),
    "yellow": ("yellow",),
    "orange": ("orange",),
    "brown": ("brown",),
    "black": ("black",),
    "white": ("white",),
    "gray": ("gray", "grey"),
    "silver": ("silver",),
    "gold": ("gold", "golden"),
    "copper": ("copper", "copper colored", "copper colour"),
    "purple": ("purple",),
    "pink": ("pink",),
    "beige": ("beige",),
}

FINISH_TARGETS = {
    "polished": 0.16,
    "smooth": 0.33,
    "matte": 0.62,
    "rough": 0.82,
}
FINISH_NAMES = tuple(FINISH_TARGETS)
FINISH_ALIASES: dict[str, tuple[str, ...]] = {
    "polished": ("polished", "glossy", "high gloss"),
    "smooth": ("smooth", "satin"),
    "matte": ("matte", "matt"),
    "rough": ("rough", "coarse"),
}

MICRO_FLAGS = (
    "brushed",
    "speckled",
    "cracked",
    "porous",
    "rusted",
    "woven",
    "patterned",
    "flaked",
    "weathered",
    "layered",
)
MICRO_ALIASES: dict[str, tuple[str, ...]] = {
    "brushed": ("brushed",),
    "speckled": ("speckled", "flecked"),
    "cracked": ("cracked", "crackle"),
    "porous": ("porous",),
    "rusted": ("rusted", "rusty"),
    "woven": ("woven", "weave"),
    "patterned": ("patterned", "diamond plate"),
    "flaked": ("metal flake", "metallic flake"),
    "weathered": ("weathered", "worn"),
    "layered": ("layered", "clearcoat", "clear coat"),
}

ARCHETYPE_ALIASES: dict[str, tuple[str, ...]] = {
    "automotive_paint": ("automotive paint", "car paint", "auto paint"),
    "rusted_metal": ("rusted metal", "rusty metal"),
    "bare_metal": (
        "aluminum",
        "aluminium",
        "steel",
        "iron",
        "copper",
        "brass",
        "zinc",
        "metal",
    ),
    "plastic_rubber": ("plastic", "rubber", "abs", "hdpe"),
    "paint_coating": (
        "paint coating",
        "powder coat",
        "epoxy coating",
        "latex paint",
    ),
    "marble": ("marble",),
    "porous_stone": ("granite", "basalt", "slate", "limestone", "stone"),
    "concrete_asphalt": ("concrete", "asphalt"),
    "masonry_plaster": ("brick", "plaster", "terracotta"),
    "ceramic": ("ceramic", "porcelain"),
    "engineered_composite": ("composite", "carbon fiber", "terrazzo"),
}

FAMILY_NAMES = (
    "rusted_metal",
    "veined_marble",
    "gravel",
    "automotive_paint",
    "chipped_paint",
    "cracked_concrete",
    "speckled_ceramic",
    "hammered_metal",
)
FAMILY_INDEX = {name: index for index, name in enumerate(FAMILY_NAMES)}
EFFECT_NAMES = (
    "rust",
    "patina",
    "vein",
    "gravel_cell",
    "flake",
    "chip",
    "crack",
    "pore",
    "speckle",
    "hammer",
    "scratch",
    "coating",
)
EFFECT_INDEX = {name: index for index, name in enumerate(EFFECT_NAMES)}
EFFECT_ALIASES: dict[str, tuple[str, ...]] = {
    "rust": ("rust", "rusted", "rusty", "oxidized", "oxidised"),
    "patina": ("patina", "verdigris", "copper green"),
    "vein": ("vein", "veined", "veining", "marbling"),
    "gravel_cell": ("gravel", "pebble", "crushed stone", "aggregate"),
    "flake": ("flake", "metal flake", "metallic flake", "sparkle"),
    "chip": ("chip", "chipped", "peeling", "paint loss"),
    "crack": ("crack", "cracked", "crackle"),
    "pore": ("pore", "porous", "pitted"),
    "speckle": ("speckle", "speckled", "fleck", "spotted"),
    "hammer": ("hammered", "hammer finish", "dimpled"),
    "scratch": ("scratch", "scratched", "scuff"),
    "coating": ("paint", "coating", "lacquer", "glaze"),
}


def _contains(text: str, alias: str) -> bool:
    if re.fullmatch(r"[a-z0-9 ]+", alias):
        return bool(re.search(rf"\b{re.escape(alias)}\b", text))
    return alias in text


def _find_alias(text: str, aliases: dict[str, tuple[str, ...]]) -> str | None:
    candidates: list[tuple[int, str]] = []
    for name, values in aliases.items():
        for alias in values:
            if _contains(text, alias):
                candidates.append((len(alias), name))
    return max(candidates, default=(0, None))[1]


def infer_archetype(description: str, fallback: str | None = None) -> str:
    normalized = description.casefold().replace("-", " ")
    rust_markers = ("rusted", "rusty", "oxidized", "oxidised")
    metal_markers = (
        "metal",
        "copper",
        "steel",
        "iron",
        "brass",
        "zinc",
        "aluminum",
        "aluminium",
    )
    if any(_contains(normalized, value) for value in rust_markers) and any(
        _contains(normalized, value) for value in metal_markers
    ):
        return "rusted_metal"
    if any(
        value in normalized
        for value in ("car paint", "automotive paint", "auto paint")
    ):
        return "automotive_paint"
    if any(
        _contains(normalized, value)
        for value in ("gravel", "pebble", "crushed stone")
    ):
        return "porous_stone"
    detected = _find_alias(normalized, ARCHETYPE_ALIASES)
    if detected is not None:
        return detected
    if fallback in ARCHETYPE_INDEX:
        return str(fallback)
    return "paint_coating"


GLOBAL_ATTRIBUTE_DIM = (
    len(ARCHETYPES)
    + 3
    + len(COLOR_NAMES)
    + 1
    + 1
    + len(FINISH_NAMES)
    + 1
    + 1
    + 1
    + len(MICRO_FLAGS)
    + 1
)
SPATIAL_ATTRIBUTE_DIM = len(FAMILY_NAMES) + len(EFFECT_NAMES) + 3
CONDITION_DIM = GLOBAL_ATTRIBUTE_DIM + SPATIAL_ATTRIBUTE_DIM


def parse_global(description: str) -> dict[str, object]:
    normalized = " ".join(description.casefold().replace("-", " ").split())
    archetype = infer_archetype(normalized)
    color = _find_alias(normalized, COLOR_ALIASES)
    finish = _find_alias(normalized, FINISH_ALIASES)
    dark = any(_contains(normalized, value) for value in ("dark", "deep"))
    light = any(_contains(normalized, value) for value in ("light", "pale"))
    secondary_context = any(
        _contains(normalized, value)
        for value in ("vein", "veins", "veining", "texture", "pattern")
    )
    secondary_color = color if color is not None and secondary_context else None
    if secondary_color is not None:
        color = None
    implicit_dark = color is None and dark
    if implicit_dark:
        color = "black"
    color_rgb = np.zeros(3, dtype=np.float32)
    color_one_hot = np.zeros(len(COLOR_NAMES), dtype=np.float32)
    if color is not None:
        color_rgb[:] = (0.12, 0.13, 0.14) if implicit_dark else BASIC_COLORS[color]
        if dark and not implicit_dark:
            color_rgb *= 0.62
        elif light:
            color_rgb = color_rgb * 0.62 + 0.34
        color_one_hot[COLOR_NAMES.index(color)] = 1.0
    finish_one_hot = np.zeros(len(FINISH_NAMES), dtype=np.float32)
    roughness_target = 0.0
    if finish is not None:
        finish_one_hot[FINISH_NAMES.index(finish)] = 1.0
        roughness_target = FINISH_TARGETS[finish]
    explicit_metallic = any(
        _contains(normalized, value) for value in ("metallic", "metal flake")
    )
    explicit_nonmetal = any(
        _contains(normalized, value) for value in ("non metallic", "nonmetal")
    )
    metallic_active = explicit_metallic or explicit_nonmetal
    metallic_target = 0.92 if explicit_metallic and not explicit_nonmetal else 0.02
    micro = np.asarray(
        [
            float(any(_contains(normalized, alias) for alias in MICRO_ALIASES[name]))
            for name in MICRO_FLAGS
        ],
        dtype=np.float32,
    )
    archetype_one_hot = np.zeros(len(ARCHETYPES), dtype=np.float32)
    archetype_one_hot[ARCHETYPE_INDEX[archetype]] = 1.0
    vector = np.concatenate(
        (
            archetype_one_hot,
            color_rgb,
            color_one_hot,
            np.asarray([float(color is not None)], dtype=np.float32),
            np.asarray([roughness_target], dtype=np.float32),
            finish_one_hot,
            np.asarray([float(finish is not None)], dtype=np.float32),
            np.asarray([metallic_target], dtype=np.float32),
            np.asarray([float(metallic_active)], dtype=np.float32),
            micro,
            np.asarray([float(bool(normalized))], dtype=np.float32),
        )
    ).astype(np.float32)
    if vector.shape != (GLOBAL_ATTRIBUTE_DIM,):
        raise RuntimeError("SKPBR global Prompt dimension changed")
    return {
        "description": description,
        "archetype": archetype,
        "color": color,
        "secondary_color": secondary_color,
        "finish": finish,
        "metallic_active": bool(metallic_active),
        "micro_flags": [
            name for name, active in zip(MICRO_FLAGS, micro) if bool(active)
        ],
        "vector": vector,
    }


def infer_family(description: str, parsed_archetype: str) -> str:
    value = description.casefold().replace("-", " ")
    if any(_contains(value, alias) for alias in EFFECT_ALIASES["chip"]):
        return "chipped_paint"
    if any(_contains(value, alias) for alias in EFFECT_ALIASES["rust"]):
        return "rusted_metal"
    if any(_contains(value, alias) for alias in EFFECT_ALIASES["vein"]) and (
        "marble" in value or parsed_archetype == "marble"
    ):
        return "veined_marble"
    if any(_contains(value, alias) for alias in EFFECT_ALIASES["gravel_cell"]):
        return "gravel"
    if any(_contains(value, alias) for alias in EFFECT_ALIASES["crack"]):
        return "cracked_concrete"
    if any(_contains(value, alias) for alias in EFFECT_ALIASES["speckle"]):
        return "speckled_ceramic"
    if any(_contains(value, alias) for alias in EFFECT_ALIASES["hammer"]):
        return "hammered_metal"
    if parsed_archetype == "automotive_paint" or any(
        marker in value for marker in ("automotive", "car paint")
    ):
        return "automotive_paint"
    fallback = {
        "rusted_metal": "rusted_metal",
        "marble": "veined_marble",
        "porous_stone": "gravel",
        "concrete_asphalt": "cracked_concrete",
        "ceramic": "speckled_ceramic",
        "bare_metal": "hammered_metal",
        "paint_coating": "chipped_paint",
        "automotive_paint": "automotive_paint",
    }
    return fallback.get(parsed_archetype, "automotive_paint")


def parse_prompt(description: str) -> dict[str, object]:
    parsed = parse_global(description)
    family = infer_family(description, str(parsed["archetype"]))
    family_one_hot = np.zeros(len(FAMILY_NAMES), dtype=np.float32)
    family_one_hot[FAMILY_INDEX[family]] = 1.0
    effects = np.zeros(len(EFFECT_NAMES), dtype=np.float32)
    for name in EFFECT_NAMES:
        if any(_contains(description.casefold(), alias) for alias in EFFECT_ALIASES[name]):
            effects[EFFECT_INDEX[name]] = 1.0
    implied = {
        "rusted_metal": ("rust",),
        "veined_marble": ("vein",),
        "gravel": ("gravel_cell", "pore"),
        "automotive_paint": ("coating",),
        "chipped_paint": ("chip", "coating"),
        "cracked_concrete": ("crack", "pore"),
        "speckled_ceramic": ("speckle", "coating"),
        "hammered_metal": ("hammer",),
    }
    for name in implied[family]:
        effects[EFFECT_INDEX[name]] = 1.0
    secondary_rgb = np.zeros(3, dtype=np.float32)
    secondary = parsed.get("secondary_color")
    if secondary in BASIC_COLORS:
        secondary_rgb[:] = BASIC_COLORS[str(secondary)]
    spatial = np.concatenate((family_one_hot, effects, secondary_rgb)).astype(
        np.float32
    )
    condition = np.concatenate(
        (np.asarray(parsed["vector"], dtype=np.float32), spatial)
    ).astype(np.float32)
    if condition.shape != (CONDITION_DIM,):
        raise RuntimeError("SKPBR full Prompt dimension changed")
    return {
        **parsed,
        "spatial_family": family,
        "spatial_effects": [
            name for name in EFFECT_NAMES if bool(effects[EFFECT_INDEX[name]])
        ],
        "condition_vector": condition,
    }
