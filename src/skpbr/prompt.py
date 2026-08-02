"""Deterministic bilingual Prompt encoding for the planar SKPBR model."""

from __future__ import annotations

from collections.abc import Iterable
import hashlib
import re

import numpy as np


MATERIAL_CLASSES = (
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
    "cork",
    "leather",
    "textile",
    "loose_granular",
)
CLASS_INDEX = {name: index for index, name in enumerate(MATERIAL_CLASSES)}

PHYSICAL_REGIMES = ("conductor", "dielectric", "coated_conductor", "mixed")
REGIME_INDEX = {name: index for index, name in enumerate(PHYSICAL_REGIMES)}

COLORS: dict[str, tuple[tuple[float, float, float], tuple[str, ...]]] = {
    "black": ((0.035, 0.035, 0.040), ("black", "dark", "黑", "深色")),
    "white": ((0.900, 0.900, 0.880), ("white", "ivory", "白", "象牙")),
    "gray": ((0.430, 0.450, 0.470), ("gray", "grey", "灰")),
    "silver": ((0.720, 0.750, 0.780), ("silver", "银")),
    "red": ((0.660, 0.080, 0.045), ("red", "crimson", "红", "赤")),
    "orange": ((0.860, 0.280, 0.035), ("orange", "橙")),
    "yellow": ((0.780, 0.630, 0.070), ("yellow", "黄")),
    "gold": ((0.820, 0.550, 0.130), ("gold", "golden", "金色", "金纹")),
    "green": ((0.080, 0.420, 0.180), ("green", "verdigris", "patina", "绿", "铜绿")),
    "cyan": ((0.040, 0.480, 0.570), ("cyan", "teal", "青", "青蓝")),
    "blue": ((0.035, 0.180, 0.670), ("blue", "cobalt", "indigo", "蓝", "钴蓝", "靛蓝")),
    "purple": ((0.360, 0.100, 0.480), ("purple", "violet", "紫")),
    "brown": ((0.340, 0.140, 0.055), ("brown", "tan", "棕", "褐")),
    "beige": ((0.660, 0.520, 0.340), ("beige", "sand", "米色", "沙色")),
}
COLOR_NAMES = tuple(COLORS)

FINISHES = ("polished", "glossy", "satin", "matte", "rough", "smooth")
EFFECTS = (
    "brushed",
    "oxidized",
    "rusted",
    "patina",
    "veined",
    "speckled",
    "porous",
    "cracked",
    "aggregate",
    "glazed",
    "flake",
    "woven",
    "grain",
    "coated",
    "weathered",
    "anisotropic",
)
HASH_DIM = 32
CONDITION_DIM = (
    len(MATERIAL_CLASSES)
    + len(PHYSICAL_REGIMES)
    + len(COLOR_NAMES)
    + 3
    + len(FINISHES)
    + len(EFFECTS)
    + 3
    + HASH_DIM
)


def normalize_text(value: str) -> str:
    value = value.casefold().replace("_", " ").replace("-", " ")
    return re.sub(r"\s+", " ", value).strip()


def contains(value: str, aliases: Iterable[str]) -> bool:
    normalized = normalize_text(value)
    for alias in aliases:
        token = normalize_text(alias)
        if token.isascii() and token.replace(" ", "").isalpha():
            if re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", normalized):
                return True
        elif token in normalized:
            return True
    return False


