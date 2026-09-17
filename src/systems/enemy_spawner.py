"""Directeur de population des ennemis.

Le niveau fournit des points de spawn, mais ne decide pas lui-meme quand un
ennemi doit apparaitre. ``EnemySpawnDirector`` garde une population lisible :

* un plafond d'ennemis actifs ;
* des renforts par petites vagues ;
* un delai apres une mort ;
* un test de securite autour du joueur, des autres ennemis et de la camera ;
* une courte phase de prespawn visible avant la materialisation.

Les ennemis crees par le directeur ne laissent pas d'ame. Les ennemis poses
directement dans la carte peuvent en laisser une fois : cela evite de rendre
les respawns exploitables pour farmer la progression du fantome.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass, replace

import arcade

import settings
from src.entities.enemy import Enemy
from src.entities.glow import draw_glow, glow_pass


@dataclass(frozen=True, slots=True)
class EnemySpawnConfig:
    """Reglages d'un directeur, surchargeables dans une carte JSON."""

    enabled: bool = True
    max_active: int = 6
    wave_size: int = 2
    initial_delay: float = 5.0
    wave_interval: float = 6.0
    respawn_delay: float = 4.0
    retry_delay: float = 0.5
    warning_duration: float = 0.7
    min_player_distance: float = 224.0
    min_enemy_distance: float = 96.0
    offscreen_margin: float = 64.0

    @classmethod
    def defaults(cls) -> "EnemySpawnConfig":
        """Construit les valeurs par defaut a l'execution.

        Les anciens noms ``ENEMY_RESPAWN_*`` restent la source de verite pour
        les trois reglages de securite/delai afin de conserver la compatibilite
        avec les outils de test et les reglages deja presents dans le projet.
        """
        return cls(
            max_active=settings.ENEMY_SPAWN_MAX_ACTIVE,
            wave_size=settings.ENEMY_SPAWN_WAVE_SIZE,
            initial_delay=settings.ENEMY_SPAWN_INITIAL_DELAY,
            wave_interval=settings.ENEMY_SPAWN_WAVE_INTERVAL,
            respawn_delay=settings.ENEMY_RESPAWN_DELAY,
            retry_delay=settings.ENEMY_RESPAWN_RETRY_DELAY,
            warning_duration=settings.ENEMY_SPAWN_WARNING_DURATION,
            min_player_distance=settings.ENEMY_RESPAWN_MIN_PLAYER_DISTANCE,
            min_enemy_distance=settings.ENEMY_RESPAWN_MIN_ENEMY_DISTANCE,
            offscreen_margin=settings.ENEMY_SPAWN_OFFSCREEN_MARGIN,
        )


def parse_enemy_spawn_config(raw: object) -> EnemySpawnConfig:
    """Valide le bloc ``enemy_spawn_director`` d'une carte."""
    config = EnemySpawnConfig.defaults()
    if raw is None:
        return config
    if not isinstance(raw, dict):
        raise ValueError("enemy_spawn_director doit etre un objet")

    values: dict[str, object] = {}
    aliases = {
        "interval": "wave_interval",
        "delay": "respawn_delay",
    }
    for key, value in raw.items():
        canonical = aliases.get(key, key)
        if canonical in {
            "enabled",
            "max_active",
            "wave_size",
            "initial_delay",
            "wave_interval",
            "respawn_delay",
            "retry_delay",
            "warning_duration",
            "min_player_distance",
            "min_enemy_distance",
            "offscreen_margin",
        }:
            values[canonical] = value

    if "enabled" in values:
        enabled = values["enabled"]
        if not isinstance(enabled, bool):
            raise ValueError("enabled doit etre un booleen")
        config = replace(config, enabled=enabled)
    if "max_active" in values:
        config = replace(config, max_active=_positive_int(values["max_active"], "max_active"))
    if "wave_size" in values:
        config = replace(config, wave_size=_positive_int(values["wave_size"], "wave_size"))
    for field_name in (
        "initial_delay",
        "wave_interval",
        "respawn_delay",
        "retry_delay",
        "warning_duration",
        "min_player_distance",
        "min_enemy_distance",
        "offscreen_margin",
    ):
        if field_name not in values:
            continue
        minimum = 0.0 if field_name in {"initial_delay", "min_player_distance", "min_enemy_distance", "offscreen_margin"} else 0.001
        config = replace(
            config,
            **{field_name: _number(values[field_name], field_name, minimum)},
        )
    return config


def _positive_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} doit etre un entier strictement positif")
    return value


def _number(value: object, name: str, minimum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} doit etre un nombre")
    number = float(value)
    if not math.isfinite(number) or number < minimum:
        raise ValueError(f"{name} doit etre superieur ou egal a {minimum:g}")
    return number


@dataclass(slots=True)
class _PendingSpawn:
    point_index: int
    time_left: float


