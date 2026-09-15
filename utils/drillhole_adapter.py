"""
Utilities to prepare drillhole, assay and survey data from QGIS layers.

This module keeps the drillhole preparation logic reusable by both the UI
dialogs and Mtumishi's future QGIS -> SDK adapters.
"""

import math


CANDIDATE_HOLE_ID_FIELDS = (
    "hole_id",
    "bhid",
    "dhid",
    "id",
    "collar",
    "borehole",
    "hole",
    "sample_id",
)

X_FIELD_NAMES = ("x", "xcollar", "east", "easting", "lon", "longitude")
Y_FIELD_NAMES = ("y", "ycollar", "north", "northing", "lat", "latitude")
FROM_FIELD_NAMES = ("from", "from_m", "dept_from", "depth_from")
TO_FIELD_NAMES = ("to", "to_m", "dept_to", "depth_to")
Z_FIELD_NAMES = ("z", "elevation", "zcollar", "alt", "depth")
AZIMUTH_FIELD_NAMES = ("az", "azimuth", "bearing", "dir")
DIP_FIELD_NAMES = ("dip", "inclination", "inc", "plunge")
LIKELY_GRADE_FIELDS = (
    "cu_pct",
    "au_ppm",
    "zn_pct",
    "pb_pct",
    "fe_pct",
    "ag_ppm",
    "co_pct",
    "grade",
    "teneur",
    "cu",
    "au",
    "zn",
    "pb",
    "fe",
    "co",
    "ag",
)


def safe_float(value):
    if value is None:
        return None
    text = str(value).strip()
    if hasattr(value, "isNull") and value.isNull():
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not text or text.upper() in ("NULL", "NONE", "NAN", "N/A"):
        return None
    text = text.replace(",", ".")
    try:
        return float(text)
    except (TypeError, ValueError):
        cleaned = "".join(char for char in text if char.isdigit() or char in (".", "-"))
        try:
            return float(cleaned) if cleaned else None
        except ValueError:
            return None


def match_field_name(field_names, exact_names=(), contains_tokens=()):
    normalized = [(name, str(name).lower()) for name in field_names]
    for exact in exact_names:
        exact_lower = exact.lower()
        for original, lowered in normalized:
            if lowered == exact_lower:
                return original
    for token in contains_tokens:
        token_lower = token.lower()
        for original, lowered in normalized:
            if token_lower in lowered:
                return original
    return None


def resolve_field_name(layer, field_name):
    if not layer or not field_name:
        return None
    field_names = [field.name() for field in layer.fields()]
    return match_field_name(field_names, exact_names=(field_name,), contains_tokens=())


def infer_grade_field_name(layer):
    if not layer:
        return None

    field_names = [field.name() for field in layer.fields()]
    grade_field = match_field_name(field_names, exact_names=LIKELY_GRADE_FIELDS, contains_tokens=("grade", "teneur", "cu", "au", "zn", "pb", "fe", "co", "ag"))
    if grade_field:
        return grade_field

    excluded = {
        *(name.lower() for name in CANDIDATE_HOLE_ID_FIELDS),
        *(name.lower() for name in X_FIELD_NAMES),
        *(name.lower() for name in Y_FIELD_NAMES),
        *(name.lower() for name in FROM_FIELD_NAMES),
        *(name.lower() for name in TO_FIELD_NAMES),
        *(name.lower() for name in Z_FIELD_NAMES),
    }
    for field in layer.fields():
        lowered = field.name().lower()
        if lowered in excluded or "hole" in lowered or "dh" in lowered:
            continue
        return field.name()
    return None


def _project_layers(project_or_layers):
    if project_or_layers is None:
        return []
    if isinstance(project_or_layers, (list, tuple)):
        return list(project_or_layers)
    if hasattr(project_or_layers, "mapLayers"):
        return list(project_or_layers.mapLayers().values())
    return []


def _is_valid_vector_layer(layer):
    return bool(layer and hasattr(layer, "isValid") and layer.isValid())


def _is_spatial(layer):
    return bool(layer and hasattr(layer, "isSpatial") and layer.isSpatial())


def _is_point_layer(layer):
    return bool(_is_valid_vector_layer(layer) and _is_spatial(layer) and getattr(layer, "geometryType", lambda: None)() == 0)


