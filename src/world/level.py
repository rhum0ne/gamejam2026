"""Chargement d'un niveau depuis un fichier JSON de `assets/maps/`.

Format attendu (voir `assets/maps/level_1_tuto.json`) :

    {
      "name": "Le Puits Mortel",
      "hint": "texte affiche dans le HUD",
      "tile_size": 32,
      "legend": {"#": "wall", ...},
      "rows": ["####...", "#..P..#", ...]
    }

`rows` se lit de haut en bas : la premiere chaine est la ligne la plus haute de
l'ecran. Chaque caractere est traduit via `legend` en un nom de type, lui-meme
associe a une fabrique de sprite dans `_FACTORIES`.

Pour ajouter un type de tuile : ajouter le symbole dans la legende de la carte,
puis une entree dans `_FACTORIES` (et si besoin une classe dans `obstacles.py`).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import arcade

import settings
from src.entities.enemy import Enemy
from src.entities.item import Item, ItemKind
from src.world.obstacles import Checkpoint, Door, SpectralWall, Spike, Wall


class LevelFormatError(ValueError):
    """Carte invalide : symbole inconnu, lignes de longueurs differentes, etc."""


@dataclass(slots=True)
class Level:
    """Contenu statique et dynamique d'un niveau, pret a etre dessine."""

    name: str
    hint: str
    tile_size: int
    columns: int
    rows: int
    walls: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    spectral_walls: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    hazards: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    doors: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    checkpoints: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    items: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    enemies: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    corpses: arcade.SpriteList = field(default_factory=arcade.SpriteList)
    player_spawn: tuple[float, float] = (0.0, 0.0)
    checkpoint_spawn: tuple[float, float] = (0.0, 0.0)

    # ------------------------------------------------------------------ #
    # Chargement
    # ------------------------------------------------------------------ #

    @classmethod
    def from_file(cls, path: str | Path) -> "Level":
        """Charge un niveau depuis un fichier JSON."""
        map_path = Path(path)
        if not map_path.is_absolute():
            map_path = settings.MAPS_DIR / map_path
        if not map_path.exists():
            raise FileNotFoundError(f"carte introuvable : {map_path}")
        with map_path.open(encoding="utf-8") as stream:
            data = json.load(stream)
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict) -> "Level":
        """Construit un niveau a partir d'un dictionnaire deja charge."""
        grid: list[str] = data.get("rows", [])
        if not grid:
            raise LevelFormatError("la carte ne contient aucune ligne ('rows')")
        widths = {len(row) for row in grid}
        if len(widths) != 1:
            raise LevelFormatError(f"lignes de longueurs differentes : {sorted(widths)}")

        legend: dict[str, str] = data.get("legend", {})
        tile_size = int(data.get("tile_size", settings.TILE_SIZE))
        level = cls(
            name=data.get("name", "Niveau sans nom"),
            hint=data.get("hint", ""),
            tile_size=tile_size,
            columns=widths.pop(),
            rows=len(grid),
        )
        level._build(grid, legend)
        return level

    def _build(self, grid: list[str], legend: dict[str, str]) -> None:
        for row_index, row in enumerate(grid):
            for column_index, symbol in enumerate(row):
                kind = legend.get(symbol, "vide" if symbol == "." else None)
                if kind is None:
                    raise LevelFormatError(
                        f"symbole '{symbol}' absent de la legende "
                        f"(ligne {row_index}, colonne {column_index})"
                    )
                if kind == "vide":
                    continue
                factory = _FACTORIES.get(kind)
                if factory is None:
                    raise LevelFormatError(f"type de tuile inconnu : '{kind}'")
                center = self.tile_center(column_index, row_index, len(grid))
                factory(self, *center)
        self._bind_initial_checkpoint()

    def _bind_initial_checkpoint(self) -> None:
        """Le spawn initial est le checkpoint le plus proche du joueur, pas le premier 'C' du fichier.

        Sans ca, un checkpoint sur une plateforme haute (parse en premier, car en haut
        de la carte) volerait le point de reapparition du tutoriel.
        """
        if self.player_spawn == (0.0, 0.0):
            return
        nearest = None
        nearest_distance = None
        for checkpoint in self.checkpoints:
            distance = math.dist(checkpoint.position, self.player_spawn)
            if nearest_distance is None or distance < nearest_distance:
                nearest = checkpoint
                nearest_distance = distance
        if nearest is not None and nearest_distance <= 3 * self.tile_size:
            self.checkpoint_spawn = (nearest.center_x, nearest.center_y)
            return
        self.checkpoint_spawn = self.player_spawn

    def tile_center(self, column: int, row: int, total_rows: int) -> tuple[float, float]:
        """Convertit des coordonnees de grille en coordonnees monde (pixels)."""
        x = column * self.tile_size + self.tile_size / 2
        y = (total_rows - 1 - row) * self.tile_size + self.tile_size / 2
        return x, y

    # ------------------------------------------------------------------ #
    # Dimensions et helpers
    # ------------------------------------------------------------------ #

    @property
    def width(self) -> float:
        return self.columns * self.tile_size

    @property
    def height(self) -> float:
        return self.rows * self.tile_size

    @property
    def solid_platforms(self) -> list[arcade.SpriteList]:
        """Listes solides pour le corps physique (murs + murs spectraux + cadavres)."""
        return [self.walls, self.spectral_walls, self.corpses]

    def spawn_corpse(self, corpse: arcade.Sprite) -> None:
        """Ajoute un cadavre au niveau (il devient solide immediatement)."""
        self.corpses.append(corpse)

    def spawn_item(self, item: Item) -> None:
        self.items.append(item)

    def draw(self) -> None:
        """Dessine le decor puis les entites, dans l'ordre d'empilement voulu."""
        self.walls.draw()
        self.spectral_walls.draw()
        self.hazards.draw()
        self.checkpoints.draw()
        self.doors.draw()
        self.corpses.draw()
        self.items.draw()
        self.enemies.draw()

    def update(self, delta_time: float) -> None:
        """Met a jour les elements dont la logique ne depend pas de l'etat de jeu."""
        self.corpses.update(delta_time)
        self.items.update(delta_time)


