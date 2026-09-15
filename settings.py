"""Constantes globales de Project Astral Platformer.

Ce module ne doit contenir que des valeurs (aucune logique, aucun import
d'Arcade) afin de pouvoir etre importe depuis n'importe quel autre module
sans risque d'import circulaire.

Toutes les valeurs de vitesse / gravite sont exprimees en pixels par frame
(convention des moteurs de physique d'Arcade), avec une base de 60 FPS.
"""

from pathlib import Path

# --------------------------------------------------------------------------- #
# Chemins
# --------------------------------------------------------------------------- #

ROOT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = ROOT_DIR / "assets"
SPRITES_DIR = ASSETS_DIR / "sprites"
UI_DIR = ASSETS_DIR / "ui"
SOUNDS_DIR = ASSETS_DIR / "sons"
MAPS_DIR = ASSETS_DIR / "maps"

# Ordre de parcours des niveaux : le nom du fichier dans assets/maps/.
LEVEL_SEQUENCE: tuple[str, ...] = ("level_1_tuto.json",)

# --------------------------------------------------------------------------- #
# Fenetre
# --------------------------------------------------------------------------- #

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_MIN_WIDTH = 640
SCREEN_MIN_HEIGHT = 360
SCREEN_TITLE = "Project Astral Platformer"
FPS = 60
FRAME_TIME = 1 / FPS

# Etendue de monde (en unites monde, = pixels a zoom 1) que la camera montre
# a l'ecran, quelle que soit la taille reelle de la fenetre/du moniteur. Sans
# ca, passer en plein ecran revelerait plus de niveau (donc plus de chunks a
# soumettre au rendu) et ferait chuter le FPS rien qu'a cause du changement
# de dimensions : voir `CameraRig` dans `src/world/camera.py`.
WORLD_VIEW_WIDTH = SCREEN_WIDTH
WORLD_VIEW_HEIGHT = SCREEN_HEIGHT

# --------------------------------------------------------------------------- #
# Monde / tuiles
# --------------------------------------------------------------------------- #

TILE_SIZE = 32
# Taille d'un paquet de rendu, en tuiles. Le hash spatial ne sert qu'aux
# collisions : le draw ne soumet que les chunks qui touchent la camera.
RENDER_CHUNK_TILES = 16

# Noms de fichiers dans SPRITES_DIR, sans extension. La legende d'une carte
# JSON reprend ces noms (ou un alias : rock, dirt). Le chargeur ajoute `.png`.
SPRITE_DIRT = "dirt_1"
SPRITE_BEDROCK = "bedrock"
SPRITE_ROCK_1 = "rock_1"
SPRITE_ROCK_2 = "rock_2"
SPRITE_GRASS = "grass"
SPRITE_GRASS_VARIANT = "grass_1"
SPRITE_GRASS_CORNER = "grass_corner"
SPRITE_DIRT_TOP = "dirt_top"
SPRITE_DIRT_CORNER = "dirt_corner"
SPRITE_DIRT_CORNER_RIGHT = "dirt_corner_right"
SPRITE_DIRT_FLOATING = "dirt_floating_block"
SPRITE_SPIKE = "spike"
SPRITE_SPIKE_HANGING = "spike_up"
# Bandeaux d'entites (fichiers tels quels, y compris le typo "gost").
SPRITE_PLAYER_WALK = "player_walk"
SPRITE_PLAYER_IDLE = "player_idle"
SPRITE_GHOST_WALK = "gost_walk"
SPRITE_GHOST_DISAPPEAR = "gost_disappears"
SPRITE_FRAME_SIZE = 32
# Taille a l'ecran des sprites joueur / fantome (1.0 = 32 px).
ENTITY_SCALE = 1.5
ANIM_WALK_FRAME_TIME = 0.07
ANIM_IDLE_FRAME_TIME = 0.12
ANIM_GHOST_DISAPPEAR_FRAME_TIME = 0.08
# 1.0 = rythme de base ; plus petit = plus lent (0.5 = deux fois plus lent).
ANIM_SPEED = 0.5

# --------------------------------------------------------------------------- #
# Physique du corps physique (joueur vivant)
# --------------------------------------------------------------------------- #