def detect_support_layers(assay_layer, project_or_layers=None, collar_layer=None, survey_layer=None):
    layers = _project_layers(project_or_layers)
    if collar_layer and survey_layer:
        return collar_layer, survey_layer

    assay_field_names = [field.name() for field in assay_layer.fields()] if assay_layer else []
    assay_hole_field = match_field_name(
        assay_field_names,
        exact_names=CANDIDATE_HOLE_ID_FIELDS,
        contains_tokens=("hole", "dh"),
    )

    detected_collar = collar_layer
    detected_survey = survey_layer

    if detected_collar is None:
        for layer in layers:
            if layer is assay_layer or not _is_point_layer(layer):
                continue
            if "collar" in layer.name().lower() or "head" in layer.name().lower():
                detected_collar = layer
                break

        if detected_collar is None and assay_hole_field:
            for layer in layers:
                if layer is assay_layer or not _is_point_layer(layer):
                    continue
                layer_field_names = [field.name() for field in layer.fields()]
                matched = match_field_name(
                    layer_field_names,
                    exact_names=(assay_hole_field,) + CANDIDATE_HOLE_ID_FIELDS,
                    contains_tokens=("hole", "dh"),
                )
                if matched:
                    detected_collar = layer
                    break

    if detected_survey is None:
        for layer in layers:
            if layer is assay_layer or not _is_valid_vector_layer(layer):
                continue
            lname = layer.name().lower()
            if "survey" in lname or "devia" in lname:
                detected_survey = layer
                break

    return detected_collar, detected_survey


def infer_drillhole_schema(assay_layer, collar_layer=None, survey_layer=None, grade_field=None):
    if not _is_valid_vector_layer(assay_layer):
        raise ValueError("La couche d'analyses/forages est invalide ou absente.")

    assay_field_names = [field.name() for field in assay_layer.fields()]
    schema = {
        "grade_field": resolve_field_name(assay_layer, grade_field) if grade_field else infer_grade_field_name(assay_layer),
        "assay_hole_id_field": match_field_name(
            assay_field_names,
            exact_names=CANDIDATE_HOLE_ID_FIELDS,
            contains_tokens=("hole", "dh"),
        ),
        "x_field": match_field_name(assay_field_names, exact_names=X_FIELD_NAMES),
        "y_field": match_field_name(assay_field_names, exact_names=Y_FIELD_NAMES),
        "from_field": match_field_name(assay_field_names, exact_names=FROM_FIELD_NAMES),
        "to_field": match_field_name(assay_field_names, exact_names=TO_FIELD_NAMES),
        "z_field": match_field_name(assay_field_names, exact_names=Z_FIELD_NAMES),
        "collar_hole_id_field": None,
        "collar_z_field": None,
        "survey_hole_id_field": None,
        "survey_azimuth_field": None,
        "survey_dip_field": None,
    }

    if collar_layer and _is_valid_vector_layer(collar_layer):
        collar_field_names = [field.name() for field in collar_layer.fields()]
        schema["collar_hole_id_field"] = match_field_name(
            collar_field_names,
            exact_names=tuple(
                candidate for candidate in (schema["assay_hole_id_field"],) + CANDIDATE_HOLE_ID_FIELDS if candidate
            ),
            contains_tokens=("hole", "dh"),
        )
        schema["collar_z_field"] = match_field_name(collar_field_names, exact_names=Z_FIELD_NAMES)

    if survey_layer and _is_valid_vector_layer(survey_layer):
        survey_field_names = [field.name() for field in survey_layer.fields()]
        schema["survey_hole_id_field"] = match_field_name(
            survey_field_names,
            exact_names=tuple(
                candidate for candidate in (schema["assay_hole_id_field"],) + CANDIDATE_HOLE_ID_FIELDS if candidate
            ),
            contains_tokens=("hole", "dh"),
        )
        schema["survey_azimuth_field"] = match_field_name(survey_field_names, exact_names=AZIMUTH_FIELD_NAMES)
        schema["survey_dip_field"] = match_field_name(survey_field_names, exact_names=DIP_FIELD_NAMES)

    return schema


def validate_drillhole_schema(schema, require_grade_field=True):
    errors = []
    if require_grade_field and not schema.get("grade_field"):
        errors.append("Aucun champ de teneur valide n'a été détecté.")
    return errors


def _find_field_index(layer, field_name):
    if not layer or not field_name:
        return -1
    fields = layer.fields()
    index = fields.indexOf(field_name)
    if index == -1:
        index = fields.lookupField(field_name)
    if index == -1:
        for idx, field in enumerate(fields):
            if field.name().lower() == field_name.lower():
                return idx
    return index


