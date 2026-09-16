"""Obstacles statiques du decor.

Regle de collision fondamentale du jeu :
    - le corps physique est bloque par tous les murs ;
    - le fantome est bloque par les murs normaux mais traverse les murs
      spectraux (`SpectralWall`, symbole `=` dans les cartes).

Les murs et les piques prennent le sprite nomme dans la legende de la carte
(`"#" : "wall"`, `"^" : "spike"`). La hitbox reste un rectangle plein :
changer l'apparence d'une tuile ne doit jamais modifier la physique.

Une seule matiere terre/roche (planche `settings.SHEET_GROUND`, kind
`"wall"`) : le level designer pose un seul type de mur, et l'auto-tiling
choisit la case a afficher pour toute la grille en un coup, via
`compute_ground_cells` (herbe/terre/dessous, pilier d'un bloc de large,
plateforme fine, grotte, ilot 2x2 - cf. `_base_ground_cell`). `world/level.py`
(jeu) et `editor/canvas.py` (editeur) appellent cette meme fonction sur leur
grille respective, pour que l'apercu de l'editeur corresponde au rendu en jeu.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
import math
import time
from dataclasses import dataclass
from pathlib import Path

import arcade

import settings
from src.entities.glow import draw_glow
from src.entities.particles import SoulBurst
from src.ui import sprites


@dataclass(frozen=True, slots=True)
class TileSpec:
    """Description d'une tuile choisie dans la legende d'une carte.

    Deux sources possibles pour un mur : `sprite` seul (fichier de
    `assets/sprites/`, tel quel) ou `sheet` + `cell` (case fixe decoupee dans
    une planche) / `autotile=True` (case choisie par `compute_ground_cells`,
    passee a `terrain_texture` au cas par cas) - utilise en priorite quand il
    est renseigne.
    """

    sprite: str = ""
    role: str = "wall"
    hanging: bool = False
    sheet: Path | None = None
    cell: tuple[int, int] | None = None
    autotile: bool = False
    tint: tuple[int, int, int] | None = None


def _wall(
    sprite: str = "",
    *,
    sheet: Path | None = None,
    cell: tuple[int, int] | None = None,
    autotile: bool = False,
    tint: tuple[int, int, int] | None = None,
) -> TileSpec:
    return TileSpec(
        sprite=sprite,
        role="wall",
        sheet=sheet,
        cell=cell,
        autotile=autotile,
        tint=tint,
    )


def _spike(sprite: str, *, hanging: bool = False) -> TileSpec:
    return TileSpec(sprite=sprite, role="spike", hanging=hanging)


# Noms acceptes dans `legend` d'une carte, en plus des types de gameplay
# (porte, spawn, cle, ...). "wall" est la seule matiere terre/roche du jeu
# (planche "new_textures", auto-tilee) ; "bedrock" est un socle distinct, a
# case fixe ; les piques restent sur leurs PNG d'origine.
TILE_SPECS: dict[str, TileSpec] = {
    "wall": _wall(sheet=settings.SHEET_GROUND, autotile=True),
    "bedrock": _wall(sheet=settings.SHEET_GROUND, cell=settings.GROUND_BEDROCK, tint=settings.COLOR_BEDROCK_TINT),
    "spike": _spike(settings.SPRITE_SPIKE),
    "spike_up": _spike(settings.SPRITE_SPIKE_HANGING, hanging=True),
}

# Kinds qui occupent une case pleine et solide (bloquent la vue d'un cote pour
# l'auto-tiling). Les piques, decors et entites n'en font pas partie : une
# tuile "wall" a cote d'un pique affiche quand meme son herbe. Le mur spectral
# en fait partie : il doit etre indetectable pour le corps physique, donc ni
# lui ni ses voisins ne doivent trahir sa presence par une bordure ou de
# l'herbe (fiche concept : "devoile les elements invisibles en mode normal").
SOLID_GROUND_KINDS = frozenset({"wall", "bedrock", "spectral_wall"})


def tile_spec(name: str) -> TileSpec:
    """Retourne la spec d'une tuile de terrain, ou leve ValueError."""
    if not name:
        raise ValueError("name ne doit pas etre vide")
    spec = TILE_SPECS.get(name)
    if spec is None:
        raise ValueError(f"tuile inconnue : '{name}'")
    return spec