def material_class_for_text(value: str) -> str:
    rules = (
        ("textile", ("fabric", "denim", "cotton", "felt", "lace", "linen", "nylon", "ripstop", "mesh", "tarpaulin", "wool", "布", "棉", "牛仔", "毛毡", "蕾丝", "亚麻", "尼龙", "网", "羊毛")),
        ("leather", ("leather", "suede", "reptile skin", "皮革", "麂皮")),
        ("cork", ("cork", "软木")),
        ("loose_granular", ("sand", "granular", "沙", "砂")),
        ("automotive_paint", ("automotive", "car paint", "车漆", "汽车漆", "汽车金属漆", "车用漆")),
        ("rusted_metal", ("rust", "rusted", "rusty", "oxidized", "oxidised", "patina", "锈", "生锈", "氧化", "铜绿")),
        ("marble", ("marble", "大理石")),
        ("concrete_asphalt", ("concrete", "asphalt", "混凝土", "沥青")),
        ("masonry_plaster", ("brick", "plaster", "gypsum", "terracotta tile", "砖", "石膏", "灰泥")),
        ("ceramic", ("ceramic", "porcelain", "earthenware", "terracotta", "陶", "瓷")),
        ("engineered_composite", ("carbon fiber", "carbon fibre", "terrazzo", "composite", "碳纤维", "磨石")),
        ("plastic_rubber", ("plastic", "abs", "hdpe", "rubber", "polymer", "塑料", "橡胶")),
        ("paint_coating", ("paint", "painted", "coating", "coated", "powder coat", "powder coated", "epoxy", "latex", "lacquer", "漆", "喷漆", "涂层")),
        ("porous_stone", ("granite", "basalt", "slate", "travertine", "rock", "stone", "gravel", "花岗岩", "玄武岩", "板岩", "洞石", "岩石", "砾石")),
        ("bare_metal", ("metal", "steel", "iron", "aluminum", "aluminium", "copper", "brass", "zinc", "foil", "金属", "钢", "铁", "铝", "铜", "黄铜", "锌")),
    )
    for name, aliases in rules:
        if contains(value, aliases):
            return name
    return "paint_coating"


def regime_for_text(value: str, material_class: str | None = None) -> str:
    selected = material_class or material_class_for_text(value)
    if selected == "rusted_metal" or contains(value, ("mixed", "partly metallic", "混合金属")):
        return "mixed"
    if selected in ("paint_coating", "automotive_paint") and contains(
        value, ("steel", "metal", "automotive", "car", "钢", "金属", "车")
    ):
        return "coated_conductor"
    if selected == "bare_metal":
        return "conductor"
    return "dielectric"


def effect_flags(value: str) -> dict[str, float]:
    aliases = {
        "brushed": ("brushed", "拉丝"),
        "oxidized": ("oxidized", "oxidised", "氧化"),
        "rusted": ("rust", "rusted", "锈"),
        "patina": ("patina", "verdigris", "铜绿"),
        "veined": ("vein", "veined", "纹理", "脉络", "石纹"),
        "speckled": ("speckle", "speckled", "fleck", "斑点"),
        "porous": ("pore", "porous", "孔", "多孔"),
        "cracked": ("crack", "cracked", "裂纹", "开裂"),
        "aggregate": ("aggregate", "gravel", "骨料", "砾石"),
        "glazed": ("glaze", "glazed", "釉"),
        "flake": ("flake", "sparkle", "闪片", "闪粉"),
        "woven": ("woven", "weave", "twill", "knit", "编织", "斜纹", "针织"),
        "grain": ("grain", "grainy", "粒面", "颗粒"),
        "coated": ("coat", "coated", "paint", "涂层", "漆"),
        "weathered": ("weathered", "worn", "风化", "磨损"),
        "anisotropic": ("anisotropic", "directional", "brushed", "定向", "拉丝"),
    }
    return {name: float(contains(value, values)) for name, values in aliases.items()}


def _hash_features(text: str) -> np.ndarray:
    result = np.zeros(HASH_DIM, dtype=np.float32)
    for token in re.findall(r"[\w\u4e00-\u9fff]+", normalize_text(text)):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "little") % HASH_DIM
        result[index] += 1.0 if digest[4] & 1 else -1.0
    norm = float(np.linalg.norm(result))
    if norm:
        result /= norm
    return result