def _build_collar_lookup(collar_layer, schema):
    lookup = {}
    if not (_is_valid_vector_layer(collar_layer) and schema.get("collar_hole_id_field")):
        return lookup

    id_index = _find_field_index(collar_layer, schema["collar_hole_id_field"])
    z_index = _find_field_index(collar_layer, schema.get("collar_z_field"))
    if id_index == -1:
        return lookup

    for feature in collar_layer.getFeatures():
        hole_value = feature.attribute(id_index)
        if hole_value is None:
            continue
        geometry = feature.geometry()
        if not geometry or geometry.isEmpty():
            continue
        point = geometry.asPoint() if not geometry.isMultipart() else (geometry.asMultiPoint()[0] if geometry.asMultiPoint() else None)
        if point is None:
            continue
        lookup[str(hole_value).strip().lower()] = {
            "point": point,
            "z": safe_float(feature.attribute(z_index)) if z_index != -1 else 0.0,
        }
    return lookup


def _build_survey_lookup(survey_layer, schema):
    lookup = {}
    if not _is_valid_vector_layer(survey_layer):
        return lookup

    hole_index = _find_field_index(survey_layer, schema.get("survey_hole_id_field"))
    azimuth_index = _find_field_index(survey_layer, schema.get("survey_azimuth_field"))
    dip_index = _find_field_index(survey_layer, schema.get("survey_dip_field"))
    if hole_index == -1 or (azimuth_index == -1 and dip_index == -1):
        return lookup

    for feature in survey_layer.getFeatures():
        hole_value = feature.attribute(hole_index)
        if hole_value is None:
            continue
        lookup[str(hole_value).strip().lower()] = {
            "azimuth": safe_float(feature.attribute(azimuth_index)) if azimuth_index != -1 else 0.0,
            "dip": safe_float(feature.attribute(dip_index)) if dip_index != -1 else 90.0,
        }
    return lookup


def _build_sdk_assays(assay_layer, schema):
    grade_index = _find_field_index(assay_layer, schema["grade_field"])
    hole_index = _find_field_index(assay_layer, schema["assay_hole_id_field"])
    from_index = _find_field_index(assay_layer, schema["from_field"])
    to_index = _find_field_index(assay_layer, schema["to_field"])
    assays = []

    for feature in assay_layer.getFeatures():
        grade_value = safe_float(feature.attribute(grade_index))
        if grade_value is None:
            continue
        hole_value = feature.attribute(hole_index) if hole_index != -1 else None
        assay = {
            "hole_id": str(hole_value).strip() if hole_value is not None else f"feature_{feature.id()}",
            "from_m": safe_float(feature.attribute(from_index)) if from_index != -1 else 0.0,
            "to_m": safe_float(feature.attribute(to_index)) if to_index != -1 else 0.0,
            schema["grade_field"]: grade_value,
        }
        if assay["to_m"] is None:
            assay["to_m"] = assay["from_m"] or 0.0
        if assay["from_m"] is None:
            assay["from_m"] = 0.0
        assays.append(assay)
    return assays


def _build_sdk_collars(collar_layer, records, schema, survey_lookup):
    collars = []
    if _is_valid_vector_layer(collar_layer) and schema.get("collar_hole_id_field"):
        hole_index = _find_field_index(collar_layer, schema["collar_hole_id_field"])
        z_index = _find_field_index(collar_layer, schema.get("collar_z_field"))
        for feature in collar_layer.getFeatures():
            hole_value = feature.attribute(hole_index) if hole_index != -1 else None
            if hole_value is None:
                continue
            geometry = feature.geometry()
            if not geometry or geometry.isEmpty():
                continue
            point = geometry.asPoint() if not geometry.isMultipart() else (geometry.asMultiPoint()[0] if geometry.asMultiPoint() else None)
            if point is None:
                continue
            survey_info = survey_lookup.get(str(hole_value).strip().lower(), {})
            collars.append({
                "hole_id": str(hole_value).strip(),
                "x": float(point.x()),
                "y": float(point.y()),
                "z": float(safe_float(feature.attribute(z_index)) if z_index != -1 else 0.0),
                "dip": float(survey_info.get("dip") if survey_info.get("dip") is not None else -90.0),
                "azimuth": float(survey_info.get("azimuth") or 0.0),
            })
        return collars

    seen = {}
    for record in records:
        hole_id = record["hole_id"]
        if hole_id in seen:
            continue
        survey_info = survey_lookup.get(hole_id.lower(), {})
        seen[hole_id] = {
            "hole_id": hole_id,
            "x": float(record["point"].x()),
            "y": float(record["point"].y()),
            "z": float(record["z_value"] + record["mid_depth"]),
            "dip": float(survey_info.get("dip") if survey_info.get("dip") is not None else -90.0),
            "azimuth": float(survey_info.get("azimuth") or 0.0),
        }
    return list(seen.values())


