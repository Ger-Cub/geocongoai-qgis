# GeoCongo AI pour QGIS

Extension QGIS connectée au SDK GeoCongo AI `0.4.3` pour la recherche documentaire géoscientifique, la télédétection, l'analyse de forages et l'assistance en langage naturel dans QGIS.

## Vue d'ensemble

Le plugin ajoute un panneau latéral et des boîtes de dialogue dédiées pour travailler avec quatre briques principales :

- `Mtumishi` : assistant QGIS pour dialoguer avec le plugin, exécuter des actions dans QGIS et mobiliser les moteurs GeoCongo AI.
- `Pekua` : recherche documentaire RAG sur des rapports, thèses, cartes et publications géoscientifiques.
- `Gundua` : analyses de télédétection et workflows Greenfield sur l'emprise courante de la carte.
- `Chimbua` : analyse de forages, clustering 3D, estimation de ressources et exports de rapports.

## Fonctionnalités principales

- Assistant Mtumishi avec conversation persistante, streaming en temps réel et rendu Markdown dans le chat.
- Journal visuel des actions de Mtumishi en coulisse : `status`, `thought`, `tool_call`, `tool_result`.
- Diagnostic automatique au démarrage pour vérifier que le moteur conversationnel avancé est prêt dans le Python de QGIS.
- Bouton `Réparer` pour tenter l'installation ou la mise à jour automatique des dépendances nécessaires à Mtumishi.
- Recherche `Pekua` avec synthèse RAG, sources citées et recherche documentaire filtrée par domaine et province.
- Analyse `Gundua` avec BBOX dynamique, exécution asynchrone via `QgsTask` et chargement automatique des couches vectorielles et raster.
- Analyse `Chimbua` avec sélection native des couches QGIS, préparation des jeux de forages, clustering DBSCAN, vue 3D HTML et rechargement des résultats 3D dans QGIS.
- Estimation de ressources pilotable depuis Mtumishi avec validation métier des champs, interpolation `IDW` ou `Ordinary Kriging`, classification des blocs et chargement d'une couche ressources dans QGIS.
- Symbologie automatique des catégories de ressources dans QGIS (`Mesuré`, `Indiqué`, `Inféré`, `Non Économique`).
- Export automatique du rapport de ressources en `HTML` et `JSON`.
- Outils QGIS utilisables par Mtumishi : liste de couches, zoom, suppression de couche, symbologie raster, scripts PyQGIS, préparation de forages, pipeline Chimbua 3D et estimation de ressources.

## Installation

### 1. Installer le plugin

Copiez ce dossier dans le répertoire des extensions QGIS, par exemple :

```text
~/.local/share/QGIS/QGIS3/profiles/default/python/plugins/geocongoai_qgis
```

Puis redémarrez QGIS ou rechargez l'extension.

### 2. Installer les dépendances Python

Le plugin repose sur le paquet `geocongoai`. Dans l'environnement Python utilisé par QGIS :

```bash
python3 -m pip install --user --upgrade geocongoai[agent]
```

Selon votre environnement, vous pouvez aussi installer explicitement :

```bash
python3 -m pip install --user --upgrade geocongoai google-genai protobuf
```

## Configuration

Ouvrez `GeoCongo AI > Paramètres API & Serveur`, puis renseignez :

- `Clé API Google Gemini` pour la conversation IA avancée avec Mtumishi.
- `Clé API GeoCongo AI` pour accéder aux services GeoCongo AI.
- `Modèle Gemini` si vous souhaitez forcer un modèle précis.
- `URL du serveur` seulement pour Gundua si vous utilisez une instance spécifique.

### Diagnostic Mtumishi

Le plugin vérifie automatiquement au démarrage si la conversation IA avancée est prête dans le Python de QGIS.

- Si tout est prêt, Mtumishi fonctionne avec une vraie session conversationnelle.
- Si une dépendance manque ou si `protobuf` est incompatible, un message visuel apparaît dans l'onglet Mtumishi.
- Le bouton `Réparer` tente de corriger automatiquement l'environnement Python de QGIS.

## Utilisation

### Mtumishi

Le panneau `Mtumishi` est l'entrée principale du plugin.

Exemples de demandes :

