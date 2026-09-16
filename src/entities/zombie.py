"""Zombie : traqueur au sol, lent tant qu'il n'a pas vu le joueur.

Priorites de comportement, de la plus forte a la plus faible :
    0. etats engages (DYING, HURT, ALERT, ATTACK) : vont au bout de leur
       animation avant toute autre decision ;
    1. FEAST  : un cadavre est a portee d'odorat -> il y court et le devore
                (plus gourmand que le squelette : `ZOMBIE_CORPSE_SMELL_RANGE`) ;
    2. CHASE  : le joueur est VU (`_can_see` : cone avant + ligne de vue, les
                murs bloquent) -> course. Depuis PATROL/FEAST, un cri d'alerte
                (ALERT) precede toujours la course : c'est l'avertissement
                laisse au joueur. A portee, griffe bondissante (ATTACK) ;
                ... ou le joueur a ete perdu de vue depuis moins de
                `ZOMBIE_MEMORY_TIME` -> course vers le dernier point vu ;
    3. SEARCH : memoire epuisee (ou point atteint) -> regarde a gauche et a
                droite pendant `ZOMBIE_SEARCH_TIME`, puis reprend la patrouille ;
    4. PATROL : va-et-vient lent, demi-tour devant un mur ou au bord.

Ce qui le distingue du squelette (`Enemy`) :
    * il ne voit que devant lui (dans son dos, seulement au contact) et pas a
      travers les murs : on peut le contourner ;
    * 2 PV : le premier coup le sonne (HURT, interrompt son attaque) puis il
      fonce sur le joueur meme sans le voir ;
    * en course, il met `ZOMBIE_TURN_TIME` a faire demi-tour (sauter par-dessus
      lui fait gagner du temps) ;
    * en course, il se laisse tomber d'une plateforme si sa cible est plus bas
      et qu'un sol existe a au plus `ZOMBIE_MAX_DROP_TILES` tuiles (`_may_drop`).
      En patrouille, il reste prudent et fait demi-tour au bord.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum, auto

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.enemy_base import EnemyBase
from src.entities.player import Player
from src.ui import sprites


class ZombieState(Enum):
    """Etats de l'IA."""

    PATROL = auto()
    ALERT = auto()
    CHASE = auto()
    ATTACK = auto()
    SEARCH = auto()
    FEAST = auto()
    HURT = auto()
    DYING = auto()


# Etats ou le zombie sait deja que le joueur est la : le revoir relance la
# course directement, sans nouveau cri d'alerte.
_AWARE_STATES = frozenset({ZombieState.CHASE, ZombieState.SEARCH})


def _strip(path) -> tuple[arcade.Texture, ...]:
    return sprites.load_strip(
        path, settings.ZOMBIE_FRAME_SIZE, settings.ZOMBIE_FRAME_SIZE, scale=settings.ZOMBIE_SCALE
    )