@dataclass(frozen=True, slots=True)
class GroundNeighbors:
    """Occupation des 8 cases autour d'une tuile "wall".

    `True` = case voisine libre (aucun terrain solide : `vide`, un pique, un
    decor, une entite), donc ce bord/coin doit etre habille ; `False` =
    voisine solide (`wall`/`bedrock`/`spectral_wall`, ou hors carte).
    """

    top_open: bool = True
    right_open: bool = False
    bottom_open: bool = False
    left_open: bool = False
    top_left_open: bool = True
    top_right_open: bool = True
    bottom_left_open: bool = False
    bottom_right_open: bool = False


GroundCell = tuple[int, int]  # (colonne, ligne) dans SHEET_GROUND

# Apercu par defaut quand aucune case n'est connue (icone de palette, tuile
# isolee instanciee hors d'un niveau) : une crete d'herbe ordinaire.
_DEFAULT_CELL: GroundCell = (settings.GROUND_COL_MID, settings.GROUND_ROW_GRASS)

_PLAIN_INTERIOR: GroundCell = (settings.GROUND_COL_MID, settings.GROUND_ROW_DIRT)
_PLAIN_SURFACE: GroundCell = (settings.GROUND_COL_MID, settings.GROUND_ROW_GRASS)

# Pools de variantes indexes par leur case CANONIQUE : `_pick_variant` remplace
# une case canonique par l'une de ses variantes selon la position de la tuile.
_VARIANT_POOLS: dict[GroundCell, tuple[GroundCell, ...]] = {
    _PLAIN_SURFACE: settings.GROUND_SURFACE_VARIANTS,
    _PLAIN_INTERIOR: settings.GROUND_DIRT_VARIANTS,
    (settings.GROUND_COL_MID, settings.GROUND_ROW_BOTTOM): settings.GROUND_BOTTOM_VARIANTS,
    settings.GROUND_SOLO: settings.GROUND_SOLO_VARIANTS,
    settings.GROUND_PLATFORM_LEFT: settings.GROUND_PLATFORM_LEFT_VARIANTS,
    settings.GROUND_PLATFORM_MID: settings.GROUND_PLATFORM_MID_VARIANTS,
    settings.GROUND_PLATFORM_RIGHT: settings.GROUND_PLATFORM_RIGHT_VARIANTS,
    settings.GROUND_CAVE_CEILING: settings.GROUND_CAVE_CEILING_VARIANTS,
}


def _pick_variant(cell: GroundCell, column: int, row: int) -> GroundCell:
    """Choisit une variante graphique stable pour une case canonique.

    Deterministe (aucun etat aleatoire) : la meme tuile donne toujours la meme
    variante, donc le jeu et l'apercu de l'editeur restent identiques. Le
    melange des deux coordonnees evite les rayures visibles (une seule ligne ou
    colonne qui prendrait toujours la meme variante).
    """
    pool = _VARIANT_POOLS.get(cell)
    if not pool:
        return cell
    index = (column * 73856093) ^ (row * 19349663)
    return pool[index % len(pool)]


def _surface_cell(n: GroundNeighbors) -> GroundCell:
    """Choisit la tuile d'herbe d'une pelouse (ciel au-dessus, terre en dessous).

    - Bord Sombre Haut : crete plate, ou bosse posee sur un sol plus large
      (les diagonales du dessous sont pleines, le vide ne descend pas).
    - Coin Sombre HG/HD : vrai coin de masse profonde, le vide continue
      sous le cote ouvert (falaise, paroi de puits).
    - Sommet de pilier : colonne d'une tuile, vide des deux cotes y compris
      en dessous. Une bosse d'une case sur le sol n'en est pas une.
    """
    left_cliff = n.left_open and n.bottom_left_open
    right_cliff = n.right_open and n.bottom_right_open
    if n.left_open and n.right_open:
        if left_cliff and right_cliff:
            return settings.GROUND_PILLAR_TOP
        return _PLAIN_SURFACE
    if left_cliff and not n.right_open:
        return (settings.GROUND_COL_LEFT, settings.GROUND_ROW_GRASS)
    if right_cliff and not n.left_open:
        return (settings.GROUND_COL_RIGHT, settings.GROUND_ROW_GRASS)
    return _PLAIN_SURFACE


