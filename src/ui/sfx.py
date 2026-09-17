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
    echo: bool = True,
    echo_delay: float | None = None,
    echo_decay: float | None = None,
    echo_taps: int | None = None,
) -> None:
    """Joue un bruitage. Ignore si le fichier n'a pas pu etre charge.

    `echo` ajoute des repetitions plus faibles (effet de grande salle vide).
    Les clics d'interface le desactivent pour rester nets.
    """
    sound = load(filename, fallback=fallback)
    if sound is None:
        return
    volume = max(0.0, min(1.0, volume))
    speed = max(0.1, speed)
    arcade.play_sound(sound, volume=volume, speed=speed)
    if echo:
        _queue_echo(
            sound,
            volume,
            speed,
            delay=echo_delay if echo_delay is not None else settings.SOUND_ECHO_DELAY,
            decay=echo_decay if echo_decay is not None else settings.SOUND_ECHO_DECAY,
            taps=echo_taps if echo_taps is not None else settings.SOUND_ECHO_TAPS,
        )


def _queue_echo(
    sound: arcade.Sound,
    volume: float,
    speed: float,
    *,
    delay: float,
    decay: float,
    taps: int,
) -> None:
    """Programme les copies d'echo sans re-declencher un nouvel echo."""
    if taps <= 0 or delay <= 0.0 or decay <= 0.0:
        return
    echo_speed = max(0.1, speed * settings.SOUND_ECHO_SPEED)
    for index in range(1, taps + 1):
        tap_volume = volume * (decay**index)
        if tap_volume < 0.02:
            continue
        arcade.schedule_once(
            _make_echo_callback(sound, tap_volume, echo_speed),
            delay * index,
        )


def _make_echo_callback(
    sound: arcade.Sound, volume: float, speed: float
):
    def _play(_delta_time: float) -> None:
        arcade.play_sound(sound, volume=max(0.0, min(1.0, volume)), speed=speed)

    return _play


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


def play_menu_click(*, echo: bool = False) -> None:
    play(settings.SOUND_MENU_CLICK, settings.SOUND_VOLUME_MENU_CLICK, echo=echo)


def play_menu_hover() -> None:
    play(settings.SOUND_MENU_HOVER, settings.SOUND_VOLUME_MENU_HOVER, echo=False)


def play_ghost_start() -> None:
    play(settings.SOUND_GHOST_START, settings.SOUND_VOLUME_GHOST_START)


def play_ghost_end() -> None:
    play(settings.SOUND_GHOST_END, settings.SOUND_VOLUME_GHOST_END)


def play_dash() -> None:
    play(settings.SOUND_DASH, settings.SOUND_VOLUME_DASH)


def play_jump() -> None:
    """Saut : meme sample que le dash en attendant un bruitage dedie."""
    play(settings.SOUND_JUMP, settings.SOUND_VOLUME_JUMP)


def play_boss_fire() -> None:
    play(settings.SOUND_BOSS_FIRE, settings.SOUND_VOLUME_BOSS_FIRE)


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
    play(
        settings.SOUND_FOOTSTEP,
        volume,
        speed=speed,
        echo_delay=settings.SOUND_ECHO_FOOTSTEP_DELAY,
        echo_decay=settings.SOUND_ECHO_FOOTSTEP_DECAY,
        echo_taps=settings.SOUND_ECHO_FOOTSTEP_TAPS,
    )

def play_zombie_breath()->None:
    play(settings.SOUND_ZOMBIE_BREATH, settings.SOUND_VOLUME_ZOMBIE_BREATH)