def parse_prompt(prompt: str) -> dict[str, object]:
    material_class = material_class_for_text(prompt)
    regime = regime_for_text(prompt, material_class)
    vector = np.zeros(CONDITION_DIM, dtype=np.float32)
    offset = 0
    vector[offset + CLASS_INDEX[material_class]] = 1.0
    offset += len(MATERIAL_CLASSES)
    vector[offset + REGIME_INDEX[regime]] = 1.0
    offset += len(PHYSICAL_REGIMES)

    selected_color = next(
        (name for name, (_, aliases) in COLORS.items() if contains(prompt, aliases)),
        None,
    )
    color_confidence = float(selected_color is not None)
    selected_color = selected_color or "gray"
    vector[offset + COLOR_NAMES.index(selected_color)] = color_confidence
    offset += len(COLOR_NAMES)
    vector[offset : offset + 3] = np.asarray(COLORS[selected_color][0], dtype=np.float32) * color_confidence
    offset += 3

    finish_aliases = {
        "polished": ("polished", "mirror", "抛光", "镜面"),
        "glossy": ("glossy", "shiny", "亮光", "光亮"),
        "satin": ("satin", "semi matte", "semi-matte", "缎面", "半哑光"),
        "matte": ("matte", "matt", "哑光"),
        "rough": ("rough", "coarse", "粗糙"),
        "smooth": ("smooth", "fine", "光滑", "细腻"),
    }
    selected_finish = next(
        (name for name, aliases in finish_aliases.items() if contains(prompt, aliases)),
        None,
    )
    if selected_finish:
        vector[offset + FINISHES.index(selected_finish)] = 1.0
    offset += len(FINISHES)

    effects = effect_flags(prompt)
    vector[offset : offset + len(EFFECTS)] = [effects[name] for name in EFFECTS]
    offset += len(EFFECTS)
    roughness = {
        "polished": 0.12,
        "glossy": 0.25,
        "satin": 0.45,
        "matte": 0.68,
        "rough": 0.86,
        "smooth": 0.35,
    }.get(selected_finish, 0.50)
    metallic = {
        "conductor": 0.95,
        "dielectric": 0.02,
        "coated_conductor": 0.02,
        "mixed": 0.50,
    }[regime]
    vector[offset : offset + 3] = (roughness, metallic, color_confidence)
    offset += 3
    vector[offset : offset + HASH_DIM] = _hash_features(prompt)
    offset += HASH_DIM
    if offset != CONDITION_DIM or not np.isfinite(vector).all():
        raise RuntimeError("Prompt vector contract drift")
    return {
        "prompt": prompt,
        "material_class": material_class,
        "physical_regime": regime,
        "color": selected_color,
        "finish": selected_finish,
        "condition": vector,
        "condition_vector": vector,
    }


# v0.3 adds a second, explicit Prompt contract without changing the 93-D
# conditioning vector consumed by the frozen reconstruction core.
CLASS_SLICE = slice(0, len(MATERIAL_CLASSES))
REGIME_SLICE = slice(CLASS_SLICE.stop, CLASS_SLICE.stop + len(PHYSICAL_REGIMES))
BASE_RGB_SLICE = slice(REGIME_SLICE.stop, REGIME_SLICE.stop + 3)
SECONDARY_RGB_SLICE = slice(BASE_RGB_SLICE.stop, BASE_RGB_SLICE.stop + 3)
BASE_CONFIDENCE_INDEX = SECONDARY_RGB_SLICE.stop
SECONDARY_CONFIDENCE_INDEX = BASE_CONFIDENCE_INDEX + 1
ROUGHNESS_HINT_INDEX = SECONDARY_CONFIDENCE_INDEX + 1
METALLIC_HINT_INDEX = ROUGHNESS_HINT_INDEX + 1
RELIEF_HINT_INDEX = METALLIC_HINT_INDEX + 1
RELIEF_CONFIDENCE_INDEX = RELIEF_HINT_INDEX + 1
FINISH_SLICE = slice(
    RELIEF_CONFIDENCE_INDEX + 1,
    RELIEF_CONFIDENCE_INDEX + 1 + len(FINISHES),
)
EFFECT_SLICE = slice(FINISH_SLICE.stop, FINISH_SLICE.stop + len(EFFECTS))
LIGHT_INDEX = EFFECT_SLICE.stop
DARK_INDEX = LIGHT_INDEX + 1
ATTRIBUTE_DIM = DARK_INDEX + 1

if ATTRIBUTE_DIM != 55:
    raise RuntimeError(f"Structured Prompt contract drift: {ATTRIBUTE_DIM}")


