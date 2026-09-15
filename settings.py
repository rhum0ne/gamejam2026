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
SCREEN_TITLE = "Project Astral Platformer"
FPS = 60
FRAME_TIME = 1 / FPS

# --------------------------------------------------------------------------- #
# Monde / tuiles
# --------------------------------------------------------------------------- #

TILE_SIZE = 32

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
GHOST_ACCELERATION = 0.45  # facteur de lissage du deplacement (0 = inerte)
GHOST_DURATION = 12.0  # duree de base du mode fantome, en secondes
GHOST_MAX_RANGE = 480.0  # distance max autour du cadavre d'ancrage, en pixels
GHOST_VISION_RADIUS = 160.0  # rayon de revelation des elements caches
GHOST_CARRY_CAPACITY = 1  # nombre d'objets transportables simultanement
GHOST_TRAP_MARKER_OFFSETS: tuple[tuple[float, float], ...] = (
    (-30.0, -2.0),
    (-20.0, 14.0),
    (-10.0, 25.0),
    (0.0, 30.0),
    (10.0, 25.0),
    (20.0, 14.0),
    (30.0, -2.0),
)
GHOST_TRAP_MARKER_SIZE = 5.0
GHOST_TEXT_SIZE = 16

# Un piege cache s'active apres un court contact avec le corps physique.
HIDDEN_TRAP_ACTIVATION_DELAY = 0.50

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
COLOR_GHOST_WARNING = (174, 224, 255)
COLOR_GHOST_TEXT = (182, 220, 255)
COLOR_CORPSE = (140, 120, 120)
COLOR_ENEMY = (188, 92, 160)
COLOR_KEY = (232, 204, 96)
COLOR_SOUL_ORB = (110, 190, 255)
COLOR_HUD_TEXT = (228, 228, 236)
COLOR_HUD_BAR_BACKGROUND = (48, 48, 62)
COLOR_HUD_BAR_FILL = (128, 200, 255)
COLOR_MENU_TITLE = (200, 220, 255)
COLOR_MENU_HINT = (150, 155, 175)

# Opacite du voile d'obscurite hors du champ de vision du fantome (0-255).
FOG_ALPHA = 170

# --------------------------------------------------------------------------- #
# Camera
# --------------------------------------------------------------------------- #

CAMERA_LERP = 0.12  # 0 = camera figee, 1 = camera collee a la cible
CAMERA_LOOK_AHEAD = 48.0  # avance de la camera dans le sens du deplacement

# --------------------------------------------------------------------------- #
# Debug
# --------------------------------------------------------------------------- #

DEBUG_SHOW_HITBOXES = False
DEBUG_SHOW_FPS = True
