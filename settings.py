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

# Bruitages (`assets/sons/`). Fichier manquant = silence, pas de crash.
# Version nettoyee du coup d'epee : l'original a ~570 ms de silence en tete.
SOUND_ATTACK = "attack_sword_sync.wav"
SOUND_ATTACK_FALLBACK = ":resources:sounds/hit1.wav"
SOUND_LEVEL_WIN = "level-win.wav"
SOUND_SOUL_GET = "soul_get.wav"
SOUND_CHECKPOINT = "checkpoint_set.wav"
SOUND_KEY_FOUND = "key_found.wav"
SOUND_MENU_CLICK = "menu-click.wav"
SOUND_MENU_HOVER = "menu_hover.wav"
SOUND_MOB_HIT = "mob_hit.wav"
SOUND_GHOST_START = "ghost_start.wav"
SOUND_GHOST_END = "ghost_end.wav"
SOUND_DASH = "dash.wav"
# Temporaire : pas de sample de saut dedie, on reutilise le dash.
SOUND_JUMP = "dash.wav"
SOUND_BOSS_FIRE = "boss-fire.wav"
SOUND_RESPAWN = "respawn.wav"
SOUND_FOOTSTEP = "Steps_dirt-001.ogg"
SOUND_VOLUME_ATTACK = 0.45
SOUND_VOLUME_LEVEL_WIN = 0.6
SOUND_VOLUME_SOUL_GET = 0.7
SOUND_VOLUME_CHECKPOINT = 0.65
SOUND_VOLUME_KEY_FOUND = 0.65
SOUND_VOLUME_MENU_CLICK = 0.5
SOUND_VOLUME_MENU_HOVER = 0.35
SOUND_VOLUME_MOB_HIT = 0.55
SOUND_VOLUME_GHOST_START = 0.65
SOUND_VOLUME_GHOST_END = 0.65
SOUND_VOLUME_DASH = 0.55
SOUND_VOLUME_JUMP = 0.48
SOUND_VOLUME_BOSS_FIRE = 0.7
SOUND_VOLUME_RESPAWN = 0.65
SOUND_VOLUME_FOOTSTEP = 0.4
SOUND_VOLUME_FOOTSTEP_LAND = 0.55
SOUND_FOOTSTEP_PITCH_MIN = 0.92
SOUND_FOOTSTEP_PITCH_MAX = 1.08
# Echo "caverne" : copies plus faibles et un peu plus graves, pour le vide.
SOUND_ECHO_DELAY = 0.22
SOUND_ECHO_DECAY = 0.34
SOUND_ECHO_TAPS = 2
SOUND_ECHO_SPEED = 0.97
SOUND_ECHO_FOOTSTEP_DELAY = 0.12
SOUND_ECHO_FOOTSTEP_DECAY = 0.22
SOUND_ECHO_FOOTSTEP_TAPS = 1

# --------------------------------------------------------------------------- #
# Police
# --------------------------------------------------------------------------- #

# Chargee une fois au demarrage (`main.create_window`) via `arcade.load_font`.
# "Press Start 2P" est le nom de famille tel qu'embarque dans le fichier .ttf
# (Google Fonts, licence OFL) : c'est ce nom qu'il faut passer a chaque
# `arcade.Text(font_name=...)`.
FONT_FILE = FONTS_DIR / "PressStart2P-Regular.ttf"
FONT_PIXEL = "Press Start 2P"
# Panneau editeur : police proportionnelle, lisible en petit (Press Start 2P
# a 10 px devenait du bruit). Fallback systeme, pas de fichier extra.
EDITOR_UI_FONT = ("Segoe UI", "Calibri", "Arial", "Helvetica")

# Ordre de parcours des niveaux : le nom du fichier dans assets/maps/.
LEVEL_SEQUENCE: tuple[str, ...] = (
    "level_1_tuto.json",
    "Niveau_1-1.json",
    "Niveau_1-2.json",
    "Niveau_1-3.json",
    "Niveau_1-4.json",
    "Niveau_1-5.json",
    "Niveau_1-6.json",
    "Niveau_Bonus_ouvert.json",
)

# --------------------------------------------------------------------------- #
# Fenetre
# --------------------------------------------------------------------------- #

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_MIN_WIDTH = 640
SCREEN_MIN_HEIGHT = 360
START_FULLSCREEN = True
GAME_TITLE = "Out Of Body!"
SCREEN_TITLE = GAME_TITLE
FPS = 60
FRAME_TIME = 1 / FPS

# Etendue de monde (en unites monde, = pixels a zoom 1) que la camera montre
# a l'ecran, quelle que soit la taille reelle de la fenetre/du moniteur. Sans
# ca, passer en plein ecran revelerait plus de niveau (donc plus de chunks a
# soumettre au rendu) et ferait chuter le FPS rien qu'a cause du changement
# de dimensions : voir `CameraRig` dans `src/world/camera.py`.
WORLD_VIEW_WIDTH = SCREEN_WIDTH
WORLD_VIEW_HEIGHT = SCREEN_HEIGHT
# Pixels du framebuffer hors-ecran par pixel de conception. 2 = image 2560x1440
# pour une vue 1280x720 : le zoom camera (2.4) et le plein ecran restent nets.
# Le nombre de chunks soumis ne change pas (le cadrage monde est identique).
RENDER_SCALE = 2

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

# Identifiants de TYPE de tuile (legende JSON / TILE_SPECS). Ce ne sont PAS
# des noms de fichiers sprite : les confondre cassait le chargeur.
TILE_KIND_ICE = "ice_block"
TILE_KIND_FALLING = "falling_block"
TILE_KIND_HIDDEN = "hidden_wall"
TILE_KIND_SPRING = "spring"

# Noms de fichiers dans SPRITES_DIR, sans extension. Le chargeur ajoute `.png`.
# Le terrain (dirt/grass/...) vient desormais de `SHEET_GROUND` plus bas
# (planche "new_textures") : les anciens PNG individuels (dirt_1.png,
# grass.png, ...) restent dans `assets/sprites/` mais ne sont plus charges.
SPRITE_SPIKE = "spike"
SPRITE_SPIKE_HANGING = "spike_up"
# Bandeaux d'entites (fichiers tels quels, y compris le typo "gost").
SPRITE_PLAYER_WALK = "player_walk"
SPRITE_PLAYER_IDLE = "player_idle"
SPRITE_PLAYER_ATTACK = "player_attack_1"
SPRITE_PLAYER_DEATH = "player_death"
SPRITE_PLAYER_BONES = "player_bones"
SPRITE_BOSS_WALK = "boss_walk"
SPRITE_BOSS_SHOT = "boss_shot"
SPRITE_BOSS_LASER = "boss_laser-shot"
SPRITE_BOSS_DEATH = "boss_death"
SPRITE_BOSS_BEAM = "Laser_sheet"
SPRITE_BOSS_PROJECTILE = "arm_projectile_glowing"
SPRITE_GHOST_WALK = "gost_walk"
SPRITE_GHOST_DISAPPEAR = "gost_disappears"
SPRITE_KEY = "key"
SPRITE_DOOR_CLOSED = "door_close"
SPRITE_DOOR_OPEN = "door_open"
SPRITE_CHECKPOINT = "phoenix_resurrection-desactive"
SPRITE_CHECKPOINT_ACTIVE = "phoenix_resurrection-active"
SPRITE_FLAMETHROWER = "Lance_flamme"
# Art natif 125 px ; affiche ~3 tuiles, pieds cales sur la case.
CHECKPOINT_SIZE = TILE_SIZE * 3
# Porte : art 32x32 affiche sur 2 tuiles de haut (meme collision qu'avant).
DOOR_DISPLAY_SIZE = TILE_SIZE * 2
# Flash au vantail ouvert (juice), puis delai avant de valider le niveau :
# laisse le temps de voir la porte s'ouvrir avant l'ecran de victoire.
DOOR_OPEN_FLASH_TIME = 0.5
DOOR_OPEN_FLASH_SIZE = 60.0
DOOR_OPEN_FLASH_ALPHA = 200
DOOR_WIN_DELAY = 0.9
SPRITE_FRAME_SIZE = 32
# Taille a l'ecran des sprites joueur / fantome (1.0 = 32 px).
# L'agrandissement est fait en nearest-neighbor dans `load_strip`.
ENTITY_SCALE = 1.5
ANIM_WALK_FRAME_TIME = 0.07
ANIM_IDLE_FRAME_TIME = 0.12
ANIM_PLAYER_ATTACK_FRAME_TIME = 0.03
ANIM_PLAYER_DEATH_FRAME_TIME = 0.12  # pose de chute, avant le fondu
ANIM_PLAYER_DEATH_BLEND_TIME = 0.16  # fondu vers le corps au sol
ANIM_GHOST_DISAPPEAR_FRAME_TIME = 0.08
# 1.0 = rythme de base ; plus petit = plus lent (0.5 = deux fois plus lent).
ANIM_SPEED = 0.5

# Torche (placeholder, pas de collision)
TORCH_WIDTH = 8
TORCH_HEIGHT = 12
TORCH_STEM_WIDTH = 3
TORCH_STEM_HEIGHT = 10
TORCH_GLOW_OUTER = 168.0
TORCH_GLOW_MID = 78.0
TORCH_GLOW_INNER = 28.0
TORCH_GLOW_ALPHA = 145
TORCH_GLOW_MID_ALPHA = 200
TORCH_GLOW_INNER_ALPHA = 245
TORCH_FLICKER = 0.16
TORCH_FLICKER_SPEED = 8.4
TORCH_FLICKER_SPEED_FAST = 19.0

# --------------------------------------------------------------------------- #
# Planches "new_textures" (pack de remplacement des tuiles de terrain)
# --------------------------------------------------------------------------- #

NEW_TEXTURES_DIR = SPRITES_DIR / "new_textures"
SHEET_GROUND = NEW_TEXTURES_DIR / "TX Tileset Ground.png"
SHEET_GROUND_SAND = NEW_TEXTURES_DIR / "TX Tileset Sand.png"
SHEET_GROUND_ROCK = NEW_TEXTURES_DIR / "TX Tileset Rock.png"
SHEET_PROPS = NEW_TEXTURES_DIR / "TX Village Props.png"
SHEET_CHEST = NEW_TEXTURES_DIR / "TX Chest Animation.png"

