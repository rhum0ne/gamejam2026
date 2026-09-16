"""Chargement d'un niveau depuis un fichier JSON de `assets/maps/`.

Format attendu (voir `assets/maps/level_1_tuto.json`) :

    {
      "name": "Le Puits Mortel",
      "hint": "texte affiche dans le HUD",
      "tile_size": 32,
      "legend": {"#": "wall", "^": "spike", "B": "bedrock", ...},
      "rows": ["####...", "#.P....#", ...]
    }

`rows` se lit de haut en bas : la premiere chaine est la ligne la plus haute de
l'ecran. Chaque caractere est traduit via `legend` :
    - un type de gameplay (`door`, `key`, `player_spawn`, `spectral_wall`, ...) ;
    - ou le nom d'un sprite de terrain (`wall`, `spike`, `bedrock`, ...).

`wall` est la seule matiere terre/roche : il suffit de dessiner sa forme dans
`rows`, l'apparence (herbe en surface, coin, terre enterree, pilier, coin
interieur...) est deduite de la grille entiere a chaque chargement
(auto-tiling, cf. `world/obstacles.py` :: `compute_ground_cells`). Pas de
symbole dedie a l'herbe : ne jamais en ajouter un, ce serait de nouveau au
level designer de la placer a la main.

Les plaques d'activation sont declarees a part, en coordonnees de grille
(x = colonne, y = ligne depuis le haut, comme `rows`) :

    "activators": [
      {
        "x": 13,
        "y": 31,
        "width": 4,
        "activate": {
          "setBlock": [
            {"x": 17, "y": 40, "type": "void"}
          ]
        }
      }
    ]

`setBlock type=void` retire le bloc existant tant qu'un poids (joueur, cadavre,
ennemi au sol ; un ennemi volant comme la chauve-souris ne pese pas, voir
`EnemyBase.weighs_on_plates`) reste sur la plaque. `"invert": true` inverse
le sens : les blocs sont caches au chargement et n'apparaissent que tant que
la plaque est enfoncee. `width` est optionnel (1 tuile par defaut).
Une pique de plafond (`spike_up`) tombe si le bloc au-dessus d'elle disparait :
elle tue au contact puis se brise au sol.

Pour ajouter un sprite de terrain : deposer le PNG dans `assets/sprites/`,
l'enregistrer dans `TILE_SPECS` (`src/world/obstacles.py`), puis l'utiliser
dans la legende de la carte.

`torch` (symbole `i`) est un decor sans collision : placeholder + halo.
Les autres decors (`chest`, `sign`, `crate`, `tombstone`, ...) viennent de
`world/decorations.py` : chaque entree du catalogue a une fabrique generee
automatiquement ci-dessous.
`flamethrower` (symbole `f`) est un piege : buse sprite + jet shader. Les
reglages (`range` en tuiles, `interval` en secondes, `dir` right/down/left/up)
vivent dans le champ JSON `flamethrowers`, comme les plaques. L'ancien champ
`facing` 1/-1 est encore lu.

`falling_block` est une plateforme qui s'effondre : delay puis chute sans
collision avec le terrain, puis respawn. Les delais vivent dans le champ
JSON `falling_blocks` (`delay` et `respawn`, en secondes).
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import arcade

import settings
from src.entities.bat import Bat
from src.entities.corpse import Corpse
from src.entities.enemy import Enemy
from src.entities.glow import glow_pass
from src.entities.item import Item, ItemKind
from src.entities.zombie import Zombie
from src.world.decorations import Decoration, decoration_kinds
from src.world.falling_block import FallingBlock, FallingSpec, parse_falling_specs
from src.world.flamethrower import FlameSpec, Flamethrower, parse_flame_specs
from src.world.mechanisms import (
    GatedTile,
    Mechanism,
    PressurePlate,
    group_gated_chunks,
    plate_geometry,
)
from src.world.obstacles import (
    SOLID_GROUND_KINDS,
    TILE_SPECS,
    Checkpoint,
    Door,
    IceBlock,
    SpectralWall,
    Spike,
    TileSpec,
    Torch,
    Wall,
    compute_ground_cells,
    tile_spec,
)


def _static_sprite_list() -> arcade.SpriteList:
    """Liste pour le terrain immobile : le hash spatial rend les collisions O(voisinage)."""
    return arcade.SpriteList(
        use_spatial_hash=True,
        spatial_hash_cell_size=settings.TILE_SIZE * 4,
        capacity=4096,
    )


def _dynamic_sprite_list() -> arcade.SpriteList:
    """Liste pour les sprites qui bougent (cadavres, ennemis, objets)."""
    return arcade.SpriteList(capacity=64)


def _render_chunk_list() -> arcade.SpriteList:
    """Liste de dessin d'un chunk : pas de hash, les tuiles n'y bougent jamais."""
    return arcade.SpriteList(
        use_spatial_hash=False,
        capacity=settings.RENDER_CHUNK_TILES * settings.RENDER_CHUNK_TILES,
    )


def _resolve_map_path(path: str | Path) -> Path:
    map_path = Path(path)
    if not map_path.is_absolute():
        map_path = settings.MAPS_DIR / map_path
    if not map_path.exists():
        raise FileNotFoundError(f"carte introuvable : {map_path}")
    return map_path


def peek_level_info(path: str | Path) -> tuple[str, str]:
    """Lit juste le nom et le sous-titre d'une carte (ecran de transition).

    Evite de construire tout le niveau (sprites, collisions...) uniquement
    pour afficher son titre avant le chargement reel.
    """
    with _resolve_map_path(path).open(encoding="utf-8") as stream:
        data = json.load(stream)
    return data.get("name", "Niveau sans nom"), data.get("subtitle", "")


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
    # Nom court affiche en plus du titre sur l'ecran de transition (ex: le nom
    # d'ambiance du niveau, une fois que `name` se limitera a "Niveau N").
    subtitle: str = ""
    walls: arcade.SpriteList = field(default_factory=_static_sprite_list)
    spectral_walls: arcade.SpriteList = field(default_factory=_static_sprite_list)
    hazards: arcade.SpriteList = field(default_factory=_static_sprite_list)
    doors: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    checkpoints: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    items: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    enemies: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    corpses: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    remains: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    plates: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    falling_spikes: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    mechanisms: list[Mechanism] = field(default_factory=list)
    torches: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    decorations: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    torch_stems: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    flamethrowers: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    falling_blocks: arcade.SpriteList = field(default_factory=_dynamic_sprite_list)
    player_spawn: tuple[float, float] = (0.0, 0.0)
    checkpoint_spawn: tuple[float, float] = (0.0, 0.0)
    tiles_drawn: int = 0
    walls_drawn: int = 0
    chunks_drawn: int = 0
    chunks_total: int = 0
    _chunk_pixel_size: int = 0
    _chunk_columns: int = 0
    _chunk_rows: int = 0
    _wall_chunks: list[arcade.SpriteList] = field(default_factory=list)
    _spectral_chunks: list[arcade.SpriteList] = field(default_factory=list)
    _hazard_chunks: list[arcade.SpriteList] = field(default_factory=list)
    _flame_specs: dict[tuple[int, int], FlameSpec] = field(default_factory=dict)
    _falling_specs: dict[tuple[int, int], FallingSpec] = field(default_factory=dict)
    _falling_gone: list[FallingBlock] = field(default_factory=list)

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
            raise LevelFormatError(f"carte introuvable : {map_path.name}")
        try:
            with map_path.open(encoding="utf-8") as stream:
                data = json.load(stream)
        except json.JSONDecodeError as error:
            raise LevelFormatError(
                f"JSON invalide dans {map_path.name} : {error.msg} "
                f"(ligne {error.lineno}, colonne {error.colno})"
            ) from error
        try:
            return cls.from_dict(data)
        except LevelFormatError as error:
            raise LevelFormatError(f"{map_path.name} : {error}") from error

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
            subtitle=data.get("subtitle", ""),
        )
        try:
            level._flame_specs = parse_flame_specs(data.get("flamethrowers"))
        except ValueError as error:
            raise LevelFormatError(str(error)) from error
        try:
            level._falling_specs = parse_falling_specs(data.get("falling_blocks"))
        except ValueError as error:
            raise LevelFormatError(str(error)) from error
        level._build(grid, legend)
        level._bind_activators(data.get("activators", []))
        return level

    def _build(self, grid: list[str], legend: dict[str, str]) -> None:
        ground_cells = _compute_ground_cells(grid, legend)
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
                if kind == "spectral_wall":
                    # Seule fabrique qui a besoin de sa case d'auto-tiling :
                    # le mur spectral se peint comme un mur normal.
                    center = self.tile_center(column_index, row_index, len(grid))
                    cell = ground_cells.get((column_index, row_index))
                    _add_spectral_wall(self, *center, cell)
                    continue
                factory = _FACTORIES.get(kind)
                if factory is not None:
                    center = self.tile_center(column_index, row_index, len(grid))
                    factory(self, *center)
                    continue
                if kind in TILE_SPECS:
                    center = self.tile_center(column_index, row_index, len(grid))
                    cell = ground_cells.get((column_index, row_index))
                    _add_terrain(self, *center, kind, cell)
                    continue
                raise LevelFormatError(f"type de tuile inconnu : '{kind}'")
        self._bind_initial_checkpoint()
        self._build_render_chunks()

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
            distance = math.dist(checkpoint.spawn_point, self.player_spawn)
            if nearest_distance is None or distance < nearest_distance:
                nearest = checkpoint
                nearest_distance = distance
        if nearest is not None and nearest_distance <= 3 * self.tile_size:
            self.checkpoint_spawn = nearest.spawn_point
            return
        self.checkpoint_spawn = self.player_spawn

    def activate_checkpoint(self, checkpoint: Checkpoint, *, ignite: bool = True) -> None:
        """Allume `checkpoint` et eteint les autres statues.

        `ignite=False` pose le halo de repos sans le flash d'allumage
        (spawn initial du niveau).
        """
        if checkpoint.active:
            return
        for other in self.checkpoints:
            if other is checkpoint:
                other.activate(ignite=ignite)
            else:
                other.deactivate()

    def checkpoint_at(self, position: tuple[float, float]) -> Checkpoint | None:
        """Totem dont le point de spawn coincide avec `position`, s'il existe."""
        x, y = position
        for checkpoint in self.checkpoints:
            spawn_x, spawn_y = checkpoint.spawn_point
            if abs(spawn_x - x) < 1 and abs(spawn_y - y) < 1:
                return checkpoint
        return None

    def _bind_activators(self, entries: object) -> None:
        """Pose les plaques et relie chaque `setBlock` au sprite de terrain deja construit."""
        if not entries:
            return
        if not isinstance(entries, list):
            raise LevelFormatError("activators doit etre une liste")
        for index, raw in enumerate(entries):
            if not isinstance(raw, dict):
                raise LevelFormatError(f"activators[{index}] doit etre un objet JSON")
            try:
                mechanism = self._parse_activator(raw)
            except LevelFormatError as error:
                raise LevelFormatError(f"activators[{index}] : {error}") from error
            self.plates.append(mechanism.plate)
            self.mechanisms.append(mechanism)

    def _parse_activator(self, raw: dict) -> Mechanism:
        column = _coord(raw, "x", "x_activator", "x_Activator")
        row = _coord(raw, "y", "y_activator", "y_Activator")
        width_tiles = int(raw.get("width", 1))
        if width_tiles < 1:
            raise LevelFormatError("width doit etre un entier >= 1")
        self._ensure_in_bounds(column, row)
        self._ensure_in_bounds(column + width_tiles - 1, row)
        center_x, center_y, width, height = plate_geometry(
            column, row, width_tiles, self.tile_size, self.rows
        )
        plate = PressurePlate(center_x, center_y, width, height)
        targets = [
            self._gated_tile_at(tile_column, tile_row)
            for tile_column, tile_row in _parse_set_blocks(raw.get("activate"))
        ]
        if not targets:
            raise LevelFormatError("activate.setBlock ne cible aucun bloc")
        return Mechanism(
            plate=plate,
            targets=targets,
            chunks=group_gated_chunks(targets, self.tile_size),
            inverted=_parse_invert(raw),
        )

    def _gated_tile_at(self, column: int, row: int) -> GatedTile:
        self._ensure_in_bounds(column, row)
        sprite = self._terrain_at(column, row)
        if sprite is None:
            occupant = self._non_gated_occupant(column, row)
            detail = (
                f"occupe par {occupant}"
                if occupant is not None
                else "case vide"
            )
            raise LevelFormatError(
                f"setBlock void : aucun bloc a ({column}, {row}) "
                f"({detail} ; la plaque ne retire que murs, murs spectraux et piques)"
            )
        lists = tuple(sprite.sprite_lists)
        if not lists:
            raise LevelFormatError(
                f"setBlock void : le bloc a ({column}, {row}) n'appartient a aucune liste"
            )
        return GatedTile(sprite=sprite, lists=lists)

    def _terrain_at(self, column: int, row: int) -> arcade.Sprite | None:
        x, y = self.tile_center(column, row, self.rows)
        for sprite_list in (self.walls, self.spectral_walls, self.hazards):
            for sprite in sprite_list:
                if abs(sprite.center_x - x) < 1 and abs(sprite.center_y - y) < 1:
                    return sprite
        return None

    def _non_gated_occupant(self, column: int, row: int) -> str | None:
        """Nom de ce qui occupe la case, si ce n'est pas un bloc void-able."""
        x, y = self.tile_center(column, row, self.rows)
        named = (
            ("un decor", self.decorations),
            ("une torche", self.torches),
            ("un lance-flammes", self.flamethrowers),
            ("un bloc tombant", self.falling_blocks),
            ("une porte", self.doors),
            ("un checkpoint", self.checkpoints),
            ("un objet", self.items),
            ("un ennemi", self.enemies),
        )
        for label, sprites in named:
            for sprite in sprites:
                if abs(sprite.center_x - x) < 1 and abs(sprite.center_y - y) < 1:
                    return label
        return None

    def _ensure_in_bounds(self, column: int, row: int) -> None:
        if column < 0 or column >= self.columns or row < 0 or row >= self.rows:
            raise LevelFormatError(
                f"coordonnees hors carte : ({column}, {row}) "
                f"(taille {self.columns}x{self.rows})"
            )

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
    def static_walls(self) -> list[arcade.SpriteList]:
        """Terrain immobile (hash spatial) : murs normaux et spectraux."""
        return [self.walls, self.spectral_walls]

    @property
    def solid_platforms(self) -> list[arcade.SpriteList]:
        """Listes solides pour le corps physique (murs + murs spectraux + cadavres)."""
        return [self.walls, self.spectral_walls, self.corpses, self.falling_blocks]

    def spawn_corpse(self, corpse: arcade.Sprite) -> None:
        """Ajoute un cadavre au niveau (il devient solide immediatement)."""
        self.corpses.append(corpse)

    def _collect_eaten_corpses(self) -> None:
        """Un cadavre devore laisse un squelette decoratif, hors des collisions."""
        for corpse in list(self.corpses):
            if not isinstance(corpse, Corpse) or not corpse.is_remnant:
                continue
            corpse.remove_from_sprite_lists()
            self.remains.append(corpse)

    def spawn_item(self, item: Item) -> None:
        self.items.append(item)

    def draw(self, view_rect=None, *, tight_cull: bool = False) -> None:
        """Dessine le decor puis les entites, dans l'ordre d'empilement voulu.

        En mode corps, les trois SpriteList maitres suffisent : Arcade 3.3
        ignore les sprites hors viewport cote GPU. En mode fantome,
        `tight_cull` restreint aux chunks du trou de vision (le voile cache
        le reste, inutile de le remplir).
        """
        if tight_cull and view_rect is not None and self._wall_chunks:
            self.walls_drawn, self.tiles_drawn = self._draw_visible_terrain(view_rect)
        else:
            self.walls.draw(pixelated=True)
            self.spectral_walls.draw(pixelated=True)
            self.hazards.draw(pixelated=True)
            if view_rect is not None and self._wall_chunks:
                self.walls_drawn, self.tiles_drawn = self._count_visible_terrain(view_rect)
            else:
                self.walls_drawn = len(self.walls)
                self.tiles_drawn = (
                    len(self.walls) + len(self.spectral_walls) + len(self.hazards)
                )
                self.chunks_drawn = self.chunks_total
        self.plates.draw(pixelated=True)
        self.falling_spikes.draw(pixelated=True)
        with glow_pass():
            for checkpoint in self.checkpoints:
                checkpoint.draw_glow()
        self.checkpoints.draw(pixelated=True)
        self.doors.draw(pixelated=True)
        self.decorations.draw(pixelated=True)
        with glow_pass():
            self._queue_torch_glows(view_rect, layer="bloom")
        self.torch_stems.draw(pixelated=True)
        self.torches.draw(pixelated=True)
        with glow_pass():
            self._queue_torch_glows(view_rect, layer="core")
            for item in self.items:
                item.draw_fx()
        for checkpoint in self.checkpoints:
            checkpoint.draw_fx()
        for thrower in self.flamethrowers:
            thrower.draw_flame()
        self.flamethrowers.draw(pixelated=True)
        self.falling_blocks.draw(pixelated=True)
        self.remains.draw(pixelated=True)
        self.corpses.draw(pixelated=True)
        self.items.draw(pixelated=True)
        self.enemies.draw(pixelated=True)

    def draw_static_hit_boxes(self, color, view_rect=None) -> None:
        """Contours de collision du terrain, culles comme le rendu."""
        if view_rect is None or not self._wall_chunks:
            self.walls.draw_hit_boxes(color)
            self.spectral_walls.draw_hit_boxes(color)
            self.hazards.draw_hit_boxes(color)
            return
        for chunk in self._iter_visible_chunks(self._wall_chunks, view_rect):
            chunk.draw_hit_boxes(color)
        for chunk in self._iter_visible_chunks(self._spectral_chunks, view_rect):
            chunk.draw_hit_boxes(color)
        for chunk in self._iter_visible_chunks(self._hazard_chunks, view_rect):
            chunk.draw_hit_boxes(color)

    def count_visible_tiles(self, view_rect) -> tuple[int, int, int, int]:
        """Retourne (tuiles visibles, tuiles totales, murs visibles, murs totaux)."""
        walls = len(arcade.get_sprites_in_rect(view_rect, self.walls))
        spectral = len(arcade.get_sprites_in_rect(view_rect, self.spectral_walls))
        hazards = len(arcade.get_sprites_in_rect(view_rect, self.hazards))
        visible = walls + spectral + hazards
        total = len(self.walls) + len(self.spectral_walls) + len(self.hazards)
        return visible, total, walls, len(self.walls)

    def _build_render_chunks(self) -> None:
        """Range le terrain immobile dans une grille de SpriteList de dessin."""
        tiles_per_chunk = max(1, settings.RENDER_CHUNK_TILES)
        self._chunk_pixel_size = self.tile_size * tiles_per_chunk
        self._chunk_columns = max(1, math.ceil(self.columns / tiles_per_chunk))
        self._chunk_rows = max(1, math.ceil(self.rows / tiles_per_chunk))
        self.chunks_total = self._chunk_columns * self._chunk_rows
        self._wall_chunks = [_render_chunk_list() for _ in range(self.chunks_total)]
        self._spectral_chunks = [_render_chunk_list() for _ in range(self.chunks_total)]
        self._hazard_chunks = [_render_chunk_list() for _ in range(self.chunks_total)]
        self._fill_chunks(self.walls, self._wall_chunks)
        self._fill_chunks(self.spectral_walls, self._spectral_chunks)
        self._fill_chunks(self.hazards, self._hazard_chunks)

    def prepare_draw(self) -> None:
        """Alloue les buffers GPU une fois, avant le jeu (Arcade 3.3 lazy init)."""
        for sprite_list in (
            self.walls,
            self.spectral_walls,
            self.hazards,
            self.doors,
            self.checkpoints,
            self.items,
            self.enemies,
            self.corpses,
            self.remains,
            self.plates,
            self.falling_spikes,
            self.torches,
            self.torch_stems,
            self.flamethrowers,
            self.falling_blocks,
        ):
            sprite_list.initialize()
        for chunks in (self._wall_chunks, self._spectral_chunks, self._hazard_chunks):
            for chunk in chunks:
                if chunk:
                    chunk.initialize()

    def _fill_chunks(self, sprites: arcade.SpriteList, chunks: list[arcade.SpriteList]) -> None:
        for sprite in sprites:
            chunks[self._chunk_index(sprite.center_x, sprite.center_y)].append(sprite)

    def _chunk_index(self, x: float, y: float) -> int:
        column = min(
            self._chunk_columns - 1,
            max(0, int(x // self._chunk_pixel_size)),
        )
        row = min(
            self._chunk_rows - 1,
            max(0, int(y // self._chunk_pixel_size)),
        )
        return row * self._chunk_columns + column

    def _visible_chunk_range(self, view_rect) -> tuple[int, int, int, int]:
        pad = self.tile_size
        size = self._chunk_pixel_size
        if size <= 0 or self._chunk_columns <= 0 or self._chunk_rows <= 0:
            return 0, -1, 0, -1
        col0 = max(0, int((view_rect.left - pad) // size))
        col1 = min(self._chunk_columns - 1, int((view_rect.right + pad) // size))
        row0 = max(0, int((view_rect.bottom - pad) // size))
        row1 = min(self._chunk_rows - 1, int((view_rect.top + pad) // size))
        return col0, col1, row0, row1

    def _iter_visible_chunks(self, chunks: list[arcade.SpriteList], view_rect):
        col0, col1, row0, row1 = self._visible_chunk_range(view_rect)
        columns = self._chunk_columns
        for row in range(row0, row1 + 1):
            base = row * columns
            for column in range(col0, col1 + 1):
                chunk = chunks[base + column]
                if chunk:
                    yield chunk

    def _count_visible_terrain(self, view_rect) -> tuple[int, int]:
        """Compte les tuiles des chunks visibles, sans les dessiner."""
        walls_drawn = 0
        tiles_drawn = 0
        self.chunks_drawn = 0
        for walls, spectral, hazards in self._iter_visible_chunk_triple(view_rect):
            self.chunks_drawn += 1
            walls_drawn += len(walls)
            tiles_drawn += len(walls) + len(spectral) + len(hazards)
        return walls_drawn, tiles_drawn

    def _iter_visible_chunk_triple(self, view_rect):
        col0, col1, row0, row1 = self._visible_chunk_range(view_rect)
        columns = self._chunk_columns
        for row in range(row0, row1 + 1):
            base = row * columns
            for column in range(col0, col1 + 1):
                index = base + column
                walls = self._wall_chunks[index]
                spectral = self._spectral_chunks[index]
                hazards = self._hazard_chunks[index]
                if walls or spectral or hazards:
                    yield walls, spectral, hazards

    def _draw_visible_terrain(self, view_rect) -> tuple[int, int]:
        """Dessine les chunks de terrain qui chevauchent `view_rect`."""
        walls_drawn = 0
        tiles_drawn = 0
        self.chunks_drawn = 0
        for walls, spectral, hazards in self._iter_visible_chunk_triple(view_rect):
            self.chunks_drawn += 1
            if walls:
                walls.draw(pixelated=True)
                walls_drawn += len(walls)
            if spectral:
                spectral.draw(pixelated=True)
            if hazards:
                hazards.draw(pixelated=True)
            tiles_drawn += len(walls) + len(spectral) + len(hazards)
        return walls_drawn, tiles_drawn

    def _queue_torch_glows(self, view_rect, *, layer: str) -> None:
        """Empile les halos de torche visibles (marge = rayon du bloom)."""
        margin = settings.TORCH_GLOW_OUTER
        for torch in self.torches:
            if view_rect is not None:
                if (
                    torch.center_x < view_rect.left - margin
                    or torch.center_x > view_rect.right + margin
                    or torch.center_y < view_rect.bottom - margin
                    or torch.center_y > view_rect.top + margin
                ):
                    continue
            torch.draw_fx(layer=layer)

    def update(self, delta_time: float, attractor: arcade.Sprite | None = None) -> None:
        """Met a jour les elements dont la logique ne depend pas de l'etat de jeu.

        `attractor` est le corps ou le fantome vers lequel les billes bleues
        derivent quand elles sont assez proches.
        """
        self.corpses.update(delta_time)
        self._collect_eaten_corpses()
        self.checkpoints.update(delta_time)
        self.flamethrowers.update(delta_time)
        self._update_falling_blocks(delta_time)
        for item in self.items:
            item.update(delta_time, attractor=attractor)

    def update_spikes(self) -> None:
        """Detache les piques sans plafond, puis les fait tomber jusqu'au sol."""
        self._release_unsupported_spikes()
        self._move_falling_spikes()

    def _release_unsupported_spikes(self) -> None:
        for spike in list(self.hazards):
            if not getattr(spike, "hanging", False) or getattr(spike, "falling", False):
                continue
            if self._ceiling_holds(spike):
                continue
            spike.remove_from_sprite_lists()
            spike.start_fall()
            self.falling_spikes.append(spike)

    def _ceiling_holds(self, spike: arcade.Sprite) -> bool:
        probe = (spike.center_x, spike.center_y + self.tile_size)
        return bool(
            arcade.get_sprites_at_point(probe, self.walls)
            or arcade.get_sprites_at_point(probe, self.spectral_walls)
        )

    def _move_falling_spikes(self) -> None:
        ground = (self.walls, self.spectral_walls, self.corpses)
        for spike in list(self.falling_spikes):
            if spike.fall(ground):
                spike.remove_from_sprite_lists()

    def _update_falling_blocks(self, delta_time: float) -> None:
        """Delay, chute libre (sans collision terrain), puis respawn a l'origine."""
        for block in list(self.falling_blocks):
            block.tick(delta_time)
            if block.went_off_screen():
                block.hide_for_respawn()
                self._falling_gone.append(block)
        still_gone: list[FallingBlock] = []
        for block in self._falling_gone:
            block.tick(delta_time)
            if not block.ready_to_respawn():
                still_gone.append(block)
                continue
            block.respawn_now()
            self.falling_blocks.append(block)
        self._falling_gone = still_gone


# --------------------------------------------------------------------------- #
# Fabriques de tuiles
# --------------------------------------------------------------------------- #


def _add_terrain(
    level: Level, x: float, y: float, kind: str, cell: GroundCell | None = None
) -> None:
    spec: TileSpec = tile_spec(kind)
    if spec.role == "spike":
        level.hazards.append(Spike(x, y, size=level.tile_size, tile=kind))
        return
    if spec.role == "ice":
        level.walls.append(IceBlock(x, y, size=level.tile_size, tile=kind))
        return
    level.walls.append(Wall(x, y, size=level.tile_size, tile=kind, cell=cell))


def _compute_ground_cells(
    grid: list[str], legend: dict[str, str]
) -> dict[tuple[int, int], GroundCell]:
    """Resout la case `SHEET_GROUND` des tuiles auto-tilees de `grid` (cf. `compute_ground_cells`).

    Une case hors carte compte comme solide : les tuiles de bordure se peignent
    comme du terrain enterre (pas d'herbe au plafond du monde ni de pilier
    flottant sur les bords), la camera ne montrant jamais l'exterieur.
    Les murs spectraux sont auto-tiles comme des murs normaux : c'est ce qui
    les rend indetectables pour le corps physique.
    """

    def out_of_bounds(column: int, row: int) -> bool:
        return row < 0 or row >= len(grid) or column < 0 or column >= len(grid[row])

    def kind_at(column: int, row: int) -> str | None:
        if out_of_bounds(column, row):
            return None
        symbol = grid[row][column]
        return legend.get(symbol, "vide" if symbol == "." else None)

    def is_solid(column: int, row: int) -> bool:
        if out_of_bounds(column, row):
            return True
        return kind_at(column, row) in SOLID_GROUND_KINDS

    def is_autotile(column: int, row: int) -> bool:
        kind = kind_at(column, row)
        if kind == "spectral_wall":
            return True
        spec = TILE_SPECS.get(kind) if kind is not None else None
        return spec is not None and spec.autotile

    return compute_ground_cells(
        len(grid[0]) if grid else 0,
        len(grid),
        is_solid=is_solid,
        is_autotile=is_autotile,
    )


def _add_spectral_wall(level: Level, x: float, y: float, cell: GroundCell | None = None) -> None:
    level.spectral_walls.append(SpectralWall(x, y, size=level.tile_size, cell=cell))


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


def _add_bat(level: Level, x: float, y: float) -> None:
    level.enemies.append(Bat(x, y))


def _add_zombie(level: Level, x: float, y: float) -> None:
    level.enemies.append(Zombie(x, y))


def _coord(raw: dict, *keys: str) -> int:
    for key in keys:
        if key in raw:
            return _as_int(raw[key], key)
    raise LevelFormatError(f"champ manquant ({', '.join(keys)})")


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LevelFormatError(f"{name} doit etre un entier")
    return value


def _parse_invert(raw: dict) -> bool:
    """Lit `invert` (defaut False). Absent = plaque qui cache a l'activation."""
    if "invert" not in raw:
        return False
    value = raw["invert"]
    if not isinstance(value, bool):
        raise LevelFormatError("invert doit etre un booleen")
    return value


def _parse_set_blocks(activate: object) -> list[tuple[int, int]]:
    """Extrait les tuiles `setBlock type=void` d'un objet `activate`."""
    if activate is None:
        raise LevelFormatError("activate est requis")
    if not isinstance(activate, dict):
        raise LevelFormatError("activate doit etre un objet { setBlock: ... }")
    if "setBlock" not in activate:
        raise LevelFormatError("activate.setBlock est requis")
    block = activate["setBlock"]
    if isinstance(block, dict):
        entries = [block]
    elif isinstance(block, list):
        entries = block
    else:
        raise LevelFormatError("setBlock doit etre un objet ou une liste d'objets")
    tiles: list[tuple[int, int]] = []
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise LevelFormatError(f"setBlock[{index}] doit etre un objet")
        kind = entry.get("type", "void")
        if kind != "void":
            raise LevelFormatError(
                f"setBlock type '{kind}' non supporte (uniquement 'void')"
            )
        tiles.append((_coord(entry, "x"), _coord(entry, "y")))
    return tiles


def _add_torch(level: Level, x: float, y: float) -> None:
    torch = Torch(x, y)
    level.torches.append(torch)
    level.torch_stems.append(torch.stem)


def _add_flamethrower(level: Level, x: float, y: float) -> None:
    column = int(x // level.tile_size)
    row = level.rows - 1 - int(y // level.tile_size)
    spec = level._flame_specs.get((column, row))
    thrower = Flamethrower(
        x,
        y,
        size=level.tile_size,
        range_tiles=spec.range_tiles if spec is not None else settings.FLAMETHROWER_RANGE,
        interval=spec.interval if spec is not None else settings.FLAMETHROWER_INTERVAL,
        direction=spec.direction if spec is not None else "right",
    )
    level.flamethrowers.append(thrower)


def _add_falling_block(level: Level, x: float, y: float) -> None:
    column = int(x // level.tile_size)
    row = level.rows - 1 - int(y // level.tile_size)
    spec = level._falling_specs.get((column, row))
    block = FallingBlock(
        x,
        y,
        size=level.tile_size,
        delay=spec.delay if spec is not None else settings.FALLING_BLOCK_DELAY,
        respawn=spec.respawn if spec is not None else settings.FALLING_BLOCK_RESPAWN,
    )
    level.falling_blocks.append(block)


def _decoration_factory(kind: str) -> Callable[[Level, float, float], None]:
    """Fabrique une fonction `_add_xxx` pour un type de `decorations.DECORATION_SPECS`."""

    def _add_decoration(level: Level, x: float, y: float) -> None:
        level.decorations.append(Decoration(kind, x, y))

    return _add_decoration


_FACTORIES: dict[str, Callable[[Level, float, float], None]] = {
    "spectral_wall": _add_spectral_wall,
    "door": _add_door,
    "checkpoint": _add_checkpoint,
    "player_spawn": _add_player_spawn,
    "key": _add_key,
    "soul_orb": _add_soul_orb,
    "enemy": _add_enemy,
    "bat": _add_bat,
    "zombie": _add_zombie,
    "torch": _add_torch,
    **{kind: _decoration_factory(kind) for kind in decoration_kinds()},
    "flamethrower": _add_flamethrower,
    settings.TILE_KIND_FALLING: _add_falling_block,
}


def gameplay_kinds() -> tuple[str, ...]:
    """Types de tuiles non-terrain acceptes dans une legende (hors `vide`).

    L'editeur de niveaux s'en sert pour lister les elements placables : ajouter
    une fabrique a `_FACTORIES` suffit pour qu'elle apparaisse dans sa palette.
    """
    return tuple(_FACTORIES)
