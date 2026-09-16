"""Blocs qui s'effondrent sous le joueur, puis respawnent.

Solides pour le corps (on marche dessus, on tombe avec), ignorer le terrain
pendant la chute : ils traversent murs et autres blocs jusqu'a sortir de
l'ecran, puis reapparaissent a leur case d'origine.

Les delais (`delay` avant la chute, `respawn` avant le retour) sont par
instance, comme les lance-flammes, via le champ JSON `falling_blocks`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

import arcade

import settings
from src.ui import sprites


class FallingState(Enum):
    """Cycle de vie d'un bloc tombant."""

    IDLE = "idle"
    ARMED = "armed"
    FALLING = "falling"
    GONE = "gone"


def _clamp_delay(value: float) -> float:
    return max(
        settings.FALLING_BLOCK_DELAY_MIN,
        min(settings.FALLING_BLOCK_DELAY_MAX, float(value)),
    )


def _clamp_respawn(value: float) -> float:
    return max(
        settings.FALLING_BLOCK_RESPAWN_MIN,
        min(settings.FALLING_BLOCK_RESPAWN_MAX, float(value)),
    )


@dataclass(frozen=True, slots=True)
class FallingSpec:
    """Reglages d'un bloc tombant, en coordonnees de grille."""

    column: int
    row: int
    delay: float = settings.FALLING_BLOCK_DELAY
    respawn: float = settings.FALLING_BLOCK_RESPAWN

    def __post_init__(self) -> None:
        if self.column < 0 or self.row < 0:
            raise ValueError("column et row doivent etre positifs")
        object.__setattr__(self, "delay", _clamp_delay(self.delay))
        object.__setattr__(self, "respawn", _clamp_respawn(self.respawn))

    def with_delay(self, delay: float) -> FallingSpec:
        return FallingSpec(self.column, self.row, delay, self.respawn)

    def with_respawn(self, respawn: float) -> FallingSpec:
        return FallingSpec(self.column, self.row, self.delay, respawn)

    def to_json(self) -> dict:
        return {
            "x": self.column,
            "y": self.row,
            "delay": round(self.delay, 3),
            "respawn": round(self.respawn, 3),
        }