def _build_sdk_survey(survey_layer, schema):
    if not _is_valid_vector_layer(survey_layer):
        return []

    hole_index = _find_field_index(survey_layer, schema.get("survey_hole_id_field"))
    azimuth_index = _find_field_index(survey_layer, schema.get("survey_azimuth_field"))
    dip_index = _find_field_index(survey_layer, schema.get("survey_dip_field"))
    if hole_index == -1:
        return []

    survey_rows = []
    for feature in survey_layer.getFeatures():
        hole_value = feature.attribute(hole_index)
        if hole_value is None:
            continue
        survey_rows.append({
            "hole_id": str(hole_value).strip(),
            "azimuth": safe_float(feature.attribute(azimuth_index)) if azimuth_index != -1 else 0.0,
            "dip": safe_float(feature.attribute(dip_index)) if dip_index != -1 else -90.0,
        })
    return survey_rows


def prepare_drillhole_dataset(
    assay_layer,
    grade_field,
    cutoff,
    collar_layer=None,
    survey_layer=None,
    project_or_layers=None,
):
    from qgis.core import QgsPointXY

    if not _is_valid_vector_layer(assay_layer):
        raise ValueError("Aucune couche de forages/analyses valide n'est disponible.")

    collar_layer, survey_layer = detect_support_layers(
        assay_layer,
        project_or_layers=project_or_layers,
        collar_layer=collar_layer,
        survey_layer=survey_layer,
    )
    schema = infer_drillhole_schema(
        assay_layer,
        collar_layer=collar_layer,
        survey_layer=survey_layer,
        grade_field=grade_field,
    )
    validation_errors = validate_drillhole_schema(schema, require_grade_field=True)
    if validation_errors:
        raise ValueError(" ".join(validation_errors))

    grade_index = _find_field_index(assay_layer, schema["grade_field"])
    hole_index = _find_field_index(assay_layer, schema["assay_hole_id_field"])
    x_index = _find_field_index(assay_layer, schema["x_field"])
    y_index = _find_field_index(assay_layer, schema["y_field"])
    from_index = _find_field_index(assay_layer, schema["from_field"])
    to_index = _find_field_index(assay_layer, schema["to_field"])
    z_index = _find_field_index(assay_layer, schema["z_field"])

    if grade_index == -1:
        raise ValueError(f"Le champ de teneur '{grade_field}' n'existe pas dans la couche.")

    collar_lookup = _build_collar_lookup(collar_layer, schema)
    survey_lookup = _build_survey_lookup(survey_layer, schema)

    records = []
    coords = []
    all_values = []
    raw_samples = []

    for feature in assay_layer.getFeatures():
        grade_value = safe_float(feature.attribute(grade_index))
        if len(raw_samples) < 5:
            raw_value = feature.attribute(grade_index)
            if raw_value is not None:
                raw_samples.append(str(raw_value))
        if grade_value is None:
            continue

        all_values.append(grade_value)
        if grade_value < cutoff:
            continue

        hole_id = str(feature.attribute(hole_index)).strip() if hole_index != -1 and feature.attribute(hole_index) is not None else "DH"
        from_value = safe_float(feature.attribute(from_index)) if from_index != -1 else None
        to_value = safe_float(feature.attribute(to_index)) if to_index != -1 else None
        if from_value is not None and to_value is not None:
            mid_depth = (from_value + to_value) / 2.0
        elif from_value is not None:
            mid_depth = from_value
        else:
            mid_depth = 0.0

        point = None
        collar_z = 0.0
        geometry = feature.geometry()
        if geometry and not geometry.isEmpty():
            point = geometry.asPoint() if not geometry.isMultipart() else (geometry.asMultiPoint()[0] if geometry.asMultiPoint() else None)
            if point is None:
                point = geometry.centroid().asPoint()

        if point is None and x_index != -1 and y_index != -1:
            x_value = safe_float(feature.attribute(x_index))
            y_value = safe_float(feature.attribute(y_index))
            if x_value is not None and y_value is not None:
                point = QgsPointXY(x_value, y_value)

        if point is None and hole_id.lower() in collar_lookup:
            collar_info = collar_lookup[hole_id.lower()]
            point = collar_info["point"]
            collar_z = collar_info["z"] or 0.0

        if point is None:
            continue

        survey_info = survey_lookup.get(hole_id.lower())
        if survey_info:
            dip_deg = abs(survey_info.get("dip") if survey_info.get("dip") is not None else 90.0)
            azimuth_deg = survey_info.get("azimuth") or 0.0
            dip_rad = math.radians(dip_deg)
            azimuth_rad = math.radians(azimuth_deg)
            horizontal_distance = mid_depth * math.cos(dip_rad)
            dz = -mid_depth * math.sin(dip_rad)
            dx = horizontal_distance * math.sin(azimuth_rad)
            dy = horizontal_distance * math.cos(azimuth_rad)
            point = QgsPointXY(point.x() + dx, point.y() + dy)
            z_value = collar_z + dz
        else:
            explicit_z = safe_float(feature.attribute(z_index)) if z_index != -1 else None
            if explicit_z is not None:
                z_value = explicit_z
            elif collar_z != 0.0:
                z_value = collar_z - mid_depth
            else:
                z_value = -mid_depth

        record = {
            "feature": feature,
            "grade_value": grade_value,
            "point": point,
            "z_value": z_value,
            "hole_id": hole_id,
            "from_m": from_value,
            "to_m": to_value,
            "mid_depth": mid_depth,
        }
        records.append(record)
        coords.append([point.x(), point.y()])

    return {
        "assay_layer": assay_layer,
        "collar_layer": collar_layer,
        "survey_layer": survey_layer,
        "schema": schema,
        "records": records,
        "coords": coords,
        "stats": {
            "all_values_count": len(all_values),
            "min_grade": min(all_values) if all_values else None,
            "max_grade": max(all_values) if all_values else None,
            "above_cutoff_count": sum(1 for value in all_values if value >= cutoff),
            "source_feature_count": assay_layer.featureCount(),
        },
        "raw_samples": raw_samples,
        "cutoff": cutoff,
        "grade_field": schema["grade_field"],
        "sdk_inputs": {
            "collars": _build_sdk_collars(collar_layer, records, schema, survey_lookup),
            "assays": _build_sdk_assays(assay_layer, schema),
            "survey": _build_sdk_survey(survey_layer, schema),
        },
    }


