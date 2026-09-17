"""Musique de fond persistante, independante du cycle des vues.

Contrairement aux bruitages de `sfx.py` (tir-et-oublie, aucun handle garde),
la musique doit :
    - survivre aux changements de vue (menu -> niveau -> niveau suivant) sans
      repartir du debut a chaque `window.show_view(...)` ;
    - pouvoir ceder la place a une boucle temporaire (mode fantome) puis
      reprendre exactement ou elle s'etait arretee, pas depuis le debut.

D'ou un singleton module (meme principe que `src.systems.event_manager.
event_manager`) qui garde la main sur les `pyglet.media.Player` retournes par
`arcade.play_sound(..., loop=True)` : `sfx.play()` jette ce handle, ici on le
garde pour pouvoir `pause()` / `play()` / `delete()` dessus plus tard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arcade

import settings
from src.ui import sfx

if TYPE_CHECKING:
    from pyglet.media.player import Player


class MusicManager:
    """Piste de fond courante (theme principal ou combat de boss), plus une
    boucle de "mode fantome" qui la met en pause le temps de la projection."""

    def __init__(self) -> None:
        self._track_kind: str | None = None
        self._track_player: Player | None = None
        self._ducked_player: Player | None = None
        self._spectral_player: Player | None = None

    def play_main_theme(self) -> None:
        """Theme principal : menu et niveaux normaux."""
        self._play_track("main", settings.SOUND_MAIN_THEME, settings.SOUND_VOLUME_MAIN_THEME)

    def play_boss_theme(self) -> None:
        """Theme du combat de boss, a la place du theme principal."""
        self._play_track("boss", settings.SOUND_BOSS_FIGHT, settings.SOUND_VOLUME_BOSS_FIGHT)

    def enter_ghost_mode(self) -> None:
        """Met la piste de fond en pause et lance la boucle du mode fantome.

        A appeler juste apres le bruitage ponctuel de projection
        (`sfx.play_ghost_start()`). No-op si deja en mode fantome.
        """
        if self._spectral_player is not None:
            return
        if self._track_player is not None:
            self._track_player.pause()
        self._ducked_player = self._track_player
        self._track_player = None
        sound = sfx.load(settings.SOUND_MODE_SPECTRAL)
        if sound is not None:
            self._spectral_player = arcade.play_sound(
                sound, volume=settings.SOUND_VOLUME_MODE_SPECTRAL, loop=True
            )

    def exit_ghost_mode(self) -> None:
        """Arrete la boucle du mode fantome et reprend la piste de fond la ou
        elle s'etait arretee (pas de redemarrage)."""
        if self._spectral_player is not None:
            self._spectral_player.delete()
            self._spectral_player = None
        self._track_player = self._ducked_player
        self._ducked_player = None
        if self._track_player is not None:
            self._track_player.play()

    def _play_track(self, kind: str, filename: str, volume: float) -> None:
        """(Re)lance la piste `kind` en boucle, sauf si elle joue deja."""
        if self._track_kind == kind and (self._track_player is not None or self._ducked_player is not None):
            return  # deja la bonne piste (jouee ou en pause pour le mode fantome)
        self._stop_track()
        self._track_kind = kind
        sound = sfx.load(filename)
        if sound is None:
            return
        self._track_player = arcade.play_sound(sound, volume=volume, loop=True)

    def _stop_track(self) -> None:
        for player in (self._track_player, self._ducked_player):
            if player is not None:
                player.delete()
        self._track_player = None
        self._ducked_player = None


music = MusicManager()