_STRUCTURED_MATERIAL_RULES = (
    ("textile", ("fabric", "denim", "cotton", "felt", "lace", "linen", "nylon", "ripstop", "mesh", "tarpaulin", "wool", "布", "棉", "牛仔", "毛毡", "蕾丝", "亚麻", "尼龙", "网眼布", "羊毛")),
    ("leather", ("leather", "suede", "reptile skin", "皮革", "麂皮")),
    ("cork", ("cork", "软木")),
    ("loose_granular", ("sand", "granular", "砂砾", "沙", "砂")),
    ("automotive_paint", ("automotive", "car paint", "car clearcoat", "clearcoat paint", "车漆", "汽车漆", "汽车金属漆", "汽车清漆", "车用漆")),
    ("rusted_metal", ("rust", "rusted", "rusty", "oxidized", "oxidised", "verdigris", "patina", "锈", "生锈", "氧化", "铜绿")),
    ("marble", ("marble", "大理石")),
    ("concrete_asphalt", ("concrete", "asphalt", "cement concrete", "混凝土", "沥青")),
    ("masonry_plaster", ("brick", "plaster", "gypsum", "terracotta tile", "cement plaster", "砖", "石膏", "灰泥", "抹灰")),
    ("ceramic", ("ceramic", "porcelain", "earthenware", "terracotta", "陶", "瓷")),
    ("engineered_composite", ("carbon fiber", "carbon fibre", "terrazzo", "composite", "碳纤维", "磨石")),
    ("plastic_rubber", ("plastic", "abs", "hdpe", "rubber", "polymer", "塑料", "橡胶")),
    ("paint_coating", ("paint", "painted", "coating", "coated", "powder coat", "powder-coated", "epoxy", "latex", "lacquer", "clear coat", "清漆", "漆", "喷漆", "涂层")),
    ("porous_stone", ("granite", "basalt", "slate", "travertine", "limestone", "sandstone", "quartzite", "rock", "stone", "gravel", "花岗岩", "玄武岩", "板岩", "洞石", "石灰岩", "砂岩", "岩石", "砾石")),
    ("bare_metal", ("metal", "steel", "iron", "aluminum", "aluminium", "copper", "brass", "zinc", "nickel", "titanium", "chrome", "chromium", "foil", "金属", "钢", "铁", "铝", "铜", "黄铜", "锌", "镍", "钛", "铬")),
)

_CLASS_RELIEF_PRIOR = {
    "bare_metal": 0.18,
    "rusted_metal": 0.52,
    "plastic_rubber": 0.14,
    "paint_coating": 0.10,
    "automotive_paint": 0.05,
    "marble": 0.09,
    "porous_stone": 0.58,
    "concrete_asphalt": 0.66,
    "masonry_plaster": 0.62,
    "ceramic": 0.07,
    "engineered_composite": 0.30,
    "cork": 0.56,
    "leather": 0.40,
    "textile": 0.36,
    "loose_granular": 0.88,
}

_EXTRA_COLOR_ALIASES = {
    "white": ("cream", "ivory", "off white", "乳白", "奶油色"),
    "red": ("burgundy", "maroon", "酒红", "勃艮第红"),
    "blue": ("navy", "汽蓝", "海军蓝"),
    "yellow": ("ochre", "赭黄"),
}

_PATTERN_MARKERS = (
    "vein", "纹", "chip", "stone chip", "屑", "fleck", "speck", "patch",
    "斑", "grain", "颗粒", "aggregate", "骨料", "flake", "闪片",
)


def _structured_material_class(value: str) -> str:
    text = normalize_text(value)
    for name, aliases in _STRUCTURED_MATERIAL_RULES:
        if contains(text, aliases):
            return name
    return "paint_coating"


def _structured_regime(value: str, material_class: str) -> str:
    text = normalize_text(value)
    if material_class == "rusted_metal" or contains(
        text, ("mixed metal", "partly metallic", "exposed metal", "混合金属", "裸露金属")
    ):
        return "mixed"
    if material_class in ("paint_coating", "automotive_paint") and contains(
        text,
        ("steel", "iron", "metal", "aluminum", "aluminium", "automotive", "car", "钢", "铁", "金属", "铝", "车"),
    ):
        return "coated_conductor"
    if material_class == "bare_metal":
        return "conductor"
    return "dielectric"


def _alias_positions(text: str, alias: str) -> list[int]:
    normalized = normalize_text(text)
    token = normalize_text(alias)
    if token.isascii() and token.replace(" ", "").isalpha():
        pattern = rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])"
        return [match.start() for match in re.finditer(pattern, normalized)]
    result = []
    start = 0
    while True:
        index = normalized.find(token, start)
        if index < 0:
            return result
        result.append(index)
        start = index + max(len(token), 1)