# Theme de terrain d'une carte (`"theme"` dans le JSON). Meme grille 16x16,
# seule la planche change. Absent ou vide -> ground.
GROUND_THEME_DEFAULT = "ground"
GROUND_THEMES: dict[str, Path] = {
    "ground": SHEET_GROUND,
    "sand": SHEET_GROUND_SAND,
    "rock": SHEET_GROUND_ROCK,
}
GROUND_THEME_LABELS: dict[str, str] = {
    "ground": "terre",
    "sand": "sable",
    "rock": "roche",
}

# Taille native d'une case de `SHEET_GROUND` (planche a grille reguliere).
GROUND_CELL = 32

# Auto-tiling du terrain ("wall" : seule matiere terre/roche du jeu, symbole
# "#" dans une carte). `obstacles.terrain_texture` choisit la case a afficher
# selon les 8 voisines : voir `obstacles.compute_ground_cells`. Le level
# designer ne pose qu'un seul type de mur ; le rendu se charge du reste.
#
# Toutes les coordonnees ci-dessous sont des cases (colonne, ligne) de
# GROUND_CELL px, (0,0) = coin haut-gauche de la planche `SHEET_GROUND`.
# La planche est une fresque 16x16 : beaucoup de cases "de scene" sont vides
# ou entaillees et ne tuilent pas. Cases du mapping absentes de ce PNG :
# (4,2), (5,3), (5,5), (6,0), (6,1), (6,2), (6,4), (7,4), (8,0), (9,4), (9,6),
# (1,8), (1,9), (1,10), (1,11), (3,8), (3,9), (0,11), (4,4).
#
# 1) Carre 3x3 en haut a gauche = case CANONIQUE de la masse profonde :
#
#            colonne 0          colonne 1           colonne 2
#            (rien a gauche)    (encadree)          (rien a droite)
#   rangee 0 : Coin Sombre HG   Bord Sombre Haut    Coin Sombre HD
#   rangee 1 : Bord Sombre G    Centre Sombre       Bord Sombre D
#   rangee 2 : Coin Sombre BG   Bord Sombre Bas     Coin Sombre BD
#
# 2) Terre, dessous et plateformes ont un POOL de variantes (position
#    deterministe, meme rendu jeu/editeur). La crete de pelouse reste
#    Bord Sombre Haut, sans fragment de fresque.
GROUND_ROW_GRASS = 0  # rien au-dessus -> Bord Sombre Haut
GROUND_ROW_DIRT = 1  # enterree des deux cotes -> Centre Sombre
GROUND_ROW_BOTTOM = 2  # rien en dessous -> Bord Sombre Bas
GROUND_COL_LEFT = 0  # rien a gauche
GROUND_COL_MID = 1  # encadree des deux cotes
GROUND_COL_RIGHT = 2  # rien a droite

# Cas particuliers hors du carre 3x3, cf. `obstacles._base_ground_cell`.
# (4,2) Petit Bloc Herbe est vide : (4,3) est le bloc herbe isole disponible.
GROUND_SOLO = (4, 3)

# Colonne d'UNE tuile de large. (6,0)/(6,1)/(6,2) Sommet/Milieu/Base Fine
# Colonne sont vides : on prend le pilier gauche, deja un sprite d'une tuile
# de large (bords arrondis). (0,11) Base Pilier est vide, (0,10) sert de pied.
GROUND_PILLAR_TOP = (0, 8)
GROUND_PILLAR_MID = (0, 9)
GROUND_PILLAR_BOTTOM = (0, 10)

# Plateforme fine (une seule tuile de haut).
GROUND_PLATFORM_LEFT = (0, 12)
GROUND_PLATFORM_MID = (1, 12)
GROUND_PLATFORM_RIGHT = (2, 12)

# Bloc creux / tunnel (anneau 0-2 x 4-6, trou en (1,5)).
GROUND_CAVE_CEILING_LEFT = (0, 4)  # Coin Plafond HG
GROUND_CAVE_CEILING = (1, 4)  # Plafond Tunnel
GROUND_CAVE_CEILING_RIGHT = (2, 4)  # Coin Plafond HD
GROUND_CAVE_WALL_LEFT = (0, 5)  # Mur Tunnel Gauche
GROUND_CAVE_WALL_RIGHT = (2, 5)  # Mur Tunnel Droit
GROUND_CAVE_FLOOR_LEFT = (0, 6)  # Coin Sol Herbe BG
GROUND_CAVE_FLOOR = (1, 6)  # Sol Herbe Tunnel
GROUND_CAVE_FLOOR_RIGHT = (2, 6)  # Coin Sol Herbe BD

# Coins interieurs d'un trou enterre (memes sprites que le tunnel).
GROUND_INNER_BOTTOM_RIGHT = GROUND_CAVE_CEILING_LEFT  # trou en SE
GROUND_INNER_BOTTOM_LEFT = GROUND_CAVE_CEILING_RIGHT  # trou en SW
GROUND_INNER_TOP_RIGHT = GROUND_CAVE_FLOOR_LEFT  # trou en NE, grotte seulement
GROUND_INNER_TOP_LEFT = GROUND_CAVE_FLOOR_RIGHT  # trou en NW, grotte seulement

# Ilot 2x2 flottant (coins arrondis, transparence volontaire).
GROUND_ISLAND_TL = (12, 0)
GROUND_ISLAND_TR = (13, 0)
GROUND_ISLAND_BL = (12, 1)
GROUND_ISLAND_BR = (13, 1)

# La crete marchable d'une masse profonde est TOUJOURS Bord Sombre Haut
# (1,0). Les cases (8,3)/(10,3)/(11,3)/(12,3)/(13,3) ont de l'herbe mais
# un profil different (fresque) : en variante, elles cassent la ligne de
# surface. Pas de pool : `_pick_variant` laisse (1,0) tel quel.
GROUND_SURFACE_VARIANTS = ((1, 0),)
# Terre pleine uniforme : aucun caillou, aucune herbe, aucun plafond estompe.
# (10,5) a des rochers jaunes : en variante de fill, ca poivrait la masse.
GROUND_DIRT_VARIANTS = (
    (1, 1),
    (11, 4),
    (12, 4),
    (12, 7),
    (5, 10),
)
# Dessous a l'air libre, sans herbe (les cases (5,15)/(9,15) sont des sols
# herbeux de la fresque : au plafond du monde elles affichaient de l'herbe).
GROUND_BOTTOM_VARIANTS = ((1, 2), (7, 15), (14, 15))
# Plafond de grotte : uniquement le sprite du bloc creux, pas la fresque.
GROUND_CAVE_CEILING_VARIANTS = (GROUND_CAVE_CEILING,)
GROUND_SOLO_VARIANTS = (GROUND_SOLO, (9, 0))
GROUND_PLATFORM_LEFT_VARIANTS = ((0, 12), (0, 14))
GROUND_PLATFORM_MID_VARIANTS = ((1, 12), (1, 14))
GROUND_PLATFORM_RIGHT_VARIANTS = ((2, 12), (2, 14))

GROUND_BEDROCK = (11, 8)
# Le socle (bordure indestructible) reprend une tuile hors du carre 3x3 de
# "wall" et se voit assombri d'un cran : lisible comme "plus dur", distinct
# du mur normal, sans nouvel asset.
COLOR_BEDROCK_TINT = (176, 176, 184)

# Les decoupages des props vivent dans `world/decorations.py`. Un pixel de
# `SHEET_PROPS` vaut un pixel de `SHEET_GROUND` ; le jeu les affiche via
# `TILE_SIZE / GROUND_CELL` (1.0 tant que les tuiles font 32 px).
# Lance-flammes : le jet est un quad shader, pas des particules.
FLAMETHROWER_RANGE = 4  # portee par defaut, en tuiles
FLAMETHROWER_RANGE_MIN = 1
FLAMETHROWER_RANGE_MAX = 12
FLAMETHROWER_INTERVAL = 2.0  # periode complete allume/eteint, en secondes
FLAMETHROWER_INTERVAL_MIN = 0.4
FLAMETHROWER_INTERVAL_MAX = 8.0
FLAMETHROWER_INTERVAL_STEP = 0.2
FLAMETHROWER_ON_RATIO = 0.42  # fraction de la periode ou le jet est allume
FLAMETHROWER_RAMP = 0.14  # fondu d'allumage / extinction
FLAMETHROWER_LETHAL_INTENSITY = 0.28
FLAMETHROWER_HEIGHT = 42.0  # epaisseur du jet, en pixels (braises, pas un laser)
FLAMETHROWER_NOZZLE = 0.5  # depart du jet, en fraction de tuile depuis le centre (face avant)
FLAMETHROWER_VISUAL_PAD = 32.0  # marge du quad (pointe et cotes) pour la calotte et le halo
FLAMETHROWER_ALWAYS_ON = 0.0  # intervalle 0 = jet permanent


# --------------------------------------------------------------------------- #
# Physique du corps physique (joueur vivant)
# --------------------------------------------------------------------------- #

GRAVITY = 1.0
SPIKE_FALL_GRAVITY = GRAVITY
SPIKE_FALL_MAX_SPEED = 14.0
SPIKE_HITBOX_WIDTH_RATIO = 0.6
# Halo des piques en mode fantome (visible a travers le voile).
SPIKE_GHOST_GLOW_SCALE = 3.4
SPIKE_GHOST_GLOW_ALPHA = 110
SPIKE_GHOST_GLOW_INNER_SCALE = 1.7
SPIKE_GHOST_GLOW_INNER_ALPHA = 180
SPIKE_GHOST_GLOW_PULSE = 0.14
SPIKE_GHOST_GLOW_PULSE_SPEED = 3.2

# Blocs tombants : delay apres le pas du joueur, puis chute sans collision
# avec le terrain, puis respawn a la position d'origine.
FALLING_BLOCK_DELAY = 0.45
FALLING_BLOCK_DELAY_MIN = 0.05
FALLING_BLOCK_DELAY_MAX = 4.0
FALLING_BLOCK_DELAY_STEP = 0.05
FALLING_BLOCK_RESPAWN = 2.0
FALLING_BLOCK_RESPAWN_MIN = 0.2
FALLING_BLOCK_RESPAWN_MAX = 12.0
FALLING_BLOCK_RESPAWN_STEP = 0.2
FALLING_BLOCK_GRAVITY = GRAVITY
FALLING_BLOCK_MAX_SPEED = 12.0
FALLING_BLOCK_SHAKE = 1.6  # pixels, pendant le delay

