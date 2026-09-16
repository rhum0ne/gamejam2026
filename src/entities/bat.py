"""Chauve-souris : ennemi volant, en embuscade au plafond.

Priorites de comportement, de la plus forte a la plus faible :
    1. ATTACK : le joueur est a portee et le cooldown est ecoule -> pique
                (`_dive`) s'il est nettement en-dessous, dans un cone assez
                large autour de la verticale (pas seulement pile en-dessous :
                sinon l'attaque ne se declenche quasiment jamais en jeu reel),
                ou charge a l'horizontale (`_lunge`) s'il est a peu pres a la
                meme hauteur. Seules les frames actives tuent (`strike_active`) ;
    2. CHASE  : le joueur est reveille et a portee de laisse -> vol direct
                vers lui, en 2D libre (pas de gravite, cf. `Ghost`) ;
    3. RETURN : le joueur est mort/hors de portee de laisse -> retour au
                perchoir d'origine, puis re-endormissement (SLEEP) ;
    4. SLEEP  : immobile, accrochee au plafond, jusqu'a ce qu'un joueur vivant
                entre dans `BAT_WAKE_RANGE` (alors WAKE, une seule fois, avant
                de rejoindre CHASE).
Un dernier etat, DYING, joue l'animation de mort avant de retirer la chauve-
souris du jeu (voir `EnemyBase.take_damage`).

Contrairement au squelette (`Enemy`), la chauve-souris ne pese pas sur les
plaques de pression (`weighs_on_plates = False`) et ne marche pas au sol : le
deplacement est un vol libre a acceleration/amortissement exponentiels, comme
`Ghost._apply_steering`/`_move_axis`, mais vise une cible (le joueur ou le
perchoir) au lieu d'une entree clavier.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from enum import Enum, auto

import arcade

import settings
from src.entities.enemy_base import EnemyBase
from src.entities.player import Player
from src.ui import sprites


class BatState(Enum):
    """Etats de l'IA."""

    SLEEP = auto()
    WAKE = auto()
    CHASE = auto()
    ATTACK = auto()
    RETURN = auto()
    DYING = auto()


def _sleep_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.BAT_SPRITE_SLEEP, settings.BAT_FRAME_SIZE, settings.BAT_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_BAT_SLEEP_FRAME_TIME, loop=True)


def _wake_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.BAT_SPRITE_WAKE, settings.BAT_FRAME_SIZE, settings.BAT_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_BAT_WAKE_FRAME_TIME, loop=False)


def _fly_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.BAT_SPRITE_FLY, settings.BAT_FRAME_SIZE, settings.BAT_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_BAT_FLY_FRAME_TIME, loop=True)


def _run_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.BAT_SPRITE_RUN, settings.BAT_FRAME_SIZE, settings.BAT_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_BAT_RUN_FRAME_TIME, loop=True)


def _dive_animation() -> sprites.StripAnimation:
    """Piquet vertical, rejoue une fois par `Bat._start_attack`. Frames actives :
    `settings.BAT_DIVE_HIT_FRAMES` (voir `strike_active`)."""
    frames = sprites.load_strip(
        settings.BAT_SPRITE_ATTACK_DIVE, settings.BAT_FRAME_SIZE, settings.BAT_FRAME_SIZE
    )
    return sprites.StripAnimation(frames, settings.ANIM_BAT_ATTACK_DIVE_FRAME_TIME, loop=False)


def _lunge_animation() -> sprites.StripAnimation:
    """Charge horizontale. Frames actives : `settings.BAT_LUNGE_HIT_FRAMES`."""
    frames = sprites.load_strip(
        settings.BAT_SPRITE_ATTACK_LUNGE, settings.BAT_FRAME_SIZE, settings.BAT_FRAME_SIZE
    )
    return sprites.StripAnimation(frames, settings.ANIM_BAT_ATTACK_LUNGE_FRAME_TIME, loop=False)


def _die_animation() -> sprites.StripAnimation:
    frames = sprites.load_strip(settings.BAT_SPRITE_DIE, settings.BAT_FRAME_SIZE, settings.BAT_FRAME_SIZE)
    return sprites.StripAnimation(frames, settings.ANIM_BAT_DIE_FRAME_TIME, loop=False)