class EnemySpawnDirector:
    """Planifie des vagues d'ennemis a partir de positions candidates."""

    def __init__(
        self,
        spawn_points: Sequence[tuple[float, float]],
        seed_enemies: Sequence[Enemy],
        config: EnemySpawnConfig | None = None,
    ) -> None:
        self.config = config if config is not None else EnemySpawnConfig.defaults()
        self._seed_enemies: list[tuple[Enemy, float, float]] = [
            (enemy, enemy.center_x, enemy.center_y) for enemy in seed_enemies
        ]
        self._seed_ids = {id(enemy) for enemy in seed_enemies}
        # Les points explicites et les graines de squelette sont compatibles
        # avec le renfort actuel. On n'utilise pas les positions d'un boss,
        # d'un zombie ou d'une chauve-souris pour faire apparaitre un squelette
        # au mauvais endroit dans les niveaux recents.
        skeleton_seeds = [enemy for enemy in seed_enemies if isinstance(enemy, Enemy)]
        self._points = self._deduplicate_points(
            [
                *spawn_points,
                *((enemy.center_x, enemy.center_y) for enemy in skeleton_seeds),
            ]
        )
        self._cursor = 0
        self._clock = 0.0
        self._wave_timer = self.config.initial_delay
        self._wave_remaining = 0
        self._pending: _PendingSpawn | None = None
        self._last_active_count: int | None = len(self._seed_enemies)
        self._platforms: list[arcade.SpriteList] = []
        self._hazards: arcade.SpriteList | None = None

    @staticmethod
    def _deduplicate_points(
        points: Sequence[tuple[float, float]],
    ) -> list[tuple[float, float]]:
        unique: list[tuple[float, float]] = []
        for point in points:
            if not any(math.dist(point, other) < 1.0 for other in unique):
                unique.append((float(point[0]), float(point[1])))
        return unique

    @property
    def spawn_points(self) -> tuple[tuple[float, float], ...]:
        """Positions candidates, utile pour le debug et l'editeur."""
        return tuple(self._points)

    @property
    def pending_spawn(self) -> tuple[float, float, float] | None:
        """Point en phase d'avertissement : x, y, progression restante."""
        if self._pending is None:
            return None
        x, y = self._points[self._pending.point_index]
        return x, y, self._pending.time_left

    @property
    def active(self) -> bool:
        """Indique si le directeur peut effectivement faire apparaitre des ennemis."""
        return self.config.enabled and bool(self._points)

    def bind_world(
        self,
        platforms: Sequence[arcade.SpriteList],
        hazards: arcade.SpriteList | None = None,
    ) -> None:
        """Conserve les collisions du niveau pour les nouveaux ennemis."""
        self._platforms = list(platforms)
        self._hazards = hazards

    def update(
        self,
        delta_time: float,
        enemies: arcade.SpriteList,
        player: arcade.Sprite,
        view=None,
    ) -> None:
        """Avance le directeur et materialise au plus une apparition par frame."""
        if not self.active or not getattr(player, "alive", True):
            return
        dt = max(0.0, delta_time)
        self._clock += dt
        active_count = len(enemies)
        if (
            self._last_active_count is not None
            and active_count < self._last_active_count
        ):
            # Le delai part quand l'animation de mort retire vraiment le sprite,
            # pas au premier impact.
            self._wave_timer = self.config.respawn_delay
        self._last_active_count = active_count

        max_active = max(self.config.max_active, len(self._seed_enemies))
        if active_count >= max_active:
            if self._pending is not None:
                self._pending = None
                self._wave_remaining = 0
                self._wave_timer = self.config.wave_interval
            return

        if self._pending is not None:
            self._pending.time_left = max(0.0, self._pending.time_left - dt)
            if self._pending.time_left > 0.0:
                return
            point_index = self._pending.point_index
            self._pending = None
            x, y = self._points[point_index]
            if not self._spawn_point_is_safe(x, y, enemies, player, view):
                self._wave_timer = self.config.retry_delay
                return
            self._materialize(point_index, enemies)
            self._wave_remaining = max(0, self._wave_remaining - 1)
            if self._wave_remaining <= 0:
                self._wave_timer = self.config.wave_interval
            return

        if self._wave_remaining > 0:
            self._wave_timer = max(0.0, self._wave_timer - dt)
            if self._wave_timer > 0.0:
                return
            self._start_warning(enemies, player, view)
            return

        self._wave_timer = max(0.0, self._wave_timer - dt)
        if self._wave_timer > 0.0:
            return
        self._wave_remaining = min(self.config.wave_size, max_active - active_count)
        self._start_warning(enemies, player, view)

    def _start_warning(
        self,
        enemies: arcade.SpriteList,
        player: arcade.Sprite,
        view,
    ) -> None:
        candidates = [
            index
            for index, (x, y) in enumerate(self._points)
            if self._spawn_point_is_safe(x, y, enemies, player, view)
        ]
        if not candidates:
            self._wave_timer = self.config.retry_delay
            return
        # Parcours circulaire : les renforts ne reviennent pas toujours sur le
        # premier point de la carte, tout en restant deterministes pour le test.
        selected = next(
            (index for index in candidates if index >= self._cursor),
            candidates[0],
        )
        self._cursor = (selected + 1) % len(self._points)
        self._pending = _PendingSpawn(selected, self.config.warning_duration)

    def _materialize(self, point_index: int, enemies: arcade.SpriteList) -> None:
        x, y = self._points[point_index]
        # Un renfort est une nouvelle entree du directeur, donc sans nouvelle
        # ame. Les ennemis initiaux gardent leur recompense de premiere mort.
        enemy = Enemy(x, y, drops_soul=False)
        enemy.bind_world(self._platforms, hazards=self._hazards)
        enemies.append(enemy)

    def _spawn_point_is_safe(
        self,
        x: float,
        y: float,
        enemies: arcade.SpriteList,
        player: arcade.Sprite,
        view,
    ) -> bool:
        if math.dist((player.center_x, player.center_y), (x, y)) < self.config.min_player_distance:
            return False
        for enemy in enemies:
            if math.dist((enemy.center_x, enemy.center_y), (x, y)) < self.config.min_enemy_distance:
                return False
        if view is not None and self._inside_view(x, y, view, self.config.offscreen_margin):
            return False
        return True

    @staticmethod
    def _inside_view(x: float, y: float, view, margin: float) -> bool:
        return (
            view.left - margin <= x <= view.right + margin
            and view.bottom - margin <= y <= view.top + margin
        )

    def reset_after_player_death(self, enemies: arcade.SpriteList) -> None:
        """Retire les renforts et remet les ennemis initiaux a leurs graines."""
        for enemy in list(enemies):
            if id(enemy) not in self._seed_ids:
                enemy.remove_from_sprite_lists()
        for enemy, x, y in self._seed_enemies:
            enemy.respawn(x, y)
            if enemy not in enemies:
                enemies.append(enemy)
        self._pending = None
        self._wave_remaining = 0
        self._wave_timer = self.config.initial_delay
        self._last_active_count = len(enemies)

    def draw(self, *, ghost_mode: bool = False) -> None:
        """Dessine le cercle de prespawn mystique quand une vague est annoncee."""
        pending = self._pending
        if pending is None:
            return
        x, y = self._points[pending.point_index]
        duration = max(self.config.warning_duration, 0.001)
        progress = 1.0 - pending.time_left / duration
        pulse = 0.5 + 0.5 * math.sin(self._clock * 10.0)
        color = settings.COLOR_ENEMY_SPAWN_GHOST if ghost_mode else settings.COLOR_ENEMY_SPAWN
        radius = settings.ENEMY_SPAWN_MARKER_RADIUS * (0.75 + 0.25 * progress)
        alpha = int(100 + 100 * pulse)
        with glow_pass():
            draw_glow(
                x,
                y,
                radius * 3.2,
                radius * 3.2,
                color,
                int(alpha * 0.65),
                bind_blend=False,
            )
        arcade.draw_circle_outline(x, y, radius, (*color, alpha), 2)
        arcade.draw_circle_outline(
            x,
            y,
            radius * (0.35 + 0.65 * progress),
            (*color, min(255, alpha + 35)),
            1,
        )
        for arm_index in range(4):
            angle = self._clock * 1.8 + arm_index * math.pi / 2.0
            inner = radius * 0.9
            outer = radius * (1.25 + 0.20 * pulse)
            arcade.draw_line(
                x + math.cos(angle) * inner,
                y + math.sin(angle) * inner,
                x + math.cos(angle) * outer,
                y + math.sin(angle) * outer,
                (*color, alpha),
                2,
            )

    def draw_ghost_hints(self, ghost: arcade.Sprite) -> None:
        """Montre au fantome les zones connues proches de sa vision."""
        radius = max(0.0, float(getattr(ghost, "vision_radius", 0.0)))
        if radius <= 0.0:
            return
        for x, y in self._points:
            if math.dist((ghost.center_x, ghost.center_y), (x, y)) > radius:
                continue
            pulse = 0.55 + 0.25 * math.sin(self._clock * 5.0 + x * 0.02)
            size = settings.ENEMY_SPAWN_GHOST_HINT_SIZE
            draw_glow(
                x,
                y,
                size,
                size,
                settings.COLOR_ENEMY_SPAWN_GHOST,
                int(settings.ENEMY_SPAWN_GHOST_HINT_ALPHA * pulse),
            )
            arcade.draw_circle_outline(
                x,
                y,
                size * 0.35,
                (*settings.COLOR_ENEMY_SPAWN_GHOST, int(170 * pulse)),
                1,
            )
