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
ANIMATIONS_DIR = ASSETS_DIR / "animations"
UI_DIR = ASSETS_DIR / "ui"
SOUNDS_DIR = ASSETS_DIR / "sons"
MAPS_DIR = ASSETS_DIR / "maps"
FONTS_DIR = ASSETS_DIR / "fonts"

# --------------------------------------------------------------------------- #
# Police
# --------------------------------------------------------------------------- #

# Chargee une fois au demarrage (`main.create_window`) via `arcade.load_font`.
# "Press Start 2P" est le nom de famille tel qu'embarque dans le fichier .ttf
# (Google Fonts, licence OFL) : c'est ce nom qu'il faut passer a chaque
# `arcade.Text(font_name=...)`.
FONT_FILE = FONTS_DIR / "PressStart2P-Regular.ttf"
FONT_PIXEL = "Press Start 2P"

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
# Marge autour de la camera (look-ahead, secousse, zoom). Sans ca, tout un
# chunk de 512 px apparait d'un coup au bord de l'ecran.
RENDER_CULL_PAD = 120.0

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
SPRITE_KEY = "key"
SPRITE_CHECKPOINT = "Check_Point"
SPRITE_CHECKPOINT_ACTIVE = "Check_Point_actif"
# PNG natif 32 px, agrandi x2 en nearest-neighbor (pas de flou).
CHECKPOINT_SIZE = TILE_SIZE * 2
SPRITE_FRAME_SIZE = 32
# Taille a l'ecran des sprites joueur / fantome (1.0 = 32 px).
# L'agrandissement est fait en nearest-neighbor dans `load_strip`.
ENTITY_SCALE = 1.5
ANIM_WALK_FRAME_TIME = 0.07
ANIM_IDLE_FRAME_TIME = 0.12
ANIM_GHOST_DISAPPEAR_FRAME_TIME = 0.08
# 1.0 = rythme de base ; plus petit = plus lent (0.5 = deux fois plus lent).
ANIM_SPEED = 0.5

# Torche (placeholder, pas de collision)
TORCH_WIDTH = 8
TORCH_HEIGHT = 12
TORCH_STEM_WIDTH = 3
TORCH_STEM_HEIGHT = 10
TORCH_GLOW_OUTER = 104.0
TORCH_GLOW_INNER = 38.0
TORCH_GLOW_ALPHA = 62
TORCH_GLOW_INNER_ALPHA = 110
TORCH_FLICKER = 0.22
TORCH_FLICKER_SPEED = 8.4
TORCH_FLICKER_SPEED_FAST = 19.0


# --------------------------------------------------------------------------- #
# Physique du corps physique (joueur vivant)
# --------------------------------------------------------------------------- #