class Bat(EnemyBase):
    """Ennemi volant, en embuscade au plafond."""

    weighs_on_plates = False

    def __init__(self, center_x: float, center_y: float) -> None:
        self._sleep = _sleep_animation()
        self._wake = _wake_animation()
        self._fly = _fly_animation()
        self._run = _run_animation()
        self._dive = _dive_animation()
        self._lunge = _lunge_animation()
        self._die = _die_animation()
        super().__init__(
            self._sleep.textures[0],
            center_x=center_x,
            center_y=center_y,
            hit_points=settings.BAT_HIT_POINTS,
            body_width=settings.BAT_WIDTH,
            body_height=settings.BAT_HEIGHT,
        )
        self.scale = settings.BAT_SCALE
        sprites.apply_rect_hit_box(
            self,
            settings.BAT_WIDTH,
            settings.BAT_HEIGHT,
            offset_x=settings.BAT_HITBOX_OFFSET_X,
            offset_y=settings.BAT_HITBOX_OFFSET_Y,
        )
        self._animator = sprites.Animator(self._sleep)
        self.state = BatState.SLEEP
        self.facing = -1
        self._apply_facing()
        self.attack_reach = settings.BAT_ATTACK_REACH
        self._attack_cooldown = 0.0
        # Perchoir d'origine : point de RETURN, remis a jour par `_on_respawn`
        # (au cas ou un jour `respawn` serait appele avec d'autres coordonnees).
        self._home_x = center_x
        self._home_y = center_y
        self._target: tuple[float, float] | None = None
        # Position du joueur au moment ou l'attaque s'engage (voir `_start_attack`) :
        # figee, pas suivie en direct, pour garder l'esquive possible pendant l'armement.
        self._attack_target: tuple[float, float] | None = None
        # Point de depart et horloge de l'elan d'attaque (voir `_advance_attack_lurch`).
        self._attack_lurch_origin: tuple[float, float] | None = None
        self._attack_lurch_elapsed = 0.0
        self._walls: list[arcade.SpriteList] | None = None
        self._configure_glow(
            scale=settings.BAT_GHOST_GLOW_SCALE,
            alpha=settings.BAT_GHOST_GLOW_ALPHA,
            inner_scale=settings.BAT_GHOST_GLOW_INNER_SCALE,
            inner_alpha=settings.BAT_GHOST_GLOW_INNER_ALPHA,
            pulse=settings.BAT_GHOST_GLOW_PULSE,
            pulse_speed=settings.BAT_GHOST_GLOW_PULSE_SPEED,
            color=settings.COLOR_BAT_GLOW,
            color_core=settings.COLOR_BAT_GLOW_CORE,
        )

    # ------------------------------------------------------------------ #
    # Initialisation
    # ------------------------------------------------------------------ #

    def bind_world(
        self,
        platforms: Sequence[arcade.SpriteList],
        hazards: arcade.SpriteList | None = None,
    ) -> None:
        """Murs opaques au vol (murs normaux + murs spectraux, comme le squelette)."""
        del hazards  # meme signature que `Enemy.bind_world` (piques ignorees en vol)
        self._walls = list(platforms)

    # ------------------------------------------------------------------ #
    # Attaque
    # ------------------------------------------------------------------ #

    @property
    def strike_active(self) -> bool:
        """Vrai pendant les frames ou l'attaque en cours peut tuer."""
        if self.state is not BatState.ATTACK:
            return False
        if self._animator.animation is self._dive:
            first, last = settings.BAT_DIVE_HIT_FRAMES
        elif self._animator.animation is self._lunge:
            first, last = settings.BAT_LUNGE_HIT_FRAMES
        else:
            return False
        return first <= self._animator.frame_index <= last

    def strike_reaches(self, target: arcade.Sprite) -> bool:
        """Portee radiale plutot que le cone frontal du squelette.

        La chauve-souris attaque depuis des angles tres differents (piquet
        vertical, charge horizontale) : un simple rayon autour du corps reste
        juste (RANGE < REACH, cf. `settings.BAT_ATTACK_RANGE`) et plus lisible
        qu'un cone par type d'attaque.
        """
        if not isinstance(target, arcade.Sprite):
            raise TypeError("target doit etre un arcade.Sprite")
        return math.dist((self.center_x, self.center_y), target.position) <= self.attack_reach

    def _pick_attack(self, player: Player) -> sprites.StripAnimation | None:
        """Choisit le piquet ou la charge selon la position du joueur, ou
        `None` si aucune des deux ne s'applique.

        Le piquet se declenche dans un cone autour de la verticale (pas
        seulement pile en-dessous : `BAT_DIVE_CONE_ANGLE` degres de chaque
        cote), sinon il ne se declencherait presque jamais en jeu reel.
        """
        dx = player.center_x - self.center_x
        dy = player.center_y - self.center_y
        distance = math.hypot(dx, dy)
        if distance > settings.BAT_ATTACK_RANGE:
            return None
        if dy <= -settings.BAT_DIVE_MIN_DROP:
            angle_from_down = math.degrees(math.atan2(abs(dx), -dy))
            if angle_from_down <= settings.BAT_DIVE_CONE_ANGLE:
                return self._dive
        if abs(dy) <= settings.BAT_LUNGE_VERTICAL_RANGE:
            return self._lunge
        return None

    def _start_attack(self, animation: sprites.StripAnimation, player_x: float, player_y: float) -> None:
        """Engage l'attaque et s'elance vers le joueur, mais pas jusqu'a lui.

        `BAT_ATTACK_LURCH_DISTANCE` plafonne l'elan : l'ancre du sprite ne
        parcourt qu'une petite distance (sinon les deux sprites se retrouvent
        colles/a la meme hauteur, illisible). C'est l'amplitude propre au
        dessin de la planche (le piquet/la charge bouge deja bien a l'interieur
        de sa frame) qui complete la distance jusqu'au contact visuel. Le
        deplacement lui-meme est pilote par `_advance_attack_lurch`.
        """
        self.state = BatState.ATTACK
        dx = player_x - self.center_x
        dy = player_y - self.center_y
        distance = math.hypot(dx, dy)
        lurch = min(distance, settings.BAT_ATTACK_LURCH_DISTANCE)
        if distance > 1e-6:
            self._attack_target = (
                self.center_x + dx / distance * lurch,
                self.center_y + dy / distance * lurch,
            )
        else:
            self._attack_target = (self.center_x, self.center_y)
        self._attack_lurch_origin = (self.center_x, self.center_y)
        self._attack_lurch_elapsed = 0.0
        self._animator.play(animation, restart=True)

    def _end_attack(self) -> None:
        self.state = BatState.CHASE
        self._attack_cooldown = settings.BAT_ATTACK_COOLDOWN

    # ------------------------------------------------------------------ #
    # Mort
    # ------------------------------------------------------------------ #

    def _on_death(self) -> None:
        self.state = BatState.DYING
        self.change_x = 0.0
        self.change_y = 0.0

    def _on_respawn(self) -> None:
        self._home_x = self.center_x
        self._home_y = self.center_y
        self.state = BatState.SLEEP
        self._attack_cooldown = 0.0
        self.facing = -1
        self.change_x = 0.0
        self.change_y = 0.0
        self._target = None
        self._attack_target = None
        self._attack_lurch_origin = None
        self._attack_lurch_elapsed = 0.0
        self._animator.play(self._sleep)
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
        self._attack_cooldown = max(0.0, self._attack_cooldown - delta_time)
        self._tick_hit_feedback(delta_time)
        self._update_ai(player)
        if self.state is BatState.ATTACK:
            self._advance_attack_lurch(delta_time)
        else:
            self._apply_steering(delta_time)
        self._move_axis("x")
        self._move_axis("y")
        self._advance_animation(delta_time)
        self._glow_time += max(0.0, delta_time)
        if self.state is BatState.DYING and self._animator.finished:
            self.remove_from_sprite_lists()

    # ------------------------------------------------------------------ #
    # Comportements
    # ------------------------------------------------------------------ #

    def _update_ai(self, player: Player | None) -> None:
        if self.state is BatState.DYING:
            self._target = None
            return
        if self.state is BatState.SLEEP:
            self._target = None
            if self._player_in_wake_range(player):
                self.state = BatState.WAKE
                self._animator.play(self._wake, restart=True)
            return
        if self.state is BatState.WAKE:
            self._target = None
            if self._animator.finished:
                self.state = BatState.CHASE
            return
        if self.state is BatState.ATTACK:
            # Le deplacement de l'elan est pilote directement dans `update`
            # (voir `_advance_attack_lurch`) : `_target`/`_apply_steering` ne
            # servent qu'a CHASE/RETURN.
            if self._animator.finished:
                self._end_attack()
            return
        if self.state is BatState.RETURN:
            # Ne PAS reprendre la poursuite si le joueur repasse a portee de
            # reveil : `BAT_LEASH_RANGE` (distance au perchoir) et
            # `BAT_WAKE_RANGE` (distance au joueur) sont deux seuils
            # independants, et le second est presque toujours vrai des le
            # debut du retour (on vient de renoncer *pres* du joueur). Annuler
            # RETURN ici recreait un aller-retour CHASE <-> RETURN a chaque
            # frame dans ce cas, une fois la laisse a nouveau depassee.
            # Engagee, la chauve-souris va jusqu'au perchoir ; le reveil normal
            # (SLEEP -> WAKE) reprendra le relais si le joueur est encore la.
            self._target = (self._home_x, self._home_y)
            if math.dist((self.center_x, self.center_y), self._target) <= settings.BAT_ARRIVE_DISTANCE:
                self._land()
            return
        # CHASE : suit le joueur tant qu'il est vivant et pas trop loin du
        # perchoir, sinon abandonne (RETURN).
        if player is None or not player.alive or self._leashed_too_far():
            self.state = BatState.RETURN
            self._target = (self._home_x, self._home_y)
            return
        if self._attack_cooldown <= 0.0:
            attack = self._pick_attack(player)
            if attack is not None:
                self.facing = 1 if player.center_x >= self.center_x else -1
                self._start_attack(attack, player.center_x, player.center_y)
                # Pas d'elan avant BAT_ATTACK_LURCH_START_FRAME (voir la
                # branche ATTACK ci-dessus) : la planche recule/monte en
                # premier, l'ancre ne doit pas encore avancer.
                self._target = None
                return
        self._target = (player.center_x, player.center_y)

    def _land(self) -> None:
        """Arrivee au perchoir : se pose pile dessus et se rendort."""
        self.center_x = self._home_x
        self.center_y = self._home_y
        self.change_x = 0.0
        self.change_y = 0.0
        self.state = BatState.SLEEP
        self._animator.play(self._sleep)

    def _player_in_wake_range(self, player: Player | None) -> bool:
        if player is None or not player.alive:
            return False
        return math.dist((self.center_x, self.center_y), player.position) <= settings.BAT_WAKE_RANGE

    def _leashed_too_far(self) -> bool:
        distance = math.dist((self.center_x, self.center_y), (self._home_x, self._home_y))
        return distance > settings.BAT_LEASH_RANGE

    # ------------------------------------------------------------------ #
    # Deplacement (vol libre, sans gravite : cf. `Ghost._apply_steering`)
    # ------------------------------------------------------------------ #

    def _apply_steering(self, delta_time: float) -> None:
        """Vol de poursuite/retour : vise `self._target` (voir `Ghost._apply_steering`).
        L'elan d'attaque a son propre pilotage, deterministe : `_advance_attack_lurch`."""
        if self._target is not None:
            dx = self._target[0] - self.center_x
            dy = self._target[1] - self.center_y
            length = math.hypot(dx, dy)
        else:
            length = 0.0
        if length > 1e-6:
            dx, dy = dx / length, dy / length
            smooth_time = settings.BAT_ACCEL_TIME
        else:
            dx, dy = 0.0, 0.0
            smooth_time = settings.BAT_COAST_TIME
        alpha = 1.0 - math.exp(-max(delta_time, 0.0) / max(smooth_time, 0.001))
        self.change_x += (dx * settings.BAT_SPEED - self.change_x) * alpha
        self.change_y += (dy * settings.BAT_SPEED - self.change_y) * alpha

    def _advance_attack_lurch(self, delta_time: float) -> None:
        """Deplacement de l'elan d'attaque : interpolation directe et plafonnee
        de `_attack_lurch_origin` vers `_attack_target`, etalee sur
        `BAT_ATTACK_LURCH_DURATION` a partir de `BAT_ATTACK_LURCH_START_FRAME`.

        Deliberement PAS un ressort vitesse/acceleration comme `_apply_steering` :
        sur un si court trajet, la vitesse acquise reste grande a l'approche et
        continuerait de porter l'ancre au-dela de la cible, qui se rearmerait
        alors la frame suivante -> aller-retour ("picorement") au lieu d'un
        elan net. Ici la distance parcourue est exactement celle voulue, sans
        survitesse residuelle a rattraper.
        """
        if (
            self._animator.frame_index < settings.BAT_ATTACK_LURCH_START_FRAME
            or self._attack_target is None
            or self._attack_lurch_origin is None
        ):
            # Armement : la planche dessine un recul/une montee (a l'oppose
            # de la cible). Bouger l'ancre des maintenant la ferait avancer
            # pendant que le dessin recule.
            self.change_x = 0.0
            self.change_y = 0.0
            return
        self._attack_lurch_elapsed = min(
            self._attack_lurch_elapsed + max(delta_time, 0.0), settings.BAT_ATTACK_LURCH_DURATION
        )
        duration = max(settings.BAT_ATTACK_LURCH_DURATION, 0.001)
        progress = self._attack_lurch_elapsed / duration
        eased = 1.0 - (1.0 - progress) ** 2  # depart vif, se pose en douceur
        origin_x, origin_y = self._attack_lurch_origin
        target_x, target_y = self._attack_target
        desired_x = origin_x + (target_x - origin_x) * eased
        desired_y = origin_y + (target_y - origin_y) * eased
        self.change_x = desired_x - self.center_x
        self.change_y = desired_y - self.center_y

    def _move_axis(self, axis: str) -> None:
        """Deplace la chauve-souris sur un seul axe, annule le pas en cas de
        collision (mur normal ou spectral : elle ne traverse rien, contrairement
        au fantome)."""
        if axis == "x":
            previous, self.center_x = self.center_x, self.center_x + self.change_x
        else:
            previous, self.center_y = self.center_y, self.center_y + self.change_y
        if not self._walls:
            return
        for wall_list in self._walls:
            if arcade.check_for_collision_with_list(self, wall_list):
                if axis == "x":
                    self.center_x = previous
                    self.change_x = 0.0
                else:
                    self.center_y = previous
                    self.change_y = 0.0
                return

    # ------------------------------------------------------------------ #
    # Animation
    # ------------------------------------------------------------------ #

    def _advance_animation(self, delta_time: float) -> None:
        """Choisit l'animation selon l'etat courant, puis avance le curseur."""
        if self.state is BatState.DYING:
            self._animator.play(self._die)
        elif self.state is BatState.SLEEP:
            self._animator.play(self._sleep)
        elif self.state is BatState.WAKE:
            self._animator.play(self._wake)
        elif self.state is BatState.ATTACK:
            pass  # deja lancee par `_start_attack` (restart=True) : ne pas rejouer par-dessus.
        else:  # CHASE / RETURN
            if abs(self.change_x) > 0.05:
                self.facing = 1 if self.change_x > 0 else -1
            speed = math.hypot(self.change_x, self.change_y)
            self._animator.play(self._run if speed > 0.3 else self._fly)
        self.texture = self._animator.update(delta_time)
        self._apply_facing()

    def _apply_facing(self) -> None:
        """La planche dessine la chauve-souris tournee vers la gauche : miroir
        par rapport au squelette (`apply_facing` suppose une orientation
        d'origine vers la droite)."""
        facing = -self.facing if settings.BAT_SPRITE_FACES_LEFT else self.facing
        sprites.apply_facing(self, facing)
