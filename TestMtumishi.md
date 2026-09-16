# Mtumishi et le plugin QGIS GeoCongo AI

Ce document sert à la fois de protocole de test, de documentation fonctionnelle et de base pour une future documentation web de **Mtumishi** dans le plugin **GeoCongo AI pour QGIS**.

## 1. Vue d'ensemble

Le plugin **GeoCongo AI** est une extension QGIS connectée au SDK `geocongoai`. Il regroupe quatre grands modules complémentaires :

- `Mtumishi` : assistant conversationnel pour piloter QGIS et déclencher les moteurs GeoCongo AI en langage naturel.
- `Pekua` : moteur de recherche documentaire géoscientifique et de synthèse RAG.
- `Gundua` : moteur d'analyse de télédétection, d'exploration Greenfield et de détection d'anomalies.
- `Chimbua` : moteur d'analyse de forages, de modélisation 3D, de clustering et d'estimation de ressources.

## 2. Rôle de Mtumishi

Mtumishi est présenté à l'utilisateur comme son **assistant QGIS** pour :

- interagir plus facilement avec le plugin,
- piloter des actions dans QGIS,
- mobiliser Pekua, Gundua et Chimbua,
- enchaîner plusieurs opérations depuis le chat,
- expliquer ce qu'il fait au fur et à mesure.

Mtumishi peut fonctionner dans deux grands modes :

- un mode conversationnel avancé avec vraie session IA lorsque le moteur conversationnel est prêt dans l'environnement Python de QGIS,
- un mode local ou natif avec routage d'actions QGIS quand certaines commandes peuvent être reconnues et exécutées directement.

## 3. Ce que voit l'utilisateur dans l'interface

Le panneau latéral `GeoCongo AI` expose quatre onglets :

- `🤖 Mtumishi`
- `🔍 Pekua`
- `🛰️ Gundua`
- `⛏️ Chimbua`

Dans l'onglet Mtumishi, l'utilisateur dispose de :

- un message d'accueil expliquant son rôle,
- un champ de saisie conversationnel,
- un bouton d'envoi,
- un indicateur visuel pendant la réflexion,
- un rendu Markdown dans le chat,
- un bloc de transparence intitulé `🧠 Ce que fait Mtumishi en coulisse`,
- un diagnostic visuel si le moteur conversationnel avancé n'est pas prêt,
- un bouton `Réparer` pour installer ou mettre à jour automatiquement les dépendances nécessaires.

## 4. Ce que fait Mtumishi en coulisse

Le bloc `🧠 Ce que fait Mtumishi en coulisse` affiche les événements techniques utiles au suivi et au débogage. On y retrouve notamment :

- `status`
- `thought`
- `tool_call`
- `tool_result`
- `error`

Toutes ces traces sont affichées en italique pour qu'elles soient visuellement distinctes de la réponse principale.

Ce bloc permet de savoir :

- si Mtumishi a bien compris l'intention,
- s'il a utilisé un outil QGIS local,
- s'il a réellement appelé un moteur GeoCongo AI,
- quel résultat brut l'outil a renvoyé,
- à quel moment une erreur s'est produite.

## 5. Capacités déjà testées avec succès

### 5.1 Pilotage QGIS

Des tests ont déjà montré que Mtumishi sait piloter QGIS pour des tâches simples et utiles :

- lister les couches affichées,
- reconnaître les couches actives,
- zoomer sur une couche,
- appliquer une symbologie sur une couche raster Greenfield,
- recentrer la vue sur une couche après stylisation,
- supprimer ou manipuler certaines couches selon la commande envoyée.

Exemples de prompts déjà testés :

- `Liste les couches actives`
- `Liste moi les couches affichées`
- `Zoome sur la couche Raster Greenfield GeoCongo AI`
- `Applique une symbologie sur la couche raster greenfield`
- `Zoom sur la couche sur laquelle tu as appliqué la symbologie`

Résultats attendus :

- la bonne couche est identifiée,
- la bonne action QGIS est exécutée,
- le retour utilisateur est clair et orienté usage,
- la trace en coulisse permet de confirmer l'outil réellement appelé.

### 5.2 Pekua

