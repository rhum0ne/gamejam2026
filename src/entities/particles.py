"""Poussiere de pied, eclats d'ames, poussiere d'os, sang et etincelles de laser."""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import settings
from src.entities.batch_draw import QuadBatch
from src.entities.glow import draw_glow, glow_pass


@dataclass(slots=True)
class _Grain:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    size: float
    gravity: float
    color: tuple[int, int, int]


class DustParticles:
    """Nuage de petits rectangles, sans collision ni SpriteList."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._run_timer = 0.0
        self._quads = QuadBatch(capacity=max(8, settings.PARTICLE_MAX))

    def clear(self) -> None:
        self._grains.clear()
        self._run_timer = 0.0

    def emit_landing(
        self,
        x: float,
        y: float,
        fall_speed: float,
        *,
        body_half: float = 12.0,
    ) -> None:
        """Eclabousse de poussiere sous les pieds, proportionnelle a la chute."""
        if fall_speed < settings.PARTICLE_LAND_MIN_SPEED:
            return
        span = max(0.001, settings.PARTICLE_LAND_MAX_SPEED - settings.PARTICLE_LAND_MIN_SPEED)
        impact = max(0.0, min(1.0, (fall_speed - settings.PARTICLE_LAND_MIN_SPEED) / span))
        count = settings.PARTICLE_LAND_COUNT_MIN + int(
            round((settings.PARTICLE_LAND_COUNT_MAX - settings.PARTICLE_LAND_COUNT_MIN) * impact)
        )
        for _ in range(count):
            side = self._rng.choice((-1.0, 1.0))
            speed_scale = 0.45 + 0.55 * impact
            vx = side * self._rng.uniform(0.35, 1.0) * settings.PARTICLE_LAND_SPEED_X * speed_scale
            vy = self._rng.uniform(0.25, 1.0) * settings.PARTICLE_LAND_SPEED_Y * speed_scale
            size = self._rng.uniform(
                settings.PARTICLE_LAND_SIZE_MIN,
                settings.PARTICLE_LAND_SIZE_MIN
                + (settings.PARTICLE_LAND_SIZE_MAX - settings.PARTICLE_LAND_SIZE_MIN)
                * (0.4 + 0.6 * impact),
            )
            life = settings.PARTICLE_LAND_LIFE * self._rng.uniform(0.7, 1.15)
            self._spawn(
                x + side * self._rng.uniform(body_half, body_half + 10.0),
                y + settings.PARTICLE_FOOT_CLEARANCE + self._rng.uniform(0.0, 4.0),
                vx,
                vy,
                life,
                size,
                settings.PARTICLE_LAND_GRAVITY,
            )

    def tick_run(self, x: float, y: float, facing: int, delta_time: float) -> None:
        """Emet un grain derriere le coureur, a intervalle regulier."""
        if self._run_timer <= 0.0:
            self._emit_run(x, y, facing)
            jitter = self._rng.uniform(0.75, 1.25)
            self._run_timer = settings.PARTICLE_RUN_INTERVAL * jitter
        else:
            self._run_timer -= max(0.0, delta_time)

    def stop_run(self) -> None:
        self._run_timer = 0.0

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 2.8 * dt)
            alive.append(grain)
        self._grains = alive[-settings.PARTICLE_MAX :]

    def draw(self) -> None:
        min_size = settings.PARTICLE_MIN_DRAW_SIZE
        self._quads.begin()
        for grain in self._grains:
            fade = max(0.0, min(1.0, grain.life / grain.max_life))
            size = max(min_size, grain.size * (0.55 + 0.45 * fade))
            alpha = int(230 * fade)
            if alpha <= 0:
                continue
            self._quads.add(grain.x, grain.y, size, grain.color, alpha)
        self._quads.flush()

    def _emit_run(self, x: float, y: float, facing: int) -> None:
        direction = -1.0 if facing >= 0 else 1.0
        vx = direction * self._rng.uniform(0.4, 1.0) * settings.PARTICLE_RUN_SPEED_X
        vy = self._rng.uniform(0.15, 1.0) * settings.PARTICLE_RUN_SPEED_Y
        life = settings.PARTICLE_RUN_LIFE * self._rng.uniform(0.75, 1.1)
        size = settings.PARTICLE_RUN_SIZE * self._rng.uniform(0.7, 1.15)
        self._spawn(
            x + direction * self._rng.uniform(6.0, 14.0),
            y + settings.PARTICLE_FOOT_CLEARANCE + self._rng.uniform(0.0, 3.0),
            vx,
            vy,
            life,
            size,
            settings.PARTICLE_LAND_GRAVITY * 0.55,
        )

    def _spawn(
        self,
        x: float,
        y: float,
        vx: float,
        vy: float,
        life: float,
        size: float,
        gravity: float,
    ) -> None:
        color = settings.COLOR_DUST if self._rng.random() > 0.35 else settings.COLOR_DUST_DARK
        self._grains.append(
            _Grain(
                x=x,
                y=y,
                vx=vx,
                vy=vy,
                life=life,
                max_life=max(life, 0.001),
                size=size,
                gravity=gravity,
                color=color,
            )
        )


class BloodBurst:
    """Gouttes de sang, emises au coup recu ou porte."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._quads = QuadBatch(capacity=max(8, settings.BLOOD_MAX))

    def clear(self) -> None:
        self._grains.clear()

    def emit(
        self,
        x: float,
        y: float,
        *,
        direction: float = 0.0,
        count: int | None = None,
    ) -> None:
        """Projette un jet de sang depuis `(x, y)`.

        `direction` : -1 gauche, +1 droite, 0 dans toutes les directions.
        """
        n = settings.BLOOD_COUNT if count is None else max(0, count)
        for _ in range(n):
            if direction == 0.0:
                angle = self._rng.uniform(0.0, math.tau)
            else:
                sign = 1.0 if direction > 0 else -1.0
                angle = sign * (math.pi * 0.15 + self._rng.uniform(-settings.BLOOD_CONE, settings.BLOOD_CONE))
            speed = self._rng.uniform(0.35, 1.0)
            vx = math.cos(angle) * settings.BLOOD_SPEED_X * speed
            vy = abs(math.sin(angle)) * settings.BLOOD_SPEED_Y * speed + self._rng.uniform(20.0, 70.0)
            if direction == 0.0:
                vy = math.sin(angle) * settings.BLOOD_SPEED_Y * speed
            life = settings.BLOOD_LIFE * self._rng.uniform(0.65, 1.2)
            size = self._rng.uniform(settings.BLOOD_SIZE_MIN, settings.BLOOD_SIZE_MAX)
            color = settings.COLOR_BLOOD_BRIGHT if self._rng.random() > 0.45 else settings.COLOR_BLOOD
            self._grains.append(
                _Grain(
                    x=x + self._rng.uniform(-settings.BLOOD_SPREAD, settings.BLOOD_SPREAD),
                    y=y + self._rng.uniform(-settings.BLOOD_SPREAD * 0.5, settings.BLOOD_SPREAD),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.BLOOD_GRAVITY,
                    color=color,
                )
            )
        self._grains = self._grains[-settings.BLOOD_MAX :]

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 2.2 * dt)
            alive.append(grain)
        self._grains = alive

    def draw(self) -> None:
        min_size = settings.PARTICLE_MIN_DRAW_SIZE
        self._quads.begin()
        for grain in self._grains:
            fade = max(0.0, min(1.0, grain.life / grain.max_life))
            size = max(min_size, grain.size * (0.5 + 0.5 * fade))
            alpha = int(240 * fade)
            if alpha <= 0:
                continue
            self._quads.add(grain.x, grain.y, size, grain.color, alpha)
        self._quads.flush()