def _base_ground_cell(
    neighbors: GroundNeighbors,
    *,
    enclosed_nw: bool,
    enclosed_ne: bool,
) -> GroundCell:
    """Classe une tuile a partir de ses 8 voisins."""
    n = neighbors
    if n.top_open and n.right_open and n.bottom_open and n.left_open:
        return settings.GROUND_SOLO

    if n.top_open and n.bottom_open:
        if n.left_open:
            return settings.GROUND_PLATFORM_LEFT
        if n.right_open:
            return settings.GROUND_PLATFORM_RIGHT
        return settings.GROUND_PLATFORM_MID

    # Sol d'un trou d'une tuile de large (parois gauche ET droite, ciel
    # bouche par la voisine haute-gauche/droite) : pas une pelouse de plaine.
    cave_floor = (
        n.top_open
        and not n.left_open
        and not n.right_open
        and not n.top_left_open
        and not n.top_right_open
    )
    if cave_floor:
        return settings.GROUND_CAVE_FLOOR

    if n.top_open and not n.bottom_open:
        return _surface_cell(n)

    if n.left_open and n.right_open:
        if n.bottom_open:
            return settings.GROUND_PILLAR_BOTTOM
        return settings.GROUND_PILLAR_MID

    buried = not n.top_open and not n.right_open and not n.bottom_open and not n.left_open
    if buried:
        if n.bottom_right_open:
            return settings.GROUND_INNER_BOTTOM_RIGHT
        if n.bottom_left_open:
            return settings.GROUND_INNER_BOTTOM_LEFT
        if n.top_right_open and enclosed_ne:
            return settings.GROUND_INNER_TOP_RIGHT
        if n.top_left_open and enclosed_nw:
            return settings.GROUND_INNER_TOP_LEFT
        return _PLAIN_INTERIOR

    # Plafond d'un trou d'une tuile de large.
    cave_ceiling = (
        n.bottom_open
        and not n.left_open
        and not n.right_open
        and not n.bottom_left_open
        and not n.bottom_right_open
    )
    if cave_ceiling:
        return settings.GROUND_CAVE_CEILING

    if not n.top_open and not n.bottom_open:
        # Paroi gauche du tunnel : le trou est A DROITE, plafond et sol solides.
        if n.right_open and not n.left_open and not n.top_right_open and not n.bottom_right_open:
            return settings.GROUND_CAVE_WALL_LEFT
        if n.left_open and not n.right_open and not n.top_left_open and not n.bottom_left_open:
            return settings.GROUND_CAVE_WALL_RIGHT

    if n.top_open:
        row = settings.GROUND_ROW_GRASS
    elif n.bottom_open:
        row = settings.GROUND_ROW_BOTTOM
    else:
        row = settings.GROUND_ROW_DIRT

    if n.left_open and not n.right_open:
        column = settings.GROUND_COL_LEFT
    elif n.right_open and not n.left_open:
        column = settings.GROUND_COL_RIGHT
    else:
        column = settings.GROUND_COL_MID
    return column, row


def _hole_is_enclosed(
    empty_column: int, empty_row: int, is_solid: Callable[[int, int], bool]
) -> bool:
    """True seulement pour un trou de grotte d'une tuile, pas un surplomb.

    Un surplomb (plateforme au-dessus d'un vide) a aussi du solide AU-DESSUS
    du vide : ce n'est pas une grotte. Un vrai trou est serre a gauche ET a
    droite. Sans ca, le sol sous une corniche recevait un coin herbeux.
    """
    if empty_row <= 0:
        return False
    if not is_solid(empty_column, empty_row - 1):
        return False
    return is_solid(empty_column - 1, empty_row) and is_solid(
        empty_column + 1, empty_row
    )


def _island_2x2_cell(
    column: int, row: int, is_solid: Callable[[int, int], bool]
) -> GroundCell | None:
    """Retourne le coin d'ilot si la tuile appartient a un 2x2 isole."""
    roles: tuple[tuple[tuple[int, int], GroundCell], ...] = (
        ((0, 0), settings.GROUND_ISLAND_TL),
        ((1, 0), settings.GROUND_ISLAND_TR),
        ((0, 1), settings.GROUND_ISLAND_BL),
        ((1, 1), settings.GROUND_ISLAND_BR),
    )
    for (dx, dy), cell in roles:
        origin_c = column - dx
        origin_r = row - dy
        if not all(
            is_solid(origin_c + x, origin_r + y) for x in (0, 1) for y in (0, 1)
        ):
            continue
        ring_solid = False
        for x in range(-1, 3):
            for y in range(-1, 3):
                if 0 <= x <= 1 and 0 <= y <= 1:
                    continue
                if is_solid(origin_c + x, origin_r + y):
                    ring_solid = True
                    break
            if ring_solid:
                break
        if not ring_solid:
            return cell
    return None