Le module Pekua a déjà été aligné avec le SDK `geocongoai` et corrigé sur les signatures d'appel attendues.

Cas déjà couverts :

- interrogation RAG documentaire depuis la boîte de dialogue Pekua,
- synthèse de la réponse,
- citation de sources,
- restitution Markdown des résultats,
- correction d'une erreur d'appel liée à `ask_rag`.

Exemples de tests Pekua :

- `La géochimie de cuivre à lualaba`
- `Quels rapports parlent du cuivre dans le Katanga ?`
- `Synthétise les documents géologiques sur le cuivre au Lualaba`

Résultats attendus :

- pas d'erreur sur les paramètres envoyés au SDK,
- une synthèse textuelle cohérente,
- une liste de sources ou références documentaires,
- une expérience utilisateur propre dans la boîte de dialogue.

### 5.3 Gundua

Le module Gundua a déjà été testé sur des analyses géospatiales pilotées à partir de l'emprise courante de QGIS.

Types d'analyses déjà intégrés ou visés dans l'interface :

- `greenfield`
- `lineaments`
- `landcover`
- `illegal_mining`
- `landslide`

Exemples de prompts ou usages testés :

- `Analyse l'emprise actuelle pour le cuivre`
- `Lance une analyse greenfield`
- `Applique une symbologie sur la couche raster greenfield`
- `Zoome sur la couche raster greenfield`

Résultats attendus :

- récupération correcte de la BBOX,
- lancement non bloquant via tâche QGIS,
- chargement des couches résultats,
- stylisation raster ou vecteur cohérente.

### 5.4 Chimbua 3D

Le module Chimbua est celui qui a connu le plus d'avancées récentes.

Les tests réussis ont déjà permis de valider :

- la préparation d'un jeu de données de forage depuis des couches QGIS,
- la détection des couches `assay`, `collar` et `survey`,
- le choix automatique d'un champ de teneur plausible,
- le lancement d'un pipeline Chimbua 3D,
- la création d'une couche QGIS résultats,
- la création de couches de colliers et de sommets de volumes,
- l'export d'une visualisation HTML 3D,
- l'ouverture de la dernière visualisation 3D,
- la symbologie QGIS par `cluster_id` ou par teneur.

Exemples de prompts déjà testés :

- `Prépare les couches assay_BABBITT, collar_BABBITT et survey_BABBITT pour une analyse 3D Chimbua`
- `Lance un pipeline Chimbua 3D sur assay_BABBITT avec collar_BABBITT et survey_BABBITT`
- `Ouvre la dernière visualisation 3D Chimbua`
- `Colorie la couche Chimbua par cluster id`
- `Colorie la couche Chimbua par teneur CU`

Résultats déjà observés :

- création de `GeoCongo AI - Chimbua 3D (CU)`,
- création de `GeoCongo AI - Chimbua Collars`,
- création de `GeoCongo AI - Chimbua Hull Vertices`,
- export HTML 3D avec rendu sombre interactif,
- filtre et logique de clusters visibles dans le rendu HTML.

### 5.5 Estimation de ressources

Mtumishi a également commencé à intégrer une logique orientée estimation de ressources, avec :

- validation métier des champs utiles,
- contrôle des paramètres comme `cutoff`,
- génération d'une couche de ressources dans QGIS,
- symbologie des catégories de ressources,
- export de rapports en HTML et JSON.

Exemples de prompts à utiliser :

- `Prépare une estimation de ressources sur assay_BABBITT avec un cutoff de 0.5`
- `Classe les ressources en mesuré, indiqué et inféré`
- `Génère le rapport ressources en HTML et JSON`
- `Applique une symbologie des catégories de ressources`

## 6. Protocole de test complet

Chaque test doit si possible documenter :

- le prompt envoyé,
- la trace des outils,
- le résultat visible dans QGIS,
- les fichiers exportés,
- la qualité du texte final produit par Mtumishi,
- les erreurs ou ambiguïtés observées.

Une grille simple peut être utilisée :

- `OK`
- `KO`
- `À améliorer`

## 7. Campagne de test par domaine

### 7.1 Tests de présentation et de conversation

Objectif :

- vérifier que Mtumishi se présente comme un assistant QGIS clair,
- vérifier la qualité du ton,
- vérifier la persistance de session,
- vérifier le rendu Markdown.

