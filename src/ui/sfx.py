"""Chargement et lecture des bruitages.

Les fichiers vivent dans `assets/sons/`. Un fichier manquant ou illisible
devient un no-op : le jeu continue sans son plutot que de planter.
"""

from __future__ import annotations

import random
from pathlib import Path

import arcade

import settings

_CACHE: dict[str, arcade.Sound | None] = {}


def load(filename: str, *, fallback: str | Path | None = None) -> arcade.Sound | None:
    """Retourne le son, en le chargeant une seule fois."""
    if filename in _CACHE:
        return _CACHE[filename]
    candidates: list[str | Path] = []
    local = settings.SOUNDS_DIR / filename
    if local.is_file():
        candidates.append(local)
    if fallback is not None:
        candidates.append(fallback)
    sound: arcade.Sound | None = None
    for candidate in candidates:
        try:
            sound = arcade.load_sound(candidate)
            break
        except (FileNotFoundError, OSError, ValueError):
            continue
    _CACHE[filename] = sound
    return sound


def play(
    filename: str,
    volume: float = 1.0,
    *,
    fallback: str | Path | None = None,
    speed: float = 1.0,
) -> None:
    """Joue un bruitage. Ignore si le fichier n'a pas pu etre charge."""
    sound = load(filename, fallback=fallback)
    if sound is None:
        return
    arcade.play_sound(
        sound,
        volume=max(0.0, min(1.0, volume)),
        speed=max(0.1, speed),
    )


def play_attack(stage: int = 1) -> None:
    """Whoosh du coup du joueur ; le finisher est un peu plus present."""
    volume = settings.SOUND_VOLUME_ATTACK * (1.0 + 0.06 * max(0, stage - 1))
    play(
        settings.SOUND_ATTACK,
        volume,
        fallback=settings.SOUND_ATTACK_FALLBACK,
    )


def play_mob_hit() -> None:
    play(settings.SOUND_MOB_HIT, settings.SOUND_VOLUME_MOB_HIT)


def play_soul_get() -> None:
    play(settings.SOUND_SOUL_GET, settings.SOUND_VOLUME_SOUL_GET)


def play_key_found() -> None:
    play(settings.SOUND_KEY_FOUND, settings.SOUND_VOLUME_KEY_FOUND)


def play_checkpoint() -> None:
    play(settings.SOUND_CHECKPOINT, settings.SOUND_VOLUME_CHECKPOINT)


def play_level_win() -> None:
    play(settings.SOUND_LEVEL_WIN, settings.SOUND_VOLUME_LEVEL_WIN)


def play_menu_click() -> None:
    play(settings.SOUND_MENU_CLICK, settings.SOUND_VOLUME_MENU_CLICK)


def play_menu_hover() -> None:
    play(settings.SOUND_MENU_HOVER, settings.SOUND_VOLUME_MENU_HOVER)


def play_ghost_start() -> None:
    play(settings.SOUND_GHOST_START, settings.SOUND_VOLUME_GHOST_START)


def play_ghost_end() -> None:
    play(settings.SOUND_GHOST_END, settings.SOUND_VOLUME_GHOST_END)


def play_dash() -> None:
    play(settings.SOUND_DASH, settings.SOUND_VOLUME_DASH)


def play_respawn() -> None:
    play(settings.SOUND_RESPAWN, settings.SOUND_VOLUME_RESPAWN)


def play_footstep(*, land: bool = False) -> None:
    """Pas au sol, pitch legerement aleatoire pour casser la repetition."""
    volume = (
        settings.SOUND_VOLUME_FOOTSTEP_LAND if land else settings.SOUND_VOLUME_FOOTSTEP
    )
    speed = random.uniform(
        settings.SOUND_FOOTSTEP_PITCH_MIN, settings.SOUND_FOOTSTEP_PITCH_MAX
    )
    play(settings.SOUND_FOOTSTEP, volume, speed=speed)