def compute_ground_cells(
    columns: int,
    rows: int,
    *,
    is_solid: Callable[[int, int], bool],
    is_autotile: Callable[[int, int], bool],
) -> dict[tuple[int, int], GroundCell]:
    """Choisit la case de `SHEET_GROUND` pour chaque tuile auto-tilee.

    `is_solid(column, row)` dit si une case bloque la vue (`wall`/`bedrock`,
    hors carte = solide). Une passe unique : ilot 2x2 isole, puis classification
    8-voisins (`_base_ground_cell`), puis variantes. Meme fonction pour le jeu
    (`world/level.py`) et l'editeur (`editor/canvas.py`).
    """
    final: dict[tuple[int, int], GroundCell] = {}
    for row in range(rows):
        for column in range(columns):
            if not is_autotile(column, row):
                continue
            island = _island_2x2_cell(column, row, is_solid)
            if island is not None:
                final[(column, row)] = island
                continue
            neighbors = GroundNeighbors(
                top_open=not is_solid(column, row - 1),
                right_open=not is_solid(column + 1, row),
                bottom_open=not is_solid(column, row + 1),
                left_open=not is_solid(column - 1, row),
                top_left_open=not is_solid(column - 1, row - 1),
                top_right_open=not is_solid(column + 1, row - 1),
                bottom_left_open=not is_solid(column - 1, row + 1),
                bottom_right_open=not is_solid(column + 1, row + 1),
            )
            cell = _base_ground_cell(
                neighbors,
                enclosed_nw=_hole_is_enclosed(column - 1, row - 1, is_solid),
                enclosed_ne=_hole_is_enclosed(column + 1, row - 1, is_solid),
            )
            final[(column, row)] = _pick_variant(cell, column, row)
    return final


def terrain_texture(
    spec: TileSpec,
    size: int,
    *,
    cell: GroundCell | None = None,
) -> arcade.Texture:
    """Texture d'affichage d'une tuile de mur, deja a la taille de la carte.

    `cell` est la case deja resolue par `compute_ground_cells` pour une tuile
    auto-tilee (`spec.autotile`) : sans lui, l'apercu par defaut (crete
    d'herbe) sert pour la palette de l'editeur ou une tuile hors niveau.
    """
    if spec.role != "wall":
        raise ValueError(f"terrain_texture attend un mur, pas '{spec.role}'")
    if spec.autotile:
        return sprites.load_sheet_cell(
            spec.sheet, *(cell or _DEFAULT_CELL), settings.GROUND_CELL, size=size
        )
    if spec.sheet is not None:
        if spec.cell is None:
            raise ValueError("spec.sheet est renseigne sans spec.cell ni spec.autotile")
        return sprites.load_sheet_cell(spec.sheet, *spec.cell, settings.GROUND_CELL, size=size)
    return sprites.load_texture(spec.sprite, size=size)


class Wall(arcade.Sprite):
    """Bloc de terrain plein, infranchissable pour tout le monde."""

    ghost_passable = False

    def __init__(
        self,
        center_x: float,
        center_y: float,
        size: int = settings.TILE_SIZE,
        tile: str = "wall",
        cell: GroundCell | None = None,
    ) -> None:
        spec = tile_spec(tile)
        if spec.role != "wall":
            raise ValueError(f"'{tile}' n'est pas une tuile de mur")
        texture = terrain_texture(spec, size, cell=cell)
        super().__init__(
            texture,
            scale=sprites.scale_for_size(texture, size),
            center_x=center_x,
            center_y=center_y,
        )
        if spec.tint is not None:
            self.color = spec.tint
        sprites.apply_rect_hit_box(self, size, size)