Prompts recommandés :

- `Bonjour`
- `Qui es-tu ?`
- `Que peux-tu faire dans QGIS ?`
- `Comment peux-tu m'aider pour la cartographie ?`

À valider :

- présentation claire de Mtumishi,
- mention de QGIS, GeoCongo AI, Pekua, Gundua et Chimbua,
- texte lisible et bien formaté,
- pas de jargon technique inutile face à un utilisateur final.

### 7.2 Tests de pilotage QGIS

Objectif :

- valider les actions bureautiques et cartographiques de base.

Prompts recommandés :

- `Liste les couches affichées`
- `Supprime la couche LC09_L1TP_173061_20260826_20260826_02_T1_B8`
- `Zoome sur la couche GeoCongo AI - Raster Greenfield`
- `Applique une symbologie sur la couche raster greenfield`
- `Montre-moi les couches actives`

À valider :

- bonne désambiguïsation des noms,
- absence de crash QGIS,
- action réellement visible sur le canevas,
- texte final utile pour l'utilisateur.

### 7.3 Tests Pekua

Objectif :

- valider le RAG géoscientifique et la recherche documentaire.

Prompts recommandés :

- `Recherche des informations sur la géochimie du cuivre au Lualaba`
- `Que disent les rapports sur les minéralisations de cuivre au Katanga ?`
- `Fais une synthèse documentaire sur les gisements de cuivre en RDC`

À valider :

- réponse structurée,
- sources restituées,
- appel correct au moteur Pekua,
- pas d'erreur de signature SDK.

### 7.4 Tests Gundua

Objectif :

- valider la chaîne complète emprise QGIS vers analyse télédétection.

Prompts recommandés :

- `Analyse l'emprise actuelle avec Gundua`
- `Lance une analyse greenfield sur la zone affichée`
- `Détecte les linéaments géologiques`
- `Cherche des indices d'exploitation minière illégale`

À valider :

- BBOX correcte,
- exécution de la tâche sans bloquer QGIS,
- création et chargement des couches résultat,
- restitution claire dans le chat.

### 7.5 Tests Chimbua

Objectif :

- valider le pipeline forage vers 3D.

Prompts recommandés :

- `Prépare les couches assay_BABBITT, collar_BABBITT et survey_BABBITT pour Chimbua`
- `Vérifie si mes couches de forage sont valides pour une analyse 3D`
- `Lance un pipeline Chimbua 3D sur assay_BABBITT avec collar_BABBITT et survey_BABBITT`
- `Ouvre la dernière visualisation 3D Chimbua`
- `Colorie la couche Chimbua par cluster id`
- `Colorie la couche Chimbua par teneur CU`

À valider :

- qualité de la préparation des données,
- cohérence du champ de teneur choisi,
- qualité visuelle des couches résultats,
- ouverture correcte du HTML,
- cohérence entre QGIS et la visualisation web.

### 7.6 Tests ressources

Objectif :

- vérifier que Mtumishi peut commencer à assister des workflows de modélisation plus avancés.

Prompts recommandés :

- `Prépare une estimation de ressources avec cutoff 0.5`
- `Lance une classification des ressources`
- `Génère un rapport ressources HTML`
- `Exporte aussi le rapport ressources en JSON`

À valider :

- garde-fous métier,
- validation des paramètres,
- production d'exports,
- symbologie claire des classes de ressources.

## 8. Tests de robustesse

Ces tests sont essentiels pour la qualité produit.

Prompts à provoquer volontairement :

- `Lance Chimbua avec assay_BABBITT seulement`
- `Utilise XYZ123 comme champ de teneur`
- `Fais une estimation avec cutoff -5`
- `Ouvre la visualisation 3D alors qu'aucun résultat n'existe`
- `Supprime la couche trois`

À valider :

- pas de plantage QGIS,
- message d'erreur compréhensible,
- proposition de correction,
- trace utile en coulisse,
- comportement sûr en cas d'ambiguïté.

## 9. Ambiguïtés déjà observées

Quelques cas réels ont montré que Mtumishi peut encore avoir besoin de garde-fous supplémentaires.

Exemples :

