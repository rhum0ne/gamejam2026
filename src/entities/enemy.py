"""Ennemis : IA basique et liberation d'une "bille bleue" a leur mort.

Priorites de comportement, de la plus forte a la plus faible :
    1. FEAST  : un cadavre est a portee d'odorat -> l'ennemi va le devorer
                (c'est le coeur de la mecanique d'appat) ;
    2. CHASE  : le corps physique vivant est a portee -> poursuite. Une fois a
                portee de melee, l'ennemi s'arrete et donne un coup d'epee
                (ATTACK, voir `_start_swing`) : seul ce coup tue le joueur, et
                seulement pendant les frames ou la lame est tendue
                (`strike_active`). Toucher le corps de l'ennemi ne tue pas ;
    3. PATROL : va-et-vient, demi-tour devant un mur ou au bord d'une plateforme.
`_player_in_range` ignore un joueur trop eloigne verticalement (pas sur le
meme "etage") : sans ca, un ennemi au sol "suit" un joueur juste au-dessus de
lui dans le vide sans jamais pouvoir l'atteindre.
Un dernier etat, DYING, joue l'animation de mort avant de retirer l'ennemi
du jeu (voir `take_damage`).

TODO(gameplay) : varier les archetypes (volant, spectral visible uniquement en
mode fantome, tireur) en sous-classant `Enemy`.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum, auto

import arcade

import settings
from src.entities.corpse import Corpse
from src.entities.glow import draw_threat_glow
from src.entities.item import Item, make_soul_orb
from src.entities.player import Player
from src.ui import sprites


class EnemyState(Enum):
    """Etats de l'IA."""

    PATROL = auto()
    CHASE = auto()
    ATTACK = auto()
    FEAST = auto()
    DYING = auto()


def _idle_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_IDLE, settings.ENEMY_FRAME_WIDTH, settings.ENEMY_FRAME_HEIGHT
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_IDLE_FRAME_TIME, loop=True)


def _walk_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_WALK, settings.ENEMY_FRAME_WIDTH, settings.ENEMY_FRAME_HEIGHT
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_WALK_FRAME_TIME, loop=True)


def _attack_animation() -> sprites.StripAnimation:
    """Un coup d'epee, rejoue une fois par `Enemy._start_swing`. La lame n'est
    dangereuse que sur `settings.ENEMY_ATTACK_HIT_FRAMES` (voir `strike_active`)."""
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_ATTACK, settings.ENEMY_FRAME_WIDTH, settings.ENEMY_FRAME_HEIGHT
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_ATTACK_FRAME_TIME, loop=False)


def _die_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(
        settings.ENEMY_SPRITE_DIE, settings.ENEMY_FRAME_WIDTH, settings.ENEMY_FRAME_HEIGHT
    )
    return sprites.StripAnimation(frames, settings.ANIM_ENEMY_DIE_FRAME_TIME, loop=False)