GRAVITY = 1.0
SPIKE_FALL_GRAVITY = GRAVITY
SPIKE_FALL_MAX_SPEED = 14.0
# Halo des piques en mode fantome (visible a travers le voile).
SPIKE_GHOST_GLOW_SCALE = 3.4
SPIKE_GHOST_GLOW_ALPHA = 110
SPIKE_GHOST_GLOW_INNER_SCALE = 1.7
SPIKE_GHOST_GLOW_INNER_ALPHA = 180
SPIKE_GHOST_GLOW_PULSE = 0.14
SPIKE_GHOST_GLOW_PULSE_SPEED = 3.2
PLAYER_WIDTH = SPRITE_FRAME_SIZE
PLAYER_HEIGHT = SPRITE_FRAME_SIZE
PLAYER_GRAVITY = 1  # un peu plus leger : saut legerement plus haut et plus lent
PLAYER_SPEED = 5.5
PLAYER_JUMP_SPEED = 18.0
PLAYER_MAX_FALL_SPEED = 14.0  # px/frame, vitesse verticale max en chute
PLAYER_COYOTE_TIME = 0.10  # secondes de tolerance pour sauter apres une chute
# PLAYER_RESPAWN_DELAY est la somme des phases REBIRTH_* (plus bas).
# Eclat d'ames bleues sur le totem au moment du respawn.
CHECKPOINT_BURST_COUNT = 22
CHECKPOINT_BURST_LIFE = 0.9
CHECKPOINT_BURST_SPEED_X = 70.0
CHECKPOINT_BURST_SPEED_Y = 110.0
CHECKPOINT_BURST_GRAVITY = 80.0  # ralentit la montee (fontaine d'ames)
CHECKPOINT_BURST_SIZE_MIN = 10.0
CHECKPOINT_BURST_SIZE_MAX = 22.0
CHECKPOINT_BURST_CORE_SIZE = 3.2
CHECKPOINT_BURST_GLOW_ALPHA = 150
CHECKPOINT_BURST_CORE_ALPHA = 220
CHECKPOINT_BURST_SPREAD = 10.0
CHECKPOINT_BURST_MAX = 48
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
PLAYER_DASH_GLOW_SCALE = 3.4
PLAYER_DASH_GLOW_ALPHA = 34
PLAYER_DASH_GLOW_STRETCH = 1.55  # etirement du halo dans l'axe du dash
PLAYER_DASH_GLOW_OFFSET = 0.32  # recul du halo, en fractions de PLAYER_WIDTH
# Trainee de points (fantome cyan / dash jaune).
TRAIL_SPACING = 6.5
TRAIL_MOTES = 2
TRAIL_LIFE = 0.48
TRAIL_SIZE = 4.4
TRAIL_SIZE_MIN = 2.2
TRAIL_ALPHA = 210
TRAIL_JITTER = 3.2
TRAIL_INHERIT = 0.28
TRAIL_DRAG = 3.4
TRAIL_WOBBLE = 16.0
TRAIL_WOBBLE_SPEED = 6.5
TRAIL_CURL = 2.8
TRAIL_MAX = 140
TRAIL_MIN_SPEED = 0.45  # px/frame, en dessous le fantome ne depose plus

# Poussiere au sol : atterrissage (plus si chute haute) et course a fond.
PARTICLE_LAND_MIN_SPEED = 4.0  # px/frame, en dessous : pas de burst
PARTICLE_LAND_MAX_SPEED = 22.0  # px/frame, burst maximal
PARTICLE_LAND_COUNT_MIN = 5
PARTICLE_LAND_COUNT_MAX = 18
PARTICLE_LAND_LIFE = 0.42
PARTICLE_LAND_SPEED_X = 180.0  # px/s
PARTICLE_LAND_SPEED_Y = 140.0
PARTICLE_LAND_GRAVITY = 480.0
PARTICLE_LAND_SIZE_MIN = 3.5
PARTICLE_LAND_SIZE_MAX = 7.5
PARTICLE_RUN_SPEED_RATIO = 0.88  # fraction de PLAYER_SPEED pour declencher
PARTICLE_RUN_INTERVAL = 0.040  # secondes entre deux grains
PARTICLE_RUN_LIFE = 0.28
PARTICLE_RUN_SPEED_X = 55.0
PARTICLE_RUN_SPEED_Y = 36.0
PARTICLE_RUN_SIZE = 3.8
PARTICLE_MAX = 64
PARTICLE_MIN_DRAW_SIZE = 3.0
PARTICLE_FOOT_CLEARANCE = 3.0  # au-dessus du sol, pour ne pas naitre dans la tuile




# --------------------------------------------------------------------------- #
# Forme fantome
# --------------------------------------------------------------------------- #

GHOST_WIDTH = 22
GHOST_HEIGHT = 30
GHOST_SPEED = 6.0
GHOST_ACCEL_TIME = 0.20  # secondes pour atteindre la vitesse visee (plus grand = plus mou)
GHOST_COAST_TIME = 0.48  # secondes pour glisser a l'arret une fois les touches lachees
GHOST_DURATION = 12.0  # duree de base du mode fantome, en secondes
GHOST_DURATION_INCREASE_VALUE = 0.5
GHOST_MAX_RANGE = 480.0  # conserve pour les paliers ; plus de limite de distance en jeu
GHOST_MAX_RANGE_INCREASE_VALUE = 20
GHOST_VISION_RADIUS = 200.0  # rayon de revelation au debut du mode fantome
GHOST_VISION_RADIUS_MIN = 12.0  # rayon en fin de timer (presque rien)
GHOST_VISION_RADIUS_INCREASE_VALUE = 10
# Exposant de fermeture : 1 = lineaire, plus grand = reste large puis se referme d'un coup.
GHOST_VISION_SHRINK_POWER = 5.0
GHOST_CARRY_CAPACITY = 1  # nombre d'objets transportables simultanement
# Filtre plein ecran du mode fantome : distorsion barillet tres legere.
GHOST_WARP_STRENGTH = 0.038  # 0 = identite ; ~2 % aux coins, en debut de timer
GHOST_WARP_STRENGTH_MAX = 0.072  # force en fin de timer, toujours discrete
GHOST_WARP_PERSPECTIVE = 0.55  # etirement vertical relatif a warp
GHOST_WARP_CHROMA = 0.10  # aberration chromatique relative a warp
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
# Plaques d'activation
# --------------------------------------------------------------------------- #

