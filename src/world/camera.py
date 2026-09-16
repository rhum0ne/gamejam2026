"""Cameras du jeu et rendu a resolution fixe.

`CameraRig` regroupe les deux cameras dont une scene a besoin :
    - `world` : suit une cible (joueur OU fantome) avec un lissage exponentiel,
      independant du FPS, et reste confinee dans les limites du niveau ;
    - `ui`    : camera fixe, en coordonnees ecran, pour le HUD.

Une secousse optionnelle (`shake`) se superpose au suivi sans le deriver.

Le zoom suit aussi une cible (`CAMERA_ZOOM_PLAYER` en corps, `CAMERA_ZOOM_GHOST`
en fantome) avec son propre lissage exponentiel : la camera recule quand on
projette le fantome hors du corps, et se rapproche au retour.

Le look-ahead n'est pas un cran binaire : il est proportionnel a la vitesse et
lui-meme lisse, pour eviter les a-coups quand `change_x` / `change_y` basculent
(physique au sol, sommet de saut, arret).

Rendu a resolution fixe (`begin_frame` / `present`)
    Les deux cameras dessinent toujours dans un framebuffer hors-ecran de
    taille fixe (`settings.WORLD_VIEW_WIDTH/HEIGHT`), jamais directement dans
    la fenetre. Sans ca, le plein ecran (ou une grande fenetre) demande de
    soumettre plus de chunks/sprites ET de remplir plus de pixels physiques
    qu'en petite fenetre, et le FPS chute rien qu'a cause du changement de
    dimensions. `present()` redimensionne cette image fixe vers la fenetre
    reelle en une seule passe (un quad texture, mise a l'echelle materielle
    quasi gratuite), en conservant le ratio d'aspect (bandes noires si besoin).
    Un `warp_strength` non nul (mode fantome) applique une distorsion barillet
    et un leger etirement perspectif sur cette copie.
"""

from __future__ import annotations

import math
from textwrap import dedent

import arcade
from arcade.camera import Camera2D
from arcade.gl import geometry
from arcade.types import LRBT

import settings


def _exp_alpha(delta_time: float, smooth_time: float) -> float:
    """Facteur de lerp equivalent a une constante de temps, stable quel que soit le FPS."""
    if smooth_time <= 0.0:
        return 1.0
    return 1.0 - math.exp(-max(delta_time, 0.0) / smooth_time)


_PRESENT_VERTEX_SHADER = dedent(
    """\
    #version 330

    in vec2 in_vert;
    in vec2 in_uv;
    out vec2 out_uv;

    void main() {
        gl_Position = vec4(in_vert, 0.0, 1.0);
        out_uv = in_uv;
    }
    """
)

_PRESENT_FRAGMENT_SHADER = dedent(
    """\
    #version 330

    uniform sampler2D screen_texture;
    uniform float warp_barrel;
    uniform float warp_perspective;
    uniform float warp_chroma;
    in vec2 out_uv;
    out vec4 frag_color;

    void main() {
        vec2 centered = out_uv - vec2(0.5);
        float r2 = dot(centered, centered);
        vec2 warped = centered * (1.0 + warp_barrel * r2);
        warped.y *= 1.0 + warp_perspective * centered.y;
        vec2 uv = vec2(0.5) + warped;
        vec2 dir = centered * inversesqrt(r2 + 1e-6);
        vec2 offset = dir * warp_chroma;
        float red = texture(screen_texture, clamp(uv + offset, 0.0, 1.0)).r;
        vec4 mid = texture(screen_texture, clamp(uv, 0.0, 1.0));
        float blue = texture(screen_texture, clamp(uv - offset, 0.0, 1.0)).b;
        frag_color = vec4(red, mid.g, blue, mid.a);
    }
    """
)

_PRESENT_BLIT_FRAGMENT_SHADER = dedent(
    """\
    #version 330

    uniform sampler2D screen_texture;
    in vec2 out_uv;
    out vec4 frag_color;

    void main() {
        frag_color = texture(screen_texture, out_uv);
    }
    """
)