class Enemy(arcade.Sprite):
    """Ennemi terrestre carnivore."""

    def __init__(self, center_x: float, center_y: float) -> None:
        self._idle = _idle_animation()
        self._walk = _walk_animation()
        self._attack = _attack_animation()
        self._die = _die_animation()
        super().__init__(self._idle.textures[0], center_x=center_x, center_y=center_y)
        self.scale = settings.ENEMY_SCALE
        # La planche fait ENEMY_FRAME_WIDTH x ENEMY_FRAME_HEIGHT px, mais le
        # squelette n'en occupe qu'une partie (l'epee balaie le reste pendant
        # les attaques) : hitbox fixe et decalee plutot que la frame entiere.
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
        self.hit_points = 1
        self.max_hit_points = self.hit_points
        self._attack_cooldown = 0.0
        self._physics: arcade.PhysicsEnginePlatformer | None = None
        self._ground: arcade.SpriteList | None = None

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

    def strike_reaches(self, target: arcade.Sprite) -> bool:
        """La lame, tendue du cote ou regarde l'ennemi, atteint-elle `target` ?

        Compte aussi une cible collee contre (ou dans) le corps de l'ennemi.
        """
        if not isinstance(target, arcade.Sprite):
            raise TypeError("target doit etre un arcade.Sprite")
        forward = (target.center_x - self.center_x) * self.facing
        if forward < -settings.ENEMY_WIDTH / 2 or forward > settings.ENEMY_ATTACK_REACH:
            return False
        return abs(target.center_y - self.center_y) <= settings.ENEMY_ATTACK_VERTICAL_RANGE

    # ------------------------------------------------------------------ #
    # Mort
    # ------------------------------------------------------------------ #

    def take_damage(self, amount: int = 1) -> Item | None:
        """Applique des degats. Retourne la bille bleue si l'ennemi meurt.

        Un ennemi deja en train de mourir (`DYING`) ignore tout nouveau coup :
        sans ca, un joueur qui reste sur sa tete pendant l'animation de mort
        ferait apparaitre plusieurs billes bleues pour un seul ennemi.
        """
        if amount <= 0:
            raise ValueError("amount doit etre strictement positif")
        if self.state is EnemyState.DYING:
            return None
        self.hit_points -= amount
        if self.hit_points > 0:
            return None
        orb = make_soul_orb(self.center_x, self.center_y)
        self._start_dying()
        return orb

    def _start_dying(self) -> None:
        """Stoppe l'ennemi et lance l'animation de mort.

        Le retrait effectif de la SpriteList est fait par `update` une fois
        l'animation terminee (voir `_animator.finished`), pas ici : ca laisse
        le temps a la bille bleue et au feedback visuel de se jouer.
        """
        self.state = EnemyState.DYING
        self.change_x = 0.0

    def respawn(self, center_x: float, center_y: float) -> None:
        """Remet l'ennemi a un point de spawn, vivant et reinitialise.

        Repositionne, annule la vitesse acquise et restaure les PV/etat/
        orientation d'origine. Ne touche pas a l'appartenance aux SpriteList :
        si l'ennemi avait ete retire via `take_damage`, c'est a l'appelant de
        le rajouter (voir `PlayView._respawn_enemies`), car `Enemy` ne garde
        pas de reference vers les listes qui le contiennent.
        """
        self.center_x = center_x
        self.center_y = center_y
        self.change_x = 0.0
        self.change_y = 0.0
        self.hit_points = self.max_hit_points
        self.state = EnemyState.PATROL
        self._attack_cooldown = 0.0
        self.facing = -1
        self._animator.play(self._idle)
        self.texture = self._animator.animation.textures[0]
        sprites.apply_facing(self, self.facing)

    # ------------------------------------------------------------------ #
    # Dessin
    # ------------------------------------------------------------------ #

    def draw_ghost_glow(self, *, bind_blend: bool = True) -> None:
        """Halo rouge identique aux piques, visible a travers le voile."""
        draw_threat_glow(self.center_x, self.center_y, bind_blend=bind_blend)

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
        self._attack_cooldown = max(0.0, self._attack_cooldown - delta_time)
        if self.state is EnemyState.ATTACK and self._animator.finished:
            self._end_swing()
        if self.state is EnemyState.ATTACK:
            # Coup engage : l'ennemi reste immobile et ne se retourne pas tant
            # que l'animation n'est pas finie, ce qui laisse le joueur esquiver.
            self.change_x = 0.0
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
            # A portee : on s'arrete face au joueur et on frappe des que le
            # coup precedent a fini de recharger.
            self.change_x = 0.0
            self.facing = 1 if player.center_x >= self.center_x else -1
            if self._attack_cooldown <= 0.0:
                self._start_swing()
            else:
                self.state = EnemyState.CHASE
            return
        self.state = EnemyState.CHASE
        self._walk_towards(player.center_x)

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
        elif self.state is EnemyState.FEAST or abs(self.change_x) <= 0.05:
            self._animator.play(self._idle)
        else:
            self._animator.play(self._walk)
        self.texture = self._animator.update(delta_time)
        sprites.apply_facing(self, self.facing)