# --------------------------------------------------------------------------- #
# Fabriques de tuiles
# --------------------------------------------------------------------------- #


def _add_wall(level: Level, x: float, y: float) -> None:
    level.walls.append(Wall(x, y, size=level.tile_size))


def _add_spectral_wall(level: Level, x: float, y: float) -> None:
    level.spectral_walls.append(SpectralWall(x, y, size=level.tile_size))


def _add_spike(level: Level, x: float, y: float) -> None:
    level.hazards.append(Spike(x, y, size=level.tile_size))


def _add_door(level: Level, x: float, y: float) -> None:
    level.doors.append(Door(x, y, size=level.tile_size))


def _add_checkpoint(level: Level, x: float, y: float) -> None:
    level.checkpoints.append(Checkpoint(x, y, size=level.tile_size))


def _add_player_spawn(level: Level, x: float, y: float) -> None:
    level.player_spawn = (x, y)
    if level.checkpoint_spawn == (0.0, 0.0):
        level.checkpoint_spawn = (x, y)


def _add_key(level: Level, x: float, y: float) -> None:
    level.items.append(Item(ItemKind.KEY, x, y))


def _add_soul_orb(level: Level, x: float, y: float) -> None:
    level.items.append(Item(ItemKind.SOUL_ORB, x, y))


def _add_enemy(level: Level, x: float, y: float) -> None:
    level.enemies.append(Enemy(x, y))


_FACTORIES: dict[str, Callable[[Level, float, float], None]] = {
    "wall": _add_wall,
    "spectral_wall": _add_spectral_wall,
    "spike": _add_spike,
    "door": _add_door,
    "checkpoint": _add_checkpoint,
    "player_spawn": _add_player_spawn,
    "key": _add_key,
    "soul_orb": _add_soul_orb,
    "enemy": _add_enemy,
}
