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
choisit la case a afficher selon les tuiles voisines (herbe sur une face
exposee a l'air libre, coin quand un seul cote voisin est libre, terre
pleine sinon, bloc dedie pour une tuile totalement isolee). Voir
`GroundNeighbors` et `_select_ground_cell` plus bas ; le calcul des voisins
lui-meme vit dans `world/level.py` (jeu) et `editor/canvas.py` (editeur), qui
connaissent tous deux la grille complete au moment de dessiner une tuile.
"""

from __future__ import annotations

from collections.abc import Sequence
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
    une planche) / `autotile=True` (case choisie dynamiquement selon les
    voisins, cf. `_select_ground_cell`) - utilise par `terrain_texture` en
    priorite quand il est renseigne.
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
# tuile "wall" a cote d'un pique affiche quand meme son herbe.
SOLID_GROUND_KINDS = frozenset({"wall", "bedrock"})


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
    """Occupation des 4 cases cardinales autour d'une tuile "wall".

    `True` = case voisine libre (aucun terrain solide dessus : `vide`, un
    pique, un decor, une entite, ou hors carte), donc ce bord doit etre
    habille (herbe, coin) ; `False` = voisine solide (`wall`/`bedrock`,
    cf. `SOLID_GROUND_KINDS`), donc ce bord est cache et reste de la terre.

    Calculee par l'appelant, qui seul connait la grille complete : voir
    `world/level.py::_ground_neighbors` (jeu) et `editor/canvas.py` (editeur,
    meme regle, pour que l'apercu corresponde exactement au rendu en jeu).
    """

    top_open: bool = True
    right_open: bool = False
    bottom_open: bool = False
    left_open: bool = False


# Apercu par defaut quand aucun voisinage n'est connu (icone de palette,
# tuile isolee instanciee hors d'un niveau) : une crete d'herbe ordinaire.
_DEFAULT_NEIGHBORS = GroundNeighbors()


def _select_ground_cell(neighbors: GroundNeighbors) -> tuple[int, int]:
    """Case (colonne, ligne) du carre 3x3 de `SHEET_GROUND` a afficher pour ces voisins.

    La rangee suit l'exposition verticale (herbe si rien au-dessus, dessous si
    rien en dessous - priorite a l'herbe si les deux, terre sinon) ; la colonne
    suit l'exposition horizontale (coin gauche/droit si un seul cote est libre,
    milieu sinon - y compris quand les deux cotes sont libres, faute de case
    dediee pour l'instant). Voir le schema dans `settings.py`.
    """
    if neighbors.top_open:
        row = settings.GROUND_ROW_GRASS
    elif neighbors.bottom_open:
        row = settings.GROUND_ROW_BOTTOM
    else:
        row = settings.GROUND_ROW_DIRT

    if neighbors.left_open and not neighbors.right_open:
        column = settings.GROUND_COL_LEFT
    elif neighbors.right_open and not neighbors.left_open:
        column = settings.GROUND_COL_RIGHT
    else:
        column = settings.GROUND_COL_MID

    return column, row


def terrain_texture(
    spec: TileSpec,
    size: int,
    *,
    neighbors: GroundNeighbors | None = None,
) -> arcade.Texture:
    """Texture d'affichage d'une tuile de mur, deja a la taille de la carte.

    `neighbors` pilote l'auto-tiling (`spec.autotile`) : sans lui, l'apercu par
    defaut (crete d'herbe) sert pour la palette de l'editeur ou une tuile hors
    niveau.
    """
    if spec.role != "wall":
        raise ValueError(f"terrain_texture attend un mur, pas '{spec.role}'")
    if spec.autotile:
        cell = _select_ground_cell(neighbors or _DEFAULT_NEIGHBORS)
        return sprites.load_sheet_cell(spec.sheet, *cell, settings.GROUND_CELL, size=size)
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
        neighbors: GroundNeighbors | None = None,
    ) -> None:
        spec = tile_spec(tile)
        if spec.role != "wall":
            raise ValueError(f"'{tile}' n'est pas une tuile de mur")
        texture = terrain_texture(spec, size, neighbors=neighbors)
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
    ) -> None:
        super().__init__(center_x, center_y, size=size, tile=tile)
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
