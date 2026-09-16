# AGENTS.md — Project Astral Platformer

Guide de reference pour tout agent (humain ou IA) qui travaille sur ce depot.
Lis ce fichier en entier avant d'ecrire une ligne de code : il contient les
conventions, l'architecture, les pieges connus et les commandes a lancer.

---

## 1. Le projet en trois phrases

Platformer 2D d'action-exploration realise pour une GameJam (inspirations :
Celeste pour le feeling, Dead Cells pour l'ambiance). La mecanique signature est
la **dualite corps / fantome** : quand le joueur meurt, son esprit se projette
hors du corps pendant un temps limite, traverse certains murs, revele les
secrets et rapporte des objets, tandis que son **cadavre** reste sur place comme
element de gameplay (plateforme, bouclier anti-piques, appat pour les ennemis).
Les ames des ennemis vaincus font monter le fantome en niveau via des paliers
automatiques (duree, portee, vision, capacite).

Le depot contient pour l'instant un **squelette fonctionnel** : tout demarre,
tourne et le niveau tutoriel est terminable, mais le contenu (assets, niveaux,
ennemis varies, feel) reste a produire.

---

## 2. Stack et commandes

| Element | Valeur |
| --- | --- |
| Langage | Python 3.11+ (teste avec 3.11.11) |
| Moteur | [Arcade](https://api.arcade.academy/) 3.3.3 (OpenGL 3.3, pyglet, pymunk) |
| Dependances | `requirements.txt` uniquement (pas de dependance cachee) |
| Point d'entree | `main.py` |
| Lanceur | `play.sh` (macOS/Linux), `play.bat` (Windows), `play.py` (partout) |
| Version minimale | Python 3.10 (le code utilise `X | None` et `slots=True`) |

```bash
# Lancer le jeu : aucune installation manuelle, aucune activation de venv
./play.sh                          # macOS / Linux
play.bat                           # Windows
python3 play.py                    # equivalent multiplateforme

./play.sh --play                   # options transmises a main.py
./play.sh --level 0
./play.sh --check                  # lance le smoke test au lieu du jeu

# Verifier que tout compile et tourne (A FAIRE AVANT CHAQUE COMMIT)
python -m compileall -q main.py settings.py src tools play.py
./play.sh --check
```

### Comment fonctionne le lancement

`tools/bootstrap.py` contient toute la logique d'environnement et n'utilise
**que la bibliotheque standard** (il doit tourner avant qu'Arcade n'existe) :

1. l'interpreteur courant a Arcade -> on joue directement avec lui ;
2. sinon `.venv/` existe et contient Arcade -> le jeu est relance avec ce
   Python-la ;
3. sinon `.venv/` est cree (avec le Python 3.10+ le plus recent trouve sur la
   machine, meme si la commande a ete lancee avec un Python plus ancien), les
   dependances sont installees, puis le jeu est relance.

`main.py` est protege par le meme mecanisme : son `import arcade` est dans un
`try` et, en cas d'echec, il appelle `bootstrap_and_relaunch`. Consequence :
`python main.py` finit toujours par marcher, y compris avec le Python systeme.
La variable d'environnement `ASTRAL_BOOTSTRAP_DONE` empeche toute boucle de
relances.

**A ne pas casser** : garde `tools/bootstrap.py` sans dependance externe, et
laisse l'`import arcade` de `main.py` dans son `try/except`. Si tu ajoutes une
dependance, mets-la dans `requirements.txt` : le lanceur la prendra en compte
automatiquement (supprime `.venv/` pour forcer une reinstallation).

`tools/smoke_test.py` cree une fenetre invisible (`visible=False`) : il ne
demande aucune interaction et peut tourner en CI. Il verifie, dans l'ordre :
les cartes se chargent, la progression d'ames fonctionne, la boucle
`PLAYING -> GHOST -> RESPAWNING -> PLAYING` s'enchaine, **le niveau 1 est
resolvable de bout en bout**, et les menus se dessinent. Un `exit code` non nul
signifie que le squelette est casse : repare avant de continuer.

---

## 3. Arborescence commentee

```
gamejam2026/
├── play.sh / play.bat      Lanceurs macOS-Linux / Windows : trouvent un Python et appellent play.py
├── play.py                 Lanceur : prepare l'environnement puis lance main.py (ou le smoke test)
├── main.py                 Cree la fenetre Arcade, affiche la premiere vue, lance arcade.run()
├── settings.py             TOUTES les constantes (ecran, FPS, gravite, timers, couleurs, chemins)
├── requirements.txt        Dependances (arcade)
├── agents.md               Ce fichier
├── README.md               Presentation, installation, controles
│
├── assets/                 Ressources, AUCUN code
│   ├── sprites/            Tuiles, joueur, fantome, cle (planches chargees via `ui/sprites.py`)
│   ├── animations/         Planches d'ennemis (squelette : Enemies/Skeletons/...)
│   ├── sons/               Bruitages et musiques - vide pour l'instant
│   └── maps/               Niveaux au format JSON
│       └── level_1_tuto.json
│
├── src/
│   ├── entities/           TOUT CE QUI VIT, BOUGE OU INTERAGIT
│   │   ├── player.py       Corps physique : marche, saut (coyote time), gravite, inventaire, mort
│   │   ├── ghost.py        Fantome : vol libre, longe, timer, revelation, transport d'objets
│   │   ├── corpse.py       Cadavre : solide, perissable, devorable par les ennemis
│   │   ├── enemy.py        IA basique (PATROL / CHASE / FEAST) + bille bleue a la mort
│   │   ├── zombie.py       Traqueur : vision en cone, cri, course, memoire, chute, 2 PV
│   │   └── item.py         Objets ramassables (cle, bille bleue) et leurs regles de ramassage
│   │
│   ├── world/              L'ENVIRONNEMENT ET LE DECOR
│   │   ├── level.py        Chargement JSON, SpriteLists, chunks de rendu (culling camera)
│   │   ├── camera.py       CameraRig : camera monde (suivi lisse + clamp) + camera UI
│   │   ├── fog.py          Voile radial du mode fantome (degrade noir -> transparent)
│   │   └── obstacles.py    Wall, SpectralWall, Spike, Door, Checkpoint
│   │
│   ├── systems/            LES REGLES ET LA LOGIQUE GLOBALE
│   │   ├── game_state.py   GameState + GameStateMachine + GameSession + PlayView (vue de jeu)
│   │   ├── collisions.py   Detection pure des chocs de gameplay (ne modifie rien)
│   │   └── upgrades.py     Essence d'ame, paliers, GhostStats
│   │
│   └── ui/                 L'INTERFACE UTILISATEUR
│       ├── keys.py         Atlas Kenney des touches (relache / enfonce)
│       ├── hud.py          HudData + Hud : ames, timer fantome, icones clavier, jauge dash
│       ├── debug.py        Overlay FPS / etats / tuiles visibles (DEBUG_OVERLAY, F3)
│       ├── display.py      Redimensionnement et plein ecran
│       └── menus.py        TitleView, GameOverView, VictoryView
│
└── tools/
    ├── bootstrap.py        Creation de .venv, installation des dependances, relance (stdlib seule)
    └── smoke_test.py       Test de demarrage et de jouabilite sans interaction
```

---

## 4. Architecture et regles de dependances

Le sens des dependances est **strict**. Le respecter evite les imports
circulaires et garde les regles testables :

```
settings  <-  entities  <-  world  <-  systems  <-  ui
   ^-------------- tout le monde peut importer settings --------------^
```

* `settings.py` n'importe **rien** du projet et surtout **pas `arcade`** : ce
  sont des valeurs brutes, utilisables meme sans fenetre.
* `entities/` ne connait ni le niveau ni les etats de jeu : une entite sait se
  deplacer et decrire son etat, c'est tout. Exception assumee : `enemy.py`
  importe `corpse`, `item` et `player` car son IA les cible.
* `world/` assemble le decor et fournit les `SpriteList` au reste.
* `systems/` orchestre : `game_state.PlayView` est le seul endroit qui applique
  les consequences (mort, ramassage, victoire).
* `ui/` ne fait que dessiner et transmettre les entrees clavier.

**Import circulaire connu et autorise** : `ui/menus.py` importe `PlayView`
depuis `systems/game_state.py` au niveau module, et `game_state.py` importe les
vues de menu **dans les methodes** (`_complete_level`, `on_key_press`). Ne
remonte pas ces imports en haut du fichier.

### Separation collisions / consequences

`systems/collisions.py` ne contient que des fonctions **sans effet de bord** qui
retournent ce qui a ete touche. Les consequences sont appliquees par
`PlayView._resolve_player_collisions` / `_resolve_ghost_collisions`. Garde cette
separation : elle permet de tester les regles sans contexte OpenGL.

---

## 5. Boucle de jeu et machine a etats

```
                 ENTREE
                   |
                [MENU] --------------------------+
                   |                             |
                   v                             |
     +--------> [PLAYING] --- porte + cle ---> [VICTORY] --> niveau suivant / VictoryView
     |          |   ^                             |
     |     mort |   | corps rendu                 |
     |          v   |
     |        [GHOST] -- timer ecoule / touche R --> [RESPAWNING]
     |             |                                     |
     +-------------+-------------------------------------+
```

* Les transitions autorisees sont declarees dans `_TRANSITIONS`
  (`systems/game_state.py`). `GameStateMachine.to()` **leve** une
  `StateTransitionError` si la transition est interdite ; `try_to()` retourne
  `False` a la place. En jeu, prefere `try_to` / `can` pour ne jamais crasher.
* `MENU`, `GAME_OVER` correspondent aussi a des `arcade.View`
  dediees dans `ui/menus.py` ; `PLAYING`, `GHOST`, `RESPAWNING`, `VICTORY` sont
  des sous-etats de `PlayView`.
* `GameSession` (progression, index de niveau, nombre de morts) est passee de
  vue en vue : c'est la seule donnee qui survit a un changement de vue.

### Ordre d'une frame de `PlayView`

1. `level.update()` : cadavres (gravite, decompte, fondu) et objets (flottement).
2. Selon l'etat : `_update_playing`, `_update_ghost` ou `_update_respawning`.
3. Entites : entree clavier -> deplacement -> moteur de physique.
4. Ennemis : IA (cadavre > joueur > patrouille) puis physique.
5. Collisions de gameplay -> consequences -> transitions d'etat.
6. Camera (suivi du joueur ou du fantome).
7. `on_draw` : camera monde (decor, entites, voile du fantome, hitboxes si
   `DEBUG_SHOW_HITBOXES`) puis camera UI (HUD + overlay si `DEBUG_OVERLAY`).

---

## 6. Specification des mecaniques (etat actuel du code)

### Corps physique — `entities/player.py`
* Vitesse max `PLAYER_SPEED`, atteinte en `PLAYER_ACCEL_TIME` (1 s) de course continue.
* Glissade `PLAYER_SLIDE_TIME` a l'arret (sol), controle aerien `PLAYER_AIR_CONTROL`.
* Atterrissage : `PLAYER_LANDING_SLOW_TIME` a `PLAYER_LANDING_SPEED_SCALE`.
* Saut `PLAYER_JUMP_SPEED`, gravite joueur `PLAYER_GRAVITY` (plus legere que
  `GRAVITY` des cadavres / ennemis), coyote `PLAYER_COYOTE_TIME`.
* `cut_jump()` : saut a hauteur variable quand la touche est relachee.
* Dash `Maj` : `PLAYER_DASH_SPEED` pendant `PLAYER_DASH_DURATION`, recharge
  `PLAYER_DASH_COOLDOWN` (jauge HUD + flash quand elle est pleine). Trainee
  d'afterimages + secousse camera (`CAMERA_DASH_SHAKE`).
* Meurt au contact des piques, sous le coup d'epee d'un ennemi, ou en sortant du niveau.
* `inventory` : ensemble de `ItemKind` (la cle ouvre la porte).

### Fantome — `entities/ghost.py`
* Apparait a la mort, ancre sur le cadavre. Aucune gravite, vol 8 directions.
* Traverse `SpectralWall`, bloque par `Wall` (collision resolue axe par axe).
* `stats` (`GhostStats`) : `max_range` (longe), `duration` (timer),
  `vision_radius`, `carry_capacity`. Valeurs de base dans `settings.py`,
  bonus via les paliers (`PALIERS`).
* Ramasse automatiquement au contact les objets `ghost_can_carry`, et les
  **livre en touchant le cadavre** (`_delivered_items` -> inventaire du corps a
  la reapparition).
* Fin du mode : timer a zero, ou touche `R`.

### Cadavre — `entities/corpse.py`
* Solide (present dans les plateformes du moteur de physique du joueur) : sert
  de marchepied et de bouclier sur les piques.
* `CORPSE_LIFETIME` puis fondu (`CORPSE_FADE_TIME`), ou disparition anticipee
  s'il est devore (`CORPSE_EAT_TIME`).
* **Attention** : un cadavre bloque aussi le joueur. Le cadavre laisse au bord
  du puits du tutoriel gene la course d'elan ; c'est un choix de design assume,
  pas un bug.

### Ennemis — `entities/enemy.py`
* Priorite : cadavre a portee d'odorat (`FEAST`) > joueur a portee (`CHASE`,
  qui passe en `ATTACK` des que le joueur est a portee de melee) > patrouille
  (`PATROL`, demi-tour sur mur ou bord de plateforme).