# Epaisseur visuelle de la plaque, posee au sol de la tuile.
PLATE_HEIGHT = 8
# Retrait horizontal de chaque cote, en pixels (la hitbox suit la plaque).
PLATE_INSET = 4
# Halo spectral : epouse la silhouette (pas un blob rond).
MECHANISM_AURA_EDGE = 20.0  # epaisseur max du voile, en px (blocs carres)
MECHANISM_AURA_MIN_PAD = 3.0  # pad mini, meme sur une plaque tres plate
MECHANISM_AURA_AXIS_RATIO = 0.35  # le pad d'un axe ne depasse pas ratio * taille
MECHANISM_AURA_FILL_ALPHA = 16
MECHANISM_AURA_OUTER_SCALE = 1.8  # deuxieme passe, plus large et plus faible
MECHANISM_AURA_PULSE = 0.22
MECHANISM_AURA_MOTE_SPACING = 34.0  # px de perimetre entre deux motes
MECHANISM_AURA_MOTE_SIZE = 11.0
MECHANISM_AURA_MOTE_ALPHA = 40
MECHANISM_AURA_MOTE_DRIFT = 7.0  # px vers l'exterieur de la forme
MECHANISM_AURA_MOTE_SPEED = 0.12  # tours de perimetre par seconde
# Vrilles plaque -> cibles : trainee d'ame, pas un trait.
MECHANISM_LINK_CURVE = 0.26  # amplitude du S, fraction de la longueur
MECHANISM_LINK_FAN = 10.0  # px : ecarte les brins d'une meme plaque
MECHANISM_LINK_WIGGLE = 5.0  # px d'ondulation orthogonale
MECHANISM_LINK_WIGGLE_WAVES = 1.7
MECHANISM_LINK_PULSE_SPEED = 1.15
MECHANISM_LINK_SPACING = 10.0  # px entre deux samples de la courbe
MECHANISM_LINK_MIN_SEGMENTS = 24
MECHANISM_LINK_STAMP_SIZE = 18.0
MECHANISM_LINK_STAMP_ALPHA = 70
MECHANISM_LINK_STAMP_SPACING = 40.0
MECHANISM_LINK_WIDTH = 7.0
MECHANISM_LINK_CORE_WIDTH = 2.5
MECHANISM_LINK_ALPHA = 90
MECHANISM_LINK_CORE_ALPHA = 160
MECHANISM_LINK_MOTE_COUNT = 3
MECHANISM_LINK_MOTE_SIZE = 3.5
MECHANISM_LINK_MOTE_ALPHA = 42
MECHANISM_LINK_MOTE_SPEED = 0.18

# --------------------------------------------------------------------------- #
# Ennemis
# --------------------------------------------------------------------------- #