class DecayBurst:
    """Nuage d'os et de poussiere, pour masquer le passage cadavre -> squelette."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._quads = QuadBatch(capacity=max(8, settings.CORPSE_DECAY_MAX))

    def clear(self) -> None:
        self._grains.clear()

    def emit(self, x: float, y: float) -> None:
        """Souffle un nuage autour du corps, assez dense pour cacher le swap."""
        for _ in range(settings.CORPSE_DECAY_COUNT):
            angle = self._rng.uniform(0.0, math.tau)
            speed = self._rng.uniform(0.2, 1.0)
            linger = self._rng.random() > 0.55
            vx = math.cos(angle) * settings.CORPSE_DECAY_SPEED * speed
            vy = math.sin(angle) * settings.CORPSE_DECAY_SPEED * speed * 0.75
            if linger:
                vx *= 0.25
                vy *= 0.2
            life = settings.CORPSE_DECAY_LIFE * self._rng.uniform(0.7, 1.2)
            size = self._rng.uniform(
                settings.CORPSE_DECAY_SIZE_MIN,
                settings.CORPSE_DECAY_SIZE_MAX,
            )
            if linger:
                size *= 1.35
                life *= 1.15
            color = (
                settings.COLOR_DUST
                if self._rng.random() > 0.4
                else settings.COLOR_DUST_DARK
            )
            self._grains.append(
                _Grain(
                    x=x + self._rng.uniform(
                        -settings.CORPSE_DECAY_SPREAD_X,
                        settings.CORPSE_DECAY_SPREAD_X,
                    ),
                    y=y + self._rng.uniform(
                        -settings.CORPSE_DECAY_SPREAD_Y,
                        settings.CORPSE_DECAY_SPREAD_Y,
                    ),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.CORPSE_DECAY_GRAVITY * (0.25 if linger else 1.0),
                    color=color,
                )
            )
        self._grains = self._grains[-settings.CORPSE_DECAY_MAX :]

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 2.4 * dt)
            alive.append(grain)
        self._grains = alive

    def draw(self) -> None:
        min_size = settings.PARTICLE_MIN_DRAW_SIZE
        self._quads.begin()
        for grain in self._grains:
            fade = max(0.0, min(1.0, grain.life / grain.max_life))
            size = max(min_size, grain.size * (0.55 + 0.45 * fade))
            alpha = int(235 * fade)
            if alpha <= 0:
                continue
            self._quads.add(grain.x, grain.y, size, grain.color, alpha)
        self._quads.flush()


class SoulBurst:
    """Eclat de motes bleues, utilise au respawn sur un checkpoint."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._quads = QuadBatch(capacity=max(8, settings.CHECKPOINT_BURST_MAX))

    def clear(self) -> None:
        self._grains.clear()

    def emit(self, x: float, y: float) -> None:
        """Propulse un nuage de motes autour de `(x, y)`."""
        spread = settings.CHECKPOINT_BURST_SPREAD
        for _ in range(settings.CHECKPOINT_BURST_COUNT):
            angle = self._rng.uniform(math.pi * 0.18, math.pi * 0.82)
            speed_x = self._rng.uniform(0.25, 1.0) * settings.CHECKPOINT_BURST_SPEED_X
            speed_y = self._rng.uniform(0.45, 1.0) * settings.CHECKPOINT_BURST_SPEED_Y
            vx = math.cos(angle) * speed_x
            vy = math.sin(angle) * speed_y
            life = settings.CHECKPOINT_BURST_LIFE * self._rng.uniform(0.65, 1.15)
            size = self._rng.uniform(
                settings.CHECKPOINT_BURST_SIZE_MIN,
                settings.CHECKPOINT_BURST_SIZE_MAX,
            )
            color = (
                settings.COLOR_CHECKPOINT_PARTICLE_CORE
                if self._rng.random() > 0.55
                else settings.COLOR_CHECKPOINT_PARTICLE
            )
            self._grains.append(
                _Grain(
                    x=x + self._rng.uniform(-spread, spread),
                    y=y + self._rng.uniform(-spread * 0.4, spread),
                    vx=vx,
                    vy=vy,
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.CHECKPOINT_BURST_GRAVITY,
                    color=color,
                )
            )
        self._grains = self._grains[-settings.CHECKPOINT_BURST_MAX :]

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 1.6 * dt)
            alive.append(grain)
        self._grains = alive

    def draw(self) -> None:
        _draw_glow_motes(
            self._grains,
            self._quads,
            glow_alpha=settings.CHECKPOINT_BURST_GLOW_ALPHA,
            core_size=settings.CHECKPOINT_BURST_CORE_SIZE,
            core_alpha=settings.CHECKPOINT_BURST_CORE_ALPHA,
            core_color=settings.COLOR_CHECKPOINT_PARTICLE_CORE,
        )