# Ressorts : H dans l'editeur cycle up / right / down / left.
# Vertical : conserve change_x, impose une montee d'environ SPRING_LAUNCH_TILES
# tuiles (v=13.6 et gravite 0.40 : ~7 tuiles). Horizontal : inverse change_x.
SPRING_LAUNCH_TILES = 7.0
SPRING_LAUNCH_SPEED = 13.6
SPRING_MIN_SPEED = 1.0  # si l'elan horizontal est quasi nul, on pousse au moins ca
SPRING_APPROACH = 0.05  # deja en train de s'eloigner si la vitesse projetee depasse
SPRING_COOLDOWN = 0.12
SPRING_HORIZONTAL_LOCK = 0.18  # ignore le frein aerien juste apres un rebond lateral

# Halo rouge des menaces (piques et ennemis), perce le voile fantome.
# Gros, saturé, identique pour les deux : un signal DANGER, pas un point.
HAZARD_GHOST_GLOW_SIZE = 260.0
HAZARD_GHOST_GLOW_MID_SIZE = 128.0
HAZARD_GHOST_GLOW_INNER_SIZE = 58.0
HAZARD_GHOST_GLOW_ALPHA = 175
HAZARD_GHOST_GLOW_MID_ALPHA = 210
HAZARD_GHOST_GLOW_INNER_ALPHA = 245
HAZARD_GHOST_GLOW_PULSE = 0.28
HAZARD_GHOST_GLOW_PULSE_SPEED = 4.8
PLAYER_WIDTH = SPRITE_FRAME_SIZE
PLAYER_HEIGHT = SPRITE_FRAME_SIZE
# Largeur de hitbox (physique), plus etroite que PLAYER_WIDTH : le moteur ne
# fait tomber le joueur qu'une fois la hitbox entiere passee du bord (les 2
# "pieds" dans le vide) ; la caler sur toute la largeur des epaules (~18 px)
# laisse pendre la moitie du sprite au-dessus du vide avant de tomber. Mesure
# des pieds au sol sur player_idle/walk.png (dernieres lignes de la frame,
# pose de repos) : x=[10,22] sur 32 (largeur ~13 px).
# La hauteur reste PLAYER_HEIGHT (le saut/la gravite n'y touchent pas).
PLAYER_HITBOX_WIDTH = 14
PLAYER_GRAVITY = 0.40  # gravite de montee maintenue (le moteur l'applique toujours)
PLAYER_SPEED = 5.5
# NSMB DS : impulsion nette, puis arc lent (~0.45 s au pic, ~4.5 tuiles).
PLAYER_JUMP_SPEED = 8.8
PLAYER_JUMP_RUN_BONUS = 1.8  # impulsion extra a pleine vitesse, comme un saut de course
PLAYER_JUMP_RISE_GRAVITY = 0.40
# Relacher augmente la gravite, sans ecraser la vitesse (hauteur analogique).
PLAYER_JUMP_CUT_GRAVITY = 0.88
PLAYER_JUMP_FALL_GRAVITY = 0.52  # un peu plus lourd a la descente
PLAYER_MAX_FALL_SPEED = 6.5
PLAYER_COYOTE_TIME = 0.12
PLAYER_JUMP_BUFFER = 0.12
# En l'air, on garde l'elan ; inverser la direction reste possible.
PLAYER_AIR_BRAKE_TIME = 0.90
PLAYER_AIR_TURN_BOOST = 1.35
# PLAYER_RESPAWN_DELAY est la somme des phases REBIRTH_* (plus bas).
# Eclat d'ames bleues sur la statue au moment du respawn.
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
# Halo de la statue : eteint au repos, flash a l'activation, pulse tant qu'elle est active.
CHECKPOINT_GLOW_LIFT = 0.10  # fraction de la hauteur, vers le phenix
CHECKPOINT_GLOW_WASH = 340.0  # nappe large, derriere la statue
CHECKPOINT_GLOW_OUTER = 240.0
CHECKPOINT_GLOW_MID = 118.0
CHECKPOINT_GLOW_INNER = 44.0
CHECKPOINT_GLOW_WIDTH_SCALE = 1.38  # halo plus large que haut
CHECKPOINT_GLOW_WASH_ALPHA = 52
CHECKPOINT_GLOW_ALPHA = 70
CHECKPOINT_GLOW_MID_ALPHA = 108
CHECKPOINT_GLOW_INNER_ALPHA = 145
CHECKPOINT_GLOW_PULSE = 0.14
CHECKPOINT_GLOW_PULSE_SPEED = 2.15
CHECKPOINT_IGNITE_TIME = 0.9
CHECKPOINT_IGNITE_PEAK = 2.15  # taille au pic du flash
CHECKPOINT_IGNITE_ALPHA = 2.4
CHECKPOINT_IGNITE_FLASH_SIZE = 380.0
CHECKPOINT_IGNITE_FLASH_ALPHA = 180
CHECKPOINT_IGNITE_RISE = 0.18  # part du flash consacree a la montee
# Temps pour atteindre PLAYER_SPEED en maintenant une direction au sol.
PLAYER_ACCEL_TIME = 0.25
# Glissade a l'arret (sol) : 2-3 frames, quelques pixels tout au plus.
PLAYER_SLIDE_TIME = 0.01
# Glace : quasi pas de frein. Dash ou cadavre pour s'arreter.
PLAYER_ICE_SLIDE_TIME = 9.0
PLAYER_ICE_ACCEL_SCALE = 0.10
PLAYER_ICE_TURN_SCALE = 0.32  # multiplier encore plus faible en demi-tour
PLAYER_ICE_STOP_SPEED = 0.015
# Fraction de l'acceleration au sol quand le joueur est en l'air (1 = aussi vif qu'au sol).
PLAYER_AIR_CONTROL = 1.15
# Ralentissement juste apres l'atterrissage.
PLAYER_LANDING_SLOW_TIME = 0.12
PLAYER_LANDING_SPEED_SCALE = 0.86
# Pas : one-shot a intervalle fixe (la planche walk n'a que 3 frames).
PLAYER_FOOTSTEP_INTERVAL = 0.22
PLAYER_FOOTSTEP_SPEED = 1.2
# Dash horizontal (Shift), vitesse en px/frame, duree et recharge en secondes.
# ~2x la course : un burst court, pas une teleportation.
PLAYER_DASH_SPEED = 22.0
PLAYER_DASH_DURATION = 0.12
PLAYER_DASH_COOLDOWN = 3.0
PLAYER_DASH_READY_FLASH = 0.38
PLAYER_DASH_GLOW_SCALE = 3.4
PLAYER_DASH_GLOW_ALPHA = 34
PLAYER_DASH_GLOW_STRETCH = 1.55  # etirement du halo dans l'axe du dash
PLAYER_DASH_GLOW_OFFSET = 0.32  # recul du halo, en fractions de PLAYER_WIDTH
# Attaque de melee du joueur (clic gauche).
PLAYER_ATTACK_RANGE = 42.0  # portee du premier coup, conservee pour compatibilite
PLAYER_ATTACK_RANGES: tuple[float, ...] = (42.0, 50.0, 62.0)
PLAYER_ATTACK_DURATION = 0.12  # duree de base, conservee pour compatibilite
PLAYER_ATTACK_DURATIONS: tuple[float, ...] = (0.12, 0.14, 0.18)
PLAYER_ATTACK_COOLDOWN = 0.35  # delai minimal quand aucun enchainement n'est prepare
PLAYER_ATTACK_DAMAGE = 1
PLAYER_ATTACK_DAMAGES: tuple[int, ...] = (1, 1, 1)
PLAYER_ATTACK_KNOCKBACK_SCALES: tuple[float, ...] = (1.0, 1.2, 1.65)
PLAYER_ATTACK_VERTICAL_SCALES: tuple[float, ...] = (1.0, 1.1, 1.3)
PLAYER_ATTACK_COMBO_COUNT = 3
PLAYER_ATTACK_BUFFER_PROGRESS = 0.28  # le clic est memorise sur la fin du coup
PLAYER_ATTACK_COMBO_RESET_TIME = 0.62  # temps avant de repartir au premier coup
PLAYER_ATTACK_IMPACT_PROGRESS = 0.50  # debut de la frame ou la lame touche vraiment
PLAYER_ATTACK_DRAW_WIDTHS: tuple[float, ...] = (48.0, 54.0, 62.0)
PLAYER_ATTACK_SWEEP_ANGLES: tuple[tuple[float, float], ...] = (
    (58.0, -40.0),
    (-44.0, 58.0),
    (84.0, -84.0),
)
PLAYER_ATTACK_TRAIL_COUNT = 3
PLAYER_ATTACK_TRAIL_DELAY = 0.075
COMBAT_HITSTOP_DURATION = 0.05  # micro-pause lors d'un impact reussi
COMBAT_HIT_SHAKE_AMPLITUDE = 1.8
COMBAT_HIT_SHAKE_DURATION = 0.08
# Eclaboussures de sang (frappe et coups recus).
BLOOD_COUNT = 12
BLOOD_COUNT_PLAYER = 18
BLOOD_LIFE = 0.38
BLOOD_SPEED_X = 210.0
BLOOD_SPEED_Y = 160.0
BLOOD_GRAVITY = 720.0
BLOOD_SIZE_MIN = 2.4
BLOOD_SIZE_MAX = 5.2
BLOOD_SPREAD = 6.0
BLOOD_MAX = 96
BLOOD_CONE = 0.7  # radians autour de la direction du coup
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
# Trainee de dash tant que la vitesse reste nettement au-dessus de la course.
PARTICLE_HIGH_SPEED_RATIO = 0.70  # fraction de PLAYER_DASH_SPEED (au-dessus de la course)
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
# Hitbox plus etroite que le sprite, pour tenir dans une gaine d'une tuile.
GHOST_HITBOX_WIDTH = 16
GHOST_HITBOX_HEIGHT = 20
GHOST_SAFE_SEARCH_RADIUS = TILE_SIZE * 8  # portee de la recherche d'un spawn libre
GHOST_SAFE_SEARCH_STEP = 4  # pas de la spirale, en pixels
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

CORPSE_LIFETIME = 15.0  # secondes avant transformation en squelette
CORPSE_FADE_TIME = 0.35  # fondu cadavre -> os (court, masque par les particules)
CORPSE_EAT_TIME = 4.0  # secondes pour qu'un ennemi devore un cadavre (laisse un squelette)
CORPSE_DECAY_COUNT = 28
CORPSE_DECAY_LIFE = 0.48
CORPSE_DECAY_SPEED = 95.0
CORPSE_DECAY_GRAVITY = 220.0
CORPSE_DECAY_SIZE_MIN = 3.2
CORPSE_DECAY_SIZE_MAX = 8.5
CORPSE_DECAY_SPREAD_X = 16.0
CORPSE_DECAY_SPREAD_Y = 9.0
CORPSE_DECAY_MAX = 80
# Hitbox plus plate que le sprite (pose allongee) : le bas de la boite est
# aligne sur le sol, et un leger lift evite que le dessin s'enfonce dans la tuile.
CORPSE_HITBOX_WIDTH = PLAYER_WIDTH + 8
CORPSE_HITBOX_HEIGHT = 16
CORPSE_GROUND_LIFT = 0

