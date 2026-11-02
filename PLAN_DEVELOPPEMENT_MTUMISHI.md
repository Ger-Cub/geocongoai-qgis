# Plan de développement — Mtumishi comme agent QGIS intégré à GeoCongo AI

## 1. Objet

Ce document définit la feuille de route pour faire évoluer le plugin GeoCongo AI QGIS vers une architecture d’agent IA robuste, inspirée des bonnes pratiques de AI_Agent, tout en conservant la spécificité de Mtumishi : géologie, environnement, exploration minière, télédétection, forages et analyse de ressources.

L’objectif central est que Mtumishi encapsule les fonctionnalités utiles de AI_Agent, sans perdre le contexte scientifique et opérationnel propre au domaine minier et environnemental de GeoCongo AI.

## 2. Vision stratégique

Mtumishi ne doit pas être seulement un assistant de chat dans QGIS. Il doit devenir :

- un moteur d’orchestration agentique local dans QGIS,
- un connecteur intelligent aux données et services GeoCongo AI,
- un contrôleur de workflows analytiques géoscientifiques,
- un système de sécurité, validation et réparation de dépendances,
- une interface unifiée entre le projet QGIS, les données ouvertes, l’API GeoCongo AI et les modules spécialisés.

La finalité : offrir une expérience d’agent IA qui est à la fois simple pour l’utilisateur final, fiable pour les administrateurs QGIS, et profondément adaptée au contexte géoscientifique de la RDC et des projets d’exploration minière.

## 3. Principes directeurs

1. Séparer l’interface QGIS du moteur d’exécution.
2. Séparer config, validation, orchestration, outils et services.
3. Gérer les dépendances et la compatibilité Python/QGIS de façon explicite.
4. Garder les appels aux données externes contrôlés, sécurisés et traçables.
5. Rendre Mtumishi capable d’exécuter à la fois :
   - tâches génériques IA/QGIS,
   - workflows spécialisés géologiques, environnementaux et miniers.
6. Maintenir un modèle de données générique, extensible, facilement testable.
7. Préserver la facilité d’installation pour les utilisateurs non techniques.

## 4. Positionnement de Mtumishi par rapport à AI_Agent

AI_Agent apporte une architecture solide en matière de :

- gestion du plugin QGIS,
- gestion de l’agent et des outils,
- contexte de projet, couches et canevas,
- sources de données ouvertes,
- orchestration de tâches,
- chaînes d’approbation / exécution / annulation,
- gestion d’authentification, comptes et paramètres,
- architecture modulaire propre.

Mtumishi apporte la valeur métier spécifique :

- interprétation géologique,
- analyse environnementale,
- exploration minière,
- télédétection géobotanique,
- STAC / Planetary Computer,
- préparation de forages,
- modélisation 3D, ressources, blocs, grade,
- connaissance du contexte minier et géoscientifique.

Le but est de faire converger les deux mondes :

- AI_Agent = architecture générale d’agent IA pour QGIS,
- Mtumishi = moteur métier géoscientifique et agent de terrain spécialisé.

## 5. Architecture cible

### 5.1. Vue d’ensemble

