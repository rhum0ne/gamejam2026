"""Fond de l'ecran titre : une carte vue en mode fantome.

Charge une grotte dediee au menu, y fait voler des esprits, et reprend le
voile radial du jeu (`GhostFog.draw_many`) : chaque fantome porte son halo.
"""

from __future__ import annotations

import math
import random

import arcade

import settings
from src.entities.glow import draw_glow, glow_pass
from src.ui import sprites
from src.ui.display import use_default_camera
from src.world.atmosphere import ForegroundAtmosphere
from src.world.camera import CameraRig
from src.world.fog import GhostFog
from src.world.level import Level, LevelFormatError


class _Wanderer(arcade.Sprite):
    """Esprit de decor : vole en 8 directions, rebondit, change de cap."""

    def __init__(
        self,
        frames: tuple[arcade.Texture, ...],
        center_x: float,
        center_y: float,
        speed: float,
        rng: random.Random,
    ) -> None:
        super().__init__(frames[0], center_x=center_x, center_y=center_y)
        sprites.apply_rect_hit_box(
            self,
            settings.GHOST_WIDTH * settings.ENTITY_SCALE,
            settings.GHOST_HEIGHT * settings.ENTITY_SCALE,
        )
        self.frames = frames
        self.speed = speed
        self.vision_radius = settings.MENU_TITLE_VISION
        self.alpha = 215
        self.facing = 1
        self.change_x = 0.0
        self.change_y = 0.0
        self._rng = rng
        self._target = (center_x, center_y)
        self._retarget_in = 0.0
        self._hover_in = 0.0
        self._curl_phase = rng.uniform(0.0, math.tau)
        self._curl_speed = rng.uniform(0.6, 1.4)
        self._pulse_phase = rng.uniform(0.0, math.tau)
        self._pulse_speed = rng.uniform(0.7, 1.3)
        sprites.apply_facing(self, self.facing)

    def unstick(self, walls: arcade.SpriteList) -> None:
        """Sort le sprite d'un mur (monte, puis decale a l'horizontale)."""
        if not arcade.check_for_collision_with_list(self, walls):
            return
        origin_x, origin_y = self.center_x, self.center_y
        max_lift = int(abs(self.height)) + settings.TILE_SIZE
        for _ in range(max_lift):
            self.center_y += 1
            if not arcade.check_for_collision_with_list(self, walls):
                return
        self.center_y = origin_y
        for shift in (32, -32, 64, -64, 96, -96):
            self.center_x = origin_x + shift
            if not arcade.check_for_collision_with_list(self, walls):
                return
        self.center_x = origin_x

    def fly(
        self,
        delta_time: float,
        walls: arcade.SpriteList,
        world: Level,
        open_cells: tuple[tuple[float, float], ...],
        flock: tuple[float, float],
    ) -> None:
        """Vole vers un cap, se tord, rebondit, et reste dans le groupe."""
        dt = max(0.0, delta_time)
        self._curl_phase += self._curl_speed * dt
        self._pulse_phase += self._pulse_speed * dt
        self._retarget_in -= dt
        self._hover_in -= dt
        if self._retarget_in <= 0.0:
            self._pick_target(open_cells)
        desired_x, desired_y = self._desired_dir(flock)
        if self._hover_in > 0.0:
            desired_x, desired_y = 0.0, 0.0
            smooth = settings.GHOST_COAST_TIME
        else:
            smooth = settings.GHOST_ACCEL_TIME
        alpha = 1.0 - math.exp(-dt / max(smooth, 0.001))
        self.change_x += (desired_x * self.speed - self.change_x) * alpha
        self.change_y += (desired_y * self.speed - self.change_y) * alpha
        self._move_axis("x", dt, walls, world)
        self._move_axis("y", dt, walls, world)
        if abs(self.change_x) > 0.05:
            self.facing = 1 if self.change_x > 0 else -1
            sprites.apply_facing(self, self.facing)
        pulse = math.sin(self._pulse_phase)
        self.vision_radius = settings.MENU_TITLE_VISION + pulse * settings.MENU_TITLE_VISION_PULSE

    def _desired_dir(self, flock: tuple[float, float]) -> tuple[float, float]:
        dx = self._target[0] - self.center_x
        dy = self._target[1] - self.center_y
        if math.hypot(dx, dy) < settings.TILE_SIZE:
            self._retarget_in = 0.0
        length = math.hypot(dx, dy) or 1.0
        dx, dy = dx / length, dy / length
        curl = math.sin(self._curl_phase) * settings.MENU_TITLE_CURL
        dx, dy = dx - dy * curl, dy + dx * curl
        flock_dx = flock[0] - self.center_x
        flock_dy = flock[1] - self.center_y
        flock_dist = math.hypot(flock_dx, flock_dy)
        if flock_dist > settings.MENU_TITLE_FLOCK_RADIUS and flock_dist > 1.0:
            pull = (flock_dist - settings.MENU_TITLE_FLOCK_RADIUS) / settings.MENU_TITLE_FLOCK_RADIUS
            dx += flock_dx / flock_dist * pull
            dy += flock_dy / flock_dist * pull
        length = math.hypot(dx, dy) or 1.0
        return dx / length, dy / length

    def aim(self, open_cells: tuple[tuple[float, float], ...]) -> None:
        """Choisit un prochain cap dans les cellules libres."""
        self._pick_target(open_cells)

    def _pick_target(self, open_cells: tuple[tuple[float, float], ...]) -> None:
        rng = self._rng
        self._retarget_in = rng.uniform(
            settings.MENU_TITLE_RETARGET_MIN,
            settings.MENU_TITLE_RETARGET_MAX,
        )
        if rng.random() < settings.MENU_TITLE_HOVER_CHANCE:
            self._hover_in = rng.uniform(0.4, 1.1)
            self._target = (self.center_x, self.center_y)
            return
        self._hover_in = 0.0
        if not open_cells:
            return
        self._target = open_cells[rng.randrange(len(open_cells))]

    def _move_axis(
        self,
        axis: str,
        delta_time: float,
        walls: arcade.SpriteList,
        world: Level,
    ) -> None:
        scale = delta_time / settings.FRAME_TIME
        margin = settings.TILE_SIZE
        if axis == "x":
            previous = self.center_x
            self.center_x += self.change_x * scale
            out = self.center_x < margin or self.center_x > world.width - margin
            hit = out or bool(arcade.check_for_collision_with_list(self, walls))
            if hit:
                self.center_x = previous
                self.change_x *= -0.4
                self._retarget_in = min(self._retarget_in, 0.2)
            return
        previous = self.center_y
        self.center_y += self.change_y * scale
        out = self.center_y < margin or self.center_y > world.height - margin
        hit = out or bool(arcade.check_for_collision_with_list(self, walls))
        if hit:
            self.center_y = previous
            self.change_y *= -0.4
            self._retarget_in = min(self._retarget_in, 0.2)


