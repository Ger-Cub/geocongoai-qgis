"""
Utilities for Chimbua 3D HTML export and QGIS symbology.
"""

import json
import math


CLUSTER_PALETTE = [
    "#e41a1c",
    "#377eb8",
    "#4daf4a",
    "#984ea3",
    "#ff7f00",
    "#ffff33",
    "#a65628",
    "#f781bf",
    "#00ced1",
    "#ff1493",
    "#7fff00",
    "#00bfff",
    "#ff8c00",
    "#9932cc",
    "#808000",
]
NOISE_COLOR = "#8c8c8c"
GRADE_COLORSCALE = [
    [0.0, "#440154"],
    [0.2, "#355f8d"],
    [0.4, "#1f9e89"],
    [0.6, "#73d055"],
    [0.8, "#fde725"],
    [0.9, "#f8961e"],
    [1.0, "#d62828"],
]


def _coerce_float(value, default=None):
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _percentile(sorted_values, fraction):
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    fraction = min(1.0, max(0.0, float(fraction)))
    position = fraction * (len(sorted_values) - 1)
    lower_index = int(math.floor(position))
    upper_index = int(math.ceil(position))
    if lower_index == upper_index:
        return float(sorted_values[lower_index])
    lower_value = float(sorted_values[lower_index])
    upper_value = float(sorted_values[upper_index])
    weight = position - lower_index
    return lower_value + ((upper_value - lower_value) * weight)


def compute_grade_display_stats(values, lower_fraction=0.02, upper_fraction=0.98):
    numeric_values = sorted(
        value for value in (_coerce_float(item) for item in values)
        if value is not None and math.isfinite(value)
    )
    if not numeric_values:
        return {
            "rawMin": 0.0,
            "rawMax": 0.0,
            "displayMin": 0.0,
            "displayMax": 0.0,
            "p05": 0.0,
            "p95": 0.0,
            "p02": 0.0,
            "p98": 0.0,
        }

    raw_min = float(numeric_values[0])
    raw_max = float(numeric_values[-1])
    p02 = _percentile(numeric_values, lower_fraction)
    p98 = _percentile(numeric_values, upper_fraction)
    p05 = _percentile(numeric_values, 0.05)
    p95 = _percentile(numeric_values, 0.95)

    display_min = p02
    display_max = p98
    if display_min >= display_max:
        display_min = raw_min
        display_max = raw_max
    if display_min >= display_max:
        display_max = display_min + 1.0

    return {
        "rawMin": raw_min,
        "rawMax": raw_max,
        "displayMin": float(display_min),
        "displayMax": float(display_max),
        "p05": float(p05),
        "p95": float(p95),
        "p02": float(p02),
        "p98": float(p98),
    }


def cluster_color(cluster_id):
    if cluster_id in (None, "", -1, "-1"):
        return NOISE_COLOR
    try:
        cluster_int = int(cluster_id)
    except (TypeError, ValueError):
        return NOISE_COLOR
    if cluster_int < 0:
        return NOISE_COLOR
    return CLUSTER_PALETTE[cluster_int % len(CLUSTER_PALETTE)]


def make_qgis_symbol(layer):
    from qgis.core import QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol, QgsWkbTypes

    symbol = None
    with_geometry_type = getattr(layer, "geometryType", None)
    if callable(with_geometry_type):
        try:
            geometry_type = layer.geometryType()
        except Exception:
            geometry_type = None
    else:
        geometry_type = None

    try:
        from qgis.core import QgsSymbol

        symbol = QgsSymbol.defaultSymbol(geometry_type) if geometry_type is not None else None
    except Exception:
        symbol = None

    if symbol is not None:
        return symbol

    wkb_type = None
    with_wkb_type = getattr(layer, "wkbType", None)
    if callable(with_wkb_type):
        try:
            wkb_type = layer.wkbType()
        except Exception:
            wkb_type = None

    if wkb_type is not None:
        geom_type = QgsWkbTypes.geometryType(wkb_type)
        if geom_type == 1:
            return QgsLineSymbol.createSimple({})
        if geom_type == 2:
            return QgsFillSymbol.createSimple({})

    return QgsMarkerSymbol.createSimple({})