GRAVITY = 1.0
PLAYER_WIDTH = SPRITE_FRAME_SIZE
PLAYER_HEIGHT = SPRITE_FRAME_SIZE
PLAYER_GRAVITY = 1  # un peu plus leger : saut legerement plus haut et plus lent
PLAYER_WIDTH = 24
PLAYER_HEIGHT = 44
PLAYER_SPEED = 5.5
PLAYER_JUMP_SPEED = 18.0
PLAYER_COYOTE_TIME = 0.10  # secondes de tolerance pour sauter apres une chute
PLAYER_RESPAWN_DELAY = 0.4  # secondes avant de reprendre le controle du corps
# Temps pour atteindre PLAYER_SPEED en maintenant une direction au sol.
PLAYER_ACCEL_TIME = 0.25
# Glissade a l'arret (sol) : 2-3 frames, quelques pixels tout au plus.
PLAYER_SLIDE_TIME = 0.01
# Fraction de l'acceleration au sol quand le joueur est en l'air.
PLAYER_AIR_CONTROL = 5.0
# Ralentissement juste apres l'atterrissage.
PLAYER_LANDING_SLOW_TIME = 0.12
PLAYER_LANDING_SPEED_SCALE = 0.86
# Dash horizontal (Shift), vitesse en px/frame, duree et recharge en secondes.
PLAYER_DASH_SPEED = 30.0
PLAYER_DASH_DURATION = 0.12
PLAYER_DASH_COOLDOWN = 3.0
PLAYER_DASH_READY_FLASH = 0.38
PLAYER_DASH_TRAIL_LIFE = 0.22  # duree de vie d'une afterimage, en secondes
PLAYER_DASH_GLOW_SCALE = 3.4
PLAYER_DASH_GLOW_ALPHA = 34
PLAYER_DASH_TRAIL_GLOW_SCALE = 3.2
PLAYER_DASH_TRAIL_GLOW_ALPHA = 28
PLAYER_DASH_GLOW_STRETCH = 1.55  # etirement du halo dans l'axe du dash
PLAYER_DASH_GLOW_OFFSET = 0.32  # recul du halo, en fractions de PLAYER_WIDTH


# --------------------------------------------------------------------------- #
# Forme fantome
# --------------------------------------------------------------------------- #

GHOST_WIDTH = 22
GHOST_HEIGHT = 30
GHOST_SPEED = 6.0
GHOST_ACCEL_TIME = 0.20  # secondes pour atteindre la vitesse visee (plus grand = plus mou)
GHOST_COAST_TIME = 0.48  # secondes pour glisser a l'arret une fois les touches lachees
GHOST_DURATION = 12.0  # duree de base du mode fantome, en secondes
GHOST_MAX_RANGE = 480.0  # distance max autour du cadavre d'ancrage, en pixels
GHOST_VISION_RADIUS = 160.0  # rayon de revelation des elements caches
GHOST_CARRY_CAPACITY = 1  # nombre d'objets transportables simultanement
# Fleche de rappel vers le corps : cachee tant que le fantome est assez proche.
GHOST_HOME_ARROW_MIN_DISTANCE = 96.0
GHOST_HOME_ARROW_OFFSET = 42.0  # distance du centre du fantome a la pointe
GHOST_HOME_ARROW_LENGTH = 12.0
GHOST_HOME_ARROW_WIDTH = 9.0
GHOST_GLOW_SCALE = 3.8
GHOST_GLOW_ALPHA = 32
GHOST_GLOW_PULSE_SPEED = 2.2
GHOST_GLOW_PULSE = 0.12  # variation d'opacite (0 = halo fixe)


# --------------------------------------------------------------------------- #
# Cadavre
# --------------------------------------------------------------------------- #

CORPSE_LIFETIME = 15.0  # secondes avant dissipation
CORPSE_FADE_TIME = 3.0  # secondes de fondu en fin de vie
CORPSE_EAT_TIME = 4.0  # secondes pour qu'un ennemi devore un cadavre

# --------------------------------------------------------------------------- #
# Ennemis
# --------------------------------------------------------------------------- #

ENEMY_WIDTH = 28
ENEMY_HEIGHT = 36
ENEMY_SPEED = 1.6
ENEMY_AGGRO_RANGE = 220.0  # distance de detection du joueur
ENEMY_CORPSE_SMELL_RANGE = 320.0  # distance d'attraction vers un cadavre

# --------------------------------------------------------------------------- #
# Objets et progression
# --------------------------------------------------------------------------- #

ITEM_SIZE = 18
ITEM_BOB_AMPLITUDE = 4.0  # amplitude du flottement vertical, en pixels
ITEM_BOB_SPEED = 2.5

SOUL_ESSENCE_PER_ORB = 1
# Essence cumulee necessaire pour atteindre le niveau n+1 (index = niveau - 1).
SOUL_LEVEL_THRESHOLDS: tuple[int, ...] = (0, 3, 8, 15, 25, 40)

# --------------------------------------------------------------------------- #
# Couleurs (RGB) - palette provisoire, remplacee par les sprites plus tard
# --------------------------------------------------------------------------- #