def build_no_result_message(prepared_dataset):
    stats = prepared_dataset["stats"]
    grade_field = prepared_dataset["grade_field"]
    cutoff = prepared_dataset["cutoff"]
    assay_layer = prepared_dataset["assay_layer"]

    if stats["all_values_count"]:
        if stats["above_cutoff_count"] == 0:
            return (
                f"Aucun échantillon ne dépasse le seuil minimum de teneur ({cutoff}) pour le champ '{grade_field}'.\n\n"
                f"📊 Statistiques lues ({stats['all_values_count']} valeurs) :\n"
                f"• Teneur minimale : {stats['min_grade']}\n"
                f"• Teneur maximale : {stats['max_grade']}\n"
                f"• Exemples : {', '.join(prepared_dataset['raw_samples'][:5])}"
            )
        return (
            f"⚠️ {stats['above_cutoff_count']} échantillons dépassent le seuil ({cutoff}) pour '{grade_field}', "
            "mais aucune géométrie spatiale (X, Y) n'a pu leur être associée.\n\n"
            f"💡 Raison : La couche sélectionnée ('{assay_layer.name()}') est une table sans géométrie exploitable.\n"
            "Sélectionnez la couche de colliers correspondante dans l'interface ou vérifiez les champs X/Y."
        )

    return (
        f"Aucun échantillon n'a pu être lu dans le champ '{grade_field}'.\n"
        "Vérifiez que le champ sélectionné contient bien des valeurs numériques."
    )


def build_resource_sample_points(prepared_dataset):
    sample_points = []
    grade_field = prepared_dataset.get("grade_field") or "grade"

    for record in prepared_dataset.get("records", []):
        point = record.get("point")
        if point is None:
            continue
        grade_value = safe_float(record.get("grade_value"))
        z_value = safe_float(record.get("z_value"))
        if grade_value is None or z_value is None:
            continue
        sample_points.append({
            "hole_id": record.get("hole_id"),
            "from_m": safe_float(record.get("from_m")),
            "to_m": safe_float(record.get("to_m")),
            "x": float(point.x()),
            "y": float(point.y()),
            "z": float(z_value),
            "grade": float(grade_value),
            grade_field: float(grade_value),
        })

    return sample_points


