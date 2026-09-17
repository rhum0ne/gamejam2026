"""Ennemis : IA basique et liberation d'une "bille bleue" a leur mort.

Priorites de comportement, de la plus forte a la plus faible :
    1. FEAST  : un cadavre est a portee d'odorat -> l'ennemi va le devorer
                (c'est le coeur de la mecanique d'appat) ;
    2. CHASE  : le corps physique vivant est a portee -> poursuite. Une fois a
                portee de melee, l'ennemi s'arrete et donne un coup d'epee
                (WINDUP puis ATTACK, voir `_start_windup`) : seul ce coup tue
                le joueur, et seulement pendant les frames ou la lame est
                tendue (`strike_active`). Toucher le corps de l'ennemi ne tue
                pas ;
    3. PATROL : va-et-vient, demi-tour devant un mur ou au bord d'une plateforme.
`_player_in_range` ignore un joueur trop eloigne verticalement (pas sur le
meme "etage") : sans ca, un ennemi au sol "suit" un joueur juste au-dessus de
lui dans le vide sans jamais pouvoir l'atteindre.
Un dernier etat, DYING, joue l'animation de mort avant de retirer l'ennemi
du jeu (voir `take_damage`, herite de `EnemyBase`).

Les PV/mort/halo/portee d'attaque generiques sont dans `EnemyBase`
(`src/entities/enemy_base.py`). Voir aussi `src/entities/bat.py` pour un
archetype different (volant).
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.enemy_base import EnemyBase
from src.entities.player import Player
from src.ui import sprites


class EnemyState(Enum):
    """Etats de l'IA."""

    PATROL = auto()
    CHASE = auto()
    WINDUP = auto()
    ATTACK = auto()
    FEAST = auto()
    DYING = auto()


def _idle_animation() -> sprites.StripAnimation:
    """Meme planche que la marche (`ENEMY_SPRITE_IDLE == ENEMY_SPRITE_WALK`),
    juste rejouee plus lentement au repos."""
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_IDLE,
        settings.ENEMY_ACTION_FRAME_SIZE,
        settings.ENEMY_ACTION_FRAME_SIZE,
        scale=settings.ENEMY_ACTION_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_IDLE_FRAME_TIME, loop=True)


def _walk_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_WALK,
        settings.ENEMY_ACTION_FRAME_SIZE,
        settings.ENEMY_ACTION_FRAME_SIZE,
        scale=settings.ENEMY_ACTION_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_WALK_FRAME_TIME, loop=True)


def _attack_animation() -> sprites.StripAnimation:
    """Un coup d'epee, rejoue une fois par `Enemy._start_swing`. La lame n'est
    dangereuse que sur `settings.ENEMY_ATTACK_HIT_FRAMES` (voir `strike_active`)."""
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_ATTACK,
        settings.ENEMY_ACTION_FRAME_SIZE,
        settings.ENEMY_ACTION_FRAME_SIZE,
        scale=settings.ENEMY_ACTION_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_ATTACK_FRAME_TIME, loop=False)


def _die_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_DIE,
        settings.ENEMY_ACTION_FRAME_SIZE,
        settings.ENEMY_ACTION_FRAME_SIZE,
        scale=settings.ENEMY_ACTION_SCALE,
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_DIE_FRAME_TIME, loop=False)