# --------------------------------------------------------------------------- #
# Plaques d'activation
# --------------------------------------------------------------------------- #

# Epaisseur visuelle de la plaque, posee au sol de la tuile.
PLATE_HEIGHT = 8
# Retrait horizontal de chaque cote, en pixels (la hitbox suit la plaque).
PLATE_INSET = 4
# Actions par lien : une meme plaque peut cacher un mur, en reveler un autre,
# et allumer un lance-flammes. L'ancien champ JSON `invert` vaut `show` partout.
LINK_ACTION_HIDE = "hide"
LINK_ACTION_SHOW = "show"
LINK_ACTION_IGNITE = "ignite"
LINK_ACTIONS = (LINK_ACTION_HIDE, LINK_ACTION_SHOW, LINK_ACTION_IGNITE)
ACTIVATOR_KIND_PLATE = "plate"
ACTIVATOR_KIND_SPECTRAL = "spectral"
ACTIVATOR_KINDS = (ACTIVATOR_KIND_PLATE, ACTIVATOR_KIND_SPECTRAL)
# Bouton spectral : visible / pressable seulement en fantome (touche F).
SPECTRAL_BUTTON_DURATION = 4.0
SPECTRAL_BUTTON_DURATION_MIN = 0.4
SPECTRAL_BUTTON_DURATION_MAX = 20.0
SPECTRAL_BUTTON_DURATION_STEP = 0.5
SPECTRAL_BUTTON_INSET = 6
# Halo spectral : plaque en nappe floue, lien en brume (pas de trait net).
MECHANISM_PLATE_GLOW_SIZE = 200.0
MECHANISM_PLATE_GLOW_MID = 110.0
MECHANISM_PLATE_GLOW_INNER = 44.0
MECHANISM_PLATE_GLOW_ALPHA = 130
MECHANISM_PLATE_GLOW_MID_ALPHA = 165
MECHANISM_PLATE_GLOW_INNER_ALPHA = 220
MECHANISM_AURA_EDGE = 22.0
MECHANISM_AURA_MIN_PAD = 6.0
MECHANISM_AURA_AXIS_RATIO = 0.45
MECHANISM_AURA_FILL_ALPHA = 55
MECHANISM_AURA_CORE_ALPHA = 90
MECHANISM_AURA_OUTER_SCALE = 2.2
MECHANISM_AURA_PULSE = 0.22
MECHANISM_PRESSED_GLOW = 1.25
MECHANISM_LINK_CURVE = 0.34
MECHANISM_LINK_FAN = 14.0
MECHANISM_LINK_WIGGLE = 16.0
MECHANISM_LINK_WIGGLE_WAVES = 2.15
MECHANISM_LINK_WIGGLE_SLOW = 7.0  # seconde ondulation, plus lente
MECHANISM_LINK_WIGGLE_SLOW_WAVES = 0.7
MECHANISM_LINK_PULSE_SPEED = 0.85
MECHANISM_LINK_FLOW_SPEED = 0.42
MECHANISM_LINK_FLOW_COUNT = 4
MECHANISM_LINK_FLOW_SIZE = 78.0
MECHANISM_LINK_FLOW_ALPHA = 90
MECHANISM_LINK_FLOW_CORE_SIZE = 28.0
MECHANISM_LINK_FLOW_CORE_ALPHA = 160
MECHANISM_LINK_SPACING = 20.0
MECHANISM_LINK_MIN_SEGMENTS = 12
MECHANISM_LINK_MAX_SEGMENTS = 24
MECHANISM_LINK_GLOW_SIZE = 70.0
MECHANISM_LINK_GLOW_ALPHA = 70
MECHANISM_LINK_CORE_SIZE = 30.0
MECHANISM_LINK_CORE_ALPHA = 95

# --------------------------------------------------------------------------- #
# Ennemis
# --------------------------------------------------------------------------- #

# Planches "Skeleton_Sword" (squelette blanc, sans VFX) : assets/animations/.
ENEMY_SKELETON_DIR = (
    ANIMATIONS_DIR / "Enemies" / "Skeletons" / "Skeleton_Sword" / "Skeleton_White" / "Skeleton_Without_VFX"
)
# Idle / marche / attaque / mort : meme planche marche pour idle et marche
# (Skelleton_dance.png, rejouee plus lentement au repos via
# ANIM_ENEMY_IDLE_FRAME_TIME) -> tout le squelette vient desormais d'un seul
# jeu de planches (assets/sprites/), 3 frames de 40x40 chacune.
ENEMY_SPRITE_IDLE = SPRITES_DIR / "Skelleton_dance.png"
ENEMY_SPRITE_WALK = SPRITES_DIR / "Skelleton_dance.png"
ENEMY_SPRITE_ATTACK = SPRITES_DIR / "Skelleton_fight.png"
ENEMY_SPRITE_DIE = SPRITES_DIR / "Skelleton_Death.png"
# Frames natives 40x40, personnage quasi plein cadre (38 px de haut) ->
# agrandies de 46/38 pour retrouver la taille de personnage de l'ancienne
# planche (idle native en 96x64, 46 px de haut), qui servait de reference a
# ENEMY_WIDTH/ENEMY_HEIGHT/ENEMY_SPEED et au reste du reglage de l'IA.
ENEMY_ACTION_FRAME_SIZE = 40
ENEMY_ACTION_SCALE = 46 / 38
ENEMY_SCALE = 1.0
# Hitbox rectangulaire = corps visible du squelette, pas la frame entiere.
# Offsets mesures sur Skelleton_dance.png (frame 0, apres mise a l'echelle) :
# le squelette est decale vers la gauche et les pieds touchent le bas de la
# frame (voir sprites.apply_rect_hit_box).
ENEMY_WIDTH = 34
ENEMY_HEIGHT = 46
ENEMY_HITBOX_OFFSET_X = -4.84
ENEMY_HITBOX_OFFSET_Y = -1.21
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
# Skelleton_fight.png : 3 frames (0 = armement, 1 = impact/flash, 2 = retour) ;
# seule frame 1 est dangereuse. Avec 3 frames seulement, la fenetre d'esquive
# (avant frame 1) est plus courte qu'avec l'ancienne planche a 10 frames ;
# compense en partie par ANIM_ENEMY_ATTACK_FRAME_TIME plus long (voir plus bas).
ENEMY_ATTACK_HIT_FRAMES: tuple[int, int] = (1, 1)
ENEMY_ATTACK_COOLDOWN = 0.4  # secondes de pause entre deux coups
ENEMY_CORPSE_SMELL_RANGE = 320.0  # distance d'attraction vers un cadavre
ENEMY_HIT_FLASH_DURATION = 0.18
ENEMY_KNOCKBACK_SPEED = 5.0
ENEMY_KNOCKBACK_FRICTION = 0.72
# Halo rouge en mode fantome (squelette) : meme vocabulaire que BAT_/ZOMBIE_.
ENEMY_GHOST_GLOW_SCALE = 5.6
ENEMY_GHOST_GLOW_ALPHA = 96
ENEMY_GHOST_GLOW_INNER_SCALE = 2.4
ENEMY_GHOST_GLOW_INNER_ALPHA = 170
ENEMY_GHOST_GLOW_PULSE = 0.16
ENEMY_GHOST_GLOW_PULSE_SPEED = 3.4
ANIM_ENEMY_IDLE_FRAME_TIME = 0.12
# Marche/attaque/mort n'ont plus que 3 frames chacune (contre 10-13 avant) :
# temps par frame augmente pour garder une duree totale d'animation comparable
# (cycle de marche ~0.5 s, coup ~0.6 s, mort ~1.5 s, a ANIM_SPEED=0.5).
ANIM_ENEMY_WALK_FRAME_TIME = 0.09
ANIM_ENEMY_ATTACK_FRAME_TIME = 0.1
ANIM_ENEMY_DIE_FRAME_TIME = 0.25

# --------------------------------------------------------------------------- #
# Ennemis - chauve-souris (volant)
# --------------------------------------------------------------------------- #

# Planches "Bat with VFX" (impacts/trainees dessines dans les planches d'attaque
# elles-memes) : assets/animations/. Frames natives carrees, contrairement au
# squelette (96x64) : 64x64.
BAT_DIR = ANIMATIONS_DIR / "Enemies" / "Bat" / "Bat with VFX"
BAT_SPRITE_SLEEP = BAT_DIR / "Bat-Sleep.png"
BAT_SPRITE_WAKE = BAT_DIR / "Bat-WakeUp.png"
BAT_SPRITE_FLY = BAT_DIR / "Bat-IdleFly.png"
BAT_SPRITE_RUN = BAT_DIR / "Bat-Run.png"
BAT_SPRITE_ATTACK_DIVE = BAT_DIR / "Bat-Attack1.png"  # piquet vertical
BAT_SPRITE_ATTACK_LUNGE = BAT_DIR / "Bat-Attack2.png"  # charge horizontale
BAT_SPRITE_DIE = BAT_DIR / "Bat-Die.png"
BAT_FRAME_SIZE = 64
BAT_SCALE = 1.0
# Hitbox rectangulaire = corps visible (ailes repliees), pas l'envergure en
# plein vol : mesuree au centre de la frame, a affiner avec DEBUG_SHOW_HITBOXES.
BAT_WIDTH = 22
BAT_HEIGHT = 22
BAT_HITBOX_OFFSET_X = 0.0
BAT_HITBOX_OFFSET_Y = -4.0
# La planche dessine la chauve-souris tournee vers la gauche (le squelette est
# tourne vers la droite) : `Bat.facing` doit donc s'appliquer en miroir.
BAT_SPRITE_FACES_LEFT = True
BAT_HIT_POINTS = 1

# Deplacement (vol libre, sans gravite : cf. Ghost._apply_steering/_move_axis).
BAT_SPEED = 3.2  # px/frame
BAT_ACCEL_TIME = 0.18  # secondes pour atteindre BAT_SPEED
BAT_COAST_TIME = 0.30  # secondes pour freiner une fois la cible hors de portee
BAT_ARRIVE_DISTANCE = 6.0  # px : assez pres du perchoir pour se rendormir