class CameraRig:
    """Paire de cameras monde / interface, dessinant a resolution fixe."""

    def __init__(self, world_width: float = 0.0, world_height: float = 0.0) -> None:
        self._window = arcade.get_window()
        self._target = self._window.ctx.framebuffer(
            color_attachments=[
                self._window.ctx.texture(
                    (settings.WORLD_VIEW_WIDTH, settings.WORLD_VIEW_HEIGHT),
                    components=4,
                )
            ]
        )
        # Le viewport/projection par defaut d'une Camera2D derive de la
        # taille de son render_target : les deux valent donc deja
        # WORLD_VIEW_WIDTH/HEIGHT, quelle que soit la taille de la fenetre.
        self.world = Camera2D(render_target=self._target)
        self.ui = Camera2D(render_target=self._target)
        self.world_width = world_width
        self.world_height = world_height
        self._look_x = 0.0
        self._look_y = 0.0
        self._anchor_x = 0.0
        self._anchor_y = 0.0
        self._shake_x = 0.0
        self._shake_y = 0.0
        self._shake_time = 0.0
        self._shake_duration = 0.001
        self._shake_amp = 0.0
        self._shake_phase = 0.0
        self._zoom = settings.CAMERA_ZOOM_PLAYER
        self._present_geometry = geometry.quad_2d_fs()
        self._present_program = self._window.ctx.program(
            vertex_shader=_PRESENT_VERTEX_SHADER,
            fragment_shader=_PRESENT_FRAGMENT_SHADER,
        )
        self._blit_program = self._window.ctx.program(
            vertex_shader=_PRESENT_VERTEX_SHADER,
            fragment_shader=_PRESENT_BLIT_FRAGMENT_SHADER,
        )
        self._present_viewport = (0, 0, settings.WORLD_VIEW_WIDTH, settings.WORLD_VIEW_HEIGHT)

    def set_bounds(self, world_width: float, world_height: float) -> None:
        """Definit les dimensions du niveau utilisees pour le clamp."""
        self.world_width = world_width
        self.world_height = world_height

    def snap_to(self, target: arcade.Sprite, zoom: float = settings.CAMERA_ZOOM_PLAYER) -> None:
        """Place instantanement la camera sur la cible (changement de niveau)."""
        self._look_x = 0.0
        self._look_y = 0.0
        self._shake_time = 0.0
        self._shake_x = 0.0
        self._shake_y = 0.0
        self._zoom = zoom
        self.world.zoom = zoom
        self._anchor_x, self._anchor_y = self._clamp(target.center_x, target.center_y)
        self._apply_offset()

    def shake(self, amplitude: float, duration: float) -> None:
        """Declenche une petite secousse (dash, impact)."""
        self._shake_amp = amplitude
        self._shake_duration = max(duration, 0.001)
        self._shake_time = self._shake_duration
        self._shake_phase = 0.0

    @property
    def zoom(self) -> float:
        return self._zoom

    def apply_cinematic(
        self,
        x: float,
        y: float,
        zoom: float,
        delta_time: float,
    ) -> None:
        """Cadre un point avec un zoom impose, sans look-ahead.

        Sert a la transition mort -> fantome : le zoom est pilote par la
        cinematique (courbe finie), la position reste collee au corps.
        """
        self._zoom = zoom
        self.world.zoom = zoom
        self._look_x = 0.0
        self._look_y = 0.0
        desired_x, desired_y = self._clamp(x, y)
        alpha = _exp_alpha(delta_time, settings.DEATH_CAMERA_LOCK_TIME)
        self._anchor_x += (desired_x - self._anchor_x) * alpha
        self._anchor_y += (desired_y - self._anchor_y) * alpha
        self._tick_shake(delta_time)
        self._apply_offset()

    def follow(
        self,
        target: arcade.Sprite,
        delta_time: float,
        zoom: float = settings.CAMERA_ZOOM_PLAYER,
    ) -> None:
        """Rapproche la camera d'une cible mouvante, avec un look-ahead lisse.

        `zoom` est la cible vers laquelle le niveau de zoom est lisse : passer
        `CAMERA_ZOOM_GHOST` (plus petit que `CAMERA_ZOOM_PLAYER`) donne l'effet
        de recul/projection hors du corps au passage humain -> fantome.
        """
        self._ease_look_ahead(target.change_x, target.change_y, delta_time)
        self._advance(target.center_x + self._look_x, target.center_y + self._look_y, delta_time, zoom)

    def drift_to(
        self,
        x: float,
        y: float,
        delta_time: float,
        zoom: float = settings.CAMERA_ZOOM_PLAYER,
    ) -> None:
        """Ramene doucement la camera vers un point fixe, sans cible ni look-ahead.

        Sert au retour au corps (mode `RESPAWNING`) : le corps n'a pas encore
        bouge au point de reapparition, donc rien a suivre, mais on veut la
        meme transition fluide (position + zoom) qu'avec `follow`, plutot
        qu'un saut instantane une fois le delai de respawn ecoule.
        """
        self._ease_look_ahead(0.0, 0.0, delta_time)
        self._advance(x + self._look_x, y + self._look_y, delta_time, zoom)

    def _advance(self, target_x: float, target_y: float, delta_time: float, zoom: float) -> None:
        zoom_alpha = _exp_alpha(delta_time, settings.CAMERA_ZOOM_SMOOTH_TIME)
        self._zoom += (zoom - self._zoom) * zoom_alpha
        self.world.zoom = self._zoom
        desired_x, desired_y = self._clamp(target_x, target_y)
        alpha = _exp_alpha(delta_time, settings.CAMERA_SMOOTH_TIME)
        self._anchor_x += (desired_x - self._anchor_x) * alpha
        self._anchor_y += (desired_y - self._anchor_y) * alpha
        self._tick_shake(delta_time)
        self._apply_offset()

    def use_world(self) -> None:
        self.world.use()

    def use_ui(self) -> None:
        self.ui.use()

    def visible_rect(self) -> LRBT:
        """Rectangle monde actuellement a l'ecran (camera non tournee)."""
        center_x, center_y = self.world.position
        half_width = self.world.width / 2
        half_height = self.world.height / 2
        return LRBT(
            center_x - half_width,
            center_x + half_width,
            center_y - half_height,
            center_y + half_height,
        )

    def cull_rect(self) -> LRBT:
        """Rectangle de culling, plus large que l'ecran pour eviter les pop-in."""
        view = self.visible_rect()
        pad = settings.RENDER_CULL_PAD
        return LRBT(
            view.left - pad,
            view.right + pad,
            view.bottom - pad,
            view.top + pad,
        )

    def cull_rect_around(self, x: float, y: float, radius: float) -> LRBT:
        """Intersection du culling camera et d'un disque (vision du fantome)."""
        view = self.cull_rect()
        left = max(view.left, x - radius)
        right = min(view.right, x + radius)
        bottom = max(view.bottom, y - radius)
        top = min(view.top, y + radius)
        if left >= right or bottom >= top:
            return view
        return LRBT(left, right, bottom, top)

    def begin_frame(self) -> None:
        """Efface l'image hors-ecran, avant que le monde et le HUD n'y dessinent."""
        self._target.clear(color=settings.COLOR_BACKGROUND)

    def present(self, warp_strength: float = 0.0) -> None:
        """Recopie l'image hors-ecran (resolution fixe) dans la fenetre reelle.

        `warp_strength` 0 laisse l'image intacte. Une valeur positive (mode
        fantome) deforme legerement la perspective sur tout l'ecran.
        """
        screen = self._window.ctx.screen
        screen.use()
        screen.clear(
            color=settings.COLOR_BACKGROUND,
            viewport=(0, 0, self._window.width, self._window.height),
        )
        screen.viewport = self._present_viewport
        self._target.color_attachments[0].use(unit=0)
        strength = max(0.0, float(warp_strength))
        if strength <= 0.0:
            self._blit_program["screen_texture"] = 0
            self._present_geometry.render(self._blit_program)
            return
        self._present_program["screen_texture"] = 0
        self._present_program["warp_barrel"] = strength
        self._present_program["warp_perspective"] = strength * settings.GHOST_WARP_PERSPECTIVE
        self._present_program["warp_chroma"] = strength * settings.GHOST_WARP_CHROMA
        self._present_geometry.render(self._present_program)

    def on_resize(self, width: int, height: int) -> None:
        """Recalcule seulement le rectangle d'affichage (letterbox) dans la fenetre.

        Le monde et le HUD continuent de se dessiner a taille fixe dans le
        framebuffer hors-ecran ; seule cette derniere etape (`present`) doit
        s'adapter a la fenetre reelle.
        """
        self._present_viewport = self._letterboxed(width, height)

    def _letterboxed(self, width: int, height: int) -> tuple[int, int, int, int]:
        """Plus grand rectangle centre, au format de conception, dans `width x height`."""
        design_aspect = settings.WORLD_VIEW_WIDTH / settings.WORLD_VIEW_HEIGHT
        if width <= 0 or height <= 0:
            return (0, 0, max(1, width), max(1, height))
        if width / height > design_aspect:
            box_height = height
            box_width = int(box_height * design_aspect)
        else:
            box_width = width
            box_height = int(box_width / design_aspect)
        return ((width - box_width) // 2, (height - box_height) // 2, box_width, box_height)

    def _tick_shake(self, delta_time: float) -> None:
        if self._shake_time <= 0.0:
            self._shake_x = 0.0
            self._shake_y = 0.0
            return
        self._shake_time = max(0.0, self._shake_time - delta_time)
        strength = (self._shake_time / self._shake_duration) ** 2
        self._shake_phase += delta_time * 58.0
        self._shake_x = math.sin(self._shake_phase * 1.7) * self._shake_amp * strength
        self._shake_y = math.cos(self._shake_phase * 2.3) * self._shake_amp * 0.4 * strength

    def _apply_offset(self) -> None:
        self.world.position = (self._anchor_x + self._shake_x, self._anchor_y + self._shake_y)

    def _ease_look_ahead(self, change_x: float, change_y: float, delta_time: float) -> None:
        max_speed = max(abs(settings.PLAYER_SPEED), abs(settings.GHOST_SPEED), 1.0)
        desired_x = max(-1.0, min(1.0, change_x / max_speed)) * settings.CAMERA_LOOK_AHEAD
        desired_y = 0.0
        if change_y < -settings.CAMERA_FALL_LOOK_THRESHOLD:
            desired_y = -settings.CAMERA_LOOK_AHEAD
        elif change_y > settings.CAMERA_RISE_LOOK_THRESHOLD:
            desired_y = settings.CAMERA_LOOK_AHEAD * 0.35
        alpha = _exp_alpha(delta_time, settings.CAMERA_LOOK_SMOOTH_TIME)
        self._look_x += (desired_x - self._look_x) * alpha
        self._look_y += (desired_y - self._look_y) * alpha

    def _clamp(self, x: float, y: float) -> tuple[float, float]:
        """Garde le cadre de la camera a l'interieur du niveau (en unites monde)."""
        half_width = self.world.width / 2
        half_height = self.world.height / 2
        if self.world_width > 2 * half_width:
            x = min(max(x, half_width), self.world_width - half_width)
        else:
            x = self.world_width / 2
        if self.world_height > 2 * half_height:
            y = min(max(y, half_height), self.world_height - half_height)
        else:
            y = self.world_height / 2
        return x, y
