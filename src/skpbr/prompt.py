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