# Reveil / poursuite / laisse (distances au joueur ou au perchoir d'origine).
BAT_WAKE_RANGE = 190.0
BAT_LEASH_RANGE = 340.0  # au-dela du perchoir, la chauve-souris abandonne et rentre

# Attaque : la chauve-souris pique si le joueur est nettement en-dessous, dans
# un cone autour de la verticale (pas seulement pile en-dessous : un angle
# genereux, sinon l'attaque ne se declenche presque jamais en jeu reel) ; elle
# charge a l'horizontale si le joueur est a peu pres a la meme hauteur.
BAT_ATTACK_RANGE = 70.0  # distance de declenchement (CHASE -> ATTACK)
BAT_ATTACK_REACH = 46.0  # rayon reel du coup pendant les frames actives, depuis la position apres l'elan
# RANGE < LURCH_DISTANCE + REACH : un joueur immobile a portee de declenchement
# est touche ; un joueur qui s'ecarte pendant l'armement peut esquiver.
BAT_DIVE_MIN_DROP = 16.0  # px : le joueur doit etre au moins ce peu en-dessous
BAT_DIVE_CONE_ANGLE = 50.0  # degres de part et d'autre de la verticale (piquet)
BAT_LUNGE_VERTICAL_RANGE = 20.0  # tolerance de hauteur pour la charge horizontale
BAT_ATTACK_COOLDOWN = 0.5  # secondes de pause entre deux attaques
# Frames actives de chaque planche d'attaque, calees sur le pic du mouvement
# dessine (mesure sur les planches, voir le dessin du corps par frame, pas
# juste la duree totale) : le piquet touche le fond de sa boucle (~13px sous
# le centre), la charge son extension horizontale maximale (~19px).
BAT_DIVE_HIT_FRAMES: tuple[int, int] = (5, 6)
BAT_LUNGE_HIT_FRAMES: tuple[int, int] = (7, 9)
# La planche anime elle-meme un vrai mouvement (piquet/charge), mais son
# amplitude est modeste (10-20px autour du centre de la frame 64x64) : bien
# moins que BAT_ATTACK_RANGE. Sans un minimum de vrai deplacement du sprite,
# l'attaque semble foncer sur le joueur sans jamais l'atteindre des qu'il
# n'est pas deja tout pres. On ne va donc pas jusqu'au joueur (ca collerait
# les deux sprites, cf. retour visuel) : juste un elan court et plafonne vers
# lui, que l'amplitude dessinee complete jusqu'au contact.
BAT_ATTACK_LURCH_DISTANCE = 32.0  # px : distance max parcourue par l'ancre pendant l'elan
# Duree de l'elan (interpolation directe vers la cible, cf. `Bat._advance_attack_lurch`) :
# volontairement PAS un ressort vitesse/acceleration comme le vol normal, qui
# survolerait la cible sur un trajet si court et rearmerait sans fin
# ("picorement"). Doit tenir dans la fenetre entre BAT_ATTACK_LURCH_START_FRAME
# et le debut des frames actives (le piquet laisse le moins de marge : ~0.1s).
BAT_ATTACK_LURCH_DURATION = 0.07  # secondes
# Les toutes premieres frames des deux planches d'attaque dessinent un recul/
# une montee (l'armement, a l'oppose du joueur : mesure sur les planches,
# cf. commentaire au-dessus). Faire foncer l'ancre des la frame 0 la ferait
# avancer pendant que le dessin recule : un contresens visuel tres marque
# (l'impression de "rejouer" quelque chose). L'elan n'est donc arme qu'a
# partir de cette frame, une fois le dessin reellement lance vers la cible.
BAT_ATTACK_LURCH_START_FRAME = 4

ANIM_BAT_SLEEP_FRAME_TIME = 0.20
ANIM_BAT_WAKE_FRAME_TIME = 0.05
ANIM_BAT_FLY_FRAME_TIME = 0.09
ANIM_BAT_RUN_FRAME_TIME = 0.06
ANIM_BAT_ATTACK_DIVE_FRAME_TIME = 0.045
ANIM_BAT_ATTACK_LUNGE_FRAME_TIME = 0.04
ANIM_BAT_DIE_FRAME_TIME = 0.05

BAT_GHOST_GLOW_SCALE = 5.0
BAT_GHOST_GLOW_ALPHA = 90
BAT_GHOST_GLOW_INNER_SCALE = 2.2
BAT_GHOST_GLOW_INNER_ALPHA = 160
BAT_GHOST_GLOW_PULSE = 0.18
BAT_GHOST_GLOW_PULSE_SPEED = 3.8
COLOR_BAT = (150, 96, 190)
COLOR_BAT_GLOW = (255, 28, 22)
COLOR_BAT_GLOW_CORE = (255, 92, 64)

# --------------------------------------------------------------------------- #
# Ennemis - zombie (traqueur au sol)
# --------------------------------------------------------------------------- #

# Planches "Zombie_Default" : 6 frames 64x64 chacune. Pas de planche de course :
# la course rejoue Walk en accelere (ANIM_ZOMBIE_RUN_FRAME_TIME).
ZOMBIE_DIR = ANIMATIONS_DIR / "Enemies" / "Zombie"
ZOMBIE_SPRITE_IDLE = ZOMBIE_DIR / "Zombie_Default_Idle.png"
ZOMBIE_SPRITE_WALK = ZOMBIE_DIR / "Zombie_Default_Walk.png"
ZOMBIE_SPRITE_ATTACK = ZOMBIE_DIR / "Zombie_Default_Attack1.png"
ZOMBIE_SPRITE_HURT = ZOMBIE_DIR / "Zombie_Default_Hurt.png"
ZOMBIE_SPRITE_DIE = ZOMBIE_DIR / "Zombie_Default_Dead.png"
ZOMBIE_FRAME_SIZE = 64
# Planches agrandies au chargement (nearest-neighbor, cf. ENTITY_SCALE du
# joueur) : a 1.0, le zombie (~31 px de haut) paraissait minuscule a cote du
# squelette (~46 px) et du joueur. A 1.5, il fait ~46 px, comme le squelette.
ZOMBIE_SCALE = 1.5
# Corps mesure sur les planches natives : x 20-44, y 17-48 (pieds a 16 px du
# bas de la frame, pas tout en bas comme le squelette) -> hitbox 22x30
# centree, abaissee d'1 px pour que son bas tombe pile sous les pieds.
# Valeurs en pixels finaux (apres ZOMBIE_SCALE), comme `apply_rect_hit_box` l'attend.
ZOMBIE_WIDTH = 22 * ZOMBIE_SCALE
ZOMBIE_HEIGHT = 30 * ZOMBIE_SCALE
ZOMBIE_HITBOX_OFFSET_X = 0.0
ZOMBIE_HITBOX_OFFSET_Y = -1.0 * ZOMBIE_SCALE
# Les planches dessinent le zombie tourne vers la gauche (cf. BAT_SPRITE_FACES_LEFT).
ZOMBIE_SPRITE_FACES_LEFT = True
# 2 PV : le premier stomp le sonne (HURT) et l'enrage, le second le tue.
ZOMBIE_HIT_POINTS = 2

# Deplacement : traine les pieds en patrouille, sprinte une fois qu'il a vu le
# joueur. Le joueur (PLAYER_SPEED 5.5) le distance, mais doit s'engager.
ZOMBIE_PATROL_SPEED = 0.8  # px/frame
ZOMBIE_RUN_SPEED = 3.4  # px/frame
ZOMBIE_ACCEL_TIME = 0.30  # secondes (lissage exponentiel de change_x)
# Demi-tour en course : il freine et met ce temps a se retourner. Sauter
# par-dessus lui fait donc gagner un vrai temps d'avance.
ZOMBIE_TURN_TIME = 0.25

# Vision : cone avant (demi-plan du cote ou il regarde) + ligne de vue (les
# murs bloquent). Dans son dos, il ne "sent" le joueur qu'au contact.
ZOMBIE_SIGHT_RANGE = 280.0
ZOMBIE_BACK_SENSE_RANGE = 48.0
# Asymetrique : il ne peut pas grimper (pas de vision vers le haut au-dela d'un
# petit ecart, comme ENEMY_AGGRO_VERTICAL_RANGE), mais il peut se laisser
# tomber jusqu'a ZOMBIE_MAX_DROP_TILES : il voit donc aussi loin vers le bas.
ZOMBIE_SIGHT_UP_RANGE = 48.0
ZOMBIE_MAX_DROP_TILES = 4
ZOMBIE_SIGHT_DOWN_RANGE = (ZOMBIE_MAX_DROP_TILES + 0.5) * TILE_SIZE
ZOMBIE_EYE_OFFSET_Y = 12.0  # px au-dessus du centre : point de depart de la ligne de vue
ZOMBIE_SIGHT_CHECK_INTERVAL = 0.1  # secondes entre deux tests de ligne de vue (perf)
ZOMBIE_SIGHT_CHECK_RESOLUTION = 8  # px entre deux echantillons du rayon
# Cri d'alerte (PATROL -> CHASE) : laisse au joueur le temps de reagir.
# Duree reelle = frames x FRAME_TIME / ANIM_SPEED : 5 x 0.04 / 0.5 = 0.4 s.
ANIM_ZOMBIE_ALERT_FRAME_TIME = 0.04

# Memoire : une fois la vue perdue, il court au dernier point ou il a vu le
# joueur pendant ZOMBIE_MEMORY_TIME, puis cherche (regarde a gauche/droite)
# pendant ZOMBIE_SEARCH_TIME avant de reprendre sa patrouille.
ZOMBIE_MEMORY_TIME = 1.5
ZOMBIE_SEARCH_TIME = 1.5
ZOMBIE_SEARCH_LOOK_TIME = 0.5  # secondes entre deux changements de regard
ZOMBIE_ARRIVE_DISTANCE = 8.0  # px : assez pres du dernier point vu

# Chute : en course, il se laisse tomber d'une plateforme si sa cible est plus
# bas et qu'un sol existe a au plus ZOMBIE_MAX_DROP_TILES tuiles sous le bord
# (les puits a piques du tutoriel sont bien plus profonds : il ne s'y jette pas).
# La cible doit etre au moins ce peu sous le centre du zombie : un joueur au
# meme etage a son centre a la meme hauteur (a quelques px pres), un joueur une
# seule tuile plus bas l'a deja ~32 px en dessous.
ZOMBIE_DROP_MIN_TARGET_DROP = 12.0
# Pendant la chute, l'elan de course porte le zombie ~1 tuile plus loin que le
# bord : le sol d'arrivee est aussi cherche une colonne plus loin.
ZOMBIE_DROP_PROBE_COLUMNS = 2