def _color_hits(value: str) -> list[dict[str, object]]:
    text = normalize_text(value)
    hits: list[dict[str, object]] = []
    for name, (_rgb, aliases) in COLORS.items():
        candidates = list(aliases) + list(_EXTRA_COLOR_ALIASES.get(name, ()))
        for alias in candidates:
            normalized_alias = normalize_text(alias)
            for position in _alias_positions(text, alias):
                tail = text[position + len(normalized_alias) : position + len(normalized_alias) + 18]
                marked = any(marker in tail for marker in _PATTERN_MARKERS)
                hits.append({"name": name, "position": position, "marked": marked})
    hits.sort(key=lambda item: (int(item["position"]), COLOR_NAMES.index(str(item["name"]))))
    return hits


def _material_position(value: str, material_class: str) -> int:
    text = normalize_text(value)
    aliases = next(aliases for name, aliases in _STRUCTURED_MATERIAL_RULES if name == material_class)
    positions = [position for alias in aliases for position in _alias_positions(text, alias)]
    return min(positions) if positions else len(text)


def _structured_colors(value: str, material_class: str) -> tuple[str, str | None, float, float]:
    text = normalize_text(value)
    hits = _color_hits(text)
    material_position = _material_position(text, material_class)
    primary_candidates = [
        hit for hit in hits if not bool(hit["marked"]) and int(hit["position"]) <= material_position + 3
    ]
    if primary_candidates:
        primary = str(primary_candidates[0]["name"])
        primary_confidence = 1.0
    else:
        unmarked = [hit for hit in hits if not bool(hit["marked"])]
        if unmarked and not contains(text, (" with ", "带", "具有")):
            primary = str(unmarked[0]["name"])
            primary_confidence = 1.0
        elif contains(text, ("light", "pale", "浅色", "浅", "淡色")):
            primary = {
                "porous_stone": "beige",
                "engineered_composite": "white",
                "ceramic": "white",
                "masonry_plaster": "gray",
                "concrete_asphalt": "gray",
            }.get(material_class, "gray")
            primary_confidence = 0.72
        else:
            primary = "gray"
            primary_confidence = 0.0
    secondary_candidates = [
        hit
        for hit in hits
        if str(hit["name"]) != primary
        and (bool(hit["marked"]) or int(hit["position"]) > material_position + 3)
    ]
    secondary = str(secondary_candidates[0]["name"]) if secondary_candidates else None
    return primary, secondary, primary_confidence, 1.0 if secondary is not None else 0.0


def _structured_finish(value: str) -> tuple[str | None, float]:
    text = normalize_text(value)
    candidates: list[tuple[str, float]] = []
    rules = (
        ("polished", 0.12, ("polished", "mirror", "抛光", "镜面")),
        ("glossy", 0.18, ("glossy", "shiny", "clear coat", "clearcoat", "glazed", "亮光", "光亮", "清漆", "釉面")),
        ("satin", 0.42, ("satin", "semi matte", "semi-matte", "honed", "缎面", "半哑光", "磨光")),
        ("matte", 0.68, ("matte", "matt", "dry finish", "哑光", "干燥")),
        ("rough", 0.86, ("rough", "coarse", "grainy", "粗糙", "粗砺", "粗颗粒")),
        ("smooth", 0.31, ("smooth", "fine surface", "光滑", "细腻")),
    )
    for name, roughness, aliases in rules:
        if contains(text, aliases):
            candidates.append((name, roughness))
    if not candidates:
        return None, 0.50
    if contains(text, ("polished", "mirror", "glossy", "clear coat", "clearcoat", "glazed", "抛光", "镜面", "亮光", "清漆", "釉面")):
        return min(candidates, key=lambda item: item[1])
    if contains(text, ("rough", "coarse", "dry finish", "粗糙", "粗砺", "干燥")):
        return max(candidates, key=lambda item: item[1])
    return candidates[0]


def _structured_relief(value: str, material_class: str) -> tuple[float, float, str]:
    text = normalize_text(value)
    rules = (
        (0.0, "flat", ("almost flat", "nearly flat", "perfectly flat", "no relief", "几乎平坦", "近乎平面", "无凹凸")),
        (0.055, "very_low", ("very low relief", "very low geometric relief", "extremely subtle relief", "minimal relief", "很低凹凸", "很低的几何凹凸", "极轻微凹凸")),
        (0.14, "low", ("low relief", "shallow relief", "subtle relief", "轻微凹凸", "浅凹凸", "低凹凸")),
        (0.46, "medium", ("medium relief", "moderate relief", "中等凹凸")),
        (0.88, "strong", ("strong relief", "deep relief", "pronounced relief", "强烈凹凸", "深凹凸", "明显凹凸")),
    )
    for hint, label, aliases in rules:
        if contains(text, aliases):
            return hint, 1.0, label
    return _CLASS_RELIEF_PRIOR.get(material_class, 0.30), 0.0, "class_prior"


