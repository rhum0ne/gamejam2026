"""Decors sans collision poses dans le niveau.

Purement visuel : ces sprites n'entrent jamais dans les listes solides du
moteur de physique (`Level.solid_platforms` / `Level.static_walls`). Une
entree dans `_CATALOG` (planche, rectangle, libelle) suffit : `world/level.py`
genere la fabrique et l'editeur peuple sa palette.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import arcade

import settings
from src.ui import sprites


@dataclass(frozen=True, slots=True)
class DecorationSpec:
    """Description d'un type de decoration choisi dans la legende d'une carte."""

    sheet: Path
    box: tuple[int, int, int, int]
    label: str
    symbol: str

    @property
    def native_size(self) -> tuple[int, int]:
        """Largeur et hauteur du sprite dans la planche, en pixels."""
        left, top, right, bottom = self.box
        return right - left, bottom - top


def decoration_scale() -> float:
    """Un pixel de la planche (GROUND_CELL) correspond a ce facteur en jeu."""
    return settings.TILE_SIZE / settings.GROUND_CELL


def _prop(
    kind: str,
    box: tuple[int, int, int, int],
    label: str,
    symbol: str = "",
    *,
    sheet: Path | None = None,
) -> tuple[str, DecorationSpec]:
    source = sheet if sheet is not None else settings.SHEET_PROPS
    return kind, DecorationSpec(source, box, label, symbol)


# Tous les props complets de `SHEET_PROPS` / `SHEET_CHEST` (fragments vides
# et marqueur cyan de la planche exclus).
_CATALOG: tuple[tuple[str, DecorationSpec], ...] = (
    _prop("chest", (0, 0, 64, 64), "Coffre", "c", sheet=settings.SHEET_CHEST),
    _prop("lamp", (969, 6, 982, 24), "Lampe", "l"),
    _prop("lantern", (1002, 6, 1015, 24), "Lanterne"),
    _prop("sign_double", (414, 11, 447, 64), "Panneau double"),
    _prop("sign", (480, 18, 512, 64), "Panneau", "p"),
    _prop("crate", (42, 19, 87, 64), "Caisse X", "r"),
    _prop("target", (717, 20, 755, 64), "Cible"),
    _prop("mill", (873, 20, 918, 64), "Moulin"),
    _prop("sign_right", (388, 21, 417, 64), "Panneau droit"),
    _prop("crate_slat", (127, 29, 162, 64), "Caisse lattes"),
    _prop("barrel", (195, 29, 222, 64), "Tonneau", "n"),
    _prop("pole", (941, 32, 957, 129), "Poteau"),
    _prop("well_stand", (797, 33, 836, 64), "Support de puits"),
    _prop("jug", (264, 35, 281, 64), "Jarre"),
    _prop("jug_b", (328, 35, 347, 64), "Jarre 2"),
    _prop("well_arm", (976, 37, 1009, 63), "Bras de puits"),
    _prop("pot", (294, 45, 315, 64), "Pot"),
    _prop("sword", (352, 69, 388, 78), "Epee"),
    _prop("sword_b", (352, 84, 387, 92), "Epee 2"),
    _prop("bench_log", (453, 89, 538, 128), "Banc long"),
    _prop("fence", (254, 95, 322, 128), "Barriere"),
    _prop("planks", (91, 96, 132, 128), "Planches"),
    _prop("pumpkin", (577, 97, 607, 128), "Citrouille"),
    _prop("spiked_ball", (867, 99, 894, 126), "Boule piquee"),
    _prop("pumpkin_b", (614, 105, 635, 128), "Citrouille 2"),
    _prop("axe", (352, 113, 389, 126), "Hache"),
    _prop("statue", (703, 115, 738, 192), "Statue"),
    _prop("trough_lid", (799, 117, 832, 128), "Couvercle"),
    _prop("pitchfork_head", (352, 129, 401, 140), "Fourche (tete)"),
    _prop("mallet_head", (352, 144, 385, 157), "Maillet (tete)"),
    _prop("tombstone", (511, 145, 546, 192), "Pierre tombale", "t"),
    _prop("cross", (579, 147, 606, 192), "Croix"),
    _prop("cross_celtic", (643, 149, 670, 192), "Croix celtique"),
    _prop("table", (189, 163, 288, 224), "Table"),
    _prop("press", (32, 165, 119, 256), "Pressoir"),
    _prop("stump", (800, 165, 831, 192), "Souche"),
    _prop("grave", (447, 167, 481, 192), "Tombe"),
    _prop("counter", (315, 171, 388, 224), "Comptoir"),
    _prop("anvil", (857, 172, 899, 192), "Enclume"),
    _prop("chair", (394, 188, 416, 224), "Chaise"),
    _prop("sack", (452, 222, 477, 256), "Sac"),
    _prop("sack_b", (514, 225, 543, 256), "Sac 2"),
    _prop("shutter", (642, 226, 670, 285), "Volet"),
    _prop("scarecrow", (704, 230, 768, 320), "Epouvantail"),
    _prop("keg", (134, 231, 155, 256), "Fut"),
    _prop("post_cross", (570, 231, 616, 320), "Poteau croix"),
    _prop("scarecrow_b", (777, 253, 824, 320), "Epouvantail 2"),
    _prop("hay", (192, 254, 254, 288), "Foin"),
    _prop("sunflower", (899, 257, 925, 320), "Tournesol"),
    _prop("hay_bale", (284, 259, 325, 288), "Botte de foin"),
    _prop("sunflower_b", (930, 261, 957, 320), "Tournesol 2"),
    _prop("sunflower_c", (869, 262, 891, 320), "Tournesol 3"),
    _prop("rubble", (354, 265, 415, 288), "Gravats"),
    _prop("wheel", (128, 288, 160, 320), "Roue"),
    _prop("bench", (32, 306, 130, 347), "Banc"),
    _prop("bottle", (330, 320, 340, 359), "Bouteille"),
    _prop("awning", (387, 320, 477, 348), "Store"),
    _prop("post_b", (483, 329, 503, 416), "Poteau 2"),
    _prop("logs", (163, 335, 253, 384), "Rondins"),
    _prop("rock", (874, 358, 920, 384), "Rocher", "s"),
    _prop("stone_a", (680, 359, 695, 380), "Pierre"),
    _prop("stone_b", (713, 365, 727, 375), "Pierre 2"),
    _prop("rock_b", (816, 365, 849, 384), "Rocher 2"),
    _prop("bow", (577, 366, 669, 375), "Arc"),
    _prop("rock_c", (934, 369, 955, 384), "Rocher 3"),
    _prop("crate_small", (325, 371, 347, 384), "Caisse petite"),
    _prop("boat", (391, 383, 476, 416), "Barque"),
    _prop("picnic", (28, 384, 132, 410), "Table pique-nique"),
    _prop("stone_c", (713, 387, 728, 412), "Pierre 3"),
    _prop("oar", (582, 390, 665, 409), "Rame"),
    _prop("stone_d", (680, 391, 698, 413), "Pierre 4"),
    _prop("beam_low", (161, 395, 255, 417), "Poutre basse"),
    _prop("kettle", (737, 399, 766, 441), "Bouilloire"),
    _prop("brick_a", (330, 401, 344, 416), "Brique"),
    _prop("brick_b", (358, 404, 378, 416), "Brique 2"),
    _prop("crate_open", (28, 416, 68, 442), "Caisse ouverte"),
    _prop("chest_wood", (92, 416, 128, 442), "Coffre bois"),
    _prop("stone_e", (713, 421, 730, 444), "Pierre 5"),
    _prop("stone_f", (680, 424, 698, 442), "Pierre 6"),
    _prop("tree", (832, 447, 985, 609), "Arbre"),
    _prop("chest_wood_b", (32, 448, 68, 474), "Coffre bois 2"),
    _prop("ladder_a", (245, 448, 264, 577), "Echelle"),
    _prop("ladder_b", (280, 448, 299, 577), "Echelle 2"),
    _prop("grass", (421, 469, 444, 480), "Herbe", "g"),
    _prop("grass_b", (391, 470, 408, 480), "Herbe 2"),
    _prop("tree_b", (693, 471, 813, 609), "Arbre 2"),
    _prop("ladder_c", (320, 480, 352, 576), "Echelle 3"),
    _prop("wheat", (545, 485, 573, 544), "Ble"),
    _prop("wheat_b", (580, 487, 604, 544), "Ble 2"),
    _prop("wheat_c", (613, 490, 636, 544), "Ble 3"),
    _prop("wheat_d", (514, 494, 542, 544), "Ble 4"),
    _prop("wheat_e", (644, 496, 669, 544), "Ble 5"),
    _prop("grass_c", (390, 500, 409, 512), "Herbe 3"),
    _prop("grass_d", (455, 501, 472, 512), "Herbe 4"),
    _prop("grass_e", (420, 503, 444, 512), "Herbe 5"),
    _prop("chest_iron", (94, 514, 129, 544), "Coffre fer"),
    _prop("chest_gold", (30, 515, 65, 544), "Coffre or"),
    _prop("grass_f", (391, 530, 411, 544), "Herbe 6"),
    _prop("grass_g", (418, 535, 447, 544), "Herbe 7"),
    _prop("grass_h", (454, 536, 473, 544), "Herbe 8"),
    _prop("bush", (576, 572, 671, 609), "Buisson"),
    _prop("bush_b", (452, 573, 541, 609), "Buisson 2"),
    _prop("stone_grave", (161, 574, 192, 608), "Stele"),
    _prop("chest_iron_b", (32, 578, 66, 608), "Coffre fer 2"),
    _prop("chest_gold_b", (94, 579, 129, 608), "Coffre or 2"),
    _prop("bush_c", (356, 580, 413, 609), "Buisson 3"),
    _prop("beam_t", (416, 629, 480, 673), "Poutre T"),
    _prop("pergola", (513, 629, 639, 673), "Pergola"),
    _prop("stone_wall", (733, 629, 869, 672), "Muret"),
    _prop("scaffold", (160, 632, 192, 673), "Echafaud"),
    _prop("scaffold_x", (224, 640, 256, 673), "Echafaud X"),
    _prop("scaffold_box", (288, 648, 320, 673), "Echafaud caisse"),
    _prop("platform_wood", (352, 656, 384, 673), "Plateforme bois"),
    _prop("stairs", (158, 678, 262, 737), "Escalier"),
    _prop("stairs_b", (286, 693, 362, 737), "Escalier 2"),
    _prop("ramp", (680, 693, 800, 737), "Rampe"),
    _prop("post_t", (913, 698, 975, 737), "Poteau T"),
    _prop("stairs_c", (382, 701, 444, 737), "Escalier 3"),
    _prop("stairs_d", (478, 709, 526, 737), "Escalier 4"),
    _prop("stairs_e", (541, 718, 575, 737), "Marche"),
    _prop("crate_tiny", (266, 771, 281, 794), "Caisse minuscule"),
    _prop("plank", (193, 779, 255, 789), "Planche"),
    _prop("beam", (32, 787, 160, 833), "Poutre"),
    _prop("watchtower", (901, 803, 993, 986), "Tour de guet"),
)

DECORATION_SPECS: dict[str, DecorationSpec] = dict(_CATALOG)

_PLANT_MARKERS = ("grass", "wheat", "bush", "tree", "sunflower", "hay")
_STONE_MARKERS = ("rock", "stone", "tomb", "grave", "cross", "anvil", "brick")
_LIGHT_KINDS = frozenset({"lamp", "lantern"})


def _swatch_color(kind: str) -> tuple[int, int, int]:
    if kind in _LIGHT_KINDS:
        return (255, 196, 96)
    if any(kind.startswith(marker) or marker in kind for marker in _PLANT_MARKERS):
        return (80, 140, 70)
    if any(marker in kind for marker in _STONE_MARKERS):
        return (120, 124, 128)
    return (150, 110, 60)


def decoration_spec(name: str) -> DecorationSpec:
    """Retourne la spec d'une decoration, ou leve ValueError."""
    if not name:
        raise ValueError("name ne doit pas etre vide")
    spec = DECORATION_SPECS.get(name)
    if spec is None:
        raise ValueError(f"decoration inconnue : '{name}'")
    return spec