* `_player_in_range` ignore un joueur trop eloigne verticalement
  (`ENEMY_AGGRO_VERTICAL_RANGE`) : un ennemi au sol ne "suit" pas un joueur
  juste au-dessus de lui sur une autre plateforme, inatteignable.
* En `ATTACK` (declenche a `ENEMY_ATTACK_RANGE` du joueur), l'ennemi s'arrete
  et donne un coup d'epee engage (il ne bouge ni ne se retourne avant la fin
  de l'animation), puis attend `ENEMY_ATTACK_COOLDOWN` avant le suivant.
  **Seul ce coup tue** : `collisions.enemy_striking_player` ne compte que les
  frames ou la lame est tendue (`ENEMY_ATTACK_HIT_FRAMES`,
  `Enemy.strike_active`) et une cible a moins de `ENEMY_ATTACK_REACH` devant
  lui. Toucher le corps d'un ennemi ne tue pas (le joueur peut le traverser) ;
  reculer pendant l'armement permet d'esquiver.
* `_walk_towards` (utilise par `CHASE` et `FEAST`) respecte le meme
  garde-fou anti-vide que `_patrol` (`_blocked_ahead`/`_floor_ahead`) : sans
  ca, un ennemi poste sur une petite plateforme tomberait au sol en
  poursuivant une cible situee au-dela du bord.