class SpectralWall(Wall):
    """Mur que seul le fantome peut traverser.

    Indetectable pour le corps physique : il est peint comme un mur normal
    et ne prend sa teinte spectrale que dans le champ de vision du fantome
    (fiche concept : "devoile les elements invisibles en mode normal").
    """

    ghost_passable = True

    def __init__(
        self,
        center_x: float,
        center_y: float,
        size: int = settings.TILE_SIZE,
        tile: str = "wall",
        cell: GroundCell | None = None,
    ) -> None:
        super().__init__(center_x, center_y, size=size, tile=tile, cell=cell)
        self.revealed = False

    def set_revealed(self, revealed: bool) -> None:
        """Affiche ou masque la nature spectrale du mur."""
        if revealed == self.revealed:
            return
        self.revealed = revealed
        self.color = settings.COLOR_SPECTRAL_WALL if revealed else arcade.color.WHITE


class Spike(arcade.Sprite):
    """Piques : mortelles pour le corps physique, inoffensives pour le fantome.

    La hitbox ne couvre que la moitie de la tuile (bas si posees au sol, haut
    si accrochees au plafond) pour que le joueur puisse raser les piques sans
    mourir injustement.
    """

    def __init__(
        self,
        center_x: float,
        center_y: float,
        size: int = settings.TILE_SIZE,
        tile: str = "spike",
    ) -> None:
        spec = tile_spec(tile)
        if spec.role != "spike":
            raise ValueError(f"'{tile}' n'est pas une tuile de piques")
        texture = sprites.load_texture(spec.sprite, size=size)
        super().__init__(
            texture,
            scale=sprites.scale_for_size(texture, size),
            center_x=center_x,
            center_y=center_y,
        )
        self.lethal_for_body = True
        self.lethal_for_ghost = False
        self.hanging = spec.hanging
        self.falling = False
        self._tile_size = size
        hit_height = size // 2
        offset_y = (size - hit_height) / 2
        if not spec.hanging:
            offset_y = -offset_y
        sprites.apply_rect_hit_box(self, size, hit_height, offset_y=offset_y)

    def draw_ghost_glow(self, *, bind_blend: bool = True) -> None:
        """Halo rouge, visible a travers le voile du fantome."""
        pulse = 1.0 + settings.SPIKE_GHOST_GLOW_PULSE * math.sin(
            time.perf_counter() * settings.SPIKE_GHOST_GLOW_PULSE_SPEED
            + self.center_x * 0.11
            + self.center_y * 0.07
        )
        size = self._tile_size
        draw_glow(
            self.center_x,
            self.center_y,
            size * settings.SPIKE_GHOST_GLOW_SCALE,
            size * settings.SPIKE_GHOST_GLOW_SCALE,
            settings.COLOR_SPIKE_GLOW,
            int(settings.SPIKE_GHOST_GLOW_ALPHA * pulse),
            bind_blend=bind_blend,
        )
        draw_glow(
            self.center_x,
            self.center_y,
            size * settings.SPIKE_GHOST_GLOW_INNER_SCALE,
            size * settings.SPIKE_GHOST_GLOW_INNER_SCALE,
            settings.COLOR_SPIKE_GLOW_CORE,
            int(settings.SPIKE_GHOST_GLOW_INNER_ALPHA * pulse),
            bind_blend=bind_blend,
        )

    def start_fall(self) -> None:
        """Detache la pique du plafond : elle devient un projectile mortel."""
        if self.falling:
            return
        self.hanging = False
        self.falling = True
        self.change_y = 0.0
        sprites.apply_rect_hit_box(self, self._tile_size, self._tile_size)

    def fall(self, walls: Sequence[arcade.SpriteList]) -> bool:
        """Fait tomber la pique. Retourne True si elle a touche le sol (a casser)."""
        if not self.falling:
            return False
        self.change_y -= settings.SPIKE_FALL_GRAVITY
        if self.change_y < -settings.SPIKE_FALL_MAX_SPEED:
            self.change_y = -settings.SPIKE_FALL_MAX_SPEED
        previous_y = self.center_y
        self.center_y += self.change_y
        for wall_list in walls:
            if arcade.check_for_collision_with_list(self, wall_list):
                self.center_y = previous_y
                return True
        if self.top < -settings.TILE_SIZE:
            return True
        return False