def decoration_kinds() -> tuple[str, ...]:
    """Types de decoration disponibles (ordre du catalogue)."""
    return tuple(kind for kind, _spec in _CATALOG)


def decoration_palette_meta() -> dict[str, tuple[str, str, tuple[int, int, int]]]:
    """kind -> (libelle, symbole habituel, couleur de pastille)."""
    return {
        kind: (spec.label, spec.symbol, _swatch_color(kind))
        for kind, spec in _CATALOG
    }


class Decoration(arcade.Sprite):
    """Element de decor pose au sol de sa tuile : jamais solide, jamais mis a jour.

    La texture garde la taille native de la planche (un pixel de `SHEET_PROPS`
    = un pixel de `SHEET_GROUND`). Seul le rapport `TILE_SIZE / GROUND_CELL`
    s'applique, pour rester aligne sur les tuiles. La base du sprite est
    alignee sur le bas de la tuile.
    """

    def __init__(self, kind: str, center_x: float, center_y: float) -> None:
        spec = decoration_spec(kind)
        texture = sprites.load_sheet_region(spec.sheet, spec.box)
        scale = decoration_scale()
        tile_bottom = center_y - settings.TILE_SIZE / 2
        super().__init__(
            texture,
            scale=scale,
            center_x=center_x,
            center_y=tile_bottom + texture.height * scale / 2,
        )
        self.kind = kind