* Meurent en un coup quand le joueur retombe sur leur tete
  (`collisions.enemy_stomped_by_player`) et laissent une bille bleue.
* Sprite anime (squelette, `assets/animations/Enemies/Skeletons/...`, planches
  96x64 px) : idle/walk/attack/die geres par un `Animator`, comme le joueur.
  A la mort, l'etat passe a `DYING` : l'ennemi ne bouge plus, ne tue plus au
  contact et ne peut plus etre re-stomp (`collisions.py` ignore les ennemis
  `DYING`), le temps que `Die` se joue une fois ; il n'est retire de la
  `SpriteList` qu'a la fin de l'animation.
* Dans `level_1_tuto.json`, l'unique ennemi est sur une petite corniche
  flottante pres du spawn (`rows[27]` col 11, sol `rows[28]` cols 9-13) : a
  un saut du chemin principal, mais hors du couloir au sol que parcourent les
  scripts de `smoke_test.py` (`check_gameplay_loop`,
  `check_tutorial_is_solvable`) — ne pas le reposer sur le sol principal sans
  rejouer ces tests.

### Zombie — `entities/zombie.py`
* Ennemi au sol a **2 PV** (`ZOMBIE_HIT_POINTS`) : le 1er coup declenche
  `EnemyBase._on_hurt` -> etat `HURT` (flash blanc, interrompt l'attaque),
  puis il fonce sur le joueur meme sans le voir. Le 2e coup le tue.
* **Vision** (`_can_see`) : demi-plan du cote ou il regarde, jusqu'a
  `ZOMBIE_SIGHT_RANGE`, **ligne de vue** bloquee par les murs
  (`arcade.has_line_of_sight`, testee au plus toutes les
  `ZOMBIE_SIGHT_CHECK_INTERVAL` s). Dans son dos, il ne sent le joueur qu'a
  `ZOMBIE_BACK_SENSE_RANGE`. Verticalement asymetrique : peu vers le haut
  (il ne grimpe pas), `ZOMBIE_MAX_DROP_TILES` tuiles vers le bas.
* `PATROL` lente -> `ALERT` (cri, Hurt sans la frame blanche) -> `CHASE` en
  course (Walk accelere, pas de planche Run). Demi-tour en course freine
  pendant `ZOMBIE_TURN_TIME` : sauter par-dessus lui fait gagner du temps.
* Vue perdue : court au dernier point vu pendant `ZOMBIE_MEMORY_TIME`, puis
  `SEARCH` (regarde a gauche/droite) pendant `ZOMBIE_SEARCH_TIME`, puis
  `PATROL`. Le revoir en `CHASE`/`SEARCH` relance la course sans cri.
* `ATTACK` : griffe bondissante (elan sur les frames 0-3, frames actives
  `ZOMBIE_ATTACK_HIT_FRAMES`), fin penchee = fenetre pour le punir.
  `ZOMBIE_ATTACK_RANGE > ZOMBIE_ATTACK_REACH` : c'est le bond qui comble.
* **Chute** (`_may_drop`) : en course seulement, il saute d'un bord si sa
  cible est plus bas et qu'un sol existe a au plus `ZOMBIE_MAX_DROP_TILES`
  tuiles (sur 2 colonnes, pour l'elan). Les puits du tutoriel sont plus
  profonds : il ne s'y jette pas. En patrouille, demi-tour au bord.
* `FEAST` : cadavre a `ZOMBIE_CORPSE_SMELL_RANGE` (400 px, plus que le
  squelette), il y va en courant ; au level design, garde les zombies a
  plus de 400 px des endroits ou le joueur doit mourir.
* Planches `Zombie_Default_*` 64x64, dessinees **tournees vers la gauche**
  (`ZOMBIE_SPRITE_FACES_LEFT`), pieds a 16 px du bas de la frame (d'ou la
  hitbox 22x30 native). Agrandies x`ZOMBIE_SCALE` (1.5) au chargement pour
  avoir la taille du squelette : hitbox et offsets sont en pixels finaux.
  Les durees d'animation passent par `ANIM_SPEED` (0.5).
* Dans `level_1_tuto.json` (symbole `z`) : zone de test, juste apres le
  squelette sur le sol principal (`rows[31]` col 34). Il est sur le couloir
  des scripts de `smoke_test.py` (`check_tutorial_is_solvable` passe
  toujours) : si tu le deplaces ou changes ses stats, relance le smoke test.

### Ames et paliers — `systems/upgrades.py`
* Une bille bleue ramassee = `SOUL_ESSENCE_PER_ORB` essence.
* Le niveau du fantome vient de `SOUL_LEVEL_THRESHOLDS` (essence *totale*
  recoltee). Atteindre un palier debloque ses bonus automatiquement (pas de shop).
* Un `Palier` est **purement declaratif** (niveau requis + bonus additifs) :
  pour en ajouter un, ajoute une entree dans `PALIERS`, rien d'autre.

---

## 7. Format des cartes (`assets/maps/*.json`)

```json
{
  "name": "Le Puits Mortel",
  "hint": "texte optionnel (les icones clavier du HUD le remplacent en jeu)",
  "tile_size": 32,
  "legend": { "#": "wall", "^": "spike", "P": "player_spawn" },
  "rows": ["########", "#..P...#"]
}
```

* `rows` se lit **de haut en bas** : la premiere chaine est la ligne la plus
  haute. Toutes les lignes doivent avoir la **meme longueur** (sinon
  `LevelFormatError`).
* `.` = vide (implicite). Tout autre symbole doit figurer dans `legend`.
* Types disponibles (cles de `_FACTORIES` dans `world/level.py`) :
  `wall`, `spectral_wall`, `spike`, `door`, `checkpoint`, `player_spawn`,
  `key`, `soul_orb`, `enemy`, `bat`, `zombie`, `torch`.

**Ajouter un type de tuile** : creer la classe dans `world/obstacles.py` (ou
l'entite dans `entities/`), ajouter une petite fonction `_add_xxx` et son entree
dans `_FACTORIES`, puis le symbole dans la legende de la carte.

**Ajouter un niveau** : deposer le JSON dans `assets/maps/`, puis l'ajouter a
`settings.LEVEL_SEQUENCE` (l'ordre de ce tuple est l'ordre de jeu). La
transition de niveau est automatique (`GameSession.advance_level`).

**Contraintes de level design a respecter** (valeurs actuelles) :
* largeur actuelle du tutoriel : **160 tuiles** (4 ecrans de 40) ;
* hauteur actuelle du tutoriel : **48 tuiles** (1536 px, plus haut que l'ecran
  de 720 px) pour exercer le defilement vertical ;
* portee de saut du corps : environ **185 px**, soit 5 tuiles au maximum et
  4 tuiles confortablement ;
* longe du fantome : **480 px** au depart (la cle du tutoriel est a 430 px du
  cadavre : c'est volontairement serre) ;
* un ennemi sent un cadavre a **320 px** : ne place pas d'ennemi a moins de
  cette distance d'un endroit ou le joueur doit mourir, sinon son cadavre est
  devore avant de servir.
* le premier `C` de la carte est le spawn initial ; les suivants ne deviennent
  le point de reapparition que lorsque le corps les touche.

---

## 8. Conventions de code

1. **Langue** : identifiants et noms de fichiers en anglais
   (`Player`, `Corpse`, `max_range`), docstrings et commentaires en francais,
   **sans accents** (le code reste lisible sur tous les terminaux et evite les
   soucis d'encodage). Les textes affiches a l'ecran suivent la meme regle pour
   l'instant.
2. **Annotations de type partout**, avec `from __future__ import annotations` en
   tete de fichier.
3. **`dataclass`** pour les structures de donnees (`frozen=True` + `slots=True`
   si l'objet est immuable : `GhostStats`, `ItemProfile`, `HudData`, `Palier`).
4. **Une responsabilite par module.** Si un fichier depasse ~300 lignes ou
   melange deux sujets, decoupe-le.
5. **Aucune constante magique dans le code** : toute valeur de gameplay,
   couleur ou chemin va dans `settings.py`.
6. **Commentaires utiles uniquement** : explique une contrainte ou un choix non
   evident, jamais ce que le code dit deja. Les intentions non implementees sont
   marquees `TODO(sujet) : ...` (sujets utilises : `design`, `gameplay`, `rendu`).
7. **Validation des entrees des methodes publiques** : leve `ValueError` /
   `TypeError` sur un argument invalide (voir `SoulProgression.absorb_orb`,
   `Enemy.take_damage`). Pas de validation dans les methodes privees.
8. **Pas de `except` nu**, pas de `print` de debug laisse dans `src/`
   (les `print` sont reserves a `tools/`).

---

## 9. Pieges Arcade a connaitre

* **`Sprite.kill()` existe deja** dans Arcade (retire le sprite de toutes ses
  listes). Ne le redefinis pas : le joueur utilise `die()`, l'ennemi
  `take_damage()`.
* **Signature de `update`** : Arcade appelle `sprite.update(delta_time)` via
  `SpriteList.update()`. Garde toujours
  `def update(self, delta_time: float = settings.FRAME_TIME, *args, **kwargs)`.
  Pour passer des arguments supplementaires (`Enemy` a besoin du joueur et des
  cadavres), appelle l'entite directement, pas la `SpriteList`.
* **`PhysicsEnginePlatformer` et les listes par reference** : les `SpriteList`
  passees dans `walls=[...]` sont conservees telles quelles, donc ajouter un
  cadavre a `level.corpses` le rend solide immediatement, sans reconstruire le
  moteur. **Corollaire** : ne jamais passer a une entite une liste qui la
  contient elle-meme (un cadavre avec `level.corpses` dans ses murs se bloque
  lui-meme) — d'ou `PlayView._static_platforms()`.
* **Vitesses en pixels par frame**, pas par seconde (convention Arcade). La base
  est 60 FPS ; un `delta_time` est quand meme utilise pour les timers. La fenetre
  est creee avec `vsync=True` et `update_rate = draw_rate = 1/60`. Le compteur
  FPS de l'overlay (`ui/debug.py`, actif si `DEBUG_OVERLAY`) mesure le rythme
  de `on_draw`, pas seulement l'update. `F3` bascule l'overlay en jeu.
  `DEBUG_SHOW_FPS` n'affiche le compteur HUD que lorsque l'overlay est masque.
  `Level.draw(view_rect)` ne soumet que les chunks de terrain (`RENDER_CHUNK_TILES`)
  qui chevauchent la camera ; `tiles_drawn` est le nombre reellement envoye au GPU.
* **Hash spatial** sur les murs immobiles (`Level._static_sprite_list`). Sans ca,
  le moteur de physique teste 2000+ tuiles par frame et tombe vers 25 FPS. Les
  cadavres passent dans `platforms`, pas dans `walls`. Le hash ne culle **pas**
  le rendu : d'ou les chunks de `Level._build_render_chunks`.
* **Deux cameras** : dessine le monde avec `camera.use_world()` et le HUD avec
  `camera.use_ui()`, sinon le HUD defile avec le niveau.
* **Jamais `arcade.draw_text` dans une boucle de rendu** : Arcade emet un
  `PerformanceWarning`. Le HUD cree ses objets `arcade.Text` une fois pour
  toutes (`Hud._build_texts`) et les menus passent par le cache `_label` de
  `ui/menus.py`. Utilise l'un des deux plutot que d'appeler `draw_text`.
* **Pas de fenetre = pas de contexte OpenGL** : creer un sprite sans fenetre
  fonctionne, mais dessiner non. Les tests qui dessinent doivent creer une
  `arcade.Window(visible=False)`.

---

## 10. Etat d'avancement

### Fait
* Squelette complet, importable, qui demarre et tourne (`smoke_test` vert).
* Corps physique : marche acceleree, glissade, dash, saut, coyote time, mort, checkpoint, inventaire.
* Fantome : vol, murs spectraux, longe, timer, revelation, transport/livraison.
* Cadavre : solide, gravite, dissipation, devorable.
* Ennemi : patrouille, poursuite, festin, bille bleue, sprite anime (squelette)
  avec mort animee (etat `DYING`).
* Zombie : vision en cone + ligne de vue, cri, course, memoire/recherche,
  griffe bondissante, 2 PV (etat `HURT`), chute controlee.
* Niveau 1 "Le Puits Mortel" charge depuis JSON et **terminable**.
* Camera lissee (constante de temps, look-ahead proportionnel a la vitesse), HUD, ecran titre, victoire, game over.

### A faire (par ordre de priorite pour la jam)
1. **Assets** : joueur, fantome et ennemi (squelette) ont deja des sprites
   animes ; il reste le cadavre (`entities/corpse.py`, encore
   `SpriteSolidColor`), et sons/musique (`assets/sons/`, vide).
2. **Feel** : jump buffer, particules, tremblement de camera, transitions de niveau.
3. **Niveaux** : 3 a 5 cartes apres le tutoriel, introduisant le cadavre comme
   plateforme puis comme bouclier anti-piques.
4. **Combat** : attaque du corps physique (pour l'instant seul l'ecrasement
   tue), varietes d'ennemis (volant, spectral visible seulement en mode fantome).
5. **Revelation** : le voile est un degrade radial (`src/world/fog.py`) dont
   le rayon suit `GhostStats.vision_radius`. Un cone oriente (shader) reste
   optionnel si le feel le demande.
6. **Sauvegarde** de la `GameSession` (JSON) et menu pause.
7. **Tests** : extraire des tests unitaires `pytest` de `tools/smoke_test.py`
   (les fonctions de `collisions.py` et `upgrades.py` se testent sans fenetre).

### Points de design encore ouverts
* La fiche concept dit que la bille bleue est recoltable "uniquement par le
  corps physique" puis que "le fantome recolte la bille bleue". Le code autorise
  les deux (`ItemProfile.body_can_pick` / `ghost_can_carry`) : a trancher.
* Le mode fantome est declenche par la mort **et** volontairement (touche `F`,
  le joueur se sacrifie). Verifier que ca ne casse pas la difficulte.
* Aucune limite au nombre de cadavres : peut devenir un exploit d'escalier
  infini, a surveiller au playtest.

---

## 11. Workflow de jam

* Branche par fonctionnalite (`feat/ghost-dash`, `level/2-catacombes`), petits
  commits, messages a l'imperatif en francais (`ajoute le dash du fantome`).
* Avant chaque commit : `./play.sh --check` doit passer.
* Ne commite pas `.venv/`, `__pycache__/`, `.DS_Store` (deja dans
  `.gitignore`). Les assets, eux, se commitent.
* Si tu changes une valeur de `settings.py` qui touche le level design (saut,
  gravite, longe du fantome), relance le smoke test : il verifie que le niveau 1
  reste resolvable.
* Repartition naturelle du travail sans conflits : `entities/` (gameplay),
  `world/` + `assets/maps/` (level design), `ui/` (interface), `assets/` (art et
  son).

---

## 12. Glossaire francais / code

| Fiche concept | Code |
| --- | --- |
| Corps physique | `Player` |
| Fantome / projection astrale | `Ghost`, `GameState.GHOST` |
| Cadavre | `Corpse` |
| Bille bleue / ame | `ItemKind.SOUL_ORB` |
| Essence d'ame | `SoulProgression.essence` |
| Portee / longe | `GhostStats.max_range`, `Ghost.leash_ratio` |
| Perception extra-sensorielle | `GhostStats.vision_radius`, `Ghost.reveals()` |
| Mur passe-muraille | `SpectralWall` |
| Piques | `Spike` |
| Paliers du fantome | `PALIERS`, `SoulProgression.ghost_stats` |