```text
GeoCongoAI_QGIS/
├── __init__.py
├── geocongoai_qgis.py
├── metadata.txt
├── README.md
├── PLAN_DEVELOPPEMENT_MTUMISHI.md
├── app/
│   ├── bootstrap.py
│   ├── plugin.py
│   ├── lifecycle.py
│   └── menu_actions.py
├── core/
│   ├── settings.py
│   ├── runtime_checks.py
│   ├── compatibility.py
│   ├── controller.py
│   ├── session_manager.py
│   ├── context_builder.py
│   ├── logger.py
│   └── telemetry.py
├── ai/
│   ├── agent.py
│   ├── model_client.py
│   ├── tool_registry.py
│   ├── prompt_manager.py
│   ├── conversation_state.py
│   └── execution_policy.py
├── data/
│   ├── connectors/
│   │   ├── stac.py
│   │   ├── geodata.py
│   │   ├── cloud_api.py
│   │   └── local_files.py
│   ├── project_context.py
│   ├── layer_context.py
│   ├── attachment_manager.py
│   └── dataset_catalog.py
├── geoscience/
│   ├── geology/
│   │   ├── geology_agent.py
│   │   ├── mineral_knowledge.py
│   │   └── mapping_tools.py
│   ├── environment/
│   │   ├── env_agent.py
│   │   ├── risk_tools.py
│   │   └── climate_context.py
│   ├── mining/
│   │   ├── mining_agent.py
│   │   ├── drillhole_tools.py
│   │   ├── resource_estimation_tools.py
│   │   └── exploration_workflows.py
│   └── remote_sensing/
│       ├── stac_tools.py
│       ├── msv_tools.py
│       └── index_workflows.py
├── qgis/
│   ├── layer_tools.py
│   ├── canvas_tools.py
│   ├── processing_tools.py
│   ├── symbology_tools.py
│   ├── export_tools.py
│   └── undo_manager.py
├── api/
│   ├── account_api.py
│   ├── pairing_api.py
│   ├── cloud_client.py
│   └── auth.py
├── ui/
│   ├── main_dock.py
│   ├── settings_dialog.py
│   ├── chat_widget.py
│   └── components/
├── workers/
│   ├── task_worker.py
│   ├── background_tasks.py
│   └── long_running_jobs.py
├── utils/
│   ├── compatibility.py
│   ├── logs.py
│   ├── qgis_helpers.py
│   └── diagnostics.py
└── tests/
    ├── test_compatibility.py
    ├── test_context_builder.py
    ├── test_geo_workflows.py
    └── test_ui_smoke.py
```

### 5.2. Rôle de chaque couche

- `app/` : bootstrap QGIS, chargement des menus, dock, lifecycle.
- `core/` : gestion du moteur, état, paramétrage, vérification environnement.
- `ai/` : orchestrateur d’agent, prompts, outils, garde-fous, API model.
- `data/` : accès aux données ouvertes, données du projet, cloud et données locales.
- `geoscience/` : workflows métiers spécifiques à la géologie, environnement et exploration minière.
- `qgis/` : outils spécialisés QGIS et PyQGIS.
- `ui/` : composants de dialogue et interface utilisateur.
- `workers/` : exécution asynchrone des tâches longues.
- `tests/` : validation continue.

## 6. Ce que Mtumishi doit hériter de AI_Agent

### 6.1. Expérience d’agent IA dans QGIS

Mtumishi doit intégrer les fonctions suivantes dérivées de AI_Agent :

- assistant conversationnel dans un dock QGIS,
- système de contexte projet (couches, canevas, sélection, métadonnées),
- attachement de fichiers et couches au prompt,
- historique de conversation par projet,
- exécution de tâches en plusieurs étapes,
- approbation utilisateur avant modifications destructrices,
- annulation automatique / restauration,
- journal d’étapes et affichage progressif des actions,
- support des tâches longues et non bloquantes via `QgsTask` ou workers.

### 6.2. Gestion des données et des connexions

Le plugin doit intégrer les accès suivants :

- données open source via catalogues STAC,
- données internes du projet QGIS,
- données institutionnelles / cloud GeoCongo AI,
- API de données et de catalogues,
- données d’attachés / fichiers / rasters / shapefiles / GeoJSON.

### 6.3. Outils universels de l’agent

L’agent doit exposer des outils capables de :

- charger des couches,
- lire les propriétés des couches,
- faire du zoom/centrage sur un objet,
- créer un style ou une classification,
- exporter une couche ou un raster,
- exécuter des algorithmes QGIS,
- modifier les attributs, géométries et symboles,
- lancer des tâches de calcul en arrière-plan.

## 7. Ce que Mtumishi doit garder comme spécificité

### 7.1. Domaines métier

Mtumishi doit rester centré sur :

- géologie structurale et lithologique,
- cartographie des minéralisations,
- altérations hydrothermales,
- géobotanique et stress végétal,
- exploration minière,
- forages et ressources,
- données environnementales / risques / hydrographie / occupation du sol,
- télédétection et STAC orientés géosciences.

### 7.2. Outils spécialisés

Il faut ajouter des outils spécifiques :