# Planches "Skeleton_Sword" (squelette blanc, sans VFX) : assets/animations/.
ENEMY_SKELETON_DIR = (
    ANIMATIONS_DIR / "Enemies" / "Skeletons" / "Skeleton_Sword" / "Skeleton_White" / "Skeleton_Without_VFX"
)
ENEMY_SPRITE_IDLE = ENEMY_SKELETON_DIR / "Skeleton_01_White_Idle.png"
ENEMY_SPRITE_WALK = ENEMY_SKELETON_DIR / "Skeleton_01_White_Walk.png"
ENEMY_SPRITE_ATTACK = ENEMY_SKELETON_DIR / "Skeleton_01_White_Attack1.png"
ENEMY_SPRITE_DIE = ENEMY_SKELETON_DIR / "Skeleton_01_White_Die.png"
# Planches natives en 96x64 : le squelette (dessine vers la droite) n'occupe
# qu'une partie de la frame (l'epee balaie le reste pendant les attaques).
ENEMY_FRAME_WIDTH = 96
ENEMY_FRAME_HEIGHT = 64
ENEMY_SCALE = 1.0
# Hitbox rectangulaire = corps visible du squelette, pas la frame entiere.
# Offsets mesures sur les planches idle/walk (voir sprites.apply_rect_hit_box).
ENEMY_WIDTH = 34
ENEMY_HEIGHT = 46
ENEMY_HITBOX_OFFSET_X = 3.0
ENEMY_HITBOX_OFFSET_Y = -9.0
ENEMY_SPEED = 1.6
ENEMY_AGGRO_RANGE = 150.0  # distance de detection du joueur
# Au-dela, on considere que le joueur n'est pas sur le meme "etage" (une
# plateforme au-dessus/en-dessous) : l'ennemi ne peut pas l'atteindre en
# marchant, donc ne doit pas le suivre juste parce qu'il est proche a vol
# d'oiseau. Reste volontairement serre : un saut vers une plateforme passe
# une bonne partie de sa montee hors de cette plage, l'aggro ne se declenche
# donc qu'une fois (presque) arrive a la meme hauteur, pas des le decollage.
ENEMY_AGGRO_VERTICAL_RANGE = 48.0
# Le contact avec le corps ne tue pas : seule la lame tue, pendant les frames
# ou elle est tendue (ENEMY_ATTACK_HIT_FRAMES). L'ennemi declenche son coup a
# ENEMY_ATTACK_RANGE du joueur ; la lame touche jusqu'a ENEMY_ATTACK_REACH
# devant lui (pointe a ~44 px du centre du sprite + demi-largeur du joueur).
# RANGE < REACH : un joueur immobile est touche, un joueur qui recule pendant
# l'armement (frames avant l'impact) esquive.
ENEMY_ATTACK_RANGE = 48.0
ENEMY_ATTACK_REACH = 60.0
ENEMY_ATTACK_VERTICAL_RANGE = 40.0  # tolerance verticale (doit etre a peu pres au meme sol)
# Frames d'Attack1 (0-9) : 1-4 = armement (epee en arriere), 5-7 = lame tendue.
ENEMY_ATTACK_HIT_FRAMES: tuple[int, int] = (5, 7)
ENEMY_ATTACK_COOLDOWN = 0.4  # secondes de pause entre deux coups
ENEMY_CORPSE_SMELL_RANGE = 320.0  # distance d'attraction vers un cadavre
ANIM_ENEMY_IDLE_FRAME_TIME = 0.12
ANIM_ENEMY_WALK_FRAME_TIME = 0.07
ANIM_ENEMY_ATTACK_FRAME_TIME = 0.05
ANIM_ENEMY_DIE_FRAME_TIME = 0.06
ENEMY_GHOST_GLOW_SCALE = 5.6
ENEMY_GHOST_GLOW_ALPHA = 96
ENEMY_GHOST_GLOW_INNER_SCALE = 2.4
ENEMY_GHOST_GLOW_INNER_ALPHA = 170
ENEMY_GHOST_GLOW_PULSE = 0.16
ENEMY_GHOST_GLOW_PULSE_SPEED = 3.4

# --------------------------------------------------------------------------- #
# Objets et progression
# --------------------------------------------------------------------------- #

ITEM_BOB_AMPLITUDE = 4.0  # amplitude du flottement vertical, en pixels
ITEM_BOB_SPEED = 2.5
SOUL_ORB_SIZE = 16
SOUL_ORB_ALPHA = 170
SOUL_ORB_GLOW_SCALE = 4.2
SOUL_ORB_GLOW_ALPHA = 46
SOUL_ORB_GLOW_PULSE = 0.18
SOUL_ORB_GLOW_PULSE_SPEED = 2.8
SOUL_ORB_MAGNET_RANGE = 96.0  # px : l'orbe derive vers le joueur dans ce rayon
SOUL_ORB_MAGNET_SPEED = 42.0  # px / seconde

SOUL_ESSENCE_PER_ORB = 1
# Ames cumulees pour atteindre le niveau n+1 (index = niveau - 1).
# Niveau 1 : 0, 2 : 3, 3 : 8, 4 : 15, 5 : 25, 6 : 40. Bonus : `PALIERS`.
SOUL_LEVEL_THRESHOLDS: tuple[int, ...] = (0, 3, 8, 15, 25, 40)