def validate_resource_estimation_inputs(
    prepared_dataset,
    cutoff_grade=0.5,
    density=2.7,
    block_size=(25.0, 25.0, 10.0),
    search_range=100.0,
    min_samples=3,
    method="idw",
):
    errors = []
    warnings = []
    schema = prepared_dataset.get("schema") or {}
    stats = prepared_dataset.get("stats") or {}
    records = prepared_dataset.get("records") or []
    sample_points = build_resource_sample_points(prepared_dataset)
    unique_holes = sorted({str(row.get("hole_id")).strip() for row in sample_points if row.get("hole_id")})

    if not schema.get("grade_field"):
        errors.append("Aucun champ de teneur exploitable n'a été détecté pour l'estimation de ressources.")
    if not schema.get("assay_hole_id_field"):
        errors.append("Un champ identifiant de trou est requis pour une estimation de ressources fiable.")
    if not schema.get("from_field") or not schema.get("to_field"):
        errors.append("Les champs d'intervalles From/To sont requis pour l'estimation de ressources.")
    if not sample_points:
        errors.append("Aucun point 3D de teneur n'est disponible pour interpoler un modèle de blocs.")
    if len(unique_holes) < 2:
        errors.append("Au moins deux trous de forage sont nécessaires pour estimer des ressources.")
    if len(sample_points) < max(4, int(min_samples or 1)):
        errors.append("Le nombre de composites/intervalles exploitables est insuffisant pour interpoler des blocs.")

    if safe_float(cutoff_grade) is None or float(cutoff_grade) < 0.0:
        errors.append("Le cutoff doit être un nombre positif ou nul.")
    if safe_float(density) is None or float(density) <= 0.0:
        errors.append("La densité doit être strictement positive.")
    if len(block_size) != 3 or any(safe_float(value) is None or float(value) <= 0.0 for value in block_size):
        errors.append("La taille de bloc doit contenir trois dimensions strictement positives.")
    if safe_float(search_range) is None or float(search_range) <= 0.0:
        errors.append("La portée de recherche doit être strictement positive.")
    if int(min_samples or 0) < 1:
        errors.append("Le nombre minimum d'échantillons doit être au moins égal à 1.")
    if method not in ("idw", "ordinary_kriging"):
        errors.append("La méthode d'estimation doit être 'idw' ou 'ordinary_kriging'.")

    if not prepared_dataset.get("collar_layer") and not (schema.get("x_field") and schema.get("y_field")):
        errors.append("Une couche collar ou des coordonnées X/Y sont nécessaires pour positionner les forages.")
    if not prepared_dataset.get("survey_layer"):
        warnings.append("Aucune couche survey détectée: les trajectoires seront approximées sans déviation détaillée.")
    if len(unique_holes) < 3:
        warnings.append("Moins de trois trous sont disponibles: la continuité spatiale estimée restera très fragile.")
    if len(sample_points) < 20:
        warnings.append("Le nombre d'intervalles exploitables est faible pour une estimation de ressources robuste.")
    if float(search_range or 0.0) < max(float(block_size[0]), float(block_size[1]), float(block_size[2])) * 1.5:
        warnings.append("La portée de recherche est courte par rapport à la taille des blocs; plusieurs blocs risquent de rester peu informés.")
    if stats.get("above_cutoff_count", 0) == 0 and float(cutoff_grade or 0.0) > 0.0:
        warnings.append("Aucun intervalle source ne dépasse actuellement le cutoff demandé.")

    x_values = [point["x"] for point in sample_points]
    y_values = [point["y"] for point in sample_points]
    z_values = [point["z"] for point in sample_points]
    extent = None
    if x_values and y_values and z_values:
        extent = {
            "xmin": min(x_values),
            "ymin": min(y_values),
            "zmin": min(z_values),
            "xmax": max(x_values),
            "ymax": max(y_values),
            "zmax": max(z_values),
        }

    return {
        "ok": not errors,
        "errors": errors,
        "warnings": warnings,
        "sample_points": sample_points,
        "unique_hole_count": len(unique_holes),
        "sample_count": len(sample_points),
        "extent": extent,
    }