class Torch(arcade.SpriteSolidColor):
    """Torche decorative : placeholder solide + halo additif qui vacille.

    Pas de collision : c'est du decor. Le sprite sera remplace plus tard.
    """

    def __init__(self, center_x: float, center_y: float) -> None:
        super().__init__(
            settings.TORCH_WIDTH,
            settings.TORCH_HEIGHT,
            center_x=center_x,
            center_y=center_y + settings.TORCH_STEM_HEIGHT / 2,
            color=settings.COLOR_TORCH_FLAME,
        )
        self._time = 0.0
        self._phase = (center_x * 0.17 + center_y * 0.09) % math.tau

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self._time += max(0.0, delta_time)

    def draw_fx(self) -> None:
        """Halo chaud, puis le baton du placeholder (la flamme est le sprite)."""
        flicker = self._flicker()
        flame_x = self.center_x
        flame_y = self.center_y
        draw_glow(
            flame_x,
            flame_y,
            settings.TORCH_GLOW_OUTER * flicker,
            settings.TORCH_GLOW_OUTER * flicker * 1.15,
            settings.COLOR_TORCH_GLOW,
            int(settings.TORCH_GLOW_ALPHA * flicker),
        )
        draw_glow(
            flame_x,
            flame_y,
            settings.TORCH_GLOW_INNER * flicker,
            settings.TORCH_GLOW_INNER * flicker,
            settings.COLOR_TORCH_GLOW_CORE,
            int(settings.TORCH_GLOW_INNER_ALPHA * flicker),
        )
        stem_top = self.bottom
        stem_bottom = stem_top - settings.TORCH_STEM_HEIGHT
        half = settings.TORCH_STEM_WIDTH / 2
        arcade.draw_lrbt_rectangle_filled(
            self.center_x - half,
            self.center_x + half,
            stem_bottom,
            stem_top,
            settings.COLOR_TORCH_STEM,
        )

    def _flicker(self) -> float:
        slow = math.sin(self._time * settings.TORCH_FLICKER_SPEED + self._phase)
        fast = math.sin(self._time * settings.TORCH_FLICKER_SPEED_FAST + self._phase * 1.7)
        return 1.0 + settings.TORCH_FLICKER * (0.65 * slow + 0.35 * fast)


class Door(arcade.SpriteSolidColor):
    """Porte de fin de niveau, verrouillee jusqu'a l'obtention de la cle."""

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        super().__init__(
            size,
            size * 2,
            center_x=center_x,
            center_y=center_y + size / 2,
            color=settings.COLOR_DOOR_LOCKED,
        )
        self.locked = True

    def unlock(self) -> None:
        """Deverrouille la porte (feedback visuel provisoire : changement de couleur)."""
        if not self.locked:
            return
        self.locked = False
        self.color = settings.COLOR_DOOR_OPEN


class Checkpoint(arcade.Sprite):
    """Point de reapparition du corps physique apres la fin du mode fantome."""

    def __init__(self, center_x: float, center_y: float, size: int = settings.TILE_SIZE) -> None:
        display = settings.CHECKPOINT_SIZE
        self._idle = sprites.load_texture(settings.SPRITE_CHECKPOINT, size=display)
        self._lit = sprites.load_texture(settings.SPRITE_CHECKPOINT_ACTIVE, size=display)
        lift = (display - size) / 2
        self._spawn = (center_x, center_y)
        super().__init__(self._idle, center_x=center_x, center_y=center_y + lift)
        sprites.apply_rect_hit_box(self, size, size, offset_y=-lift)
        self.active = False
        self._burst = SoulBurst()

    @property
    def spawn_point(self) -> tuple[float, float]:
        """Centre de la tuile, pas du sprite (le totem est plus haut que la case)."""
        return self._spawn

    def activate(self) -> None:
        """Passe a la texture allumee. No-op si deja le checkpoint courant."""
        if self.active:
            return
        self.active = True
        self.texture = self._lit

    def deactivate(self) -> None:
        """Revient a la texture eteinte."""
        if not self.active:
            return
        self.active = False
        self.texture = self._idle

    def play_respawn(self) -> None:
        """Eclat de motes bleues : le corps revient ici."""
        self._burst.emit(self.center_x, self.center_y + self.height * 0.15)

    def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs) -> None:
        self._burst.update(delta_time)

    def draw_fx(self) -> None:
        self._burst.draw()


def is_solid_for_ghost(wall: arcade.Sprite) -> bool:
    """Indique si `wall` bloque le fantome."""
    return not getattr(wall, "ghost_passable", False)