class Zombie(EnemyBase):
    """Ennemi terrestre qui traque le joueur une fois qu'il l'a vu."""

    def __init__(self, center_x: float, center_y: float) -> None:
        walk = _strip(settings.ZOMBIE_SPRITE_WALK)
        attack = _strip(settings.ZOMBIE_SPRITE_ATTACK)
        hurt = _strip(settings.ZOMBIE_SPRITE_HURT)
        self._idle = sprites.StripAnimation(
            _strip(settings.ZOMBIE_SPRITE_IDLE), settings.ANIM_ZOMBIE_IDLE_FRAME_TIME, loop=True
        )
        self._walk = sprites.StripAnimation(walk, settings.ANIM_ZOMBIE_WALK_FRAME_TIME, loop=True)
        self._run = sprites.StripAnimation(walk, settings.ANIM_ZOMBIE_RUN_FRAME_TIME, loop=True)
        # Hurt sans sa frame 0 (silhouette blanche) : bouche ouverte, bras
        # ecartes, ca se lit comme un cri.
        self._alert = sprites.StripAnimation(hurt[1:], settings.ANIM_ZOMBIE_ALERT_FRAME_TIME, loop=False)
        self._attack = sprites.StripAnimation(attack, settings.ANIM_ZOMBIE_ATTACK_FRAME_TIME, loop=False)
        # Attack1 frames 3-4 (penche en avant) en boucle : mastication.
        self._eat = sprites.StripAnimation(attack[3:5], settings.ANIM_ZOMBIE_EAT_FRAME_TIME, loop=True)
        self._hurt = sprites.StripAnimation(hurt, settings.ANIM_ZOMBIE_HURT_FRAME_TIME, loop=False)
        self._die = sprites.StripAnimation(
            _strip(settings.ZOMBIE_SPRITE_DIE), settings.ANIM_ZOMBIE_DIE_FRAME_TIME, loop=False
        )
        super().__init__(
            self._idle.textures[0],
            center_x=center_x,
            center_y=center_y,
            hit_points=settings.ZOMBIE_HIT_POINTS,
            body_width=settings.ZOMBIE_WIDTH,
            body_height=settings.ZOMBIE_HEIGHT,
        )
        sprites.apply_rect_hit_box(
            self,
            settings.ZOMBIE_WIDTH,
            settings.ZOMBIE_HEIGHT,
            offset_x=settings.ZOMBIE_HITBOX_OFFSET_X,
            offset_y=settings.ZOMBIE_HITBOX_OFFSET_Y,
        )
        self._animator = sprites.Animator(self._idle)
        self.state = ZombieState.PATROL
        self.facing = -1
        self._apply_facing()
        self.attack_reach = settings.ZOMBIE_ATTACK_REACH
        self.attack_vertical_range = settings.ZOMBIE_ATTACK_VERTICAL_RANGE
        self._attack_cooldown = 0.0
        self._lunge_speed = 0.0
        self._turn_timer = 0.0
        self._last_seen: tuple[float, float] | None = None
        self._memory_timer = 0.0
        self._search_timer = 0.0
        self._look_timer = 0.0
        # Le test de ligne de vue est le plus couteux : son resultat est garde
        # `ZOMBIE_SIGHT_CHECK_INTERVAL` secondes (voir `_line_of_sight`).
        self._sight_timer = 0.0
        self._sight_clear = True
        # Recalcule une fois par frame dans `update` (`can_jump` lance une collision).
        self._grounded = True
        self._eating = False
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._platforms: list[arcade.SpriteList] = []
        self._configure_glow(
            scale=settings.ZOMBIE_GHOST_GLOW_SCALE,
            alpha=settings.ZOMBIE_GHOST_GLOW_ALPHA,
            inner_scale=settings.ZOMBIE_GHOST_GLOW_INNER_SCALE,
            inner_alpha=settings.ZOMBIE_GHOST_GLOW_INNER_ALPHA,
            pulse=settings.ZOMBIE_GHOST_GLOW_PULSE,
            pulse_speed=settings.ZOMBIE_GHOST_GLOW_PULSE_SPEED,
            color=settings.COLOR_ZOMBIE_GLOW,
            color_core=settings.COLOR_ZOMBIE_GLOW_CORE,
        )

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(
        self,
        platforms: Sequence[arcade.SpriteList],
        hazards: arcade.SpriteList | None = None,
    ) -> None:
        """Branche la physique sur les plateformes ; elles bloquent aussi la vue."""
        del hazards  # meme signature que `Enemy.bind_world` (le zombie contourne les piques autrement)
        self._platforms = list(platforms)
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=self._platforms,
            gravity_constant=settings.GRAVITY,
        )

    # ------------------------------------------------------------------ #
    # Attaque
    # ------------------------------------------------------------------ #

    @property
    def strike_active(self) -> bool:
        """Vrai pendant les frames ou la griffe est lancee (le coup peut tuer)."""
        if self.state is not ZombieState.ATTACK or self._animator.animation is not self._attack:
            return False
        first, last = settings.ZOMBIE_ATTACK_HIT_FRAMES
        return first <= self._animator.frame_index <= last

    def _start_attack(self) -> None:
        self.state = ZombieState.ATTACK
        # Le bond reprend l'elan de course s'il est plus fort : un zombie lance
        # a pleine vitesse glisse plus loin qu'un zombie a l'arret.
        self._lunge_speed = max(abs(self.change_x), settings.ZOMBIE_ATTACK_LUNGE_SPEED)
        self._animator.play(self._attack, restart=True)

    def _advance_lunge(self, delta_time: float) -> None:
        """Elan pendant l'armement et la griffe, jamais dans le vide ni dans un mur."""
        if (
            self._animator.frame_index > settings.ZOMBIE_ATTACK_LUNGE_LAST_FRAME
            or self._blocked_ahead()
            or not self._floor_ahead()
        ):
            self.change_x = 0.0
            return
        self.change_x = self.facing * self._lunge_speed
        self._lunge_speed *= math.exp(-delta_time / max(settings.ZOMBIE_ATTACK_LUNGE_DECAY, 0.001))

    def _end_attack(self) -> None:
        self.state = ZombieState.CHASE
        self._attack_cooldown = settings.ZOMBIE_ATTACK_COOLDOWN
        self._lunge_speed = 0.0
        self.change_x = 0.0

    # ------------------------------------------------------------------ #
    # Degats et mort
    # ------------------------------------------------------------------ #

    def _on_hurt(self) -> None:
        """Premier coup : sonne (interrompt l'attaque en cours), puis enrage."""
        self.state = ZombieState.HURT
        self.change_x = 0.0
        self._lunge_speed = 0.0
        self._animator.play(self._hurt, restart=True)

    def _recover_from_hurt(self, player: Player | None) -> None:
        """Fin de HURT : il sait ou est le joueur, meme hors de son champ de vision."""
        self.state = ZombieState.CHASE
        self._turn_timer = 0.0
        if player is not None and player.alive:
            self._remember(player)
            self.facing = 1 if player.center_x >= self.center_x else -1

    def _on_death(self) -> None:
        """Le retrait de la SpriteList est fait par `update`, une fois `Dead` jouee."""
        self.state = ZombieState.DYING
        self.change_x = 0.0

    def _on_respawn(self) -> None:
        self.state = ZombieState.PATROL
        self.facing = -1
        self._attack_cooldown = 0.0
        self._lunge_speed = 0.0
        self._turn_timer = 0.0
        self._last_seen = None
        self._memory_timer = 0.0
        self._search_timer = 0.0
        self._look_timer = 0.0
        self._sight_timer = 0.0
        self._sight_clear = True
        self._animator.play(self._idle)
        self.texture = self._animator.animation.textures[0]
        self._apply_facing()

    # ------------------------------------------------------------------ #
    # Boucle de jeu
    # ------------------------------------------------------------------ #

    def update(
        self,
        delta_time: float = settings.FRAME_TIME,
        *args,
        player: Player | None = None,
        corpses: arcade.SpriteList | None = None,
        **kwargs,
    ) -> None:
        delta_time = max(0.0, delta_time)
        self._tick_hit_feedback(delta_time)
        self._attack_cooldown = max(0.0, self._attack_cooldown - delta_time)
        self._sight_timer = max(0.0, self._sight_timer - delta_time)
        self._grounded = self._physics is None or self._physics.can_jump()
        self._update_ai(delta_time, player, corpses)
        self._advance_animation(delta_time)
        self._glow_time += delta_time
        if self._physics is not None:
            self._physics.update()
        if self.state is ZombieState.DYING and self._animator.finished:
            self.remove_from_sprite_lists()

    def _update_ai(
        self,
        delta_time: float,
        player: Player | None,
        corpses: arcade.SpriteList | None,
    ) -> None:
        self._eating = False
        if self.state is ZombieState.DYING:
            return
        if self.state is ZombieState.HURT:
            self.change_x = 0.0
            if self._animator.finished:
                self._recover_from_hurt(player)
            return
        if self.state is ZombieState.ALERT:
            self.change_x = 0.0
            if not self._animator.finished:
                return
            self.state = ZombieState.CHASE
        if self.state is ZombieState.ATTACK:
            # Coup engage : pas de demi-tour ni de changement de cible avant la
            # fin de l'animation, ce qui laisse le joueur esquiver.
            self._advance_lunge(delta_time)
            if not self._animator.finished:
                return
            self._end_attack()

        corpse = self._closest_corpse(corpses)
        if corpse is not None:
            self._feast(delta_time, corpse)
            return
        if player is not None and self._can_see(player):
            self._remember(player)
            if self.state in _AWARE_STATES:
                self._chase(delta_time, player)
            else:
                self._start_alert(player)
            return
        if self._memory_timer > 0.0 and self._last_seen is not None:
            self._memory_timer = max(0.0, self._memory_timer - delta_time)
            self._pursue_last_seen(delta_time)
            return
        if self.state in _AWARE_STATES:
            self._search(delta_time)
            return
        self._patrol(delta_time)

    # ------------------------------------------------------------------ #
    # Comportements
    # ------------------------------------------------------------------ #

    def _closest_corpse(self, corpses: arcade.SpriteList | None) -> Corpse | None:
        if not corpses:
            return None
        in_range = [
            corpse
            for corpse in corpses
            if arcade.get_distance_between_sprites(self, corpse) <= settings.ZOMBIE_CORPSE_SMELL_RANGE
            and not corpse.is_remnant
        ]
        if not in_range:
            return None
        return min(in_range, key=lambda corpse: arcade.get_distance_between_sprites(self, corpse))

    def _feast(self, delta_time: float, corpse: Corpse) -> None:
        self.state = ZombieState.FEAST
        if arcade.check_for_collision(self, corpse):
            self.change_x = 0.0
            self._eating = True
            corpse.eaters += 1
            corpse.feed(delta_time)
            return
        self._run_towards(delta_time, corpse.center_x, corpse.center_y, settings.ZOMBIE_RUN_SPEED)

    def _start_alert(self, player: Player) -> None:
        self.state = ZombieState.ALERT
        self.facing = 1 if player.center_x >= self.center_x else -1
        self.change_x = 0.0
        self._turn_timer = 0.0
        self._animator.play(self._alert, restart=True)

    def _chase(self, delta_time: float, player: Player) -> None:
        self.state = ZombieState.CHASE
        dx = player.center_x - self.center_x
        facing_player = dx * self.facing >= 0 or abs(dx) <= settings.ZOMBIE_WIDTH / 2
        if self._in_melee_range(player) and facing_player and self._grounded:
            if self._attack_cooldown <= 0.0:
                self._start_attack()
            else:
                # Recharge : reste face au joueur sans le pousser.
                self._steer(0.0, delta_time)
            return
        self._run_towards(delta_time, player.center_x, player.center_y, settings.ZOMBIE_RUN_SPEED)

    def _pursue_last_seen(self, delta_time: float) -> None:
        self.state = ZombieState.CHASE
        target_x, target_y = self._last_seen
        if abs(target_x - self.center_x) <= settings.ZOMBIE_ARRIVE_DISTANCE and self._grounded:
            self._memory_timer = 0.0
            self._start_search()
            return
        self._run_towards(delta_time, target_x, target_y, settings.ZOMBIE_RUN_SPEED)

    def _start_search(self) -> None:
        self.state = ZombieState.SEARCH
        self._search_timer = settings.ZOMBIE_SEARCH_TIME
        self._look_timer = settings.ZOMBIE_SEARCH_LOOK_TIME
        self._turn_timer = 0.0

    def _search(self, delta_time: float) -> None:
        if self.state is not ZombieState.SEARCH:
            self._start_search()
        self._search_timer -= delta_time
        if self._search_timer <= 0.0:
            self._last_seen = None
            self._patrol(delta_time)
            return
        self._look_timer -= delta_time
        if self._look_timer <= 0.0:
            # Changer de regard change aussi le cone de vision (`_can_see`).
            self.facing = -self.facing
            self._look_timer = settings.ZOMBIE_SEARCH_LOOK_TIME
        self._steer(0.0, delta_time)

    def _patrol(self, delta_time: float) -> None:
        self.state = ZombieState.PATROL
        self._turn_timer = 0.0
        if self._grounded and (self._blocked_ahead() or not self._floor_ahead()):
            self.facing = -self.facing
            self.change_x = 0.0
        self._steer(self.facing * settings.ZOMBIE_PATROL_SPEED, delta_time)

    def _remember(self, player: Player) -> None:
        self._last_seen = (player.center_x, player.center_y)
        self._memory_timer = settings.ZOMBIE_MEMORY_TIME

    def _in_melee_range(self, player: Player) -> bool:
        dx = abs(player.center_x - self.center_x)
        dy = abs(player.center_y - self.center_y)
        return dx <= settings.ZOMBIE_ATTACK_RANGE and dy <= settings.ZOMBIE_ATTACK_VERTICAL_RANGE

    # ------------------------------------------------------------------ #
    # Vision
    # ------------------------------------------------------------------ #

    def _can_see(self, player: Player) -> bool:
        """Joueur vivant, dans le cone avant (ou colle dans le dos), sans mur entre eux."""
        if not player.alive:
            return False
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        if dy > settings.ZOMBIE_SIGHT_UP_RANGE or dy < -settings.ZOMBIE_SIGHT_DOWN_RANGE:
            return False
        distance = math.hypot(dx, dy)
        if distance > settings.ZOMBIE_SIGHT_RANGE:
            return False
        if dx * self.facing < 0 and distance > settings.ZOMBIE_BACK_SENSE_RANGE:
            return False
        return self._line_of_sight(player)

    def _line_of_sight(self, player: Player) -> bool:
        if not self._platforms:
            return True
        if self._sight_timer > 0.0:
            return self._sight_clear
        self._sight_timer = settings.ZOMBIE_SIGHT_CHECK_INTERVAL
        eye = (self.center_x, self.center_y + settings.ZOMBIE_EYE_OFFSET_Y)
        self._sight_clear = all(
            arcade.has_line_of_sight(
                eye,
                player.position,
                walls,
                check_resolution=settings.ZOMBIE_SIGHT_CHECK_RESOLUTION,
            )
            for walls in self._platforms
        )
        return self._sight_clear

    # ------------------------------------------------------------------ #
    # Deplacement
    # ------------------------------------------------------------------ #

    def _run_towards(self, delta_time: float, target_x: float, target_y: float, speed: float) -> None:
        """Court vers la cible : demi-tour lent, arret au bord sauf chute sure."""
        if not self._grounded:
            return  # en l'air (chute) : l'elan horizontal est conserve tel quel
        dx = target_x - self.center_x
        if abs(dx) < 2.0:
            self._steer(0.0, delta_time)
            return
        direction = 1 if dx > 0 else -1
        if direction != self.facing:
            # Freine d'abord, ne se retourne qu'apres ZOMBIE_TURN_TIME.
            self._turn_timer += delta_time
            self._steer(0.0, delta_time)
            if self._turn_timer >= settings.ZOMBIE_TURN_TIME:
                self.facing = direction
                self._turn_timer = 0.0
            return
        self._turn_timer = 0.0
        if self._blocked_ahead() or (not self._floor_ahead() and not self._may_drop(target_y)):
            # Arret net : un lissage le ferait glisser par-dessus le bord.
            self.change_x = 0.0
            return
        self._steer(direction * speed, delta_time)

    def _steer(self, target_speed: float, delta_time: float) -> None:
        alpha = 1.0 - math.exp(-delta_time / max(settings.ZOMBIE_ACCEL_TIME, 0.001))
        self.change_x += (target_speed - self.change_x) * alpha
        if abs(self.change_x) < 0.01:
            self.change_x = 0.0

    def _may_drop(self, target_y: float) -> bool:
        """Se laisser tomber du bord ? Seulement vers une cible plus basse, et
        s'il y a un sol a au plus `ZOMBIE_MAX_DROP_TILES` tuiles (pas un puits)."""
        if target_y > self.center_y - settings.ZOMBIE_DROP_MIN_TARGET_DROP:
            return False
        edge_x = self.center_x + self.facing * (settings.ZOMBIE_WIDTH / 2 + 4)
        for tiles in range(1, settings.ZOMBIE_MAX_DROP_TILES + 1):
            probe_y = self.bottom - 4 - tiles * settings.TILE_SIZE
            for column in range(settings.ZOMBIE_DROP_PROBE_COLUMNS):
                probe_x = edge_x + self.facing * column * settings.TILE_SIZE
                if self._solid_at((probe_x, probe_y)):
                    return True
        return False

    def _blocked_ahead(self) -> bool:
        return self._solid_at((self.center_x + self.facing * (settings.ZOMBIE_WIDTH / 2 + 4), self.center_y))

    def _floor_ahead(self) -> bool:
        if not self._platforms:
            return True
        return self._solid_at((self.center_x + self.facing * (settings.ZOMBIE_WIDTH / 2 + 4), self.bottom - 4))

    def _solid_at(self, point: tuple[float, float]) -> bool:
        return any(arcade.get_sprites_at_point(point, walls) for walls in self._platforms)

    # ------------------------------------------------------------------ #
    # Animation
    # ------------------------------------------------------------------ #

    def _advance_animation(self, delta_time: float) -> None:
        """Choisit l'animation selon l'etat courant, puis avance le curseur."""
        speed = abs(self.change_x)
        if self.state is ZombieState.DYING:
            self._animator.play(self._die)
        elif self.state is ZombieState.HURT:
            self._animator.play(self._hurt)
        elif self.state is ZombieState.ALERT:
            self._animator.play(self._alert)
        elif self.state is ZombieState.ATTACK:
            self._animator.play(self._attack)
        elif speed <= 0.05:
            self._animator.play(self._eat if self._eating else self._idle)
        elif speed > settings.ZOMBIE_PATROL_SPEED + 0.4:
            self._animator.play(self._run)
        else:
            self._animator.play(self._walk)
        self.texture = self._animator.update(delta_time)
        self._apply_facing()

    def _apply_facing(self) -> None:
        """Planches dessinees tournees vers la gauche (cf. `Bat._apply_facing`)."""
        facing = -self.facing if settings.ZOMBIE_SPRITE_FACES_LEFT else self.facing
        sprites.apply_facing(self, facing)