COLOR_BACKGROUND = (18, 18, 28)
COLOR_WALL = (72, 76, 96)
COLOR_SPECTRAL_WALL = (96, 84, 140)
COLOR_SPIKE = (196, 84, 84)
COLOR_DOOR_LOCKED = (150, 110, 46)
COLOR_DOOR_OPEN = (96, 170, 110)
COLOR_CHECKPOINT = (86, 148, 196)
COLOR_PLAYER = (232, 232, 240)
COLOR_GHOST = (128, 200, 255)
COLOR_GHOST_GLOW = (110, 190, 255)
COLOR_CORPSE = (140, 120, 120)
COLOR_ENEMY = (188, 92, 160)
COLOR_KEY = (232, 204, 96)
COLOR_SOUL_ORB = (110, 190, 255)
COLOR_HUD_TEXT = (228, 228, 236)
COLOR_HUD_BAR_BACKGROUND = (48, 48, 62)
COLOR_HUD_BAR_FILL = (128, 200, 255)
COLOR_DASH = (255, 214, 120)
COLOR_DASH_GLOW = (255, 224, 150)
COLOR_DASH_GAUGE = (255, 186, 72)
COLOR_MENU_TITLE = (200, 220, 255)
COLOR_MENU_HINT = (150, 155, 175)

# Opacite du voile hors du champ de vision du fantome (0-255).
FOG_ALPHA = 200
# Part du rayon entierement transparente au centre (0 = degrade des le centre).
GHOST_VISION_CLEAR_RATIO = 0.25

# --------------------------------------------------------------------------- #
# Atmosphere de premier plan (brouillard + nuages, parallaxe > 1)
# --------------------------------------------------------------------------- #

ATMOSPHERE_SEED = 2026
ATMOSPHERE_FOG_COLOR = (168, 176, 204)
ATMOSPHERE_CLOUD_COLOR = (220, 226, 240)
# (count, parallax, size_min, size_max, alpha_min, alpha_max, drift_px_s, y_bias)
# y_bias 0 = repartition uniforme, 1 = concentre vers le bas de l'ecran.
ATMOSPHERE_FOG_LAYERS: tuple[tuple[int, float, float, float, int, int, float, float], ...] = (
    (10, 1.28, 160.0, 280.0, 14, 28, 7.0, 0.72),
    (8, 1.52, 70.0, 140.0, 18, 36, 14.0, 0.40),
)
ATMOSPHERE_CLOUD_LAYERS: tuple[tuple[int, float, float, float, int, int, float, float], ...] = (
    (28, 1.92, 7.0, 18.0, 50, 105, 22.0, 0.18),
    (16, 2.65, 4.0, 10.0, 70, 140, 40.0, 0.12),
)

# --------------------------------------------------------------------------- #
# Camera
# --------------------------------------------------------------------------- #

# Constante de temps du suivi (secondes) : plus grand = plus fluide, plus de retard.
CAMERA_SMOOTH_TIME = 0.22
# Lissage du look-ahead, independant du suivi de position.
CAMERA_LOOK_SMOOTH_TIME = 0.30
CAMERA_LOOK_AHEAD = 56.0  # pixels d'avance a pleine vitesse
# Seuils en pixels/frame : ignore les micro-secousses de la physique au sol.
CAMERA_FALL_LOOK_THRESHOLD = 4.0
CAMERA_RISE_LOOK_THRESHOLD = 10.0
# Secousse du dash : amplitude en pixels, duree en secondes.
CAMERA_DASH_SHAKE = 5.5
CAMERA_DASH_SHAKE_TIME = 0.18

# --------------------------------------------------------------------------- #
# Icones clavier (Kenney Input Prompts, dans assets/ui/)
# --------------------------------------------------------------------------- #

UI_KEYBOARD_LETTERS = "Keyboard Letters and Symbols.png"
UI_KEYBOARD_EXTRAS = "Keyboard Extras.png"
UI_KEY_CELL = 16  # taille native d'une touche-lettre
UI_KEY_ICON_HEIGHT = 40  # hauteur a l'ecran (nearest-neighbor)
UI_KEY_CAPTION_SIZE = 16  # libelles a cote des icones

# --------------------------------------------------------------------------- #
# Debug
# --------------------------------------------------------------------------- #

DEBUG_OVERLAY = True  # panneau : FPS, etat, tuiles a l'ecran, positions (F3 en jeu)
DEBUG_SHOW_HITBOXES = False
DEBUG_SHOW_FPS = True  # si l'overlay est off, affiche quand meme le FPS en bas a gauche
COLOR_DEBUG = (140, 230, 160)
COLOR_DEBUG_PANEL = (8, 12, 18, 180)
COLOR_DEBUG_HITBOX = (80, 255, 120, 200)