class TitleStage:
    """Carte fantome derriere le tableau de niveaux."""

    def __init__(self) -> None:
        self._time = 0.0
        self._frames = sprites.load_strip(
            settings.SPRITE_GHOST_WALK,
            settings.SPRITE_FRAME_SIZE,
            scale=settings.ENTITY_SCALE,
        )
        self._level: Level | None = None
        self._camera: CameraRig | None = None
        self._fog = GhostFog()
        self._atmosphere = ForegroundAtmosphere()
        self._ghosts: list[_Wanderer] = []
        self._open_cells: tuple[tuple[float, float], ...] = ()
        self._ready = False
        self._boot()

    def _boot(self) -> None:
        try:
            level = Level.from_file(settings.MENU_TITLE_MAP)
        except (LevelFormatError, OSError):
            return
        level.prepare_draw()
        camera = CameraRig(level.width, level.height)
        window = arcade.get_window()
        camera.on_resize(window.width, window.height)
        cells = _open_cells(level)
        ghosts = self._spawn_ghosts(level, cells)
        if not ghosts:
            return
        camera.snap_to(ghosts[0], settings.MENU_TITLE_ZOOM)
        self._level = level
        self._camera = camera
        self._ghosts = ghosts
        self._open_cells = cells
        self._ready = True

    def _spawn_ghosts(
        self,
        level: Level,
        cells: tuple[tuple[float, float], ...],
    ) -> list[_Wanderer]:
        rng = random.Random(settings.ATMOSPHERE_SEED)
        spots = _spread_cells(cells, settings.MENU_TITLE_GHOST_COUNT, rng)
        if not spots:
            spots = (level.player_spawn,)
        ghosts: list[_Wanderer] = []
        for x, y in spots:
            speed = settings.MENU_TITLE_GHOST_SPEED * rng.uniform(0.75, 1.2)
            wanderer = _Wanderer(self._frames, x, y, speed, random.Random(rng.random()))
            wanderer.unstick(level.walls)
            wanderer.aim(cells)
            ghosts.append(wanderer)
        return ghosts

    def resize(self, width: float, height: float) -> None:
        if self._camera is not None:
            self._camera.on_resize(int(width), int(height))

    def update(self, delta_time: float) -> None:
        dt = max(0.0, delta_time)
        self._time += dt
        if not self._ready or self._level is None or self._camera is None:
            return
        self._atmosphere.update(dt)
        self._level.update(dt)
        flock = _centroid(self._ghosts)
        for ghost in self._ghosts:
            ghost.fly(dt, self._level.walls, self._level, self._open_cells, flock)
            if self._frames:
                frame = int(self._time / settings.ANIM_WALK_FRAME_TIME) % len(self._frames)
                ghost.texture = self._frames[frame]
        self._camera.drift_to(flock[0], flock[1], dt, settings.MENU_TITLE_ZOOM)

    def draw(self) -> None:
        window = arcade.get_window()
        if not self._ready or self._level is None or self._camera is None:
            arcade.draw_lrbt_rectangle_filled(
                0, window.width, 0, window.height, settings.COLOR_BACKGROUND
            )
            return
        camera = self._camera
        camera.begin_frame()
        camera.use_world()
        view = camera.cull_rect()
        for wall in self._level.spectral_walls:
            wall.set_revealed(any(self._in_vision(ghost, wall) for ghost in self._ghosts))
        self._level.draw(view, tight_cull=True)
        self._atmosphere.draw(camera.world)
        self._fog.draw_many(self._ghosts, camera.world)
        with glow_pass():
            for ghost in self._ghosts:
                self._draw_halo(ghost)
        for ghost in self._ghosts:
            sprites.draw_pixel_sprite(ghost)
        camera.present(settings.MENU_TITLE_WARP)
        use_default_camera(window)

    @staticmethod
    def _in_vision(ghost: _Wanderer, sprite: arcade.Sprite) -> bool:
        return math.dist((ghost.center_x, ghost.center_y), sprite.position) <= ghost.vision_radius

    @staticmethod
    def _draw_halo(ghost: arcade.Sprite) -> None:
        draw_glow(
            ghost.center_x,
            ghost.center_y,
            settings.GHOST_WIDTH * settings.GHOST_GLOW_SCALE,
            settings.GHOST_HEIGHT * settings.GHOST_GLOW_SCALE,
            settings.COLOR_GHOST_GLOW,
            settings.GHOST_GLOW_ALPHA,
        )