# --------------------------------------------------------------------------- #
# Couleurs (RGB) - palette provisoire, remplacee par les sprites plus tard
# --------------------------------------------------------------------------- #

COLOR_BACKGROUND = (18, 18, 28)
COLOR_WALL = (72, 76, 96)
COLOR_SPECTRAL_WALL = (96, 84, 140)
COLOR_SPIKE = (196, 84, 84)
COLOR_SPIKE_GLOW = (255, 36, 28)
COLOR_SPIKE_GLOW_CORE = (255, 110, 72)
COLOR_DOOR_LOCKED = (150, 110, 46)
COLOR_DOOR_OPEN = (96, 170, 110)
COLOR_CHECKPOINT = (86, 148, 196)
COLOR_CHECKPOINT_PARTICLE = (90, 186, 255)
COLOR_CHECKPOINT_PARTICLE_CORE = (210, 240, 255)
COLOR_PRESSURE_PLATE = (92, 108, 132)
COLOR_PRESSURE_PLATE_PRESSED = (64, 168, 214)
COLOR_MECHANISM_LINK = (80, 190, 255)
COLOR_MECHANISM_GLOW = (90, 186, 255)
COLOR_PLAYER = (232, 232, 240)
COLOR_GHOST = (128, 200, 255)
COLOR_GHOST_GLOW = (110, 190, 255)
COLOR_TRAIL_GHOST = (132, 214, 255)
COLOR_TRAIL_GHOST_CORE = (230, 248, 255)
COLOR_DEATH_PARTICLE = (150, 214, 255)
COLOR_DEATH_PARTICLE_CORE = (245, 252, 255)
COLOR_CORPSE = (140, 120, 120)
COLOR_ENEMY = (188, 92, 160)
COLOR_ENEMY_GLOW = (255, 28, 22)
COLOR_ENEMY_GLOW_CORE = (255, 92, 64)
COLOR_KEY = (232, 204, 96)
COLOR_SOUL_ORB = (110, 190, 255)
COLOR_HUD_TEXT = (228, 228, 236)
COLOR_HUD_BAR_BACKGROUND = (48, 48, 62)
COLOR_HUD_BAR_FILL = (128, 200, 255)
COLOR_HUD_GHOST_GAUGE = (110, 196, 255)
COLOR_DASH = (255, 214, 120)
COLOR_DASH_GLOW = (255, 224, 150)
COLOR_TRAIL_DASH = (255, 214, 96)
COLOR_TRAIL_DASH_CORE = (255, 250, 210)
COLOR_DASH_GAUGE = (255, 186, 72)
COLOR_TORCH_STEM = (94, 58, 34)
COLOR_TORCH_FLAME = (255, 158, 52)
COLOR_TORCH_GLOW = (255, 132, 36)
COLOR_TORCH_GLOW_CORE = (255, 220, 130)
COLOR_DUST = (236, 228, 208)
COLOR_DUST_DARK = (186, 174, 150)
COLOR_MENU_TITLE = (200, 220, 255)
COLOR_MENU_HINT = (150, 155, 175)

