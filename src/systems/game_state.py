"""Etats de jeu et vue de jeu principale.

Deux choses vivent ici :

1. `GameState` / `GameStateMachine` : l'automate qui autorise (ou refuse) les
   transitions Menu -> Niveau -> Mort -> Mode Fantome -> Victoire.
2. `PlayView` : la vue Arcade qui fait tourner un niveau. Elle orchestre les
   entites, la camera, le HUD et applique les consequences des collisions
   detectees par `src.systems.collisions`.

La `GameSession` porte tout ce qui doit survivre au changement de vue ou de
niveau (essence d'ame, ameliorations, niveau courant, nombre de morts).

Note sur les imports : `menus.py` importe `PlayView` et `PlayView` doit pouvoir
afficher les menus. Les imports de `src.ui.menus` sont donc faits *dans* les
methodes, pour eviter un import circulaire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.ghost import Ghost
from src.entities.item import ItemKind
from src.entities.player import Player
from src.systems import collisions
from src.systems.upgrades import SoulProgression
from src.ui.hud import Hud, HudData
from src.world.camera import CameraRig
from src.world.level import Level


class GameState(Enum):
    """Etats possibles de la partie."""

    MENU = auto()
    PLAYING = auto()
    GHOST = auto()
    RESPAWNING = auto()
    VICTORY = auto()
    GAME_OVER = auto()
    UPGRADES = auto()


_TRANSITIONS: dict[GameState, frozenset[GameState]] = {
    GameState.MENU: frozenset({GameState.PLAYING}),
    GameState.PLAYING: frozenset(
        {GameState.GHOST, GameState.VICTORY, GameState.GAME_OVER, GameState.UPGRADES, GameState.MENU}
    ),
    GameState.GHOST: frozenset({GameState.RESPAWNING, GameState.GAME_OVER, GameState.MENU}),
    GameState.RESPAWNING: frozenset({GameState.PLAYING, GameState.MENU}),
    GameState.VICTORY: frozenset({GameState.PLAYING, GameState.UPGRADES, GameState.MENU}),
    GameState.GAME_OVER: frozenset({GameState.PLAYING, GameState.MENU}),
    GameState.UPGRADES: frozenset({GameState.PLAYING, GameState.MENU}),
}

STATE_LABELS: dict[GameState, str] = {
    GameState.MENU: "Menu",
    GameState.PLAYING: "Corps physique",
    GameState.GHOST: "Projection astrale",
    GameState.RESPAWNING: "Retour au corps...",
    GameState.VICTORY: "Niveau termine",
    GameState.GAME_OVER: "Game Over",
    GameState.UPGRADES: "Arbre de competences",
}


class StateTransitionError(RuntimeError):
    """Transition d'etat interdite par `_TRANSITIONS`."""


class GameStateMachine:
    """Automate des etats de jeu, avec transitions explicitement autorisees."""

    def __init__(self, initial: GameState = GameState.MENU) -> None:
        self._state = initial
        self.history: list[GameState] = [initial]

    @property
    def state(self) -> GameState:
        return self._state

    def can(self, target: GameState) -> bool:
        return target in _TRANSITIONS[self._state]

    def to(self, target: GameState) -> None:
        """Change d'etat, ou leve `StateTransitionError` si c'est interdit."""
        if not isinstance(target, GameState):
            raise TypeError("target doit etre un GameState")
        if not self.can(target):
            raise StateTransitionError(f"transition interdite : {self._state.name} -> {target.name}")
        self._state = target
        self.history.append(target)

    def try_to(self, target: GameState) -> bool:
        """Variante tolerante de `to` : retourne False au lieu de lever."""
        if not self.can(target):
            return False
        self.to(target)
        return True


@dataclass(slots=True)
class GameSession:
    """Donnees de partie partagees entre toutes les vues."""

    progression: SoulProgression = field(default_factory=SoulProgression)
    level_index: int = 0
    deaths: int = 0

    @property
    def level_file(self) -> str:
        return settings.LEVEL_SEQUENCE[self.level_index]

    @property
    def is_last_level(self) -> bool:
        return self.level_index >= len(settings.LEVEL_SEQUENCE) - 1

    def advance_level(self) -> bool:
        """Passe au niveau suivant. Retourne False si l'aventure est terminee."""
        if self.is_last_level:
            return False
        self.level_index += 1
        return True

    def restart(self) -> None:
        """Remet la session a zero (nouvelle partie depuis le menu titre)."""
        self.progression = SoulProgression()
        self.level_index = 0
        self.deaths = 0