class FallingBlock(arcade.Sprite):
    """Plateforme mobile : delay, chute libre, respawn."""

    ghost_passable = False
    slippery = False

    def __init__(
        self,
        center_x: float,
        center_y: float,
        *,
        size: int = settings.TILE_SIZE,
        delay: float = settings.FALLING_BLOCK_DELAY,
        respawn: float = settings.FALLING_BLOCK_RESPAWN,
    ) -> None:
        texture = sprites.placeholder_tile(
            settings.COLOR_FALLING_BLOCK,
            size,
            accent=settings.COLOR_FALLING_BLOCK_INNER,
        )
        super().__init__(
            texture,
            scale=sprites.scale_for_size(texture, size),
            center_x=center_x,
            center_y=center_y,
        )
        sprites.apply_rect_hit_box(self, size, size)
        self.home_x = center_x
        self.home_y = center_y
        self.delay = _clamp_delay(delay)
        self.respawn = _clamp_respawn(respawn)
        self._size = size
        self.state = FallingState.IDLE
        self._timer = 0.0
        self._shake_age = 0.0
        self._fall_speed = 0.0
        self.just_respawned = False

    @property
    def is_solid(self) -> bool:
        return self.state is not FallingState.GONE

    def supports(self, sprite: arcade.Sprite, slack: float = 8.0) -> bool:
        """True si `sprite` repose (ou vient de reposer) sur le dessus du bloc."""
        overlap = min(sprite.right, self.right) - max(sprite.left, self.left)
        if overlap < 4.0:
            return False
        gap = sprite.bottom - self.top
        return -8.0 <= gap <= slack

    def arm(self) -> None:
        """Declenche le compte a rebours, si le bloc etait encore en place."""
        if self.state is not FallingState.IDLE:
            return
        self.state = FallingState.ARMED
        self._timer = self.delay
        self._shake_age = 0.0
        self.color = settings.COLOR_FALLING_BLOCK_ARMED

    def tick(self, delta_time: float) -> None:
        """Avance les timers, la gravite et la position.

        `change_y` reste a 0 : le moteur Arcade ne doit pas deplacer le bloc
        une seconde fois (il le ferait s'il etait une plateforme mobile).
        """
        dt = max(0.0, delta_time)
        self.change_x = 0.0
        self.change_y = 0.0
        if self.state is FallingState.ARMED:
            self._shake_age += dt
            self.center_x = self.home_x + (
                math.sin(self._shake_age * 42.0) * settings.FALLING_BLOCK_SHAKE
            )
            self._timer = max(0.0, self._timer - dt)
            if self._timer <= 0.0:
                self._start_fall()
            return
        if self.state is FallingState.FALLING:
            self._fall_speed -= settings.FALLING_BLOCK_GRAVITY
            if self._fall_speed < -settings.FALLING_BLOCK_MAX_SPEED:
                self._fall_speed = -settings.FALLING_BLOCK_MAX_SPEED
            self.center_y += self._fall_speed
            return
        if self.state is FallingState.GONE:
            self._timer = max(0.0, self._timer - dt)

    def _start_fall(self) -> None:
        self.state = FallingState.FALLING
        self.center_x = self.home_x
        self._fall_speed = 0.0
        self.change_x = 0.0
        self.change_y = 0.0
        self.color = settings.COLOR_FALLING_BLOCK

    def went_off_screen(self) -> bool:
        return self.state is FallingState.FALLING and self.top < -self._size

    def hide_for_respawn(self) -> None:
        """Retire le bloc du monde le temps du respawn (plus solide)."""
        self.state = FallingState.GONE
        self._timer = self.respawn
        self._fall_speed = 0.0
        self.change_x = 0.0
        self.change_y = 0.0
        self.center_x = self.home_x
        self.center_y = self.home_y
        self.remove_from_sprite_lists()

    def ready_to_respawn(self) -> bool:
        return self.state is FallingState.GONE and self._timer <= 0.0

    def respawn_now(self) -> None:
        """Revient a la case d'origine, de nouveau solide."""
        self.state = FallingState.IDLE
        self.center_x = self.home_x
        self.center_y = self.home_y
        self._fall_speed = 0.0
        self.change_x = 0.0
        self.change_y = 0.0
        self.color = settings.COLOR_FALLING_BLOCK
        self._shake_age = 0.0
        self.just_respawned = True

    def stick_rider(self, rider: arcade.Sprite) -> None:
        """Colle `rider` sur le dessus pour qu'il tombe avec le bloc."""
        if self.state is not FallingState.FALLING:
            return
        if not self.supports(rider, slack=14.0):
            return
        rider.bottom = self.top
        if rider.change_y > self._fall_speed:
            rider.change_y = self._fall_speed

    def eject_upward(self, rider: arcade.Sprite) -> None:
        """Si `rider` est dans le bloc au respawn, le pousse au-dessus."""
        if not arcade.check_for_collision(self, rider):
            return
        overlap_y = min(rider.top, self.top) - max(rider.bottom, self.bottom)
        if overlap_y <= 4.0:
            return
        rider.bottom = self.top
        guard = 0
        while arcade.check_for_collision(self, rider) and guard < self._size * 2:
            rider.center_y += 1.0
            guard += 1
        rider.change_y = 0.0


def parse_falling_specs(raw: object) -> dict[tuple[int, int], FallingSpec]:
    """Lit le champ `falling_blocks` d'une carte, ou {} s'il est absent."""
    if raw is None:
        return {}
    if not isinstance(raw, list):
        raise ValueError("falling_blocks doit etre une liste")
    specs: dict[tuple[int, int], FallingSpec] = {}
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ValueError(f"falling_blocks[{index}] doit etre un objet")
        try:
            spec = FallingSpec(
                column=_as_int(entry.get("x"), "x"),
                row=_as_int(entry.get("y"), "y"),
                delay=_as_float(
                    entry.get("delay", settings.FALLING_BLOCK_DELAY), "delay"
                ),
                respawn=_as_float(
                    entry.get("respawn", settings.FALLING_BLOCK_RESPAWN), "respawn"
                ),
            )
        except ValueError as error:
            raise ValueError(f"falling_blocks[{index}] : {error}") from error
        specs[(spec.column, spec.row)] = spec
    return specs


def dump_falling_specs(specs: dict[tuple[int, int], FallingSpec]) -> list[dict]:
    """Serialise les blocs tombants, tries par position."""
    return [specs[key].to_json() for key in sorted(specs)]


def _as_int(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} doit etre un nombre")
    return int(value)


def _as_float(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} doit etre un nombre")
    return float(value)
