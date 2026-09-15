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

# --------------------------------------------------------------------------- #
# Monde / tuiles
# --------------------------------------------------------------------------- #

TILE_SIZE = 32

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

# --------------------------------------------------------------------------- #
# Physique du corps physique (joueur vivant)
# --------------------------------------------------------------------------- #

GRAVITY = 1.0
PLAYER_WIDTH = 24
PLAYER_HEIGHT = 44
PLAYER_SPEED = 5.5
PLAYER_JUMP_SPEED = 17.0
PLAYER_COYOTE_TIME = 0.10  # secondes de tolerance pour sauter apres une chute
PLAYER_RESPAWN_DELAY = 0.4  # secondes avant de reprendre le controle du corps

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
COLOR_CORPSE = (140, 120, 120)
COLOR_ENEMY = (188, 92, 160)
COLOR_KEY = (232, 204, 96)
COLOR_SOUL_ORB = (110, 190, 255)
COLOR_HUD_TEXT = (228, 228, 236)
COLOR_HUD_BAR_BACKGROUND = (48, 48, 62)
COLOR_HUD_BAR_FILL = (128, 200, 255)
COLOR_MENU_TITLE = (200, 220, 255)
COLOR_MENU_HINT = (150, 155, 175)

# Opacite du voile hors du champ de vision du fantome (0-255).
FOG_ALPHA = 200
# Part du rayon entierement transparente au centre (0 = degrade des le centre).
GHOST_VISION_CLEAR_RATIO = 0.25

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

# --------------------------------------------------------------------------- #
# Debug
# --------------------------------------------------------------------------- #

DEBUG_SHOW_HITBOXES = False
DEBUG_SHOW_FPS = True