# --------------------------------------------------------------------------- #
# Touches
# --------------------------------------------------------------------------- #

_LEFT_KEYS = frozenset({arcade.key.LEFT, arcade.key.A, arcade.key.Q})
_RIGHT_KEYS = frozenset({arcade.key.RIGHT, arcade.key.D})
_UP_KEYS = frozenset({arcade.key.UP, arcade.key.W, arcade.key.Z})
_DOWN_KEYS = frozenset({arcade.key.DOWN, arcade.key.S})
_JUMP_KEYS = frozenset({arcade.key.SPACE}) | _UP_KEYS
_PROJECT_KEY = arcade.key.F
_RETURN_KEY = arcade.key.R
_UPGRADE_KEY = arcade.key.TAB


class PlayView(arcade.View):
    """Vue d'un niveau : joue la boucle corps physique / fantome / cadavre."""

    def __init__(self, session: GameSession | None = None) -> None:
        super().__init__()
        self.background_color = settings.COLOR_BACKGROUND
        self.session = session if session is not None else GameSession()
        self.machine = GameStateMachine(GameState.MENU)
        self.camera = CameraRig()
        self.hud = Hud(self.window.width, self.window.height)
        self.level: Level
        self.player: Player
        self.ghost: Ghost | None = None
        self.anchor_corpse: Corpse | None = None
        self.held_keys: set[int] = set()
        self._respawn_timer = 0.0
        self._delivered_items: list[ItemKind] = []
        self.setup()

    # ------------------------------------------------------------------ #
    # Mise en place
    # ------------------------------------------------------------------ #

    def setup(self) -> None:
        """(Re)charge le niveau courant de la session et remet les entites a zero."""
        self.level = Level.from_file(self.session.level_file)
        self.player = Player(*self.level.player_spawn)
        self.player.respawn_point = self.level.checkpoint_spawn
        self.player.bind_world(self.level.solid_platforms)
        for enemy in self.level.enemies:
            enemy.bind_world(self._static_platforms())
        self.camera.set_bounds(self.level.width, self.level.height)
        self._enemy_spawns = [(enemy, enemy.center_x, enemy.center_y) for enemy in self.level.enemies]
        self.camera.snap_to(self.player)
        self.ghost = None
        self.anchor_corpse = None
        self.held_keys.clear()
        self._respawn_timer = 0.0
        self._delivered_items.clear()
        self.machine = GameStateMachine(GameState.MENU)
        self.machine.to(GameState.PLAYING)

    def _static_platforms(self) -> list[arcade.SpriteList]:
        """Plateformes solides hors cadavres (un cadavre ne doit pas se bloquer lui-meme)."""
        return [self.level.walls, self.level.spectral_walls]

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def on_draw(self) -> None:
        self.clear()
        self.camera.use_world()
        self.level.draw()
        if self.player.alive:
            arcade.draw_sprite(self.player)
        if self.machine.state is GameState.GHOST and self.ghost is not None:
            self._draw_ghost_layer(self.ghost)
        self.camera.use_ui()
        self.hud.draw(self._hud_data())

    def _draw_ghost_layer(self, ghost: Ghost) -> None:
        """Voile d'obscurite, elements reveles, longe et fantome.

        TODO(rendu) : remplacer le voile par un masque en shader pour obtenir un
        vrai cone de vision aux bords adoucis.
        """
        camera_x, camera_y = self.camera.world.position
        half_width = self.camera.world.viewport_width / 2
        half_height = self.camera.world.viewport_height / 2
        arcade.draw_lrbt_rectangle_filled(
            camera_x - half_width,
            camera_x + half_width,
            camera_y - half_height,
            camera_y + half_height,
            (0, 0, 0, settings.FOG_ALPHA),
        )
        for wall in self.level.spectral_walls:
            wall.set_revealed(ghost.reveals(wall))
            if wall.revealed:
                arcade.draw_sprite(wall)
        for sprite_list in (self.level.items, self.level.enemies):
            for sprite in sprite_list:
                if ghost.reveals(sprite):
                    arcade.draw_sprite(sprite)
        arcade.draw_line(*ghost.anchor, ghost.center_x, ghost.center_y, settings.COLOR_GHOST, 1)
        arcade.draw_circle_outline(
            ghost.center_x, ghost.center_y, ghost.vision_radius, settings.COLOR_GHOST, 1
        )
        arcade.draw_sprite(ghost)

    def _hud_data(self) -> HudData:
        state = self.machine.state
        return HudData(
            level_name=self.level.name,
            state_label=STATE_LABELS[state],
            essence=self.session.progression.essence,
            ghost_level=self.session.progression.level,
            hint=self.level.hint if state is GameState.PLAYING else "",
            has_key=self.player.has_item(ItemKind.KEY),
            corpse_count=len(self.level.corpses),
            ghost_time_left=self.ghost.time_left if self.ghost is not None else None,
            ghost_duration=self.ghost.stats.duration if self.ghost is not None else settings.GHOST_DURATION,
            leash_ratio=self.ghost.leash_ratio if self.ghost is not None else 0.0,
        )

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def on_update(self, delta_time: float) -> None:
        self.level.update(delta_time)
        state = self.machine.state
        if state is GameState.PLAYING:
            self._update_playing(delta_time)
        elif state is GameState.GHOST:
            self._update_ghost(delta_time)
        elif state is GameState.RESPAWNING:
            self._update_respawning(delta_time)

    def _update_playing(self, delta_time: float) -> None:
        self.player.walk(self._horizontal_input())
        self.player.update(delta_time)
        self._update_enemies(delta_time)
        self._resolve_player_collisions()
        if self.machine.state is GameState.PLAYING:
            self.camera.follow(self.player, delta_time)

    def _update_ghost(self, delta_time: float) -> None:
        ghost = self.ghost
        if ghost is None:
            return
        ghost.steer(self._horizontal_input(), self._vertical_input())
        if self.anchor_corpse is not None and self.anchor_corpse.time_left > 0:
            ghost.anchor = (self.anchor_corpse.center_x, self.anchor_corpse.center_y)
        ghost.update(delta_time)
        self._update_enemies(delta_time)
        self._resolve_ghost_collisions(ghost)
        self.camera.follow(ghost, delta_time)
        if ghost.expired:
            self._start_respawn()

    def _update_respawning(self, delta_time: float) -> None:
        self._respawn_timer -= delta_time
        if self._respawn_timer > 0:
            return
        self.player.respawn_at(self.player.respawn_point)
        for kind in self._delivered_items:
            self.player.give_item(kind)
        self._delivered_items.clear()
        self._update_respawn_enemies()
        self.camera.snap_to(self.player)
        self.machine.try_to(GameState.PLAYING)

    def _update_enemies(self, delta_time: float) -> None:
        for enemy in list(self.level.enemies):
            enemy.update(delta_time, player=self.player, corpses=self.level.corpses)

    def _update_respawn_enemies(self) -> None:
        for enemy, spawn_x, spawn_y in self._enemy_spawns:
            enemy.respawn(spawn_x, spawn_y)
            if enemy not in self.level.enemies:
                self.level.enemies.append(enemy)
            

    # ------------------------------------------------------------------ #
    # Consequences des collisions
    # ------------------------------------------------------------------ #

    def _resolve_player_collisions(self) -> None:
        stomped = collisions.enemy_stomped_by_player(self.player, self.level.enemies)
        if stomped is not None:
            orb = stomped.take_damage()
            if orb is not None:
                self.level.spawn_item(orb)
            self.player.change_y = settings.PLAYER_JUMP_SPEED * 0.6

        for item in collisions.items_reachable_by_body(self.player, self.level):
            self._collect(item.kind)
            item.remove_from_sprite_lists()

        door = collisions.door_touched_by_player(self.player, self.level)
        if door is not None and self.player.has_item(ItemKind.KEY):
            door.unlock()
            self._complete_level()
            return

        lethal = (
            collisions.player_hits_hazard(self.player, self.level)
            or collisions.player_out_of_bounds(self.player, self.level)
            or collisions.enemy_touching_player(self.player, self.level.enemies) is not None
        )
        if lethal:
            self._enter_ghost_mode()

    def _resolve_ghost_collisions(self, ghost: Ghost) -> None:
        for item in collisions.items_reachable_by_ghost(ghost, self.level):
            ghost.pick_up(item)

        if not ghost.carried:
            return
        corpse = collisions.corpse_touched_by_ghost(ghost, self.level.corpses)
        if corpse is None:
            return
        for item in ghost.release_all():
            self._collect(item.kind)
            item.remove_from_sprite_lists()

    def _collect(self, kind: ItemKind) -> None:
        """Applique l'effet du ramassage d'un objet.

        Les objets ramasses pendant le mode fantome sont mis de cote et remis au
        corps physique a la reapparition.
        """
        if kind is ItemKind.SOUL_ORB:
            self.session.progression.absorb_orb()
            return
        if self.machine.state is GameState.GHOST:
            self._delivered_items.append(kind)
        else:
            self.player.give_item(kind)

    # ------------------------------------------------------------------ #
    # Transitions
    # ------------------------------------------------------------------ #

    def _enter_ghost_mode(self) -> None:
        """Mort du corps : depot d'un cadavre et projection de l'esprit."""
        if not self.machine.can(GameState.GHOST):
            return
        self.session.deaths += 1
        self.player.die()
        corpse = Corpse(self.player.center_x, self.player.center_y)
        corpse.bind_world(self._static_platforms())
        self.level.spawn_corpse(corpse)
        self.anchor_corpse = corpse
        stats = self.session.progression.ghost_stats
        self.ghost = Ghost(corpse.center_x, corpse.center_y, stats, anchor=corpse.position)
        self.ghost.bind_world(self.level.walls)
        self.machine.to(GameState.GHOST)

    def _start_respawn(self) -> None:
        """Fin du mode fantome : le corps revient au dernier checkpoint."""
        if self.ghost is not None:
            for item in self.ghost.release_all():
                item.drop_at(item.center_x, item.center_y)
        self.ghost = None
        for wall in self.level.spectral_walls:
            wall.set_revealed(False)
        self._respawn_timer = settings.PLAYER_RESPAWN_DELAY
        self.machine.try_to(GameState.RESPAWNING)

    def _complete_level(self) -> None:
        """Niveau reussi : niveau suivant, ou ecran de victoire finale."""
        from src.ui.menus import VictoryView

        self.machine.try_to(GameState.VICTORY)
        if self.session.advance_level():
            self.setup()
            return
        self.window.show_view(VictoryView(self.session))

    # ------------------------------------------------------------------ #
    # Entrees clavier
    # ------------------------------------------------------------------ #

    def _horizontal_input(self) -> int:
        direction = 0
        if self.held_keys & _LEFT_KEYS:
            direction -= 1
        if self.held_keys & _RIGHT_KEYS:
            direction += 1
        return direction

    def _vertical_input(self) -> int:
        direction = 0
        if self.held_keys & _DOWN_KEYS:
            direction -= 1
        if self.held_keys & _UP_KEYS:
            direction += 1
        return direction

    def on_key_press(self, symbol: int, modifiers: int) -> None:
        from src.ui.menus import TitleView, UpgradeTreeView

        self.held_keys.add(symbol)
        state = self.machine.state
        if symbol == arcade.key.ESCAPE:
            self.window.show_view(TitleView(self.session))
            return
        if symbol == _UPGRADE_KEY:
            self.window.show_view(UpgradeTreeView(self.session, back_view=self))
            return
        if state is GameState.PLAYING:
            if symbol in _JUMP_KEYS:
                self.player.jump()
            elif symbol == _PROJECT_KEY:
                self._enter_ghost_mode()
        elif state is GameState.GHOST and symbol == _RETURN_KEY:
            self._start_respawn()

    def on_key_release(self, symbol: int, modifiers: int) -> None:
        self.held_keys.discard(symbol)
        if symbol in _JUMP_KEYS and self.machine.state is GameState.PLAYING:
            self.player.cut_jump()

    def on_resize(self, width: int, height: int) -> None:
        super().on_resize(width, height)
        self.camera.on_resize(width, height)
        self.hud.resize(width, height)