def _compute_axis_ranges(points):
    if not points:
        return {"x": [0, 1], "y": [0, 1], "z": [0, 1]}

    def _range(values):
        minimum = min(values)
        maximum = max(values)
        if minimum == maximum:
            padding = max(abs(minimum) * 0.05, 1.0)
            return [minimum - padding, maximum + padding]
        padding = max((maximum - minimum) * 0.08, 1.0)
        return [minimum - padding, maximum + padding]

    return {
        "x": _range([float(point.get("x", 0.0)) for point in points]),
        "y": _range([float(point.get("y", 0.0)) for point in points]),
        "z": _range([float(point.get("z", 0.0)) for point in points]),
    }


def _build_cluster_metadata(points):
    cluster_counts = {}
    cluster_holes = {}
    cluster_points = {}
    for point in points:
        cluster_id = str(int(point.get("cluster", -1) or -1))
        cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1
        cluster_holes.setdefault(cluster_id, set()).add(str(point.get("hole_id", "")))
        cluster_points.setdefault(cluster_id, []).append(point)

    cluster_ranges = {
        cluster_id: _compute_axis_ranges(cluster_points[cluster_id])
        for cluster_id in cluster_points
    }
    cluster_labels = {}
    for cluster_id, count in sorted(cluster_counts.items(), key=lambda item: int(item[0])):
        if cluster_id == "-1":
            cluster_labels[cluster_id] = f"Bruit (-1) - {count} intervalles"
        else:
            cluster_labels[cluster_id] = f"Cluster {cluster_id} - {count} intervalles"

    return {
        "counts": cluster_counts,
        "holes": {cluster_id: sorted(values) for cluster_id, values in cluster_holes.items()},
        "ranges": cluster_ranges,
        "labels": cluster_labels,
    }


def _build_collar_traces(collars, points):
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError("plotly est requis pour exporter la visualisation 3D Chimbua.") from exc

    traces = []
    hole_trace_indices = {}
    grouped_points = {}
    for point in points:
        grouped_points.setdefault(str(point.get("hole_id", "")), []).append(point)

    for collar in collars or []:
        hole_id = str(collar.get("hole_id", ""))
        hole_points = grouped_points.get(hole_id) or []
        if not hole_points:
            continue
        sorted_points = sorted(hole_points, key=lambda item: float(item.get("mid_depth", 0.0) or 0.0))
        trace = go.Scatter3d(
            x=[float(collar.get("x", 0.0))] + [float(point.get("x", 0.0)) for point in sorted_points],
            y=[float(collar.get("y", 0.0))] + [float(point.get("y", 0.0)) for point in sorted_points],
            z=[float(collar.get("z", 0.0))] + [float(point.get("z", 0.0)) for point in sorted_points],
            mode="lines+markers",
            line=dict(color="#c7d0d9", width=4),
            marker=dict(symbol="circle", size=2.8, color="#c7d0d9"),
            name=f"Forage {hole_id}",
            showlegend=False,
            hoverinfo="text",
            text=f"Forage: {hole_id}<br>Profondeur max: {float(sorted_points[-1].get('mid_depth', 0.0) or 0.0):.1f} m",
        )
        hole_trace_indices[hole_id] = len(traces)
        traces.append(trace)

    return traces, hole_trace_indices


def _build_hole_series(collars, points):
    grouped_points = {}
    for point in points:
        grouped_points.setdefault(str(point.get("hole_id", "")), []).append(point)

    hole_series = {}
    for collar in collars or []:
        hole_id = str(collar.get("hole_id", ""))
        hole_points = grouped_points.get(hole_id) or []
        if not hole_points:
            continue
        sorted_points = sorted(hole_points, key=lambda item: float(item.get("mid_depth", 0.0) or 0.0))
        hole_series[hole_id] = {
            "x": [float(collar.get("x", 0.0))] + [float(point.get("x", 0.0)) for point in sorted_points],
            "y": [float(collar.get("y", 0.0))] + [float(point.get("y", 0.0)) for point in sorted_points],
            "z": [float(collar.get("z", 0.0))] + [float(point.get("z", 0.0)) for point in sorted_points],
            "text": f"Forage: {hole_id}<br>Profondeur max: {float(sorted_points[-1].get('mid_depth', 0.0) or 0.0):.1f} m",
        }
    return hole_series