- recherche de scènes STAC selon bbox, dates et nuages,
- calcul d’indices spectrales et géobotaniques,
- détection d’anomalies minérales,
- préparation de jeux de forages,
- validation d’input de ressource,
- estimation de ressources (IDW, krigeage, clustering),
- production de rapports HTML/JSON,
- symbologie 3D / blocs / grade,
- interprétation de cartes géologiques et d’indices environnementaux.

## 8. Plan d’intégration fonctionnelle

### Phase 1 — Fondation architecturale

Objectif : stabiliser le plugin et préparer la migration vers une architecture modulaire.

Tâches :

- créer les modules `app/`, `core/`, `ai/`, `data/`, `geoscience/`, `ui/`, `workers/` ;
- centraliser les paramètres dans `core/settings.py` ;
- implémenter un runtime checker pour QGIS/Python/SDK ;
- créer un mécanisme de diagnostics et de réparation des dépendances ;
- séparer l’UI de l’orchestration logic ;
- définir un contrat `AgentController` ;
- rendre l’initialisation conditionnelle et non bloquante.

Livrables :

- plugin démarrant proprement sans dépendances non initialisées ;
- messages d’erreur explicites si Python/QGIS/SDK incompatible ;
- architecture modulaire et testable.

### Phase 2 — Reprise des fonctionnalités AI_Agent

Objectif : intégrer les bonnes pratiques d’AI_Agent sans casser Mtumishi.

Tâches :

- migrer la logique de chat dans `ai/agent.py` ;
- créer `tool_registry.py` pour centraliser les outils ;
- ajouter `context_builder.py` pour construire le contexte du projet QGIS ;
- implémenter `attachment_manager.py` ;
- ajouter `project_context.py` et `layer_context.py` ;
- adapter `main_dock.py` pour qu’il parle à `Controller` et non directement au moteur SDK ;
- standardiser les actions d’exécution, approbation et annulation.

Livrables :

- interface utilisateur plus robuste,
- exécution plus claire des tâches,
- meilleur contrôle sur l’état du projet et des layers.

### Phase 3 — Ajout des accès aux données AI_Agent et services GeoCongo

Objectif : faire converger les données AI_Agent et les services GeoCongo dans un même bus de données.

Tâches :

- définir un `DataProvider` unifié : local, cloud, STAC, open data ;
- créer `connectors/stac.py`, `connectors/cloud_api.py`, `connectors/geodata.py` ;
- centraliser les catalogues de datasets ;
- ajouter un accès sécurisé aux APIs GeoCongo et aux services AI_Agent ;
- intégrer le contexte utilisateur / compte / service / quotas ;
- définir le mécanisme de cache et de validation des données.

Livrables :

- accès unique aux données internes et externes,
- plus de dépendance directe aux composants dispersés,
- mécanisme de traçabilité d’accès aux services.

### Phase 4 — Spécialisation géoscientifique de Mtumishi

Objectif : transformer l’agent de base en agent géoscientifique capable d’exécuter des workflows de terrain.

Tâches :

- intégrer `geoscience/geology/`, `environment/`, `mining/`, `remote_sensing/` ;
- formaliser les outils géologiques et environnementaux dans le registry ;
- ajouter les workflows STAC + indices + geobotanique ;
- sécuriser les workflows de forages et de ressource ;
- faire évoluer les prompts pour qu’ils comprennent le vocabulaire géologique et minier.

Livrables :

- workflows miniers et environnementaux exécutables depuis le chat,
- prompts spécifiques et testables,
- outil de synthèse géoscientifique dans le panneau Mtumishi.

### Phase 5 — Fiabilité, compatibilité et installation

Objectif : corriger les douleurs actuelles d’installation et de compatibilité Python/QGIS/SDK.

Tâches :

- créer un `compatibility.py` dédié au contrôle des versions ;
- vérifier `python`, `QGIS`, `geocongoai`, `protobuf`, `pydantic`, `google-genai` ;
- installer automatiquement les dépendances dans le bon environnement QGIS ;
- afficher un diagnostic lisible et un bouton de réparation ;
- ajouter un mode “safe startup” sans rupture si le SDK est absent.

Livrables :

- installation plus facile pour les utilisateurs,
- diagnostics clairs,
- réduction des incidents de compatibilité.

