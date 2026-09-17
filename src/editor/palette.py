"""Catalogue des elements placables dans l'editeur de niveaux.

La palette n'est pas ecrite a la main : elle est deduite des registres du jeu.

    - le terrain vient de `TILE_SPECS` (`src/world/obstacles.py`) ;
    - les elements de gameplay viennent de `level.gameplay_kinds()`
      (les cles de `_FACTORIES`).

**Ajouter une tuile ou un element ne demande donc aucune modification ici** :
il apparait automatiquement dans la palette, avec un libelle deduit de son nom
et un symbole de legende pioche dans `_SYMBOL_POOL`. Les tables `_TERRAIN_META`
et `_GAMEPLAY_META` soignent l'affichage du terrain / gameplay ; les decors
prennent libelle et symbole dans `decorations.decoration_palette_meta`.
"""

from __future__ import annotations

from dataclasses import dataclass

import settings
from src.world.decorations import decoration_palette_meta
from src.world.level import gameplay_kinds
from src.world.obstacles import TILE_SPECS, TileSpec

EMPTY = ""  # cellule vide (symbole "." dans le JSON, kind "vide")
EMPTY_KIND = "vide"  # nom du vide tel qu'il apparait dans une legende

CATEGORY_TERRAIN = "Terrain"
CATEGORY_HAZARD = "Pieges"
CATEGORY_GAMEPLAY = "Gameplay"
CATEGORY_DECOR = "Decor"
CATEGORY_UNKNOWN = "Inconnu"

# Symboles disponibles pour un type sans symbole habituel. Ni le point (vide),
# ni l'espace, ni les quotes (le JSON de carte les echappe mal). L'alphabet
# grec puis cyrillique servent de rab quand les ASCII sont pris (beaucoup de
# decors, plus les archetypes d'ennemis).
_GREEK = "αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
_CYRILLIC = "абвгдежзийклмнопрстуфхцчшщъыьэюяАБВГДЕЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"
_SYMBOL_POOL = (
    "dI#TBG=^voPCDKEijklmnpqrstuwxyzabcefhABFHJLMNOQRSUVWXYZ0123456789"
    "()[]{}<>-+*/\\|!$%&@;:?~,_'`"
    + _GREEK
    + _CYRILLIC
)


@dataclass(frozen=True, slots=True)
class PaletteItem:
    """Un element placable : ce que l'editeur ecrit dans une cellule."""

    kind: str  # nom ecrit dans la legende de la carte
    label: str  # libelle affiche dans le panneau
    category: str
    symbol: str  # symbole prefere dans la legende
    color: tuple[int, int, int]  # couleur du placeholder (elements sans sprite)
    spec: TileSpec | None = None  # renseignee pour le terrain uniquement

    @property
    def is_terrain(self) -> bool:
        return self.spec is not None


# kind -> (libelle, symbole habituel)
#
# "wall" est la seule matiere terre/roche a poser : son apparence (herbe,
# coin, terre enterree, bloc isole...) est deduite automatiquement des tuiles
# voisines a chaque chargement (auto-tiling, cf. `world/obstacles.py`), donc
# aucune variante n'apparait ici en tant que type separe a choisir a la main.
_TERRAIN_META: dict[str, tuple[str, str]] = {
    "wall": ("Terre", "#"),
    "bedrock": ("Socle", "B"),
    settings.TILE_KIND_ICE: ("Glace", "~"),
    "spike": ("Piques (sol)", "^"),
    "spike_up": ("Piques (plafond)", "v"),
}

# kind -> (libelle, categorie, symbole habituel, couleur)
_GAMEPLAY_META: dict[str, tuple[str, str, str, tuple[int, int, int]]] = {
    "player_spawn": ("Depart du joueur", CATEGORY_GAMEPLAY, "P", settings.COLOR_PLAYER),
    "checkpoint": ("Statue de respawn", CATEGORY_GAMEPLAY, "C", settings.COLOR_CHECKPOINT),
    "door": ("Porte de sortie", CATEGORY_GAMEPLAY, "D", settings.COLOR_DOOR_LOCKED),
    "key": ("Cle", CATEGORY_GAMEPLAY, "K", settings.COLOR_KEY),
    "soul_orb": ("Ame (bille bleue)", CATEGORY_GAMEPLAY, "o", settings.COLOR_SOUL_ORB),
    "enemy": ("Ennemi", CATEGORY_GAMEPLAY, "E", settings.COLOR_ENEMY),
    "bat": ("Chauve-souris", CATEGORY_GAMEPLAY, "b", settings.COLOR_BAT),
    "zombie": ("Zombie", CATEGORY_GAMEPLAY, "z", settings.COLOR_ZOMBIE),
    "boss": ("Boss", CATEGORY_GAMEPLAY, "W", settings.COLOR_BOSS),
    "spectral_wall": ("Mur spectral", CATEGORY_GAMEPLAY, "=", settings.COLOR_SPECTRAL_WALL),
    settings.TILE_KIND_HIDDEN: (
        "Bloc invisible",
        CATEGORY_GAMEPLAY,
        "h",
        settings.COLOR_HIDDEN_WALL,
    ),
    "torch": ("Torche", CATEGORY_DECOR, "i", settings.COLOR_TORCH_FLAME),
    "flamethrower": ("Lance-flammes", CATEGORY_HAZARD, "f", settings.COLOR_FLAMETHROWER),
    settings.TILE_KIND_FALLING: ("Bloc tombant", CATEGORY_HAZARD, "F", settings.COLOR_FALLING_BLOCK),
}