def export_interactive_chimbua_html(result, output_path=None):
    try:
        from geocongoai.visualization.html import _get_logo_b64
    except ImportError as exc:
        raise ImportError("plotly est requis pour exporter la visualisation 3D Chimbua.") from exc

    points = list(getattr(result, "points", []) or [])
    collars = list(getattr(result, "collars", []) or [])
    geometries = list(getattr(result, "geometries", []) or [])
    metadata = dict(getattr(result, "metadata", {}) or {})
    stats = dict(getattr(result, "statistics", {}) or {})
    element = metadata.get("element", "grade")
    clean_title = metadata.get("title", "GeoCongo AI - Visualisation 3D Geologique").replace("🌍 ", "").replace("🌍", "").strip()

    axis_ranges = _compute_axis_ranges(points)
    logo_b64 = _get_logo_b64()
    point_grades = [_coerce_float(point.get(element, point.get("value", 0.0)), 0.0) for point in points]
    grade_stats = compute_grade_display_stats(point_grades)
    point_clusters = [str(int(point.get("cluster", -1) or -1)) for point in points]
    point_cluster_colors = [cluster_color(cluster_id) for cluster_id in point_clusters]
    point_holes = [str(point.get("hole_id", "")) for point in points]
    hover_texts = [
        (
            f"Forage: {point.get('hole_id', 'N/A')}"
            f"<br>Prof: {float(point.get('mid_depth', 0.0) or 0.0):.1f} m"
            f"<br>{element.upper()}: {float(point.get(element, point.get('value', 0.0)) or 0.0):.2f}%"
            f"<br>Cluster: {point_clusters[index]}"
        )
        for index, point in enumerate(points)
    ]
    cluster_meta = _build_cluster_metadata(points)
    hole_series = _build_hole_series(collars, points)
    geometry_payload = {}
    for geometry in geometries:
        cluster_id = str(int(geometry.get("cluster_id", -1) or -1))
        geometry_payload.setdefault(cluster_id, []).append({
            "x": list(geometry.get("vertices", {}).get("x", [])),
            "y": list(geometry.get("vertices", {}).get("y", [])),
            "z": list(geometry.get("vertices", {}).get("z", [])),
            "i": list(geometry.get("simplices", {}).get("i", [])),
            "j": list(geometry.get("simplices", {}).get("j", [])),
            "k": list(geometry.get("simplices", {}).get("k", [])),
            "color": geometry.get("color") or cluster_color(cluster_id),
            "volume_m3": float(geometry.get("volume_m3", 0.0) or 0.0),
        })

    n_points = metadata.get("filtered_intervals", len(points))
    n_clusters = metadata.get("cluster_count", len([cluster_id for cluster_id in set(point_clusters) if cluster_id != "-1"]))
    max_grade = f"{stats.get('max', 0.0):.2f}%" if stats.get("max") is not None else "N/A"
    heavy_dataset = len(points) > 10000 or len(geometries) > 100
    control_data = {
        "elementLabel": element.upper(),
        "points": {
            "x": [float(point.get("x", 0.0)) for point in points],
            "y": [float(point.get("y", 0.0)) for point in points],
            "z": [float(point.get("z", 0.0)) for point in points],
            "text": hover_texts,
            "grades": point_grades,
            "clusters": point_clusters,
            "clusterColors": point_cluster_colors,
            "holeIds": point_holes,
        },
        "holes": hole_series,
        "geometries": geometry_payload,
        "defaultRanges": axis_ranges,
        "clusterRanges": cluster_meta["ranges"],
        "clusterHoleIds": cluster_meta["holes"],
        "clusterLabels": cluster_meta["labels"],
        "clusterCounts": cluster_meta["counts"],
        "minGrade": grade_stats["rawMin"],
        "maxGrade": grade_stats["rawMax"],
        "gradeDisplayMin": grade_stats["displayMin"],
        "gradeDisplayMax": grade_stats["displayMax"],
        "gradeP02": grade_stats["p02"],
        "gradeP98": grade_stats["p98"],
        "gradeP05": grade_stats["p05"],
        "gradeP95": grade_stats["p95"],
        "heavyDataset": heavy_dataset,
        "allClusterIds": sorted(cluster_meta["labels"].keys(), key=int),
        "meshAllClusterLimit": 25,
    }
    control_json = json.dumps(control_data, ensure_ascii=False)
    grade_colorscale_json = json.dumps(GRADE_COLORSCALE, ensure_ascii=False)
    cluster_options = ['<option value="all">Tous les clusters</option>']
    for cluster_id in sorted(cluster_meta["labels"].keys(), key=int):
        cluster_options.append(f'<option value="{cluster_id}">{cluster_meta["labels"][cluster_id]}</option>')

    logo_html = f'<img src="{logo_b64}" class="logo-img" alt="GeoCongo AI Logo">' if logo_b64 else ""
    layout_json = json.dumps(
        {
            "paper_bgcolor": "#1e272e",
            "plot_bgcolor": "#1e272e",
            "margin": {"l": 10, "r": 10, "b": 10, "t": 10},
            "scene": {
                "xaxis": {"title": {"text": "<b>Est (X) [m]</b>", "font": {"color": "#ffffff", "size": 12}}, "backgroundcolor": "#2c3e50", "gridcolor": "#485460", "tickfont": {"color": "#ffffff"}, "range": axis_ranges["x"]},
                "yaxis": {"title": {"text": "<b>Nord (Y) [m]</b>", "font": {"color": "#ffffff", "size": 12}}, "backgroundcolor": "#2c3e50", "gridcolor": "#485460", "tickfont": {"color": "#ffffff"}, "range": axis_ranges["y"]},
                "zaxis": {"title": {"text": "<b>Elevation (Z) [m]</b>", "font": {"color": "#ffffff", "size": 12}}, "backgroundcolor": "#2c3e50", "gridcolor": "#485460", "tickfont": {"color": "#ffffff"}, "range": axis_ranges["z"]},
                "aspectmode": "data",
                "camera": {"eye": {"x": 1.5, "y": 1.5, "z": 0.9}},
            },
        },
        ensure_ascii=False,
    )
    html_code = f"""<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{clean_title}</title>
    <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
    <style>
        * {{ box-sizing: border-box; }}
        body {{ margin: 0; background: #1e272e; color: #ffffff; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif; }}
        header {{
            background: linear-gradient(135deg, #161e23 0%, #1e272e 100%);
            border-bottom: 1px solid #34495e;
            padding: 10px 24px;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
        }}
        .brand-container {{ display: flex; align-items: center; gap: 14px; }}
        .logo-img {{ width: 38px; height: 38px; object-fit: contain; }}
        .header-title {{ font-size: 1.15rem; font-weight: 700; }}
        .header-badges {{ display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }}
        .badge {{
            background-color: rgba(44, 62, 80, 0.7);
            border: 1px solid #485460;
            padding: 5px 12px;
            border-radius: 6px;
            font-size: 0.82rem;
            font-weight: 600;
            color: #dcdde1;
        }}
        .badge-highlight {{ border-color: #91fca3; color: #91fca3; background-color: rgba(145, 252, 163, 0.1); }}
        .layout {{ display: grid; grid-template-columns: 336px 1fr; height: calc(100vh - 61px); }}
        .sidebar {{
            background: rgba(24, 32, 40, 0.36);
            backdrop-filter: blur(12px);
            -webkit-backdrop-filter: blur(12px);
            padding: 16px 12px 16px 10px;
            overflow: auto;
            direction: rtl;
            scrollbar-width: thin;
            scrollbar-color: transparent transparent;
            transition: background-color 180ms ease;
        }}
        .sidebar:hover {{
            background: rgba(24, 32, 40, 0.46);
            scrollbar-color: rgba(130, 149, 166, 0.42) transparent;
        }}
        .sidebar-content {{
            direction: ltr;
            width: 100%;
        }}
        .sidebar::-webkit-scrollbar {{ width: 8px; }}
        .sidebar::-webkit-scrollbar-track {{ background: transparent; }}
        .sidebar::-webkit-scrollbar-thumb {{
            background: transparent;
            border-radius: 999px;
            border: 2px solid transparent;
            background-clip: padding-box;
            transition: background 180ms ease;
        }}
        .sidebar:hover::-webkit-scrollbar-thumb {{
            background: rgba(130, 149, 166, 0.38);
            background-clip: padding-box;
        }}
        .sidebar:hover::-webkit-scrollbar-thumb:hover {{
            background: rgba(130, 149, 166, 0.55);
            background-clip: padding-box;
        }}
        .panel {{ background: rgba(20, 27, 34, 0.72); border: 1px solid rgba(148, 163, 184, 0.12); border-radius: 12px; padding: 14px; margin-bottom: 14px; }}
        .panel h2 {{ margin: 0 0 10px; font-size: 0.95rem; color: #91fca3; }}
        .panel p {{ margin: 0 0 8px; color: #d7dde4; font-size: 0.88rem; line-height: 1.4; }}
        label {{ display: block; font-size: 0.84rem; margin: 10px 0 6px; color: #d7dde4; }}
        select, button, input {{
            width: 100%;
            border-radius: 9px;
            border: 1px solid #4d6375;
            background: #243341;
            color: #ffffff;
            padding: 10px 12px;
            font-size: 0.92rem;
            min-width: 0;
        }}
        button {{ cursor: pointer; font-weight: 600; }}
        button:hover {{ background: #2c3e50; }}
        .sidebar-action {{
            background: #1C6835;
            border-color: #2d8b4a;
            color: #ffffff;
        }}
        .sidebar-action:hover {{
            background: #17572c;
        }}
        .checkbox-row {{ display: flex; align-items: center; gap: 10px; margin-top: 12px; }}
        .checkbox-row input {{ width: auto; }}
        .form-grid {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
            gap: 8px;
            margin-top: 10px;
        }}
        .form-field {{
            min-width: 0;
        }}
        .form-field label {{
            margin-top: 0;
        }}
        .plot-wrap {{ position: relative; min-width: 0; }}
        #geocongo-3d-canvas {{ width: 100%; height: 100%; }}
        .hint {{ font-size: 0.78rem; color: #9fb0bf; }}
        .stat-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
        .stat-card {{ background: #22313f; border-radius: 10px; padding: 10px; }}
        .stat-card b {{ display: block; color: #ffffff; }}
        .cluster-chip {{ display: inline-block; width: 10px; height: 10px; border-radius: 999px; margin-right: 8px; vertical-align: middle; }}
        @media (max-width: 420px) {{
            .form-grid {{ grid-template-columns: 1fr; }}
        }}
        @media (max-width: 980px) {{
            .layout {{ grid-template-columns: 1fr; }}
            .sidebar {{ max-height: 320px; }}
        }}
    </style>
</head>
<body>
    <header>
        <div class="brand-container">
            {logo_html}
            <div class="header-title">{clean_title}</div>
        </div>
        <div class="header-badges">
            <span class="badge">Intervalles: <b>{n_points}</b></span>
            <span class="badge">Clusters 3D: <b>{n_clusters}</b></span>
            <span class="badge badge-highlight">Max {element.upper()}: <b>{max_grade}</b></span>
        </div>
    </header>
    <div class="layout">
        <aside class="sidebar">
            <div class="sidebar-content">
            <div class="panel">
                <h2>Affichage</h2>
                <label for="color-mode">Coloration des intervalles</label>
                <select id="color-mode">
                    <option value="grade">Par teneur ({element.upper()})</option>
                    <option value="cluster">Par cluster_id</option>
                </select>
                <label for="grade-scale-mode">Echelle des teneurs</label>
                <select id="grade-scale-mode">
                    <option value="robust">Robuste (P2-P98)</option>
                    <option value="full">Complete (min-max)</option>
                    <option value="manual">Manuelle</option>
                </select>
                <div class="form-grid">
                    <div class="form-field">
                        <label for="grade-min">Min affichage</label>
                        <input id="grade-min" type="number" step="0.01">
                    </div>
                    <div class="form-field">
                        <label for="grade-max">Max affichage</label>
                        <input id="grade-max" type="number" step="0.01">
                    </div>
                </div>
                <button id="apply-grade-range" class="sidebar-action" type="button" style="margin-top:10px;">Appliquer la plage</button>
                <label for="cluster-filter">Filtrer un cluster</label>
                <select id="cluster-filter">
                    {"".join(cluster_options)}
                </select>
                <div class="checkbox-row">
                    <input id="hide-other-holes" type="checkbox">
                    <label for="hide-other-holes" style="margin:0;">Masquer les autres trous</label>
                </div>
                <div class="checkbox-row">
                    <input id="show-meshes" type="checkbox">
                    <label for="show-meshes" style="margin:0;">Afficher les volumes 3D</label>
                </div>
                <button id="reset-view" class="sidebar-action" type="button" style="margin-top:12px;">Reinitialiser la vue</button>
                <p class="hint" style="margin-top:10px;">Choisir un cluster recentre automatiquement la scene sur sa zone.</p>
                <p class="hint">Mode robuste recommande quand quelques teneurs aberrantes ecrasent toutes les couleurs.</p>
                <p class="hint">Les volumes 3D sont desactives au demarrage pour eviter le blocage du navigateur.</p>
            </div>
            <div class="panel">
                <h2>Lecture geologique</h2>
                <p>Le mode <b>teneur</b> montre l'intensite geochimique. Le mode <b>cluster_id</b> montre les groupes detectes par DBSCAN.</p>
                <p>Activez <b>Masquer les autres trous</b> pour isoler les forages relies au cluster selectionne.</p>
                <p>Si une valeur fausse ou tres extreme existe, utilisez une plage manuelle comme <b>0 a 1.3</b> pour faire ressortir les zones a fort potentiel reel.</p>
            </div>
            <div class="panel">
                <h2>Performance</h2>
                <p>{"Jeu de donnees volumineux detecte : la page charge en mode allege." if heavy_dataset else "Mode interactif complet disponible."}</p>
                <p>Astuce : choisir un cluster avant d'afficher les volumes 3D.</p>
            </div>
            <div class="panel">
                <h2>Resume</h2>
                <div class="stat-grid">
                    <div class="stat-card"><span class="hint">Intervalles</span><b>{n_points}</b></div>
                    <div class="stat-card"><span class="hint">Clusters</span><b>{n_clusters}</b></div>
                    <div class="stat-card"><span class="hint">Champ</span><b>{element.upper()}</b></div>
                    <div class="stat-card"><span class="hint">Max</span><b>{max_grade}</b></div>
                </div>
            </div>
            </div>
        </aside>
        <main class="plot-wrap">
            <div id="geocongo-3d-canvas"></div>
        </main>
    </div>
    <script>
        const controlData = {control_json};
        const layoutSpec = {layout_json};
        const plotElement = document.getElementById("geocongo-3d-canvas");
        const colorModeSelect = document.getElementById("color-mode");
        const gradeScaleModeSelect = document.getElementById("grade-scale-mode");
        const gradeMinInput = document.getElementById("grade-min");
        const gradeMaxInput = document.getElementById("grade-max");
        const applyGradeRangeButton = document.getElementById("apply-grade-range");
        const clusterFilterSelect = document.getElementById("cluster-filter");
        const hideOtherHolesCheckbox = document.getElementById("hide-other-holes");
        const showMeshesCheckbox = document.getElementById("show-meshes");
        const resetViewButton = document.getElementById("reset-view");
        const gradeColorscale = {grade_colorscale_json};
        const pointData = controlData.points;
        const holeData = controlData.holes;
        const defaultGradeRange = {{
            min: controlData.gradeDisplayMin,
            max: controlData.gradeDisplayMax
        }};
        const gradeColorbar = {{
            title: {{text: "<b>" + controlData.elementLabel + " (%)</b>", font: {{color: "#ffffff", size: 13}}}},
            x: 1.02,
            y: 0.5,
            len: 0.6,
            thickness: 18,
            tickfont: {{color: "#ffffff", size: 11}},
            bgcolor: "rgba(30, 39, 46, 0.5)",
            bordercolor: "#485460",
            borderwidth: 1
        }};

        function resolveGradeRange() {{
            const mode = gradeScaleModeSelect.value;
            if (mode === "full") {{
                return {{
                    min: controlData.minGrade,
                    max: controlData.maxGrade
                }};
            }}
            if (mode === "manual") {{
                const minValue = Number(gradeMinInput.value);
                const maxValue = Number(gradeMaxInput.value);
                if (Number.isFinite(minValue) && Number.isFinite(maxValue) && minValue < maxValue) {{
                    return {{ min: minValue, max: maxValue }};
                }}
            }}
            return {{
                min: controlData.gradeDisplayMin,
                max: controlData.gradeDisplayMax
            }};
        }}

        function syncGradeInputsFromMode() {{
            const mode = gradeScaleModeSelect.value;
            const gradeModeActive = colorModeSelect.value === "grade";
            gradeScaleModeSelect.disabled = !gradeModeActive;
            gradeMinInput.disabled = !gradeModeActive || mode !== "manual";
            gradeMaxInput.disabled = !gradeModeActive || mode !== "manual";
            applyGradeRangeButton.disabled = !gradeModeActive;

            if (mode === "full") {{
                gradeMinInput.value = Number(controlData.minGrade).toFixed(2);
                gradeMaxInput.value = Number(controlData.maxGrade).toFixed(2);
                return;
            }}
            if (mode === "robust") {{
                gradeMinInput.value = Number(controlData.gradeDisplayMin).toFixed(2);
                gradeMaxInput.value = Number(controlData.gradeDisplayMax).toFixed(2);
            }}
        }}

        function buildPointIndices(selectedCluster) {{
            if (selectedCluster === "all") {{
                return pointData.clusters.map((_, index) => index);
            }}
            const matches = [];
            pointData.clusters.forEach((clusterId, index) => {{
                if (clusterId === selectedCluster) {{
                    matches.push(index);
                }}
            }});
            return matches;
        }}

        function buildPointTrace(selectedCluster, colorMode) {{
            const indices = buildPointIndices(selectedCluster);
            const marker = {{
                size: controlData.heavyDataset ? 4.2 : 5.5,
                opacity: 0.88
            }};

            if (colorMode === "cluster") {{
                marker.color = indices.map(index => pointData.clusterColors[index]);
                marker.showscale = false;
            }} else {{
                const gradeRange = resolveGradeRange();
                marker.color = indices.map(index => pointData.grades[index]);
                marker.colorscale = gradeColorscale;
                marker.cmin = gradeRange.min;
                marker.cmax = gradeRange.max;
                marker.showscale = true;
                marker.colorbar = gradeColorbar;
            }}

            return {{
                type: "scatter3d",
                mode: "markers",
                name: "Intervalles",
                showlegend: false,
                x: indices.map(index => pointData.x[index]),
                y: indices.map(index => pointData.y[index]),
                z: indices.map(index => pointData.z[index]),
                text: indices.map(index => pointData.text[index]),
                hoverinfo: "text",
                marker: marker
            }};
        }}

        function buildHoleTrace(selectedCluster, hideOtherHoles) {{
            const allowedHoles = selectedCluster === "all" ? null : new Set(controlData.clusterHoleIds[selectedCluster] || []);
            const xs = [];
            const ys = [];
            const zs = [];
            const texts = [];

            Object.entries(holeData).forEach(([holeId, values]) => {{
                if (hideOtherHoles && selectedCluster !== "all" && !allowedHoles.has(holeId)) {{
                    return;
                }}
                values.x.forEach((value, index) => {{
                    xs.push(value);
                    ys.push(values.y[index]);
                    zs.push(values.z[index]);
                    texts.push(index === 0 ? values.text : "");
                }});
                xs.push(null);
                ys.push(null);
                zs.push(null);
                texts.push("");
            }});

            return {{
                type: "scatter3d",
                mode: "lines",
                name: "Forages",
                showlegend: false,
                x: xs,
                y: ys,
                z: zs,
                hoverinfo: "skip",
                line: {{color: "#c7d0d9", width: 4}},
                opacity: hideOtherHoles ? 1.0 : 0.8
            }};
        }}

        function buildMeshTraces(selectedCluster, enabled) {{
            if (!enabled) {{
                return [];
            }}

            let clusterIds = [];
            if (selectedCluster === "all") {{
                clusterIds = controlData.heavyDataset
                    ? controlData.allClusterIds.filter(id => id !== "-1").slice(0, controlData.meshAllClusterLimit)
                    : controlData.allClusterIds.filter(id => id !== "-1");
            }} else {{
                clusterIds = [selectedCluster];
            }}

            const traces = [];
            clusterIds.forEach(clusterId => {{
                (controlData.geometries[clusterId] || []).forEach(mesh => {{
                    traces.push({{
                        type: "mesh3d",
                        x: mesh.x,
                        y: mesh.y,
                        z: mesh.z,
                        i: mesh.i,
                        j: mesh.j,
                        k: mesh.k,
                        color: mesh.color,
                        opacity: 0.34,
                        hoverinfo: "text",
                        text: "Cluster " + clusterId + "<br>Volume: " + Math.round(mesh.volume_m3 || 0) + " m3",
                        name: "Cluster " + clusterId,
                        showlegend: false
                    }});
                }});
            }});
            return traces;
        }}

        function updateAxisRanges(ranges) {{
            Plotly.relayout(plotElement, {{
                "scene.xaxis.range": ranges.x,
                "scene.yaxis.range": ranges.y,
                "scene.zaxis.range": ranges.z
            }});
        }}

        function buildSceneData() {{
            const selectedCluster = clusterFilterSelect.value;
            const colorMode = colorModeSelect.value;
            const hideOtherHoles = hideOtherHolesCheckbox.checked;
            const showMeshes = showMeshesCheckbox.checked;
            const traces = [
                buildHoleTrace(selectedCluster, hideOtherHoles),
                buildPointTrace(selectedCluster, colorMode)
            ];
            return traces.concat(buildMeshTraces(selectedCluster, showMeshes));
        }}

        function updateClusterView() {{
            const selectedCluster = clusterFilterSelect.value;
            Plotly.react(plotElement, buildSceneData(), layoutSpec, {{
                responsive: true,
                displaylogo: false
            }});
            updateAxisRanges(selectedCluster === "all" ? controlData.defaultRanges : (controlData.clusterRanges[selectedCluster] || controlData.defaultRanges));
        }}

        Plotly.newPlot(plotElement, buildSceneData(), layoutSpec, {{
            responsive: true,
            displaylogo: false
        }}).then(() => {{
            syncGradeInputsFromMode();
            colorModeSelect.addEventListener("change", updateClusterView);
            colorModeSelect.addEventListener("change", syncGradeInputsFromMode);
            gradeScaleModeSelect.addEventListener("change", () => {{
                syncGradeInputsFromMode();
                updateClusterView();
            }});
            applyGradeRangeButton.addEventListener("click", updateClusterView);
            clusterFilterSelect.addEventListener("change", updateClusterView);
            hideOtherHolesCheckbox.addEventListener("change", updateClusterView);
            showMeshesCheckbox.addEventListener("change", updateClusterView);
            resetViewButton.addEventListener("click", () => {{
                clusterFilterSelect.value = "all";
                hideOtherHolesCheckbox.checked = false;
                showMeshesCheckbox.checked = false;
                colorModeSelect.value = "grade";
                gradeScaleModeSelect.value = "robust";
                gradeMinInput.value = Number(defaultGradeRange.min).toFixed(2);
                gradeMaxInput.value = Number(defaultGradeRange.max).toFixed(2);
                syncGradeInputsFromMode();
                updateClusterView();
            }});
        }});
    </script>
</body>
</html>"""

    if output_path:
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(html_code)

    return html_code