def structured_parse_prompt(prompt: str) -> dict[str, object]:
    material_class = _structured_material_class(prompt)
    regime = _structured_regime(prompt, material_class)
    primary, secondary, primary_confidence, secondary_confidence = _structured_colors(
        prompt, material_class
    )
    finish, roughness_hint = _structured_finish(prompt)
    relief_hint, relief_confidence, relief_label = _structured_relief(prompt, material_class)
    metallic_hint = {
        "conductor": 0.95,
        "dielectric": 0.02,
        "coated_conductor": 0.02,
        "mixed": 0.50,
    }[regime]
    effects = effect_flags(prompt)
    text = normalize_text(prompt)
    if contains(text, ("clear coat", "clearcoat", "清漆")):
        effects["coated"] = 1.0
    if contains(text, ("glazed", "glaze", "釉")):
        effects["glazed"] = 1.0

    condition = np.zeros(CONDITION_DIM, dtype=np.float32)
    offset = 0
    condition[offset + CLASS_INDEX[material_class]] = 1.0
    offset += len(MATERIAL_CLASSES)
    condition[offset + REGIME_INDEX[regime]] = 1.0
    offset += len(PHYSICAL_REGIMES)
    condition[offset + COLOR_NAMES.index(primary)] = primary_confidence
    offset += len(COLOR_NAMES)
    primary_rgb = np.asarray(COLORS[primary][0], dtype=np.float32)
    condition[offset : offset + 3] = primary_rgb * primary_confidence
    offset += 3
    if finish is not None:
        condition[offset + FINISHES.index(finish)] = 1.0
    offset += len(FINISHES)
    condition[offset : offset + len(EFFECTS)] = np.asarray(
        [effects[name] for name in EFFECTS], dtype=np.float32
    )
    offset += len(EFFECTS)
    condition[offset : offset + 3] = roughness_hint, metallic_hint, primary_confidence
    offset += 3
    condition[offset : offset + HASH_DIM] = _hash_features(prompt)
    offset += HASH_DIM
    if offset != CONDITION_DIM:
        raise RuntimeError("Structured condition contract drift")

    attributes = np.zeros(ATTRIBUTE_DIM, dtype=np.float32)
    attributes[CLASS_SLICE.start + CLASS_INDEX[material_class]] = 1.0
    attributes[REGIME_SLICE.start + REGIME_INDEX[regime]] = 1.0
    attributes[BASE_RGB_SLICE] = primary_rgb
    if secondary is not None:
        attributes[SECONDARY_RGB_SLICE] = np.asarray(COLORS[secondary][0], dtype=np.float32)
    attributes[BASE_CONFIDENCE_INDEX] = primary_confidence
    attributes[SECONDARY_CONFIDENCE_INDEX] = secondary_confidence
    attributes[ROUGHNESS_HINT_INDEX] = roughness_hint
    attributes[METALLIC_HINT_INDEX] = metallic_hint
    attributes[RELIEF_HINT_INDEX] = relief_hint
    attributes[RELIEF_CONFIDENCE_INDEX] = relief_confidence
    if finish is not None:
        attributes[FINISH_SLICE.start + FINISHES.index(finish)] = 1.0
    attributes[EFFECT_SLICE] = np.asarray([effects[name] for name in EFFECTS], dtype=np.float32)
    attributes[LIGHT_INDEX] = float(contains(text, ("light", "pale", "浅色", "浅", "淡色")))
    attributes[DARK_INDEX] = float(contains(text, ("dark", "deep black", "深色", "暗色")))
    if not np.isfinite(condition).all() or not np.isfinite(attributes).all():
        raise RuntimeError("Non-finite structured Prompt")
    return {
        "prompt": prompt,
        "material_class": material_class,
        "physical_regime": regime,
        "color": primary,
        "base_color": primary,
        "secondary_color": secondary,
        "finish": finish,
        "relief": relief_label,
        "condition": condition,
        "condition_vector": condition,
        "attributes": attributes,
    }


def parse_prompt(prompt: str) -> dict[str, object]:
    """Parse a bilingual v0.3 Prompt into core and structured attributes."""
    return structured_parse_prompt(prompt)