class Enemy(EnemyBase):
    """Ennemi terrestre carnivore."""

    def __init__(
        self,
        center_x: float,
        center_y: float,
        *,
        drops_soul: bool = True,
    ) -> None:
        self._idle = _idle_animation()
        self._walk = _walk_animation()
        self._attack = _attack_animation()
        self._die = _die_animation()
        super().__init__(
            self._idle.textures[0],
            center_x=center_x,
            center_y=center_y,
            hit_points=settings.ENEMY_HIT_POINTS,
            body_width=settings.ENEMY_WIDTH,
            body_height=settings.ENEMY_HEIGHT,
        )
        self.scale = settings.ENEMY_SCALE
        # Les planches (40x40 natif, agrandies via ENEMY_ACTION_SCALE) ne sont
        # pas entierement occupees par le squelette : hitbox fixe et decalee
        # plutot que la frame entiere (voir ENEMY_HITBOX_OFFSET_*).
        sprites.apply_rect_hit_box(
            self,
            settings.ENEMY_WIDTH,
            settings.ENEMY_HEIGHT,
            offset_x=settings.ENEMY_HITBOX_OFFSET_X,
            offset_y=settings.ENEMY_HITBOX_OFFSET_Y,
        )
        self._animator = sprites.Animator(self._idle)
        self.state = EnemyState.PATROL
        self.facing = -1
        sprites.apply_facing(self, self.facing)
        self.attack_reach = settings.ENEMY_ATTACK_REACH
        self.attack_vertical_range = settings.ENEMY_ATTACK_VERTICAL_RANGE
        self._attack_cooldown = 0.0
        self._attack_windup = 0.0
        self._base_color = self.color
        self._hit_flash_left = 0.0
        self._knockback_x = 0.0
        self._drops_soul = drops_soul
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._ground: arcade.SpriteList | None = None
        self._hazards: arcade.SpriteList | None = None
        self._configure_glow(
            scale=settings.ENEMY_GHOST_GLOW_SCALE,
            alpha=settings.ENEMY_GHOST_GLOW_ALPHA,
            inner_scale=settings.ENEMY_GHOST_GLOW_INNER_SCALE,
            inner_alpha=settings.ENEMY_GHOST_GLOW_INNER_ALPHA,
            pulse=settings.ENEMY_GHOST_GLOW_PULSE,
            pulse_speed=settings.ENEMY_GHOST_GLOW_PULSE_SPEED,
            color=settings.COLOR_ENEMY_GLOW,
            color_core=settings.COLOR_ENEMY_GLOW_CORE,
        )

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(
        self,
        platforms: Sequence[arcade.SpriteList],
        hazards: arcade.SpriteList | None = None,
    ) -> None:
        """Branche la physique de l'ennemi sur les plateformes du niveau.

        `hazards` (piques au sol) ne fait pas partie des murs de collision :
        un ennemi doit marcher dessus sans etre repousse comme par un mur,
        mais ne doit pas non plus les traverser en marchant (voir
        `_hazard_ahead`) - seul un joueur (ou une pique en chute) en meurt.
        """
        self._physics = arcade.PhysicsEnginePlatformer(
            self,
            walls=list(platforms),
            gravity_constant=settings.GRAVITY,
        )
        self._ground = platforms[0] if platforms else None
        self._hazards = hazards

    # ------------------------------------------------------------------ #
    # Attaque
    # ------------------------------------------------------------------ #

    @property
    def strike_active(self) -> bool:
        """Vrai pendant les frames ou la lame est tendue (le coup peut tuer)."""
        if self.state is not EnemyState.ATTACK or self._animator.animation is not self._attack:
            return False
        first, last = settings.ENEMY_ATTACK_HIT_FRAMES
        return first <= self._animator.frame_index <= last

    # ------------------------------------------------------------------ #
    # Mort
    # ------------------------------------------------------------------ #

    def _on_death(self) -> None:
        """Stoppe l'ennemi et lance l'animation de mort.

        Le retrait effectif de la SpriteList est fait par `update` une fois
        l'animation terminee (voir `_animator.finished`), pas ici : ca laisse
        le temps a la bille bleue et au feedback visuel de se jouer.
        """
        self.state = EnemyState.DYING
        self.change_x = 0.0

    @property
    def drops_soul(self) -> bool:
        """Vrai si la prochaine mort de cet ennemi peut liberer une ame."""
        return self._drops_soul

    @property
    def is_defeated(self) -> bool:
        """Alias de compatibilite pour l'ancien nom de l'etat de mort."""
        return self.is_dying

    def _death_drop(self):
        """Ne recompense qu'une seule fois les ennemis initiaux."""
        if not self._drops_soul:
            return None
        self._drops_soul = False
        return super()._death_drop()

    def _on_respawn(self) -> None:
        self.state = EnemyState.PATROL
        self._attack_cooldown = 0.0
        self._attack_windup = 0.0
        self._hit_flash_left = 0.0
        self._knockback_x = 0.0
        self.color = self._base_color
        self.facing = -1
        self._animator.play(self._idle)
        self.texture = self._animator.animation.textures[0]
        sprites.apply_facing(self, self.facing)

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
        self._tick_hit_feedback(delta_time)
        self._attack_cooldown = max(0.0, self._attack_cooldown - delta_time)
        if self.state is EnemyState.WINDUP:
            self._attack_windup = max(0.0, self._attack_windup - delta_time)
        if self.state is EnemyState.ATTACK and self._animator.finished:
            self._end_swing()
        if self.state is EnemyState.DYING:
            self.change_x = self._knockback_x
            self._knockback_x *= settings.ENEMY_KNOCKBACK_FRICTION
        elif self._hit_flash_left > 0.0:
            self.change_x = self._knockback_x
            self._knockback_x *= settings.ENEMY_KNOCKBACK_FRICTION
        elif self.state is EnemyState.ATTACK:
            # Coup engage : l'ennemi reste immobile et ne se retourne pas tant
            # que l'animation n'est pas finie, ce qui laisse le joueur esquiver.
            self.change_x = 0.0
        elif self.state is EnemyState.WINDUP:
            self._hold_windup(player)
        elif self.state is not EnemyState.DYING:
            target_corpse = self._closest_corpse(corpses)
            if target_corpse is not None:
                self._feast(delta_time, target_corpse)
            elif self._player_in_range(player):
                self._chase(player)
            else:
                self._patrol()
        self._advance_animation(delta_time)
        if self._physics is not None:
            self._physics.update()
        if self.state is EnemyState.DYING and self._animator.finished:
            self.remove_from_sprite_lists()

    # ------------------------------------------------------------------ #
    # Comportements
    # ------------------------------------------------------------------ #

    def _closest_corpse(self, corpses: arcade.SpriteList | None) -> Corpse | None:
        if not corpses:
            return None
        in_range = [
            corpse
            for corpse in corpses
            if arcade.get_distance_between_sprites(self, corpse) <= settings.ENEMY_CORPSE_SMELL_RANGE
            and not corpse.is_remnant
        ]
        if not in_range:
            return None
        return min(in_range, key=lambda corpse: arcade.get_distance_between_sprites(self, corpse))

    def _feast(self, delta_time: float, corpse: Corpse) -> None:
        self.state = EnemyState.FEAST
        if arcade.check_for_collision(self, corpse):
            self.change_x = 0.0
            corpse.eaters += 1
            corpse.feed(delta_time)
            return
        self._walk_towards(corpse.center_x)

    def _chase(self, player: Player) -> None:
        if self._in_melee_range(player):
            # A portee : on s'arrete face au joueur, on attend, puis on frappe.
            self.change_x = 0.0
            self.facing = 1 if player.center_x >= self.center_x else -1
            if self._attack_cooldown <= 0.0:
                self._start_windup()
            else:
                self.state = EnemyState.CHASE
            return
        self.state = EnemyState.CHASE
        self._walk_towards(player.center_x)

    def _start_windup(self) -> None:
        self.state = EnemyState.WINDUP
        self._attack_windup = settings.ENEMY_ATTACK_WINDUP
        self.change_x = 0.0

    def _hold_windup(self, player: Player | None) -> None:
        """Reste plante. Si la cible part, on annule ; sinon on lance le coup."""
        self.change_x = 0.0
        if player is None or not player.alive or not self._in_melee_range(player):
            self.state = EnemyState.CHASE
            self._attack_windup = 0.0
            return
        self.facing = 1 if player.center_x >= self.center_x else -1
        if self._attack_windup <= 0.0:
            self._start_swing()

    def _start_swing(self) -> None:
        self.state = EnemyState.ATTACK
        self._animator.play(self._attack, restart=True)

    def _end_swing(self) -> None:
        self.state = EnemyState.CHASE
        self._attack_cooldown = settings.ENEMY_ATTACK_COOLDOWN

    def _in_melee_range(self, player: Player) -> bool:
        dx = abs(player.center_x - self.center_x)
        dy = abs(player.center_y - self.center_y)
        return dx <= settings.ENEMY_ATTACK_RANGE and dy <= settings.ENEMY_ATTACK_VERTICAL_RANGE

    def _patrol(self) -> None:
        self.state = EnemyState.PATROL
        if self._blocked_ahead() or self._hazard_ahead() or not self._floor_ahead():
            self.facing = -self.facing
        self.change_x = self.facing * settings.ENEMY_SPEED

    def _player_in_range(self, player: Player | None) -> bool:
        if player is None or not player.alive:
            return False
        if abs(player.center_y - self.center_y) > settings.ENEMY_AGGRO_VERTICAL_RANGE:
            return False
        return arcade.get_distance_between_sprites(self, player) <= settings.ENEMY_AGGRO_RANGE

    def _walk_towards(self, target_x: float) -> None:
        """Avance vers `target_x`, mais jamais dans le vide.

        `_chase`/`_feast` s'en servent pour poursuivre le joueur ou rejoindre
        un cadavre ; sans ce garde-fou, un ennemi poste sur une petite
        plateforme tomberait au sol en suivant une cible situee au-dela du
        bord (`_patrol` avait deja cette protection, pas `_walk_towards`).
        """
        direction = 1 if target_x > self.center_x else -1
        self.facing = direction
        if self._blocked_ahead() or self._hazard_ahead() or not self._floor_ahead():
            self.change_x = 0.0
            return
        self.change_x = direction * settings.ENEMY_SPEED

    def _blocked_ahead(self) -> bool:
        if self._ground is None:
            return False
        probe = (self.center_x + self.facing * (settings.ENEMY_WIDTH / 2 + 4), self.center_y)
        return bool(arcade.get_sprites_at_point(probe, self._ground))

    def _hazard_ahead(self) -> bool:
        """Une pique au sol juste devant ? Un ennemi n'y marche pas dessus.

        Ne tue pas l'ennemi (seule une pique en chute le fait, voir
        `enemies_hit_by_falling_spikes`) : il fait juste demi-tour, comme
        devant un mur ou le bord d'une plateforme.
        """
        if not self._hazards:
            return False
        probe = (self.center_x + self.facing * (settings.ENEMY_WIDTH / 2 + 4), self.bottom + 4)
        return bool(arcade.get_sprites_at_point(probe, self._hazards))

    def _floor_ahead(self) -> bool:
        if self._ground is None:
            return True
        probe = (self.center_x + self.facing * (settings.ENEMY_WIDTH / 2 + 4), self.bottom - 4)
        return bool(arcade.get_sprites_at_point(probe, self._ground))

    # ------------------------------------------------------------------ #
    # Animation
    # ------------------------------------------------------------------ #

    def _advance_animation(self, delta_time: float) -> None:
        """Choisit l'animation selon l'etat courant, puis avance le curseur."""
        if self.state is EnemyState.DYING:
            self._animator.play(self._die)
        elif self.state is EnemyState.ATTACK:
            self._animator.play(self._attack)
        elif self.state is EnemyState.WINDUP:
            self._animator.play(self._idle)
        elif self.state is EnemyState.FEAST or abs(self.change_x) <= 0.05:
            self._animator.play(self._idle)
        else:
            self._animator.play(self._walk)
        self.texture = self._animator.update(delta_time)
        sprites.apply_facing(self, self.facing)