_CATEGORY_ORDER = (
    CATEGORY_TERRAIN,
    CATEGORY_HAZARD,
    CATEGORY_GAMEPLAY,
    CATEGORY_DECOR,
    CATEGORY_UNKNOWN,
)


def free_symbol(taken: set[str], hint: str = "") -> str:
    """Retourne un symbole de legende encore libre, en essayant `hint` d'abord."""
    for candidate in (*hint, *_SYMBOL_POOL):
        if candidate not in taken and candidate != "." and not candidate.isspace():
            return candidate
    raise ValueError("plus aucun symbole de legende disponible")


def _terrain_items(taken: set[str]) -> list[PaletteItem]:
    items: list[PaletteItem] = []
    seen: set[TileSpec] = set()
    for kind, spec in TILE_SPECS.items():
        if spec in seen:  # alias du meme visuel (dirt / dirt_1 / wall)
            continue
        seen.add(spec)
        label, wanted = _TERRAIN_META.get(kind, (kind.replace("_", " "), ""))
        symbol = free_symbol(taken, wanted or kind.upper())
        taken.add(symbol)
        hazard = spec.role == "spike"
        if spec.role == "spike":
            color = settings.COLOR_SPIKE
        elif spec.role == "ice":
            color = settings.COLOR_ICE
        else:
            color = settings.COLOR_WALL
        items.append(
            PaletteItem(
                kind=kind,
                label=label,
                category=CATEGORY_HAZARD if hazard else CATEGORY_TERRAIN,
                symbol=symbol,
                color=color,
                spec=spec,
            )
        )
    return items


def _gameplay_items(taken: set[str]) -> list[PaletteItem]:
    items: list[PaletteItem] = []
    decor_meta = decoration_palette_meta()
    for kind in gameplay_kinds():
        if kind in decor_meta:
            label, wanted, color = decor_meta[kind]
            category = CATEGORY_DECOR
        else:
            label, category, wanted, color = _GAMEPLAY_META.get(
                kind,
                (kind.replace("_", " "), CATEGORY_GAMEPLAY, "", settings.COLOR_EDITOR_UNKNOWN),
            )
        symbol = free_symbol(taken, wanted or kind.upper())
        taken.add(symbol)
        items.append(
            PaletteItem(kind=kind, label=label, category=category, symbol=symbol, color=color)
        )
    return items


def _build() -> tuple[PaletteItem, ...]:
    taken: set[str] = {"."}
    items = _terrain_items(taken) + _gameplay_items(taken)
    order = {category: index for index, category in enumerate(_CATEGORY_ORDER)}
    items.sort(key=lambda item: (order.get(item.category, len(order)), item.label))
    return tuple(items)


PALETTE: tuple[PaletteItem, ...] = _build()
_BY_KIND: dict[str, PaletteItem] = {item.kind: item for item in PALETTE}
_UNKNOWN: dict[str, PaletteItem] = {}

CATEGORIES: tuple[str, ...] = tuple(
    category for category in _CATEGORY_ORDER if any(i.category == category for i in PALETTE)
)


def item(kind: str) -> PaletteItem:
    """Retourne l'element de palette d'un `kind`, meme s'il est inconnu du jeu.

    Une carte peut contenir un type qui n'existe plus dans le code : on ne veut
    ni planter, ni perdre la donnee, donc un element gris est fabrique a la
    volee (et signale par `EditorDocument.problems`).
    """
    if not kind:
        raise ValueError("kind ne doit pas etre vide")
    known = _BY_KIND.get(kind)
    if known is not None:
        return known
    unknown = _UNKNOWN.get(kind)
    if unknown is None:
        unknown = PaletteItem(
            kind=kind,
            label=f"{kind} (inconnu)",
            category=CATEGORY_UNKNOWN,
            symbol=free_symbol({"."}, kind.upper()),
            color=settings.COLOR_EDITOR_UNKNOWN,
        )
        _UNKNOWN[kind] = unknown
    return unknown


def is_known(kind: str) -> bool:
    """Indique si `kind` est chargeable par `Level.from_file`."""
    return kind in _BY_KIND


def items_in(category: str) -> tuple[PaletteItem, ...]:
    """Elements d'une categorie, dans l'ordre d'affichage."""
    return tuple(entry for entry in PALETTE if entry.category == category)


def preferred_symbols() -> dict[str, str]:
    """Symbole habituel de chaque type connu (kind -> symbole)."""
    return {entry.kind: entry.symbol for entry in PALETTE}