- `Liste les couches affichées`
- `Zoome sur la couche raster greenfield`
- `Applique une symbologie sur la couche active`
- `Supprime la couche LC09_L1TP_...`
- `Analyse l'emprise courante pour le cuivre`
- `Prépare les couches assay_BABBITT, collar_BABBITT et survey_BABBITT pour Chimbua`
- `Lance un pipeline Chimbua 3D sur assay_BABBITT`
- `Estime les ressources sur assay_BABBITT avec cutoff 0.5 densité 2.7`
- `Exporte le rapport ressources`

Le chat affiche :

- la réponse utilisateur,
- la réponse de Mtumishi,
- un bloc "ce que fait Mtumishi en coulisse" avec les actions internes utiles au débogage,
- un indicateur visuel pendant la réflexion,
- le texte streamé en direct quand le moteur conversationnel répond.

### Pekua

La boîte de dialogue `Pekua` permet de :

- saisir une question libre,
- filtrer par domaine thématique,
- filtrer par province en RDC,
- obtenir une synthèse RAG,
- voir les sources citées,
- compléter avec une recherche documentaire filtrée.

### Gundua

La boîte de dialogue `Gundua` permet de :

- récupérer l'emprise courante de la carte,
- choisir un type d'analyse (`greenfield`, `landcover`, `illegal_mining`, `landslide`, `lineaments`),
- définir une période en mois,
- lancer l'analyse en arrière-plan,
- ajouter automatiquement les couches de résultat dans QGIS.

### Chimbua

La boîte de dialogue `Chimbua` permet de :

- choisir une couche de forages, assays ou points d'échantillonnage,
- détecter automatiquement les champs utiles,
- lancer un clustering DBSCAN,
- créer une couche résultat dans QGIS,
- exporter une visualisation 3D HTML.

Depuis `Mtumishi`, le moteur Chimbua permet aussi de :

- préparer un dataset de forages à partir des couches `assay`, `collar` et `survey`,
- lancer un pipeline 3D réel avec rechargement des points 3D, collars et volumes,
- estimer des ressources sur un modèle de blocs,
- appliquer une symbologie automatique par catégorie de ressources,
- exporter un rapport `HTML` et `JSON`.

## Architecture rapide

```text
geocongoai_qgis.py              Point d'entrée du plugin QGIS
gui/main_dock.py                Panneau latéral principal et chat Mtumishi
gui/pekua_dialog.py             Recherche documentaire Pekua
gui/gundua_dialog.py            Analyses Gundua
gui/drillhole_dialog.py         Analyse Chimbua / DBSCAN
gui/settings_dialog.py          Clés API, diagnostic et réparation
utils/mtumishi_orchestrator.py  Intégration Mtumishi + outils QGIS locaux
utils/drillhole_adapter.py      Préparation réutilisable des données de forage
tasks/gundua_task.py            Exécution asynchrone Gundua
```

## Développement

### Recharger le plugin

Pendant le développement, rechargez l'extension depuis QGIS ou avec votre outil habituel de reload plugin.

### Vérification syntaxique

```bash
python3 -m py_compile geocongoai_qgis.py gui/*.py utils/*.py tasks/*.py
```

### Test minimal

```bash
python3 test_plugin.py
```

## État actuel

Cette version aligne le plugin avec le SDK GeoCongo AI `0.4.3` et inclut notamment :

- l'intégration réelle de Mtumishi,
- le streaming des réponses,
- le suivi des appels d'outils dans le chat,
- la compatibilité du dialogue Pekua avec les signatures actuelles du SDK,
- le diagnostic et la réparation guidée de l'environnement conversationnel dans QGIS,
- la préparation des couches de forage pour Chimbua,
- le pipeline Chimbua 3D lancé depuis Mtumishi,
- l'estimation de ressources avec classification et exports `HTML` / `JSON`.

## Limites connues

- Le comportement exact des moteurs dépend des clés API, du réseau et de la disponibilité des services distants.
- Certaines actions de Mtumishi sur les couches peuvent nécessiter une meilleure désambiguïsation si plusieurs couches portent des noms proches.
- La réparation automatique dépend des droits d'installation Python disponibles dans l'environnement QGIS local.
- L'estimation de ressources actuelle repose sur les briques disponibles du SDK `0.4.3` et constitue une première intégration orientée workflow, pas encore un module de reporting minier complet.

## Licence

Voir [LICENSE](LICENSE).