# Griffe bondissante : il garde son elan pendant l'armement (frames 0-3), puis
# reste penche (frames 4-5) -> fenetre pour le punir. RANGE > REACH ici, a
# l'inverse du squelette : c'est le bond qui comble la difference.
ZOMBIE_ATTACK_RANGE = 64.0
ZOMBIE_ATTACK_REACH = 60.0
ZOMBIE_ATTACK_VERTICAL_RANGE = 40.0
# Frames d'Attack1 (0-5) : 0-1 = armement (bras leve), 2-3 = griffe, 4-5 = penche.
ZOMBIE_ATTACK_HIT_FRAMES: tuple[int, int] = (2, 3)
ZOMBIE_ATTACK_LUNGE_LAST_FRAME = 3
ZOMBIE_ATTACK_LUNGE_SPEED = 2.6  # px/frame au depart du bond (ou la vitesse de course si plus grande)
ZOMBIE_ATTACK_LUNGE_DECAY = 0.12  # secondes (constante de temps du ralentissement)
ZOMBIE_ATTACK_COOLDOWN = 1.0
# Plus gourmand que le squelette : sent de plus loin et y va en courant.
ZOMBIE_CORPSE_SMELL_RANGE = 400.0

# Temps par frame AVANT ANIM_SPEED (0.5 : les durees reelles sont doublees).
ANIM_ZOMBIE_IDLE_FRAME_TIME = 0.12
ANIM_ZOMBIE_WALK_FRAME_TIME = 0.12
ANIM_ZOMBIE_RUN_FRAME_TIME = 0.035
# Griffe a 2 x 0.08 / 0.5 = 0.32 s du declenchement ; attaque entiere ~1 s,
# dont la fin penchee (frames 4-5) est la fenetre pour le punir.
ANIM_ZOMBIE_ATTACK_FRAME_TIME = 0.08
ANIM_ZOMBIE_EAT_FRAME_TIME = 0.15  # Attack1 frames 3-4 en boucle (penche, mastique)
ANIM_ZOMBIE_HURT_FRAME_TIME = 0.035  # sonne ~0.42 s
ANIM_ZOMBIE_DIE_FRAME_TIME = 0.07

ZOMBIE_GHOST_GLOW_SCALE = 5.2
ZOMBIE_GHOST_GLOW_ALPHA = 92
ZOMBIE_GHOST_GLOW_INNER_SCALE = 2.3
ZOMBIE_GHOST_GLOW_INNER_ALPHA = 165
ZOMBIE_GHOST_GLOW_PULSE = 0.14
ZOMBIE_GHOST_GLOW_PULSE_SPEED = 2.6  # plus lent : un zombie "respire" moins vite
COLOR_ZOMBIE = (84, 170, 132)
COLOR_ZOMBIE_GLOW = (255, 28, 22)
COLOR_ZOMBIE_GLOW_CORE = (255, 92, 64)

# --------------------------------------------------------------------------- #
# Ennemis - boss (golem de pierre, attaques a distance)
# --------------------------------------------------------------------------- #

BOSS_FRAME = 100
BOSS_DEATH_FRAME = 60  # planche 10x3, personnage a la meme echelle pixel que le walk
# Decalage vertical de l'anim de mort (negatif = plus bas). Un cran trop haut sans ca.
BOSS_DEATH_GROUND_OFFSET_Y = -TILE_SIZE/2+3
BOSS_BEAM_FRAME_WIDTH = 300
BOSS_BEAM_FRAME_HEIGHT = 100
BOSS_SCALE = 3.0
# Corps mesure sur boss_walk (golem ~48x47 dans une frame 100x100).
BOSS_WIDTH = 40.0 * BOSS_SCALE
BOSS_HEIGHT = 44.0 * BOSS_SCALE
BOSS_HITBOX_OFFSET_Y = -2.0 * BOSS_SCALE
BOSS_HIT_POINTS = 6
BOSS_PATROL_SPEED = 0.55
BOSS_AGGRO_RANGE = 420.0
BOSS_AGGRO_VERTICAL_RANGE = 96.0
BOSS_SHOT_RANGE = 400.0
BOSS_LASER_RANGE = 360.0 * BOSS_SCALE
BOSS_LASER_HEIGHT = 14.0 * BOSS_SCALE  # hitbox du rayon, independante de la hauteur du sprite
BOSS_LASER_LINGER_FRAMES = 8  # alternance derniere / avant-derniere frame du rayon
BOSS_LASER_FADE_TIME = 0.16  # fondu leger en fin de rayon, en secondes
# Temps de lissage de la visee (smooth damp) : plus grand = plus inerte.
BOSS_LASER_SMOOTH_TIME = 0.7
# Vitesse max de rotation du rayon, en deg/s. 0 = pas de plafond.
BOSS_LASER_MAX_TURN_SPEED = 80.0
# Fraction droite du sprite : le rayon s'eteint avant le vide.
BOSS_LASER_TIP_FADE = 0.12
# Gemme frontale : ~centre X, 17 px au-dessus du centre d'une frame 100x100.
BOSS_LASER_ORIGIN_X = 0.0
BOSS_LASER_ORIGIN_Y = 17.0 * BOSS_SCALE
# Largeur de contenu au-dela de laquelle une frame est un rayon (pas une etincelle).
BOSS_BEAM_FULL_MIN_WIDTH = 80.0
BOSS_SHOT_ORIGIN_X = 0.0  # depart au centre du golem
BOSS_SHOT_ORIGIN_Y = 0.0
BOSS_SHOT_SPEED = 8.0  # px/frame, vitesse initiale
BOSS_SHOT_SPEED_END = 4.0  # px/frame, palier en fin de course
BOSS_SHOT_LIFE = 2.4
BOSS_SHOT_WIDTH = 16.0 * BOSS_SCALE
BOSS_SHOT_HEIGHT = 7.0 * BOSS_SCALE
BOSS_SHOT_SPREAD_DEG = 11.0  # ecart aleatoire autour du joueur
# La planche pointe vers la gauche ; Arcade.angle est horaire.
BOSS_SHOT_ART_ANGLE = 180.0
BOSS_SHOT_BURST_COUNT = 26
BOSS_SHOT_BURST_MAX = 72
BOSS_SHOT_BURST_SPEED = 160.0
BOSS_SHOT_BURST_LIFE = 0.42
BOSS_SHOT_BURST_SIZE_MIN = 4.0
BOSS_SHOT_BURST_SIZE_MAX = 11.0
BOSS_SHOT_BURST_CORE_SIZE = 2.6
BOSS_SHOT_BURST_GLOW_ALPHA = 170
BOSS_SHOT_BURST_CORE_ALPHA = 230
BOSS_SHOT_BURST_SPREAD = 5.0
BOSS_SHOT_BURST_GRAVITY = 90.0
BOSS_ATTACK_COOLDOWN = 1.15
BOSS_PREFERRED_DISTANCE = 180.0
BOSS_SPIKE_SIZE = TILE_SIZE
BOSS_SPIKE_COUNT_MIN = 5
BOSS_SPIKE_COUNT_MAX = 9
BOSS_SPIKE_START_GAP = 56.0  # distance au centre du boss avant la 1re pique
BOSS_SPIKE_WARN_TIME = 0.72
BOSS_SPIKE_STAGGER = 0.11
BOSS_SPIKE_HOLD = 0.4
BOSS_SPIKE_DESPAWN_STAGGER = 0.09
BOSS_SPIKE_FADE_TIME = 0.18
BOSS_SPIKE_HIT_WIDTH = 22.0
BOSS_SPIKE_HIT_HEIGHT = 16.0
COLOR_BOSS_SPIKE_WARN = (255, 64, 28)
COLOR_BOSS_SPIKE_WARN_CORE = (255, 170, 90)
# Frame du lancer (bras tendu, 1re ligne de boss_shot, 10 colonnes).
BOSS_SHOT_SPAWN_FRAME = 7
ANIM_BOSS_WALK_FRAME_TIME = 0.12
ANIM_BOSS_SHOT_FRAME_TIME = 0.07
ANIM_BOSS_LASER_FRAME_TIME = 0.08
ANIM_BOSS_DEATH_FRAME_TIME = 0.06
ANIM_BOSS_PROJECTILE_FRAME_TIME = 0.08
ANIM_BOSS_BEAM_FRAME_TIME = 0.05
BOSS_GHOST_GLOW_SCALE = 4.6
BOSS_GHOST_GLOW_ALPHA = 100
BOSS_GHOST_GLOW_INNER_SCALE = 2.0
BOSS_GHOST_GLOW_INNER_ALPHA = 170
BOSS_GHOST_GLOW_PULSE = 0.16
BOSS_GHOST_GLOW_PULSE_SPEED = 2.8
COLOR_BOSS = (120, 128, 150)
COLOR_BOSS_GLOW = (40, 210, 255)
COLOR_BOSS_GLOW_CORE = (180, 245, 255)
COLOR_BOSS_DEATH_EMBER = (255, 118, 36)
COLOR_BOSS_DEATH_EMBER_CORE = (255, 220, 140)
COLOR_BOSS_DEATH_SHARD = (98, 104, 118)
COLOR_BOSS_DEATH_SHARD_DARK = (62, 66, 78)
COLOR_BOSS_DEATH_FLASH = (255, 248, 230)
COLOR_BOSS_DEATH_FLASH_CORE = (255, 255, 255)
BOSS_DEATH_FX_SPARKS = 52
BOSS_DEATH_FX_EMBERS = 38
BOSS_DEATH_FX_SHARDS = 34
BOSS_DEATH_FX_MAX = 280
BOSS_DEATH_FX_MEGA_SCALE = 1.7
BOSS_DEATH_FX_BOOM_COUNT = 6
BOSS_DEATH_FX_BOOM_INTERVAL = 0.16
BOSS_DEATH_FX_BOOM_SPREAD = 70.0
BOSS_DEATH_FX_STREAM_TIME = 1.1
BOSS_DEATH_FX_STREAM_INTERVAL = 0.05
BOSS_DEATH_FX_STREAM_COUNT = 6
BOSS_DEATH_FX_SPARK_SPEED = 420.0
BOSS_DEATH_FX_SPARK_LIFE = 0.7
BOSS_DEATH_FX_SPARK_SIZE_MIN = 10.0
BOSS_DEATH_FX_SPARK_SIZE_MAX = 26.0
BOSS_DEATH_FX_SPARK_CORE = 3.4
BOSS_DEATH_FX_SPARK_GLOW_ALPHA = 190
BOSS_DEATH_FX_SPARK_CORE_ALPHA = 240
BOSS_DEATH_FX_SPARK_GRAVITY = 40.0
BOSS_DEATH_FX_EMBER_SPEED = 260.0
BOSS_DEATH_FX_EMBER_LIFE = 0.95
BOSS_DEATH_FX_EMBER_SIZE_MIN = 8.0
BOSS_DEATH_FX_EMBER_SIZE_MAX = 20.0
BOSS_DEATH_FX_EMBER_CORE = 2.8
BOSS_DEATH_FX_EMBER_GLOW_ALPHA = 180
BOSS_DEATH_FX_EMBER_CORE_ALPHA = 230
BOSS_DEATH_FX_EMBER_GRAVITY = -70.0  # monte, les braises s'elevent
BOSS_DEATH_FX_SHARD_SPEED = 340.0
BOSS_DEATH_FX_SHARD_LIFE = 1.05
BOSS_DEATH_FX_SHARD_SIZE_MIN = 5.0
BOSS_DEATH_FX_SHARD_SIZE_MAX = 13.0
BOSS_DEATH_FX_SHARD_GRAVITY = 780.0
BOSS_DEATH_FX_SHOCK_LIFE = 0.48
BOSS_DEATH_FX_SHOCK_SIZE = 420.0
BOSS_DEATH_FX_FLASH_LIFE = 0.22
BOSS_DEATH_FX_FLASH_SIZE = 260.0
CAMERA_BOSS_DEATH_SHAKE = 16.0
CAMERA_BOSS_DEATH_SHAKE_TIME = 0.62
CAMERA_BOSS_DEATH_BOOM_SHAKE = 9.0
CAMERA_BOSS_DEATH_BOOM_SHAKE_TIME = 0.24