def apply_cluster_symbology(layer, cluster_counts=None, cluster_field="cluster_id"):
    from qgis.PyQt.QtGui import QColor
    from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory

    if cluster_counts is None:
        cluster_counts = {}
        cluster_index = layer.fields().indexOf(cluster_field)
        if cluster_index != -1:
            for feature in layer.getFeatures():
                cluster_id = int(feature.attribute(cluster_index) or -1)
                cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

    categories = []
    noise_symbol = make_qgis_symbol(layer)
    noise_symbol.setColor(QColor(NOISE_COLOR))
    noise_symbol.setOpacity(0.65)
    if hasattr(noise_symbol, "setSize"):
        noise_symbol.setSize(2.6)
    categories.append(QgsRendererCategory(-1, noise_symbol, "Bruit (-1)"))

    for cluster_id in sorted(cluster_counts.keys()):
        if int(cluster_id) == -1:
            continue
        symbol = make_qgis_symbol(layer)
        symbol.setColor(QColor(cluster_color(cluster_id)))
        if hasattr(symbol, "setSize"):
            symbol.setSize(4.6)
        categories.append(
            QgsRendererCategory(
                int(cluster_id),
                symbol,
                f"Cluster {cluster_id} ({cluster_counts[cluster_id]} pts)",
            )
        )

    renderer = QgsCategorizedSymbolRenderer(cluster_field, categories)
    layer.setRenderer(renderer)
    layer.triggerRepaint()