def _open_cells(level: Level) -> tuple[tuple[float, float], ...]:
    """Centres de tuiles vides, assez loin des bords pour y faire voler."""
    cells: list[tuple[float, float]] = []
    margin = settings.TILE_SIZE * 2
    for row in range(level.rows):
        for column in range(level.columns):
            x, y = level.tile_center(column, row, level.rows)
            if x < margin or x > level.width - margin:
                continue
            if y < margin or y > level.height - margin:
                continue
            if arcade.get_sprites_at_point((x, y), level.walls):
                continue
            cells.append((x, y))
    return tuple(cells)


def _spread_cells(
    cells: tuple[tuple[float, float], ...],
    count: int,
    rng: random.Random,
) -> tuple[tuple[float, float], ...]:
    """Choisit des points distants pour que les halos ne naissent pas empiles."""
    if not cells or count <= 0:
        return ()
    chosen: list[tuple[float, float]] = [cells[rng.randrange(len(cells))]]
    remaining = list(cells)
    while len(chosen) < count and remaining:
        best = max(
            remaining,
            key=lambda cell: min(math.dist(cell, placed) for placed in chosen),
        )
        chosen.append(best)
        remaining = [cell for cell in remaining if math.dist(cell, best) > settings.TILE_SIZE]
    return tuple(chosen[:count])


def _centroid(ghosts: list[_Wanderer]) -> tuple[float, float]:
    if not ghosts:
        return 0.0, 0.0
    return (
        sum(ghost.center_x for ghost in ghosts) / len(ghosts),
        sum(ghost.center_y for ghost in ghosts) / len(ghosts),
    )