class LaserBurst:
    """Eclat de motes cyan a l'impact d'un projectile de boss."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._quads = QuadBatch(capacity=max(8, settings.BOSS_SHOT_BURST_MAX))

    def clear(self) -> None:
        self._grains.clear()

    @property
    def active(self) -> bool:
        return bool(self._grains)

    def emit(self, x: float, y: float) -> None:
        """Projette un nuage bleu autour de `(x, y)`."""
        spread = settings.BOSS_SHOT_BURST_SPREAD
        for _ in range(settings.BOSS_SHOT_BURST_COUNT):
            angle = self._rng.uniform(0.0, math.tau)
            speed = self._rng.uniform(0.35, 1.0) * settings.BOSS_SHOT_BURST_SPEED
            life = settings.BOSS_SHOT_BURST_LIFE * self._rng.uniform(0.65, 1.2)
            size = self._rng.uniform(
                settings.BOSS_SHOT_BURST_SIZE_MIN,
                settings.BOSS_SHOT_BURST_SIZE_MAX,
            )
            color = (
                settings.COLOR_BOSS_GLOW_CORE
                if self._rng.random() > 0.45
                else settings.COLOR_BOSS_GLOW
            )
            self._grains.append(
                _Grain(
                    x=x + self._rng.uniform(-spread, spread),
                    y=y + self._rng.uniform(-spread, spread),
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=life,
                    max_life=max(life, 0.001),
                    size=size,
                    gravity=settings.BOSS_SHOT_BURST_GRAVITY,
                    color=color,
                )
            )
        self._grains = self._grains[-settings.BOSS_SHOT_BURST_MAX :]

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 1.8 * dt)
            alive.append(grain)
        self._grains = alive

    def draw(self) -> None:
        _draw_glow_motes(
            self._grains,
            self._quads,
            glow_alpha=settings.BOSS_SHOT_BURST_GLOW_ALPHA,
            core_size=settings.BOSS_SHOT_BURST_CORE_SIZE,
            core_alpha=settings.BOSS_SHOT_BURST_CORE_ALPHA,
            core_color=settings.COLOR_BOSS_GLOW_CORE,
        )


class EmergenceBurst:
    """Nuage dense de motes d'ame, pour la sortie du fantome hors du corps."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._stream_timer = 0.0
        self._quads = QuadBatch(capacity=max(8, settings.DEATH_PARTICLE_MAX))

    def clear(self) -> None:
        self._grains.clear()
        self._stream_timer = 0.0

    def emit_burst(self, x: float, y: float) -> None:
        """Explosion initiale autour du corps."""
        for _ in range(settings.DEATH_PARTICLE_COUNT):
            self._spawn_mote(x, y, burst=True)

    def emit_stream(self, x: float, y: float, delta_time: float) -> None:
        """Filet continu pendant que le fantome se detache."""
        self._stream_timer -= max(0.0, delta_time)
        if self._stream_timer > 0.0:
            return
        self._stream_timer = settings.DEATH_PARTICLE_STREAM_INTERVAL
        for _ in range(settings.DEATH_PARTICLE_STREAM_COUNT):
            self._spawn_mote(x, y, burst=False)

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            grain.vy -= grain.gravity * dt
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            grain.vx *= max(0.0, 1.0 - 1.1 * dt)
            alive.append(grain)
        self._grains = alive[-settings.DEATH_PARTICLE_MAX :]

    def draw(self) -> None:
        _draw_glow_motes(
            self._grains,
            self._quads,
            glow_alpha=settings.DEATH_PARTICLE_GLOW_ALPHA,
            core_size=settings.DEATH_PARTICLE_CORE_SIZE,
            core_alpha=settings.DEATH_PARTICLE_CORE_ALPHA,
            core_color=settings.COLOR_DEATH_PARTICLE_CORE,
        )

    def _spawn_mote(self, x: float, y: float, *, burst: bool) -> None:
        if burst:
            angle = self._rng.uniform(0.0, math.tau)
            speed = self._rng.uniform(0.35, 1.0) * settings.DEATH_PARTICLE_SPEED
        else:
            angle = self._rng.uniform(math.pi * 0.15, math.pi * 0.85)
            speed = self._rng.uniform(0.25, 0.8) * settings.DEATH_PARTICLE_SPEED_UP
        vx = math.cos(angle) * speed
        vy = math.sin(angle) * speed + self._rng.uniform(20.0, 70.0)
        life = settings.DEATH_PARTICLE_LIFE * self._rng.uniform(0.55, 1.2)
        size = self._rng.uniform(
            settings.DEATH_PARTICLE_SIZE_MIN,
            settings.DEATH_PARTICLE_SIZE_MAX,
        )
        spread = settings.DEATH_PARTICLE_SPREAD
        color = (
            settings.COLOR_DEATH_PARTICLE_CORE
            if self._rng.random() > 0.45
            else settings.COLOR_DEATH_PARTICLE
        )
        self._grains.append(
            _Grain(
                x=x + self._rng.uniform(-spread, spread),
                y=y + self._rng.uniform(-spread * 0.5, spread),
                vx=vx,
                vy=vy,
                life=life,
                max_life=max(life, 0.001),
                size=size,
                gravity=settings.DEATH_PARTICLE_GRAVITY,
                color=color,
            )
        )
        self._grains = self._grains[-settings.DEATH_PARTICLE_MAX :]