# Opacite du voile hors du champ de vision du fantome (0-255).
FOG_ALPHA = 235
# Part du rayon entierement transparente au centre (0 = degrade des le centre).
GHOST_VISION_CLEAR_RATIO = 0.0
# Courbe du degrade (1 = lineaire, plus grand = bord plus sec).
GHOST_VISION_FALLOFF_POWER = 2.5

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
# Zoom : > 1.0 rapproche (corps), < 1.0 eloigne (fantome). La transition entre
# les deux, lissee par CAMERA_ZOOM_SMOOTH_TIME, donne l'effet de projection
# hors du corps (la camera recule) quand on passe humain -> fantome.
CAMERA_ZOOM_PLAYER = 1.18
CAMERA_ZOOM_GHOST = 0.82
CAMERA_ZOOM_SMOOTH_TIME = 0.55
# Mort -> fantome : gros plan rapide, secousse + particules, puis recul.
CAMERA_ZOOM_DEATH = 1.82
DEATH_ZOOM_IN_TIME = 0.28
DEATH_BURST_TIME = 0.50
DEATH_ZOOM_OUT_TIME = 0.78
DEATH_CAMERA_LOCK_TIME = 0.06
CAMERA_DEATH_SHAKE = 4.4
CAMERA_DEATH_SHAKE_TIME = 0.42
CAMERA_DEATH_POP_SHAKE = 2.8
CAMERA_DEATH_POP_SHAKE_TIME = 0.18
DEATH_POP_AT = 0.38  # part de DEATH_BURST_TIME ou le fantome "sort"
DEATH_EMERGE_LIFT = 28.0
DEATH_EMERGE_SCALE = 0.32
DEATH_FLASH_SIZE = 160.0
DEATH_FLASH_ALPHA = 200
DEATH_PARTICLE_COUNT = 90
DEATH_PARTICLE_STREAM_INTERVAL = 0.028
DEATH_PARTICLE_STREAM_COUNT = 7
DEATH_PARTICLE_LIFE = 0.78
DEATH_PARTICLE_SPEED = 220.0
DEATH_PARTICLE_SPEED_UP = 140.0
DEATH_PARTICLE_GRAVITY = 55.0
DEATH_PARTICLE_SIZE_MIN = 7.0
DEATH_PARTICLE_SIZE_MAX = 20.0
DEATH_PARTICLE_SPREAD = 8.0
DEATH_PARTICLE_MAX = 200
DEATH_PARTICLE_GLOW_ALPHA = 170
DEATH_PARTICLE_CORE_ALPHA = 230
DEATH_PARTICLE_CORE_SIZE = 3.4
# Fantome -> corps : voile noir, reconstruction par particules, puis reveal.
REBIRTH_FADE_OUT_TIME = 0.26
REBIRTH_FORM_TIME = 0.58
REBIRTH_REVEAL_TIME = 0.42
REBIRTH_PLAYER_AT = 0.38  # part de FORM ou le sprite apparait
REBIRTH_HUD_AT = 0.42  # part de REVEAL ou le HUD commence a revenir
CAMERA_ZOOM_REBIRTH = 1.38
CAMERA_REBIRTH_SHAKE = 3.2
CAMERA_REBIRTH_SHAKE_TIME = 0.28
REBIRTH_FLASH_SIZE = 150.0
REBIRTH_FLASH_ALPHA = 210
REBIRTH_PARTICLE_COUNT = 70
REBIRTH_PARTICLE_STREAM_INTERVAL = 0.024
REBIRTH_PARTICLE_STREAM_COUNT = 5
REBIRTH_PARTICLE_LIFE = 0.72
REBIRTH_PARTICLE_SPEED = 190.0
REBIRTH_PARTICLE_RADIUS = 118.0
REBIRTH_PARTICLE_RADIUS_MIN = 36.0
REBIRTH_PARTICLE_SIZE_MIN = 6.0
REBIRTH_PARTICLE_SIZE_MAX = 16.0
REBIRTH_PARTICLE_MAX = 160
REBIRTH_PARTICLE_GLOW_ALPHA = 165
REBIRTH_PARTICLE_CORE_ALPHA = 230
REBIRTH_PARTICLE_CORE_SIZE = 3.2
COLOR_REBIRTH_VEIL = (0, 0, 0)
COLOR_REBIRTH_PARTICLE = (214, 216, 228)
COLOR_REBIRTH_PARTICLE_CORE = (250, 252, 255)
PLAYER_RESPAWN_DELAY = REBIRTH_FADE_OUT_TIME + REBIRTH_FORM_TIME + REBIRTH_REVEAL_TIME

# --------------------------------------------------------------------------- #
# Icones clavier (Kenney Input Prompts, dans assets/ui/)
# --------------------------------------------------------------------------- #

UI_KEYBOARD_LETTERS = "Keyboard Letters and Symbols.png"
UI_KEYBOARD_EXTRAS = "Keyboard Extras.png"
UI_KEY_CELL = 16  # taille native d'une touche-lettre
UI_KEY_ICON_HEIGHT = 40  # hauteur a l'ecran (nearest-neighbor)
UI_KEY_CAPTION_SIZE = 16  # libelles a cote des icones

