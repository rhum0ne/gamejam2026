"""Musique de fond persistante, independante du cycle des vues.

Contrairement aux bruitages de `sfx.py` (tir-et-oublie, aucun handle garde),
la musique doit :
    - survivre aux changements de vue (menu -> niveau -> niveau suivant) sans
      repartir du debut a chaque `window.show_view(...)` ;
    - pouvoir ceder la place a une boucle temporaire (mode fantome) puis
      reprendre exactement ou elle s'etait arretee, pas depuis le debut ;
    - pouvoir etre coupee/reactivee piste par piste (panneau "Son" du menu),
      y compris avant meme qu'une piste ait commence a jouer.

D'ou un singleton module (meme principe que `src.systems.event_manager.
event_manager`) qui garde la main sur les `pyglet.media.Player` retournes par
`arcade.play_sound(..., loop=True)` : `sfx.play()` jette ce handle, ici on le
garde pour pouvoir `pause()` / `play()` / `delete()` / regler `.volume` dessus
plus tard.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import arcade

import settings
from src.ui import sfx

if TYPE_CHECKING:
    from pyglet.media.player import Player

# Les 4 pistes reglables depuis le panneau "Son" (kind -> (fichier, volume,
# libelle affiche)). L'ordre est celui du panneau.
_TRACKS: dict[str, tuple[str, float, str]] = {
    "main": (settings.SOUND_MAIN_THEME, settings.SOUND_VOLUME_MAIN_THEME, "Theme principal"),
    "boss": (settings.SOUND_BOSS_FIGHT, settings.SOUND_VOLUME_BOSS_FIGHT, "Combat de boss"),
    "victory": (settings.SOUND_LEVEL_WIN, settings.SOUND_VOLUME_LEVEL_WIN, "Victoire de niveau"),
    "spectral": (settings.SOUND_MODE_SPECTRAL, settings.SOUND_VOLUME_MODE_SPECTRAL, "Mode fantome"),
}

# Pour le panneau de reglages : [(kind, libelle), ...], dans l'ordre voulu.
MUTABLE_TRACKS: tuple[tuple[str, str], ...] = tuple(
    (kind, label) for kind, (_file, _volume, label) in _TRACKS.items()
)

# Etat mute par defaut au lancement du jeu : theme principal et jingle de
# victoire coupes, combat de boss et mode fantome actifs.
_DEFAULT_MUTED: dict[str, bool] = {"main": True, "boss": False, "victory": True, "spectral": False}


class MusicManager:
    """Piste de fond courante (theme principal ou combat de boss), plus un
    "overlay" (mode fantome ou jingle de victoire) qui la met en pause le
    temps de jouer par-dessus, puis la reprend exactement ou elle en etait.

    Un seul overlay a la fois : le mode fantome n'existe que dans `PlayView`,
    le jingle de victoire seulement sur `VictoryView` (un ecran different,
    affiche uniquement hors mode fantome) - ils ne peuvent donc jamais se
    chevaucher.
    """

    def __init__(self) -> None:
        self._track_kind: str | None = None
        self._track_player: Player | None = None
        self._ducked_player: Player | None = None
        self._overlay_kind: str | None = None
        self._overlay_player: Player | None = None
        self._muted: dict[str, bool] = dict(_DEFAULT_MUTED)

    # ------------------------------------------------------------------ #
    # Coupure / reactivation par piste (panneau "Son")
    # ------------------------------------------------------------------ #

    def is_muted(self, kind: str) -> bool:
        if kind not in _TRACKS:
            raise ValueError(f"piste inconnue : {kind!r}")
        return self._muted[kind]

    def set_muted(self, kind: str, muted: bool) -> None:
        """Coupe/reactive `kind`, tout de suite si elle est en train de jouer.

        Fonctionne meme si la piste n'a jamais encore ete lancee (l'etat est
        simplement applique au prochain `arcade.play_sound(...)`), et meme si
        elle est en ce moment en pause (`_ducked_player`) : le volume reste
        colle au Player, donc la reprise respecte l'etat mute/actif.
        """
        if kind not in _TRACKS:
            raise ValueError(f"piste inconnue : {kind!r}")
        if self._muted[kind] == muted:
            return
        self._muted[kind] = muted
        volume = self._volume_for(kind)
        for player, player_kind in (
            (self._track_player, self._track_kind),
            (self._ducked_player, self._track_kind),
            (self._overlay_player, self._overlay_kind),
        ):
            if player is not None and player_kind == kind:
                player.volume = volume

    def _volume_for(self, kind: str) -> float:
        _file, base_volume, _label = _TRACKS[kind]
        return 0.0 if self._muted[kind] else base_volume

    # ------------------------------------------------------------------ #
    # Piste de fond (theme principal / combat de boss)
    # ------------------------------------------------------------------ #

    def play_main_theme(self) -> None:
        """Theme principal : menu et niveaux normaux."""
        self._play_track("main")

    def play_boss_theme(self) -> None:
        """Theme du combat de boss, a la place du theme principal."""
        self._play_track("boss")

    def enter_ghost_mode(self) -> None:
        """Met la piste de fond en pause et lance la boucle du mode fantome.

        A appeler juste apres le bruitage ponctuel de projection
        (`sfx.play_ghost_start()`). No-op si un overlay est deja actif.
        """
        self._start_overlay("spectral", loop=True)

    def exit_ghost_mode(self) -> None:
        """Arrete la boucle du mode fantome et reprend la piste de fond la ou
        elle s'etait arretee (pas de redemarrage)."""
        self._stop_overlay()

    def play_victory_jingle(self) -> None:
        """Met la piste de fond en pause et joue le jingle de victoire (une
        fois). A l'appui d'un bouton de `VictoryView`, appeler
        `stop_victory_jingle()` pour le couper et reprendre la piste de fond."""
        self._start_overlay("victory", loop=False)

    def stop_victory_jingle(self) -> None:
        """Coupe le jingle de victoire (s'il joue encore) et reprend la piste
        de fond la ou elle s'etait arretee."""
        self._stop_overlay()

    def _start_overlay(self, kind: str, *, loop: bool) -> None:
        if self._overlay_player is not None:
            return
        if self._track_player is not None:
            self._track_player.pause()
        self._ducked_player = self._track_player
        self._track_player = None
        filename, _volume, _label = _TRACKS[kind]
        sound = sfx.load(filename)
        if sound is not None:
            self._overlay_kind = kind
            self._overlay_player = arcade.play_sound(sound, volume=self._volume_for(kind), loop=loop)

    def _stop_overlay(self) -> None:
        if self._overlay_player is None and self._ducked_player is None:
            return  # deja repris (ou rien n'etait en pause) : ne pas toucher _track_player
        if self._overlay_player is not None:
            self._overlay_player.delete()
            self._overlay_player = None
        self._overlay_kind = None
        self._track_player = self._ducked_player
        self._ducked_player = None
        if self._track_player is not None:
            self._track_player.play()

    def _play_track(self, kind: str) -> None:
        """(Re)lance la piste `kind` en boucle, sauf si elle joue deja."""
        if self._track_kind == kind and (self._track_player is not None or self._ducked_player is not None):
            return  # deja la bonne piste (jouee ou en pause sous un overlay)
        self._stop_track()
        self._track_kind = kind
        filename, _volume, _label = _TRACKS[kind]
        sound = sfx.load(filename)
        if sound is None:
            return
        self._track_player = arcade.play_sound(sound, volume=self._volume_for(kind), loop=True)

    def _stop_track(self) -> None:
        for player in (self._track_player, self._ducked_player):
            if player is not None:
                player.delete()
        self._track_player = None
        self._ducked_player = None


music = MusicManager()