### Phase 6 — Validation, sécurité et industrialisation

Objectif : préparer le plugin pour une diffusion plus large et plus fiable.

Tâches :

- tests unitaires et d’intégration,
- tests UI smoke sur les composants clés,
- validation des workflows miniers et environnementaux,
- scan de sécurité des URLs, clés, fichiers temporaires,
- journalisation d’actions et traçabilité des résultats,
- documentation utilisateur et versioning des releases.

Livrables :

- plugin stable,
- protocoles de sécurité validés,
- meilleure confiance pour les utilisateurs et la communauté.

## 9. Plan de mise en œuvre des modules

### 9.1. `core/settings.py`

Responsabilités :

- lecture et écriture de configuration QGIS ;
- validation des clés API et URLs ;
- migration entre configs legacy et nouvelles ;
- stockage des paramètres par projet ou par profil ;
- support du mode “sans clé / local / cloud / hybride”.

### 9.2. `core/runtime_checks.py`

Responsabilités :

- détecter la version Python du plugin QGIS ;
- détecter si `geocongoai` est installé ;
- détecter les conflits de version ;
- vérifier l’accès à la clé API ;
- afficher un rapport d’intégrité de l’environnement.

### 9.3. `ai/agent.py`

Responsabilités :

- orchestration du modèle,
- gestion du chat,
- appel des outils,
- validation des résultats,
- contrôle des étapes d’exécution,
- gestion de messages streaming ou progressifs.

### 9.4. `ai/tool_registry.py`

Responsabilités :

- centraliser les outils disponibles,
- catégoriser les outils : génériques, SIG, géologie, environnement, minier,
- définir les permissions et éléments de sécurité,
- gérer le cache des outils et la compatibilité d’API.

### 9.5. `data/connectors/*.py`

Responsabilités :

- abriter les fournisseurs de données,
- normaliser les interfaces de retrieval,
- supporter STAC, fichiers, catalogues, Cloud API et projet QGIS,
- traiter les erreurs et les formats hétérogènes.

### 9.6. `geoscience/*`

Responsabilités :

- encapsuler les workflows spécifiques au secteur de l’exploration minière et de l’environnement,
- exposer les capacités métier comme des outils de l’agent,
- ne pas disperser le code de géosciences dans les fichiers UI ou utils.

## 10. Stratégie d’accès aux données AI_Agent et GeoCongo

L’architecture doit considérer trois niveaux de données :

### Niveau 1 — Données du projet QGIS

- couches actives,
- canevas courant,
- sélection utilisateur,
- attributs, styles, géométries,
- print layout et projets associés,
- données de travail en cours.

### Niveau 2 — Données ouvertes / STAC / catalogues

- Planetary Computer,
- Sentinel-2 / Landsat / Sentinel-1 / DEM,
- catalogues thématiques,
- données d’altérations et géobotanique,
- datasets gouvernementaux et institutionnels.

### Niveau 3 — Données service / cloud / AI_Agent

- API GeoCongo AI,
- services catalogues,
- modèles de synthèse / RAG,
- comptes utilisateur,
- historiques, projets partagés, documents géologiques.

Le principe à adopter :

- Les données du projet sont “contextes” de travail.
- Les données externes sont des “sources” accessibles via connecteurs normalisés.
- Les données métier GeoCongo sont “services” avec contrôle d’accès et journalisation.

## 11. Sécurité et gouvernance

L’architecture doit inclure :

- validation des clés API,
- masquage des secrets dans les jounaux,
- vérification des URLs et filtres d’entrée,
- validation de commandes QGIS avant exécution,
- approbation utilisateur sur opérations destructrices,
- journalisation des actions et des résultats,
- gestion des droits par type d’action,
- garde-fous sur scripts PyQGIS exécutés par l’agent.

## 12. Compatibilité Python / QGIS / SDK

C’est un point critique à traiter dès la phase 1.

### Problèmes à corriger

- environnement Python du plugin différent de celui du terminal,
- version de `geocongoai` incompatible avec le runtime QGIS,
- conflits entre dépendances Python déjà présentes,
- chargement trop agressif de modules au démarrage,
- erreurs bloquantes à l’initialisation du plugin.

