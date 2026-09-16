"""Trainee de points fluide, derriere le fantome ou le dash."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import settings
from src.entities.batch_draw import QuadBatch


@dataclass(slots=True)
class _Mote:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    phase: float
    curl: float


class PointTrail:
    """Chapelet de points distincts qui derivent et ondulent en s'estompant."""

    def __init__(
        self,
        color: tuple[int, int, int],
        core_color: tuple[int, int, int] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.color = color
        self.core_color = core_color if core_color is not None else color
        self._rng = rng if rng is not None else random.Random()
        self._motes: list[_Mote] = []
        self._prev: tuple[float, float] | None = None
        self._carry = 0.0
        self._time = 0.0
        self._quads = QuadBatch(capacity=max(8, settings.TRAIL_MAX * 2))

    def clear(self) -> None:
        self._motes.clear()
        self._prev = None
        self._carry = 0.0

    def follow(
        self,
        x: float,
        y: float,
        change_x: float,
        change_y: float,
        delta_time: float,
        *,
        active: bool,
    ) -> None:
        """Depose des points le long du deplacement si `active`, puis les fait vivre."""
        dt = max(0.0, delta_time)
        self._time += dt
        if active:
            self._lay_points(x, y, change_x, change_y, dt)
        else:
            self._prev = None
            self._carry = 0.0
        self._advance(dt)

    def draw(self) -> None:
        wobble = settings.TRAIL_WOBBLE
        freq = settings.TRAIL_WOBBLE_SPEED
        self._quads.begin()
        for mote in self._motes:
            fade = max(0.0, min(1.0, mote.life / mote.max_life))
            age = 1.0 - fade
            ox = math.cos(mote.phase + self._time * freq) * wobble * age
            oy = math.sin(mote.phase * 1.37 + self._time * freq * 0.82) * wobble * 0.7 * age
            size = max(settings.TRAIL_SIZE_MIN, mote.size * (0.45 + 0.55 * fade))
            alpha = int(settings.TRAIL_ALPHA * fade)
            if alpha <= 0:
                continue
            px = mote.x + ox
            py = mote.y + oy
            self._quads.add(px, py, size, self.color, alpha)
            core = max(1.6, size * 0.45)
            self._quads.add(
                px, py, core, self.core_color, min(255, int(alpha * 1.15))
            )
        self._quads.flush()

    def _lay_points(
        self,
        x: float,
        y: float,
        change_x: float,
        change_y: float,
        delta_time: float,
    ) -> None:
        if self._prev is None:
            self._prev = (x - change_x, y - change_y)
        prev_x, prev_y = self._prev
        dx = x - prev_x
        dy = y - prev_y
        dist = math.hypot(dx, dy)
        self._prev = (x, y)
        if dist < 0.01:
            return
        spacing = settings.TRAIL_SPACING
        self._carry += dist
        while self._carry >= spacing:
            self._carry -= spacing
            t = 1.0 - self._carry / dist
            t = max(0.0, min(1.0, t))
            self._emit(prev_x + dx * t, prev_y + dy * t, change_x, change_y, delta_time)

    def _emit(
        self,
        x: float,
        y: float,
        change_x: float,
        change_y: float,
        delta_time: float,
    ) -> None:
        dt = max(delta_time, settings.FRAME_TIME)
        speed_x = change_x / dt
        speed_y = change_y / dt
        motes = settings.TRAIL_MOTES
        for _ in range(motes):
            jitter = settings.TRAIL_JITTER
            inherit = settings.TRAIL_INHERIT * self._rng.uniform(0.65, 1.15)
            life = settings.TRAIL_LIFE * self._rng.uniform(0.75, 1.15)
            self._motes.append(
                _Mote(
                    x=x + self._rng.uniform(-jitter, jitter),
                    y=y + self._rng.uniform(-jitter, jitter),
                    vx=speed_x * inherit + self._rng.uniform(-18.0, 18.0),
                    vy=speed_y * inherit + self._rng.uniform(-18.0, 18.0),
                    life=life,
                    max_life=max(life, 0.001),
                    size=settings.TRAIL_SIZE * self._rng.uniform(0.75, 1.2),
                    phase=self._rng.uniform(0.0, math.tau),
                    curl=self._rng.choice((-1.0, 1.0)) * settings.TRAIL_CURL,
                )
            )

    def _advance(self, delta_time: float) -> None:
        alive: list[_Mote] = []
        drag = max(0.0, 1.0 - settings.TRAIL_DRAG * delta_time)
        for mote in self._motes:
            mote.life -= delta_time
            if mote.life <= 0.0:
                continue
            mote.vx, mote.vy = (
                mote.vx * drag - mote.vy * mote.curl * delta_time,
                mote.vy * drag + mote.vx * mote.curl * delta_time,
            )
            mote.x += mote.vx * delta_time
            mote.y += mote.vy * delta_time
            alive.append(mote)
        self._motes = alive[-settings.TRAIL_MAX :]