# Directeur de spawn : les ennemis de la carte servent de graines, puis les
# points `enemy_spawns` alimentent de petites vagues de renforts. Le directeur
# attend que la zone soit hors camera et assez loin du joueur avant d'armer
# une apparition mystique.
ENEMY_SPAWN_MAX_ACTIVE = 6
ENEMY_SPAWN_WAVE_SIZE = 2
ENEMY_SPAWN_INITIAL_DELAY = 5.0
ENEMY_SPAWN_WAVE_INTERVAL = 6.0
ENEMY_SPAWN_WARNING_DURATION = 0.7
ENEMY_SPAWN_OFFSCREEN_MARGIN = 64.0
ENEMY_SPAWN_MARKER_RADIUS = 22.0
ENEMY_SPAWN_GHOST_HINT_SIZE = 36.0
ENEMY_SPAWN_GHOST_HINT_ALPHA = 86

# Compatibilite avec les reglages de la premiere version du respawn. Le
# directeur les lit encore pour le delai et les distances de securite.
ENEMY_RESPAWN_DELAY = 4.0
ENEMY_RESPAWN_RETRY_DELAY = 0.5
ENEMY_RESPAWN_MIN_PLAYER_DISTANCE = 192.0
ENEMY_RESPAWN_MIN_ENEMY_DISTANCE = 96.0

# --------------------------------------------------------------------------- #
# Objets et progression
# --------------------------------------------------------------------------- #

ITEM_BOB_AMPLITUDE = 4.0  # amplitude du flottement vertical, en pixels
ITEM_BOB_SPEED = 2.5
SOUL_ORB_SIZE = 16
# Planche assets/sprites/essence-d-ame.png : 4 frames de 32x32 (l'orbe tourne
# sur elle-meme), deja coloree et translucide -> plus besoin de teinter/alpha
# via sprite.color comme pour l'ancien placeholder procedural.
SPRITE_SOUL_ORB = "essence-d-ame"
SOUL_ORB_FRAME_SIZE = 32
ANIM_SOUL_ORB_FRAME_TIME = 0.12
SOUL_ORB_GLOW_SCALE = 4.2
SOUL_ORB_GLOW_ALPHA = 46
SOUL_ORB_GLOW_PULSE = 0.18
SOUL_ORB_GLOW_PULSE_SPEED = 2.8
SOUL_ORB_MAGNET_RANGE = 96.0  # px : l'orbe derive vers le joueur dans ce rayon
SOUL_ORB_MAGNET_SPEED = 42.0  # px / seconde
KEY_GLOW_SCALE = 3.6
KEY_GLOW_ALPHA = 70
KEY_GLOW_INNER_SCALE = 1.6
KEY_GLOW_INNER_ALPHA = 120
KEY_GLOW_PULSE = 0.22
KEY_GLOW_PULSE_SPEED = 2.4

SOUL_ESSENCE_PER_ORB = 1
# XP cumulee pour atteindre le niveau n (croissance exponentielle) :
#   xp(n) = SOUL_XP_BASE * (SOUL_XP_GROWTH**(n-1) - 1) / (SOUL_XP_GROWTH - 1)
# Avec ces valeurs : niveau 1=0, 2=3, 3=7, 4=15, 5=27, 6=47, 7=78 ames...
SOUL_XP_BASE = 3.0
SOUL_XP_GROWTH = 1.6

# Prix en ames (monnaie depensable, `SoulProgression.essence`) du prochain
# rang d'une amelioration fantome, croissance exponentielle avec le rang deja
# achete de cette amelioration (rang 0 = jamais prise) :
#   cost(rang) = SOUL_UPGRADE_BASE_COST * SOUL_UPGRADE_COST_GROWTH**rang
SOUL_UPGRADE_BASE_COST = 2.0
SOUL_UPGRADE_COST_GROWTH = 1.7

# Bonus fixe accorde par rang achete d'une carte d'amelioration.
GHOST_UPGRADE_VISION_BONUS = 40.0  # px de rayon de revelation
GHOST_UPGRADE_SPEED_BONUS = 1.0  # px/frame de vitesse de deplacement fantome
GHOST_UPGRADE_DURATION_BONUS = 3.0  # secondes de duree en mode fantome

# --------------------------------------------------------------------------- #
# Couleurs (RGB) - palette provisoire, remplacee par les sprites plus tard
# --------------------------------------------------------------------------- #

COLOR_BACKGROUND = (18, 18, 28)
COLOR_WALL = (72, 76, 96)
COLOR_ICE = (118, 196, 220)
COLOR_ICE_INNER = (186, 232, 244)
COLOR_FALLING_BLOCK = (176, 122, 64)
COLOR_FALLING_BLOCK_INNER = (214, 168, 96)
COLOR_FALLING_BLOCK_ARMED = (212, 96, 64)
COLOR_FALLING_BLOCK_GHOST = (150, 214, 255)
COLOR_FALLING_BLOCK_GHOST_ARMED = (214, 168, 255)
COLOR_SPRING = (168, 116, 64)
COLOR_SPRING_COIL = (214, 168, 92)
COLOR_SPRING_PAD = (236, 214, 150)
FALLING_BLOCK_GHOST_ALPHA = 210
COLOR_SPECTRAL_WALL = (96, 84, 140)
# Contour du bloc invisible en mode fantome (bleu tres clair).
COLOR_HIDDEN_WALL = (176, 216, 255)
COLOR_HIDDEN_WALL_OUTLINE = (210, 236, 255)
HIDDEN_WALL_OUTLINE_WIDTH = 2
COLOR_SPIKE = (196, 84, 84)
COLOR_FLAMETHROWER = (232, 96, 36)
COLOR_FLAME_PREVIEW = (255, 120, 40, 55)
COLOR_HAZARD_GLOW = (255, 12, 4)
COLOR_HAZARD_GLOW_CORE = (255, 72, 36)
COLOR_DOOR_LOCKED = (150, 110, 46)
COLOR_DOOR_OPEN = (96, 170, 110)
COLOR_CHECKPOINT = (86, 148, 196)
COLOR_CHECKPOINT_PARTICLE = (90, 186, 255)
COLOR_CHECKPOINT_PARTICLE_CORE = (210, 240, 255)
COLOR_CHECKPOINT_GLOW = (118, 198, 255)
COLOR_CHECKPOINT_GLOW_CORE = (236, 248, 255)
COLOR_PRESSURE_PLATE = (92, 108, 132)
COLOR_PRESSURE_PLATE_PRESSED = (64, 168, 214)
COLOR_SPECTRAL_BUTTON = (118, 86, 196)
COLOR_SPECTRAL_BUTTON_ACTIVE = (176, 148, 255)
COLOR_MECHANISM_LINK = (168, 220, 255)
COLOR_MECHANISM_GLOW = (186, 232, 255)
COLOR_MECHANISM_GLOW_CORE = (236, 248, 255)
COLOR_PLAYER = (232, 232, 240)
COLOR_ATTACK = (255, 214, 112)
COLOR_ATTACK_GLOW = (255, 238, 160)
COLOR_SWORD_BLADE = (225, 231, 234)
COLOR_SWORD_EDGE = (255, 255, 248)
COLOR_SWORD_GUARD = (172, 67, 52)
COLOR_SWORD_HANDLE = (91, 49, 39)
COLOR_SWORD_POMMEL = (224, 142, 72)
COLOR_SWORD_GLOW = (255, 218, 140)
COLOR_GHOST = (128, 200, 255)
COLOR_GHOST_GLOW = (110, 190, 255)
COLOR_TRAIL_GHOST = (132, 214, 255)
COLOR_TRAIL_GHOST_CORE = (230, 248, 255)
COLOR_DEATH_PARTICLE = (150, 214, 255)
COLOR_DEATH_PARTICLE_CORE = (245, 252, 255)
COLOR_CORPSE = (140, 120, 120)
COLOR_ENEMY = (188, 92, 160)
COLOR_ENEMY_HIT = (255, 155, 155)
COLOR_ENEMY_GLOW = (255, 28, 22)
COLOR_ENEMY_GLOW_CORE = (255, 92, 64)
COLOR_ENEMY_SPAWN = (190, 78, 232)
COLOR_ENEMY_SPAWN_GHOST = (144, 208, 255)
COLOR_KEY = (232, 204, 96)
COLOR_KEY_GLOW = (255, 214, 96)
COLOR_KEY_GLOW_CORE = (255, 244, 190)
COLOR_BLOOD = (168, 18, 28)
COLOR_BLOOD_BRIGHT = (210, 36, 42)
COLOR_SOUL_ORB = (110, 190, 255)
COLOR_HUD_TEXT = (228, 228, 236)
COLOR_HUD_BAR_BACKGROUND = (48, 48, 62)
COLOR_HUD_BAR_FILL = (128, 200, 255)
COLOR_HUD_GHOST_GAUGE = (110, 196, 255)
COLOR_HUD_GHOST_GAUGE_IDLE = (92, 96, 112)  # jauge fantome hors mode, grisee
COLOR_DASH = (255, 214, 120)
COLOR_DASH_GLOW = (255, 224, 150)
COLOR_TRAIL_DASH = (255, 214, 96)
COLOR_TRAIL_DASH_CORE = (255, 250, 210)
COLOR_DASH_GAUGE = (255, 186, 72)
COLOR_TORCH_STEM = (94, 58, 34)
COLOR_TORCH_FLAME = (255, 196, 72)
COLOR_TORCH_GLOW = (255, 150, 36)
COLOR_TORCH_GLOW_CORE = (255, 240, 190)
COLOR_DUST = (236, 228, 208)
COLOR_DUST_DARK = (186, 174, 150)
COLOR_MENU_TITLE = (232, 208, 168)
COLOR_MENU_HINT = (168, 136, 100)
COLOR_MENU_PANEL = (48, 32, 22)
COLOR_MENU_PANEL_BORDER = (118, 82, 50)
COLOR_MENU_CELL = (62, 42, 28)
COLOR_MENU_CELL_BORDER = (102, 70, 44)
COLOR_MENU_FOCUS_FILL = (86, 56, 34)
COLOR_MENU_FOCUS = (196, 132, 72)
COLOR_MENU_VEIL = (16, 10, 8)
COLOR_MENU_GOLD = (216, 168, 88)
COLOR_MENU_TITLE_SHADOW = (36, 22, 14)

