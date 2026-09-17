"""Vague de piques du boss : warning VFX, spawn puis despawn progressifs."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import arcade

import settings
from src.entities.glow import additive_blend, draw_glow, glow_pass
from src.ui import sprites


@dataclass(slots=True)
class _Slot:
    x: float
    y: float
    warn_at: float
    spawn_at: float
    despawn_at: float
    sprite: arcade.Sprite | None = None
    warning: bool = False
    live: bool = False
    fading: bool = False


class BossSpikeWave:
    """Piques du boss vers le joueur, precedees d'un halo d'alerte."""

    def __init__(self) -> None:
        self.sprites = arcade.SpriteList()
        self._slots: list[_Slot] = []
        self._elapsed = 0.0
        self._end_at = 0.0
        self.active = False

    def start(
        self,
        origin_x: float,
        origin_y: float,
        target_x: float,
        platforms: Sequence[arcade.SpriteList],
    ) -> None:
        self.clear()
        self.active = True
        self._elapsed = 0.0
        spacing = float(settings.BOSS_SPIKE_SIZE)
        dx = target_x - origin_x
        direction = 1.0 if dx >= 0.0 else -1.0
        distance = abs(dx) - settings.BOSS_SPIKE_START_GAP
        count = int(distance / spacing) + 1
        count = max(
            settings.BOSS_SPIKE_COUNT_MIN,
            min(settings.BOSS_SPIKE_COUNT_MAX, count),
        )
        warn = settings.BOSS_SPIKE_WARN_TIME
        stagger = settings.BOSS_SPIKE_STAGGER
        hold = settings.BOSS_SPIKE_HOLD
        fade_stagger = settings.BOSS_SPIKE_DESPAWN_STAGGER
        last_spawn = warn + (count - 1) * stagger
        for index in range(count):
            x = origin_x + direction * (settings.BOSS_SPIKE_START_GAP + index * spacing)
            y = _floor_center_y(x, origin_y, platforms)
            spawn_at = warn + index * stagger
            despawn_at = last_spawn + hold + index * fade_stagger
            self._slots.append(
                _Slot(
                    x=x,
                    y=y,
                    warn_at=index * stagger,
                    spawn_at=spawn_at,
                    despawn_at=despawn_at,
                )
            )
        last_despawn = last_spawn + hold + (count - 1) * fade_stagger
        self._end_at = last_despawn + settings.BOSS_SPIKE_FADE_TIME

    def clear(self) -> None:
        for sprite in list(self.sprites):
            sprite.remove_from_sprite_lists()
        self._slots.clear()
        self.active = False
        self._elapsed = 0.0
        self._end_at = 0.0

    @property
    def finished(self) -> bool:
        return self.active and self._elapsed >= self._end_at

    @property
    def slot_count(self) -> int:
        return len(self._slots)

    def update(self, delta_time: float = settings.FRAME_TIME) -> None:
        if not self.active:
            return
        self._elapsed += max(0.0, delta_time)
        now = self._elapsed
        fade = settings.BOSS_SPIKE_FADE_TIME
        pulse = 0.55 + 0.45 * abs((now * 7.0) % 2.0 - 1.0)
        for slot in self._slots:
            if slot.live and now >= slot.despawn_at:
                slot.live = False
                slot.fading = True
                if slot.sprite is not None:
                    slot.sprite.lethal = False
            elif not slot.live and not slot.fading and now >= slot.spawn_at:
                self._arm_slot(slot)
            elif not slot.live and not slot.fading and now >= slot.warn_at:
                self._warn_slot(slot, pulse)
            if slot.fading and slot.sprite is not None:
                progress = (now - slot.despawn_at) / max(fade, 0.001)
                if progress >= 1.0:
                    slot.sprite.remove_from_sprite_lists()
                    slot.sprite = None
                    slot.fading = False
                else:
                    slot.sprite.alpha = max(0, int(255 * (1.0 - progress)))

    def hits(self, target: arcade.Sprite) -> bool:
        return any(
            getattr(sprite, "lethal", False) and arcade.check_for_collision(target, sprite)
            for sprite in self.sprites
        )

    def draw(self) -> None:
        if not self.active:
            return
        pulse = 0.55 + 0.45 * abs((self._elapsed * 7.0) % 2.0 - 1.0)
        with additive_blend():
            with glow_pass():
                for slot in self._slots:
                    if not slot.warning or slot.live:
                        continue
                    draw_glow(
                        slot.x,
                        slot.y,
                        settings.BOSS_SPIKE_SIZE * 2.4,
                        settings.BOSS_SPIKE_SIZE * 1.6,
                        settings.COLOR_BOSS_SPIKE_WARN,
                        int(140 * pulse),
                        bind_blend=False,
                    )
                    draw_glow(
                        slot.x,
                        slot.y,
                        settings.BOSS_SPIKE_SIZE * 0.9,
                        settings.BOSS_SPIKE_SIZE * 0.9,
                        settings.COLOR_BOSS_SPIKE_WARN_CORE,
                        int(200 * pulse),
                        bind_blend=False,
                    )
        self.sprites.draw(pixelated=True)

    def _warn_slot(self, slot: _Slot, pulse: float) -> None:
        slot.warning = True
        if slot.sprite is None:
            slot.sprite = _make_spike(slot.x, slot.y, lethal=False)
            slot.sprite.color = settings.COLOR_BOSS_SPIKE_WARN
            self.sprites.append(slot.sprite)
        slot.sprite.lethal = False
        slot.sprite.alpha = int(70 + 90 * pulse)
        slot.sprite.color = settings.COLOR_BOSS_SPIKE_WARN

    def _arm_slot(self, slot: _Slot) -> None:
        slot.warning = False
        slot.live = True
        if slot.sprite is None:
            slot.sprite = _make_spike(slot.x, slot.y, lethal=True)
            self.sprites.append(slot.sprite)
        slot.sprite.lethal = True
        slot.sprite.alpha = 255
        slot.sprite.color = (255, 255, 255)


def _make_spike(center_x: float, center_y: float, *, lethal: bool) -> arcade.Sprite:
    size = settings.BOSS_SPIKE_SIZE
    texture = sprites.load_texture(settings.SPRITE_SPIKE, size=size)
    spike = arcade.Sprite(texture, center_x=center_x, center_y=center_y)
    sprites.apply_rect_hit_box(
        spike,
        settings.BOSS_SPIKE_HIT_WIDTH,
        settings.BOSS_SPIKE_HIT_HEIGHT,
        offset_y=-size * 0.12,
    )
    spike.lethal = lethal
    return spike


def _floor_center_y(
    x: float,
    origin_y: float,
    platforms: Sequence[arcade.SpriteList],
) -> float:
    """Pose la pique sur le sol le plus haut sous `origin_y`."""
    size = settings.BOSS_SPIKE_SIZE
    best_top: float | None = None
    ceiling = origin_y + size * 0.6
    for walls in platforms:
        if not walls:
            continue
        for tile in walls:
            if tile.left - 1.0 <= x <= tile.right + 1.0 and tile.top <= ceiling:
                if best_top is None or tile.top > best_top:
                    best_top = tile.top
    if best_top is None:
        return origin_y
    return best_top + size / 2.0