def apply_grade_symbology(layer, grade_field="grade", classes=5, use_robust_range=True):
    from qgis.PyQt.QtGui import QColor
    from qgis.core import QgsGraduatedSymbolRenderer, QgsRendererRange

    values = []
    grade_index = layer.fields().indexOf(grade_field)
    if grade_index == -1:
        raise ValueError(f"Champ de teneur introuvable: {grade_field}")

    for feature in layer.getFeatures():
        value = feature.attribute(grade_index)
        try:
            if value is None:
                continue
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if not values:
        raise ValueError(f"Aucune valeur numerique disponible dans le champ {grade_field}.")

    stats = compute_grade_display_stats(values)
    minimum = stats["displayMin"] if use_robust_range else stats["rawMin"]
    maximum = stats["displayMax"] if use_robust_range else stats["rawMax"]
    if minimum >= maximum:
        minimum = stats["rawMin"]
        maximum = stats["rawMax"]
    classes = max(3, int(classes))
    step = (maximum - minimum) / float(classes) if maximum != minimum else 1.0
    palette = ["#440154", "#355f8d", "#1f9e89", "#73d055", "#fde725", "#f8961e", "#d62828"]

    ranges = []
    for idx in range(classes):
        lower = minimum + (idx * step)
        upper = maximum if idx == classes - 1 else minimum + ((idx + 1) * step)
        symbol = make_qgis_symbol(layer)
        symbol.setColor(QColor(palette[min(idx, len(palette) - 1)]))
        if hasattr(symbol, "setSize"):
            symbol.setSize(4.4)
        label = f"{lower:.2f} - {upper:.2f}"
        ranges.append(QgsRendererRange(lower, upper, symbol, label))

    renderer = QgsGraduatedSymbolRenderer(grade_field, ranges)
    renderer.setMode(QgsGraduatedSymbolRenderer.Custom)
    layer.setRenderer(renderer)
    layer.triggerRepaint()