# Cartes de choix d'amelioration fantome (montee de niveau) : accent
# bleu-spectre plutot que le marron/torche des autres menus, pour bien les
# distinguer visuellement d'une pause ou d'une victoire.
COLOR_CARD_FILL = (26, 32, 52)
COLOR_CARD_BORDER = (74, 108, 158)
COLOR_CARD_FOCUS_FILL = (40, 54, 86)
COLOR_CARD_ACCENT = (128, 200, 255)  # = COLOR_GHOST
COLOR_CARD_COST = (150, 205, 255)

MENU_CARD_WIDTH = 190
MENU_CARD_HEIGHT = 220
MENU_CARD_GAP = 24

MENU_PAUSE_VEIL_ALPHA = 176
MENU_GRID_COLUMNS = 2
MENU_CELL_WIDTH = 220
MENU_CELL_HEIGHT = 78
MENU_CELL_GAP = 12
MENU_BUTTON_WIDTH = 300
MENU_BUTTON_HEIGHT = 40
MENU_PANEL_PAD = 24
MENU_TITLE_SIZE = 20
MENU_TITLE_MAP = "title_backdrop.json"
MENU_TITLE_GHOST_COUNT = 5
MENU_TITLE_GHOST_SPEED = 2.2  # px/frame, plus lent que le fantome jouable
MENU_TITLE_VISION = 230.0  # halo de chaque esprit (suit le fantome, comme en jeu)
MENU_TITLE_VISION_PULSE = 22.0
MENU_TITLE_WARP = 0.028  # distorsion barillet discrete, comme le mode fantome
MENU_TITLE_ZOOM = 0.72
MENU_TITLE_FLOCK_RADIUS = 420.0
MENU_TITLE_RETARGET_MIN = 1.2
MENU_TITLE_RETARGET_MAX = 3.8
MENU_TITLE_CURL = 0.7
MENU_TITLE_HOVER_CHANCE = 0.14

# --------------------------------------------------------------------------- #
# Ecran de transition de niveau (nom + sous-titre sur fond noir)
# --------------------------------------------------------------------------- #

LEVEL_INTRO_FADE_TIME = 0.4  # secondes, entree et sortie du texte
LEVEL_INTRO_HOLD_TIME = 1.4  # secondes a pleine opacite
LEVEL_INTRO_TITLE_SIZE = 32
LEVEL_INTRO_SUBTITLE_SIZE = 18

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
CAMERA_ZOOM_PLAYER = 1.9
# Leger recul pendant le dash (plus petit = plus de monde a l'ecran).
CAMERA_ZOOM_DASH = 2.08
CAMERA_ZOOM_GHOST = 0.92
CAMERA_ZOOM_SMOOTH_TIME = 0.55
# Zoom du dash : plus vif que la transition corps/fantome, pour que le recul
# se lise sur les ~0.12 s du burst.
CAMERA_DASH_ZOOM_TIME = 0.09
# Mort -> fantome : gros plan rapide, secousse + particules, puis recul.
CAMERA_ZOOM_DEATH = 3.0
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

# Stats haut-droit : jauge fantome en haut, puis une ligne par item.
HUD_STAT_ICON = 40
HUD_STAT_GAP = 8  # espace vertical entre deux lignes
HUD_STAT_VALUE_GAP = 10  # espace icone -> valeur
HUD_GAUGE_WIDTH = 168
HUD_GAUGE_HEIGHT = 12
HUD_GAUGE_GAP = 8  # espace libelle "Lvl. X" -> jauge
HUD_GAUGE_LABEL_SIZE = 14
HUD_GAUGE_LOW = 0.22  # le timer fantome pulse sous ce ratio

# --------------------------------------------------------------------------- #
# Debug
# --------------------------------------------------------------------------- #

DEBUG_OVERLAY = True  # autorise le panneau FPS/etat (F3 pour l'afficher, masque au lancement)
DEBUG_SHOW_HITBOXES = False
DEBUG_SHOW_FPS = True  # si l'overlay est off, affiche quand meme le FPS en bas a gauche
# Ignore piques, flammes, ennemis et chute hors carte. F (sacrifice) reste actif.
PLAYER_INVINCIBLE = False
MOUSE_HIDE_DELAY = 3.0  # cache le curseur en jeu apres ce delai sans mouvement
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
EDITOR_PANEL_WIDTH = 400  # largeur du panneau de droite (palette + plaques)
EDITOR_STATUS_HEIGHT = 108  # hauteur de la barre d'etat du bas
EDITOR_ROW_HEIGHT = 36  # hauteur d'une ligne (plaques, chrome)
EDITOR_SWATCH_SIZE = 32  # cote d'une vignette dans la grille
EDITOR_GRID_COLUMNS = 2  # icone + nom, assez large pour lire
EDITOR_GRID_CELL_HEIGHT = 40  # une ligne : vignette a gauche, libelle a droite
EDITOR_TAB_HEIGHT = 32
EDITOR_CHIP_HEIGHT = 28
EDITOR_CHIP_SIZE = 13
EDITOR_GRID_LABEL_SIZE = 14
# Press Start 2P est une police 8 px : 16 est un multiple net, plus lisible que 12.
EDITOR_TEXT_SIZE = 16
EDITOR_TITLE_SIZE = 16
EDITOR_ZOOM_MIN = 0.25
EDITOR_ZOOM_MAX = 6.0
EDITOR_ZOOM_DEFAULT = 1.25  # 1.0 = une tuile = TILE_SIZE pixels a l'ecran
EDITOR_ZOOM_STEP = 1.15  # facteur par cran de molette
EDITOR_PAN_SPEED = 1100.0  # pixels ecran par seconde aux fleches
EDITOR_GRID_MIN_ZOOM = 0.45  # sous ce zoom, la grille n'est plus tracee
EDITOR_MESSAGE_TIME = 3.0  # secondes d'affichage d'un message de statut
EDITOR_FLOOD_LIMIT = 20000  # garde-fou du remplissage par zone
EDITOR_MAPS_GLOB = "*.json"
EDITOR_MARQUEE_SPEED = 42.0  # pixels par seconde quand un libelle debord
EDITOR_MARQUEE_PAUSE = 0.85  # pause aux extremites du defilement horizontal

COLOR_EDITOR_BACKGROUND = (13, 14, 20)
COLOR_EDITOR_PANEL = (18, 20, 30)
COLOR_EDITOR_PANEL_BORDER = (68, 74, 98)
COLOR_EDITOR_ROW_ACTIVE = (52, 74, 108)
COLOR_EDITOR_ROW_HOVER = (36, 42, 58)
COLOR_EDITOR_HEADING = (30, 34, 48)
COLOR_EDITOR_GRID = (40, 44, 60)
COLOR_EDITOR_BOUNDS = (120, 132, 172)
COLOR_EDITOR_TEXT = (236, 238, 246)
COLOR_EDITOR_TEXT_DIM = (176, 182, 204)
COLOR_EDITOR_ACCENT = (140, 210, 255)
COLOR_EDITOR_WARNING = (255, 196, 88)
COLOR_EDITOR_DANGER = (240, 96, 96)
COLOR_EDITOR_OK = (120, 210, 140)
COLOR_EDITOR_SELECTION = (128, 200, 255, 55)
COLOR_EDITOR_SELECTION_BORDER = (176, 224, 255)
COLOR_EDITOR_PASTE = (255, 214, 120, 60)
COLOR_EDITOR_HOVER = (255, 255, 255, 38)
COLOR_EDITOR_UNKNOWN = (150, 90, 190)
COLOR_EDITOR_OVERLAY = (8, 10, 16, 235)
COLOR_EDITOR_PLATE = (64, 168, 214, 80)
COLOR_EDITOR_PLATE_BORDER = (140, 220, 255)
COLOR_EDITOR_PLATE_SELECTED = (255, 210, 90, 95)
COLOR_EDITOR_PLATE_INVERT = (214, 120, 64, 80)
COLOR_EDITOR_PLATE_INVERT_BORDER = (255, 176, 96)
COLOR_EDITOR_SPECTRAL = (140, 110, 220, 90)
COLOR_EDITOR_SPECTRAL_BORDER = (196, 176, 255)
COLOR_EDITOR_GATED = (240, 110, 110, 75)
COLOR_EDITOR_GATED_BORDER = (255, 160, 160)
COLOR_EDITOR_GATED_INVERT = (96, 196, 128, 75)
COLOR_EDITOR_GATED_INVERT_BORDER = (150, 230, 170)
COLOR_EDITOR_GATED_IGNITE = (232, 120, 48, 80)
COLOR_EDITOR_GATED_IGNITE_BORDER = (255, 176, 96)
COLOR_EDITOR_LINK = (150, 214, 255)
COLOR_EDITOR_LINK_INVERT = (255, 176, 120)
COLOR_EDITOR_LINK_IGNITE = (255, 150, 70)
