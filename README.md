# Project Astral Platformer

Platformer 2D d'action-exploration realise pour la GameJam 2026 (ESIEE).
Inspirations : **Celeste** pour la precision des sauts, **Dead Cells** pour
l'ambiance.

> **Mecanique signature — la dualite corps / fantome.**
> Quand le joueur meurt, son esprit se projette hors du corps : le **fantome**
> traverse certains murs, revele les secrets et rapporte des objets, pendant que
> le **cadavre** reste sur place et devient un element de gameplay (marchepied,
> bouclier sur les piques, appat pour les ennemis). Les ames des ennemis vaincus
> font monter le fantome en niveau.

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
./play.sh --check         # lance le test de demarrage au lieu du jeu
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
| `Q` / `D`, ou fleches gauche / droite | Se deplacer |
| `Espace`, `Z` ou fleche haut | Sauter (hauteur variable : relache pour ecourter) |
| `ZQSD` / fleches | Diriger le fantome (vol libre, 8 directions) |
| `F` | Projeter son esprit (le corps meurt sur place et laisse un cadavre) |
| `R` | En mode fantome : retourner immediatement au corps |
| `Tab` | Arbre de competences |
| `Echap` | Retour au menu titre |

---

## Le niveau 1 : Le Puits Mortel (tutoriel)

1. Avance jusqu'au bord du puits : au fond, une **cle** entouree de **piques**.
2. Appuie sur `F` pour projeter ton esprit. Ton corps s'effondre et laisse un
   cadavre : c'est l'ancre du fantome (et la limite de sa portee).
3. Descends dans la fosse avec le fantome (il ne craint ni la chute ni les
   piques) et touche la cle pour la saisir.
4. Remonte et touche le cadavre pour **livrer** la cle a ton corps.
5. Le timer expire (ou `R`) : tu reapparais au checkpoint avec la cle. Franchis
   le puits d'un saut et ouvre la porte.

En mode fantome, les pieges caches restent invisibles. Une nuee de petits
fantomes apparait progressivement quand tu t'en approches pour signaler le
danger, tandis que les textes secrets ne sont lisibles que par le fantome.

Un bonus est cache dans le niveau : une **ame** enfermee derriere un mur qui
ressemble a de la roche ordinaire. Seul le fantome le revele, en s'en
approchant, et peut le traverser.

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
src/systems/     Etats de jeu, collisions, ameliorations
src/ui/          HUD et menus
tools/           Outils de developpement (smoke test)
```

Les niveaux sont de simples grilles de caracteres en JSON
(`assets/maps/level_1_tuto.json`) : en ajouter un ne demande aucun code, juste
une entree dans `settings.LEVEL_SEQUENCE`.

## Contribuer

Lis **[agents.md](agents.md)** : architecture detaillee, regles de dependances,
conventions de code, format des cartes, contraintes de level design (portee de
saut, longe du fantome), pieges Arcade et feuille de route.