- confusion entre `assay_BABBITT` et `collar_BABBITT` lors d'une préparation de dataset,
- difficulté possible avec les noms de couches numérotés comme `couche trois`,
- tendance à sur-expliquer en anglais dans certaines traces de pensée,
- besoin de meilleure désambiguïsation quand plusieurs couches ont des noms proches.

Ces points doivent être documentés comme connus, car ils servent aussi de feuille de route qualité.

## 10. Ce que la future documentation web devra mettre en avant

La documentation web issue de ce document devra expliquer clairement :

- ce qu'est GeoCongo AI pour QGIS,
- ce qu'est Mtumishi,
- dans quels cas utiliser Pekua,
- dans quels cas utiliser Gundua,
- dans quels cas utiliser Chimbua,
- comment configurer la conversation avancée,
- comment lancer un diagnostic,
- comment réparer automatiquement les dépendances,
- quels prompts sont recommandés,
- quelles sorties attendre dans QGIS,
- quelles limites existent encore.

## 11. Positionnement produit recommandé

Formulation recommandée pour le web :

`Mtumishi est votre assistant intelligent dans QGIS pour dialoguer avec GeoCongo AI, piloter votre logiciel plus facilement et accélérer vos workflows de cartographie, télédétection, recherche documentaire, analyse de forages et modélisation 3D.`

## 12. Exemples de démonstration à montrer sur le site web

### Démo 1 : navigation QGIS

Prompt :

`Liste les couches affichées puis zoome sur la couche raster greenfield`

Ce que cela démontre :

- compréhension du langage naturel,
- enchaînement de deux actions,
- pilotage direct de QGIS.

### Démo 2 : recherche documentaire

Prompt :

`Recherche les informations sur la géochimie du cuivre au Lualaba`

Ce que cela démontre :

- usage de Pekua,
- synthèse documentaire,
- restitution géoscientifique assistée par IA.

### Démo 3 : exploration Greenfield

Prompt :

`Analyse l'emprise actuelle avec Gundua pour rechercher des cibles greenfield`

Ce que cela démontre :

- connexion entre canevas QGIS et analyse distante,
- chargement des résultats,
- usage concret pour l'exploration.

### Démo 4 : modélisation 3D

Prompt :

`Lance un pipeline Chimbua 3D sur assay_BABBITT avec collar_BABBITT et survey_BABBITT puis ouvre la visualisation 3D`

Ce que cela démontre :

- préparation des données,
- lancement du pipeline,
- création de couches 3D,
- export HTML interactif.

### Démo 5 : lecture des clusters

Prompt :

`Colorie la couche Chimbua par cluster id puis zoome sur le cluster le plus intéressant`

Ce que cela démontre :

- interprétation spatiale,
- lecture des regroupements,
- passage du résultat analytique à la décision visuelle.

## 13. Critères d'acceptation globaux

Mtumishi peut être considéré comme prêt pour une communication plus large si :

- il répond de façon claire et cohérente,
- il exécute les actions QGIS annoncées,
- Pekua fonctionne sans erreur de signature,
- Gundua récupère bien l'emprise QGIS,
- Chimbua prépare et exploite correctement les couches de forage,
- les visualisations HTML sont lisibles et stables,
- les erreurs sont gérées sans crash,
- la trace en coulisse confirme le bon usage des outils.

## 14. Limites actuelles à documenter honnêtement

- Certaines requêtes ambiguës sur les couches peuvent encore nécessiter une meilleure désambiguïsation.
- Les workflows d'estimation de ressources restent plus sensibles que Pekua ou Gundua.
- Les très gros exports HTML 3D peuvent nécessiter des optimisations supplémentaires de performance.
- La qualité du résultat dépend de la qualité des couches QGIS chargées et du schéma des données forage.

## 15. Recommandation de méthode pour les prochains tests

Pour chaque nouvelle évolution de Mtumishi :

- tester d'abord un cas simple,
- tester ensuite un cas conversationnel naturel,
- tester un cas ambigu,
- tester un cas d'erreur volontaire,
- conserver dans ce document les prompts, résultats et captures les plus représentatifs.

Ce fichier doit évoluer comme une **documentation vivante** de Mtumishi dans le plugin QGIS GeoCongo AI.