### Solution cible

- un système de diagnostic au démarrage,
- un `compatibility.py` dédié,
- installation contrôlée dans l’environnement QGIS,
- fallback en mode dégradé si le SDK n’est pas disponible,
- messages clairs de réparation ou de mise à jour,
- sélection d’un environnement Python compatible par profil QGIS.

## 13. Critères de réussite

Le projet sera réussi si, à la fin des phases :

- le plugin s’installe sans friction sur les profils QGIS standards,
- Mtumishi fonctionne dans QGIS sans erreur lors du chargement,
- l’utilisateur n’a pas besoin de manipuler manuellement les dépendances Python,
- l’agent sait utiliser les couches, le canevas, les données STAC et les outils spécifiques,
- le système sait exécuter des workflows géologiques, environnementaux et miniers,
- les actions critiques sont sécurisées et revues par l’utilisateur,
- les résultats sont traçables et maintenables.

## 14. Indicateurs de performance

- temps de démarrage du plugin < 3 secondes en environnement standard,
- diagnostics de compatibilité < 1 seconde,
- taux d’installation réussie sans intervention manuelle > 90 %, 
- tâches métier de forage / STAC / géobotanique exécutées avec succès dans + de 80 % des cas de validation,
- zéro rupture du plugin en environnement QGIS 3.x/4.x avec dépendances compatibles,
- taux d’erreur par session réduit de façon significative.

## 15. Plan de tests

### Tests unitaires

- validation des classes de config,
- validation des connecteurs,
- validation de la construction du contexte projet,
- validation des outils géoscientifiques.

### Tests d’intégration

- chargement du plugin dans QGIS,
- ouverture du dock,
- connection au service AI_Agent,
- exécution d’un workflow de cartographie,
- exécution d’un workflow de STAC,
- exécution d’un workflow de forages / ressources.

### Tests de compatibilité

- Python 3.10 / 3.11 / 3.12 selon environnement QGIS,
- versions QGIS LTR et plus récentes,
- différents systèmes Linux, Windows, macOS.

## 16. Déploiement et release strategy

### Release alpha

- architecture modulaire,
- intégration minimale de AI_Agent,
- premières commandes de chat et outils QGIS,
- diagnostics de compatibilité.

### Release beta

- accès données STAC + GeoCongo,
- workflows géoscientifiques de base,
- rapport de validation sur modèles minimaux.

### Release candidate

- workflows miniers complets,
- meilleure fiabilité de l’agent,
- optimisation de l’UI,
- test sur profils utilisateur réels.

### Release stable

- version livrable pour l’usage de terrain,
- documentation utilisateur,
- procédures de support,
- mécanisme de mise à jour ciblée.

## 17. Recommandation finale

Le bon chemin n’est pas de copier AI_Agent mécaniquement, mais de l’intégrer comme fondation architecturale, puis de spécialiser Mtumishi pour les besoins du secteur géoscientifique, environnemental et minier.

En pratique :

- AI_Agent apporte la discipline architecturale et la robustesse d’agent QGIS ;
- Mtumishi apporte le contexte métier, les workflows scientifiques et les outils de terrain.

L’objectif est donc d’obtenir un système où :

- le plugin reste simple pour l’utilisateur final,
- l’agent reste puissant et explicite,
- les tâches scientifiques sont exécutées avec fiabilité,
- la compatibilité Python/QGIS/SDK est gérée de façon professionnelle,
- les données AI_Agent et GeoCongo sont accessibles dans un cadre unifié et sécuritaire.

## 18. Résumé exécutif

Mtumishi doit devenir le cœur agentique de GeoCongo AI QGIS, en s’inspirant directement de la logique de modularisation de AI_Agent, tout en conservant :

- la mémoire métier géologique,
- les workflows environnementaux,
- la logique d’exploration minière,
- la spécialisation sur les forages et les ressources,
- les outils STAC et géobotaniques,
- une orientation terrain plus proche des besoins réels de prospecteurs et d’ingénieurs.

C’est la bonne direction pour améliorer le produit, réduire les difficultés d’installation, et préparer une base plus solide pour l’avenir du plugin GeoCongo AI QGIS.
