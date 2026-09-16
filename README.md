# Project Astral Platformer

Platformer 2D d'action-exploration realise pour la GameJam 2026 (ESIEE).
Inspirations : **Celeste** pour la precision des sauts, **Dead Cells** pour
l'ambiance.

> **Mecanique signature — la dualite corps / fantome.**
> Quand le joueur meurt, son esprit se projette hors du corps : le **fantome**
> traverse certains murs, revele les secrets et rapporte des objets, pendant que
> le **cadavre** reste sur place et devient un element de gameplay (marchepied,
> bouclier sur les piques, appat pour les ennemis). Les ames des ennemis vaincus
> font monter le fantome en niveau : assez d'ames debloquent automatiquement
plus de portee, de duree, de vision et de capacite de port.

**Etat actuel : squelette jouable.** Le jeu demarre, la boucle complete
(corps -> mort -> fantome -> cadavre -> reapparition) fonctionne et le niveau
tutoriel est terminable. Les graphismes sont des rectangles de couleur en
attendant les assets.

---

## Lancer le jeu

Il n'y a **rien a installer et rien a activer** : le lanceur cree
l'environnement virtuel et installe les dependances au premier lancement.

```bash
./play.sh                 # macOS / Linux
play.bat                  # Windows (double-clic possible)
python3 play.py           # equivalent, avec n'importe quel Python 3.10+
```

Les options sont transmises au jeu :

```bash
./play.sh --play          # demarre directement le niveau, sans passer par le menu
./play.sh --level 0       # choisit le niveau de depart
./play.sh --fullscreen      # demarre en plein ecran (F11 pour quitter)
```

`python main.py` fonctionne aussi : si Arcade manque dans l'interpreteur
utilise, `main.py` prepare l'environnement et se relance tout seul.

Si tu prefere gerer l'environnement a la main :

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate
python -m pip install -r requirements.txt
python main.py
```

### Verifier que tout fonctionne

```bash
./play.sh --check         # ou : python tools/smoke_test.py dans un venv actif
```

Ce test tourne sans interaction (fenetre invisible) et verifie que les cartes se
chargent, que la boucle de jeu s'enchaine, que **le niveau 1 est resolvable** et
que les menus se dessinent. A lancer avant chaque commit.

### En cas de probleme

| Symptome | Cause et solution |
| --- | --- |
| `ModuleNotFoundError: No module named 'arcade'` | Le Python utilise n'a pas les dependances. Lance `./play.sh` : il s'en occupe. |
| `source: no such file or directory: .venv/bin/activate` | L'environnement n'existe pas encore (ou faute de frappe). Inutile de l'activer : `./play.sh` suffit. |
| `permission denied: ./play.sh` | `chmod +x play.sh`, ou lance `python3 play.py`. |
| Python trop ancien | Le lanceur cherche Python 3.10+ sur la machine ; sinon installe-le depuis [python.org](https://www.python.org/downloads/). |
| Environnement casse | Supprime `.venv/` et relance `./play.sh` : il sera reconstruit. |

---

## Controles

| Touche | Action |
| --- | --- |
| `Q` / `D`, ou fleches gauche / droite | Se deplacer (acceleration ~1 s, glissade tres courte) |
| `Espace`, `Z` ou fleche haut | Sauter (hauteur variable : relache pour ecourter) |
| `Maj` | Dash dans la direction actuelle (jauge en bas a droite) |
| `Espace`, `Z` ou fleche haut | Sauter (hauteur variable : relache pour ecourter) |
| Clic gauche | Attaquer devant soi (mode corps physique) |
| `ZQSD` / fleches | Diriger le fantome (vol libre, 8 directions) |
| `F` | Projeter son esprit (le corps meurt sur place et laisse un cadavre) |
| `R` | En mode fantome : ecourter la projection et reapparaitre tout de suite au dernier checkpoint (au lieu d'attendre la fin du timer) |
| `F11` (ou Alt/Cmd+Entree) | Plein ecran |
| `F3` | Afficher / masquer l'overlay de debug (FPS, etat, tuiles a l'ecran) |
| `Echap` | Retour au menu titre |

---

## Le niveau 1 : Le Puits Mortel (tutoriel)

1. Avance jusqu'au bord du puits : au fond, une **cle** entouree de **piques**.
2. Appuie sur `F` pour projeter ton esprit. Ton corps s'effondre et laisse un
   cadavre : c'est l'ancre du fantome (et la limite de sa portee).
3. Descends dans la fosse avec le fantome (il ne craint ni la chute ni les
   piques) et touche la cle pour la saisir.
4. Remonte et touche le cadavre pour **livrer** la cle a ton corps.
5. Le timer expire (ou `R` pour ecourter) : tu reapparais au checkpoint avec
   la cle. Franchis le puits d'un saut, puis traverse le parcours (fosses,
   piques, caisses) jusqu'a la porte au bout du niveau. Apres le puits, un
   **escalier de plateformes** monte hors ecran : la camera te suit aussi a
   la verticale.

Des **checkpoints** jalonnent la course : les toucher met a jour le point de
reapparition. Plusieurs **ames** sont cachees derriere des murs qui ressemblent
a de la roche ordinaire : seul le fantome les revele et peut les traverser.

---

## Ames et paliers du fantome

Ramasser une **bille bleue** (orbe d'ame) compte pour 1 ame. Le niveau du
fantome depend du **total cumule** sur la partie, pas d'un achat : des qu'un
seuil est atteint, ses bonus s'appliquent tout seuls.

| Niveau fantome | Ames cumulees | Bonus debloques |
| --- | --- | --- |
| 1 (depart) | 0 | Stats de base : 480 px de longe, 12 s de timer, 160 px de vision, 1 objet porte |
| 2 | 3 | **Longe astrale I** (+120 px) et **Persistance I** (+4 s) |
| 3 | 8 | **Perception I** (+60 px de revelation) |
| 4 | 15 | **Poigne spectrale I** (+1 objet transporte) |
| 5 | 25 | (pas de bonus extra pour l'instant) |
| 6 | 40 | (pas de bonus extra pour l'instant) |

Les bonus sont **additifs** et se cumulent. Exemple au niveau 4 : 600 px de
longe, 16 s de timer, 220 px de vision, 2 objets.

Les seuils vivent dans `settings.SOUL_LEVEL_THRESHOLDS`, la liste des bonus
dans `PALIERS` (`src/systems/upgrades.py`). Pour en ajouter un, une entree
dans `PALIERS` suffit.

---

## Structure du projet

```
play.sh          Lanceur macOS / Linux (installe ce qu'il faut puis joue)
play.bat         Lanceur Windows
play.py          Lanceur multiplateforme utilise par les deux precedents
main.py          Point d'entree : cree la fenetre et lance la boucle
settings.py      Toutes les constantes (ecran, FPS, gravite, timers, couleurs)
assets/          Ressources : sprites/, sons/, maps/ (niveaux JSON)
src/entities/    Joueur, fantome, cadavre, ennemis, objets
src/world/       Chargement des niveaux, camera, obstacles
src/systems/     Etats de jeu, collisions, paliers du fantome
src/ui/          HUD, overlay de debug et menus
tools/           Outils de developpement (smoke test)
```

Les niveaux sont de simples grilles de caracteres en JSON
(`assets/maps/level_1_tuto.json`) : en ajouter un ne demande aucun code, juste
une entree dans `settings.LEVEL_SEQUENCE`.

## Contribuer

Lis **[agents.md](agents.md)** : architecture detaillee, regles de dependances,
conventions de code, format des cartes, contraintes de level design (portee de
saut, longe du fantome), pieges Arcade et feuille de route.