class ReformBurst:
    """Motes qui convergent vers un point : le corps se reconstitue hors du noir."""

    def __init__(self, rng: random.Random | None = None) -> None:
        self._grains: list[_Grain] = []
        self._rng = rng if rng is not None else random.Random()
        self._stream_timer = 0.0
        self._home_x = 0.0
        self._home_y = 0.0
        self._quads = QuadBatch(capacity=max(8, settings.REBIRTH_PARTICLE_MAX))

    def clear(self) -> None:
        self._grains.clear()
        self._stream_timer = 0.0

    def emit_cloud(self, x: float, y: float) -> None:
        """Anneau initial, assez large pour qu'on voie le rappel vers le corps."""
        self._home_x = x
        self._home_y = y
        for _ in range(settings.REBIRTH_PARTICLE_COUNT):
            self._spawn_inward(x, y, burst=True)

    def emit_stream(self, x: float, y: float, delta_time: float) -> None:
        """Filet de motes qui continuent d'affluer pendant la reconstruction."""
        self._home_x = x
        self._home_y = y
        self._stream_timer -= max(0.0, delta_time)
        if self._stream_timer > 0.0:
            return
        self._stream_timer = settings.REBIRTH_PARTICLE_STREAM_INTERVAL
        for _ in range(settings.REBIRTH_PARTICLE_STREAM_COUNT):
            self._spawn_inward(x, y, burst=False)

    def emit_collapse(self, x: float, y: float) -> None:
        """Dernier rappel serre, au moment ou le sprite apparait."""
        self._home_x = x
        self._home_y = y
        for _ in range(settings.REBIRTH_PARTICLE_COUNT // 2):
            self._spawn_inward(x, y, burst=True, tight=True)

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        dt = max(0.0, delta_time)
        alive: list[_Grain] = []
        home_x, home_y = self._home_x, self._home_y
        for grain in self._grains:
            grain.life -= dt
            if grain.life <= 0.0:
                continue
            dx = home_x - grain.x
            dy = home_y - grain.y
            dist = math.hypot(dx, dy)
            if dist > 1.0:
                pull = settings.REBIRTH_PARTICLE_SPEED * (0.35 + 0.65 * min(1.0, dist / 90.0))
                grain.vx = grain.vx * max(0.0, 1.0 - 3.4 * dt) + dx / dist * pull
                grain.vy = grain.vy * max(0.0, 1.0 - 3.4 * dt) + dy / dist * pull
            grain.x += grain.vx * dt
            grain.y += grain.vy * dt
            if dist < 10.0:
                grain.life -= dt * 2.4
            alive.append(grain)
        self._grains = alive[-settings.REBIRTH_PARTICLE_MAX :]

    def draw(self) -> None:
        _draw_glow_motes(
            self._grains,
            self._quads,
            glow_alpha=settings.REBIRTH_PARTICLE_GLOW_ALPHA,
            core_size=settings.REBIRTH_PARTICLE_CORE_SIZE,
            core_alpha=settings.REBIRTH_PARTICLE_CORE_ALPHA,
            core_color=settings.COLOR_REBIRTH_PARTICLE_CORE,
        )

    def _spawn_inward(
        self,
        x: float,
        y: float,
        *,
        burst: bool,
        tight: bool = False,
    ) -> None:
        angle = self._rng.uniform(0.0, math.tau)
        if tight:
            radius = self._rng.uniform(
                settings.REBIRTH_PARTICLE_RADIUS_MIN * 0.45,
                settings.REBIRTH_PARTICLE_RADIUS_MIN,
            )
        elif burst:
            radius = self._rng.uniform(
                settings.REBIRTH_PARTICLE_RADIUS_MIN,
                settings.REBIRTH_PARTICLE_RADIUS,
            )
        else:
            radius = self._rng.uniform(
                settings.REBIRTH_PARTICLE_RADIUS * 0.7,
                settings.REBIRTH_PARTICLE_RADIUS * 1.15,
            )
        px = x + math.cos(angle) * radius
        py = y + math.sin(angle) * radius
        tangent = angle + math.pi * 0.5
        swirl = self._rng.uniform(18.0, 55.0)
        life = settings.REBIRTH_PARTICLE_LIFE * self._rng.uniform(0.55, 1.2)
        size = self._rng.uniform(
            settings.REBIRTH_PARTICLE_SIZE_MIN,
            settings.REBIRTH_PARTICLE_SIZE_MAX,
        )
        if self._rng.random() > 0.42:
            color = settings.COLOR_REBIRTH_PARTICLE_CORE
        elif self._rng.random() > 0.5:
            color = settings.COLOR_REBIRTH_PARTICLE
        else:
            color = settings.COLOR_DEATH_PARTICLE
        self._grains.append(
            _Grain(
                x=px,
                y=py,
                vx=math.cos(tangent) * swirl,
                vy=math.sin(tangent) * swirl,
                life=life,
                max_life=max(life, 0.001),
                size=size,
                gravity=0.0,
                color=color,
            )
        )
        self._grains = self._grains[-settings.REBIRTH_PARTICLE_MAX :]


def _draw_glow_motes(
    grains: list[_Grain],
    quads: QuadBatch,
    *,
    glow_alpha: int,
    core_size: float,
    core_alpha: int,
    core_color: tuple[int, int, int],
) -> None:
    """Halo additif en un glow_pass, noyaux carres en un QuadBatch."""
    if not grains:
        return
    with glow_pass():
        for grain in grains:
            fade = max(0.0, min(1.0, grain.life / grain.max_life))
            alpha = int(glow_alpha * fade)
            if alpha <= 0:
                continue
            draw_glow(grain.x, grain.y, grain.size, grain.size, grain.color, alpha)
    quads.begin()
    for grain in grains:
        fade = max(0.0, min(1.0, grain.life / grain.max_life))
        alpha = int(core_alpha * fade)
        if alpha <= 0:
            continue
        size = core_size * (0.45 + 0.55 * fade)
        quads.add(grain.x, grain.y, size, core_color, alpha)
    quads.flush()