# Jauge unique bas-centre : dash (corps) ou timer (fantome).
HUD_GAUGE_WIDTH = 168
HUD_GAUGE_HEIGHT = 10
HUD_GAUGE_ICON = 22
HUD_GAUGE_GAP = 8
HUD_GAUGE_LIFT = 10  # au-dessus des icones clavier
HUD_GAUGE_LOW = 0.22  # le timer fantome pulse sous ce ratio

# --------------------------------------------------------------------------- #
# Debug
# --------------------------------------------------------------------------- #

DEBUG_OVERLAY = True  # panneau : FPS, etat, tuiles a l'ecran, positions (F3 en jeu)
DEBUG_SHOW_HITBOXES = False
DEBUG_SHOW_FPS = True  # si l'overlay est off, affiche quand meme le FPS en bas a gauche
COLOR_DEBUG = (140, 230, 160)
COLOR_DEBUG_PANEL = (8, 12, 18, 180)
COLOR_DEBUG_HITBOX = (80, 255, 120, 200)

# --------------------------------------------------------------------------- #
# Editeur de niveaux (tools/level_editor.py)
# --------------------------------------------------------------------------- #

EDITOR_TITLE = "Project Astral - Editeur de niveaux"
EDITOR_WINDOW_WIDTH = 1440
EDITOR_WINDOW_HEIGHT = 860
# Dimensions d'une carte creee depuis l'editeur, en tuiles.
EDITOR_NEW_COLUMNS = 60
EDITOR_NEW_ROWS = 34
EDITOR_MIN_COLUMNS = 8
EDITOR_MIN_ROWS = 8
EDITOR_MAX_COLUMNS = 600
EDITOR_MAX_ROWS = 300
EDITOR_HISTORY_LIMIT = 250  # nombre d'actions annulables
EDITOR_PANEL_WIDTH = 320  # largeur du panneau de droite (palette)
EDITOR_STATUS_HEIGHT = 78  # hauteur de la barre d'etat du bas
EDITOR_ROW_HEIGHT = 34  # hauteur d'une ligne de palette
EDITOR_SWATCH_SIZE = 26  # cote d'une vignette de palette
EDITOR_TEXT_SIZE = 12
EDITOR_TITLE_SIZE = 14
EDITOR_ZOOM_MIN = 0.25
EDITOR_ZOOM_MAX = 6.0
EDITOR_ZOOM_DEFAULT = 1.25  # 1.0 = une tuile = TILE_SIZE pixels a l'ecran
EDITOR_ZOOM_STEP = 1.15  # facteur par cran de molette
EDITOR_PAN_SPEED = 1100.0  # pixels ecran par seconde aux fleches
EDITOR_GRID_MIN_ZOOM = 0.45  # sous ce zoom, la grille n'est plus tracee
EDITOR_MESSAGE_TIME = 3.0  # secondes d'affichage d'un message de statut
EDITOR_FLOOD_LIMIT = 20000  # garde-fou du remplissage par zone
EDITOR_MAPS_GLOB = "*.json"

COLOR_EDITOR_BACKGROUND = (13, 14, 20)
COLOR_EDITOR_PANEL = (22, 24, 34)
COLOR_EDITOR_PANEL_BORDER = (54, 58, 78)
COLOR_EDITOR_ROW_ACTIVE = (46, 62, 88)
COLOR_EDITOR_ROW_HOVER = (34, 38, 52)
COLOR_EDITOR_GRID = (40, 44, 60)
COLOR_EDITOR_BOUNDS = (120, 132, 172)
COLOR_EDITOR_TEXT = (226, 228, 238)
COLOR_EDITOR_TEXT_DIM = (138, 145, 168)
COLOR_EDITOR_ACCENT = (128, 200, 255)
COLOR_EDITOR_WARNING = (255, 186, 72)
COLOR_EDITOR_DANGER = (240, 96, 96)
COLOR_EDITOR_OK = (120, 210, 140)
COLOR_EDITOR_SELECTION = (128, 200, 255, 55)
COLOR_EDITOR_SELECTION_BORDER = (176, 224, 255)
COLOR_EDITOR_PASTE = (255, 214, 120, 60)
COLOR_EDITOR_HOVER = (255, 255, 255, 38)
COLOR_EDITOR_UNKNOWN = (150, 90, 190)
COLOR_EDITOR_OVERLAY = (8, 10, 16, 235)
