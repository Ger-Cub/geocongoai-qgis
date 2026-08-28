"""
Drillhole and Geochemical DBSCAN Analysis Dialog for GeoCongo AI.
Provides vector layer & field selection using native QGIS widgets, DBSCAN clustering parameters, and results preview.
"""

import os
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QDoubleSpinBox, QSpinBox, QPushButton, QLabel,
    QProgressBar, QMessageBox
)
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtCore import QVariant, Qt
from qgis.gui import QgsMapLayerComboBox, QgsFieldComboBox
from qgis.core import (
    QgsMapLayerProxyModel, QgsVectorLayer, QgsProject,
    QgsFeature, QgsGeometry, QgsPointXY, QgsField, QgsVectorFileWriter
)


def pure_python_dbscan(coords, eps, min_samples):
    """
    Pure Python DBSCAN implementation fallback when scikit-learn is not installed.
    """
    import math
    n = len(coords)
    labels = [-1] * n
    cluster_id = 0
    visited = [False] * n

    def region_query(point_idx):
        p1 = coords[point_idx]
        return [i for i in range(n) if math.hypot(p1[0] - coords[i][0], p1[1] - coords[i][1]) <= eps]

    for i in range(n):
        if visited[i]:
            continue
        visited[i] = True
        neighbors = region_query(i)

        if len(neighbors) < min_samples:
            labels[i] = -1
        else:
            labels[i] = cluster_id
            seeds = [p for p in neighbors if p != i]
            s_idx = 0
            while s_idx < len(seeds):
                curr = seeds[s_idx]
                if not visited[curr]:
                    visited[curr] = True
                    curr_neighbors = region_query(curr)
                    if len(curr_neighbors) >= min_samples:
                        for neighbor in curr_neighbors:
                            if neighbor not in seeds:
                                seeds.append(neighbor)
                if labels[curr] == -1:
                    labels[curr] = cluster_id
                s_idx += 1

            cluster_id += 1

    return labels


class DrillholeAnalysisDialog(QDialog):
    """
    Dialog for drillholes and assay vector clustering using geocongoai DBSCAN.
    """


    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface

        self.setWindowTitle("GeoCongo AI - Drillhole & Géochimie DBSCAN")
        self.resize(520, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Header Box with Logo
        header_box = QGroupBox("⛏️ Analyse Spatiale des Forages & Géochimie")
        header_layout = QHBoxLayout(header_box)

        # Logo display
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            from qgis.PyQt.QtGui import QIcon
            self.setWindowIcon(QIcon(logo_path))
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(logo_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(lbl_logo)

        lbl_info = QLabel(
            "Sélectionnez une couche de forages/échantillons pour identifier les anomalies "
            "et sous-domaines de minéralisation via l'algorithme DBSCAN."
        )
        lbl_info.setWordWrap(True)
        header_layout.addWidget(lbl_info)
        layout.addWidget(header_box)

        # Layer & Field Selection Box (Native QGIS Widgets)
        selectors_box = QGroupBox("🗺️ Couches et Attributs QGIS")
        selectors_layout = QVBoxLayout(selectors_box)

        # Vector Layer Selector (Supports Point and all Vector layers)
        selectors_layout.addWidget(QLabel("Couche d'échantillons / Forages (Assays / Collars) :"))
        self.cb_layer = QgsMapLayerComboBox(self)
        self.cb_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        selectors_layout.addWidget(self.cb_layer)

        # Collar Layer Selector (For non-spatial assay tables)
        selectors_layout.addWidget(QLabel("Couche de colliers / Surface (Collars - optionnel si table sans géométrie) :"))
        self.cb_collar_layer = QgsMapLayerComboBox(self)
        self.cb_collar_layer.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.cb_collar_layer.setAllowEmptyLayer(True)
        selectors_layout.addWidget(self.cb_collar_layer)

        # Survey Layer Selector (For drillhole trajectory deviation)
        selectors_layout.addWidget(QLabel("Couche de trajectoires / Déviation (Surveys - optionnel) :"))
        self.cb_survey_layer = QgsMapLayerComboBox(self)
        self.cb_survey_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.cb_survey_layer.setAllowEmptyLayer(True)
        selectors_layout.addWidget(self.cb_survey_layer)

        # Warning label if project has no vector layers
        self.lbl_no_layers = QLabel(
            "<font color='#d32f2f'>⚠️ Aucune couche vectorielle chargée dans QGIS. "
            "Veuillez ajouter une couche de données (GeoJSON, Shapefile, CSV) dans votre projet.</font>"
        )
        self.lbl_no_layers.setWordWrap(True)
        self.lbl_no_layers.setVisible(False)
        selectors_layout.addWidget(self.lbl_no_layers)

        # Field Selector (Linked to selected layer)
        selectors_layout.addWidget(QLabel("Élément / Teneur à analyser (ex: Cu, Au) :"))
        self.cb_field = QgsFieldComboBox(self)
        self.cb_field.setLayer(self.cb_layer.currentLayer())
        selectors_layout.addWidget(self.cb_field)

        layout.addWidget(selectors_box)

        # DBSCAN Clustering Parameters Box
        params_box = QGroupBox("⚙️ Paramètres DBSCAN")
        params_layout = QVBoxLayout(params_box)

        # Min Cutoff Grade Threshold
        cutoff_layout = QHBoxLayout()
        cutoff_layout.addWidget(QLabel("Seuil minimum de teneur :"))
        self.spn_cutoff = QDoubleSpinBox()
        self.spn_cutoff.setRange(0.0, 100.0)
        self.spn_cutoff.setDecimals(3)
        self.spn_cutoff.setValue(0.5)
        cutoff_layout.addWidget(self.spn_cutoff)
        params_layout.addLayout(cutoff_layout)

        # Eps Distance Parameter
        eps_layout = QHBoxLayout()
        eps_layout.addWidget(QLabel("Eps (Distance de recherche en m) :"))
        self.spn_eps = QDoubleSpinBox()
        self.spn_eps.setRange(0.1, 10000.0)
        self.spn_eps.setValue(25.0)
        eps_layout.addWidget(self.spn_eps)
        params_layout.addLayout(eps_layout)

        # Min Samples Parameter
        min_samples_layout = QHBoxLayout()
        min_samples_layout.addWidget(QLabel("Minimum d'échantillons par cluster :"))
        self.spn_min_samples = QSpinBox()
        self.spn_min_samples.setRange(1, 1000)
        self.spn_min_samples.setValue(5)
        min_samples_layout.addWidget(self.spn_min_samples)
        params_layout.addLayout(min_samples_layout)

        layout.addWidget(params_box)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()

        self.btn_run = QPushButton("Calculer les Clusters")
        self.btn_run.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        self.btn_run.clicked.connect(self.run_clustering)
        btn_layout.addWidget(self.btn_run)

        self.btn_export_3d = QPushButton("Exporter 3D (HTML)")
        self.btn_export_3d.setEnabled(False)
        self.btn_export_3d.setStyleSheet("""
            QPushButton {
                background-color: #2E7D32;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1B5E20;
            }
            QPushButton:disabled {
                background-color: #A5D6A7;
                color: #E8F5E9;
            }
        """)
        self.btn_export_3d.clicked.connect(self.export_3d_html)
        btn_layout.addWidget(self.btn_export_3d)

        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)

        # Initialize field list and collar layer check
        self._on_layer_changed()

    def _on_layer_changed(self):
        """Updates field combobox when vector layer selection changes."""
        layer = self.cb_layer.currentLayer()
        self.cb_field.setLayer(layer)
        if not layer:
            self.lbl_no_layers.setVisible(True)
            self.btn_run.setEnabled(False)
        else:
            self.lbl_no_layers.setVisible(False)
            self.btn_run.setEnabled(True)

            # Auto-select collar and survey layers if current layer is non-spatial
            for l in QgsProject.instance().mapLayers().values():
                if isinstance(l, QgsVectorLayer) and l.isValid():
                    ln = l.name().lower()
                    if ('collar' in ln or 'head' in ln) and l.isSpatial():
                        self.cb_collar_layer.setLayer(l)
                    elif 'survey' in ln or 'devia' in ln:
                        self.cb_survey_layer.setLayer(l)

    def run_clustering(self):
        """
        Executes spatial DBSCAN clustering on the selected vector layer filtered by cutoff threshold.
        Creates and adds a styled QGIS memory vector layer with cluster IDs.
        """
        try:
            import numpy as np
        except ImportError:
            np = None

        from qgis.core import (
            QgsVectorLayer, QgsField, QgsFeature, QgsGeometry, QgsPointXY,
            QgsProject, QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol
        )
        from qgis.PyQt.QtGui import QColor

        layer = self.cb_layer.currentLayer()
        if not layer or not layer.isValid():
            QMessageBox.warning(
                self,
                "Erreur Couche",
                "Aucune couche sélectionnée. Veuillez d'abord ajouter une couche de données dans QGIS."
            )
            return

        field_name = self.cb_field.currentField()
        if not field_name:
            QMessageBox.warning(
                self,
                "Erreur Attribut",
                "Veuillez sélectionner un champ d'attribut valide dans la liste déroulante."
            )
            return

        cutoff = self.spn_cutoff.value()
        eps = self.spn_eps.value()
        min_samples = self.spn_min_samples.value()

        # Robust field index lookup
        field_idx = layer.fields().indexOf(field_name)
        if field_idx == -1:
            field_idx = layer.fields().lookupField(field_name)
        if field_idx == -1:
            for idx, fld in enumerate(layer.fields()):
                if fld.name().lower() == field_name.lower():
                    field_idx = idx
                    break

        if field_idx == -1:
            QMessageBox.warning(self, "Erreur Champ", f"Le champ '{field_name}' n'existe pas dans la couche.")
            return

        def safe_float(val):
            if val is None or val == QVariant():
                return None
            if isinstance(val, (int, float)):
                return float(val)
            s = str(val).strip()
            if not s or s.upper() in ('NULL', 'NONE', 'NAN', 'N/A', ''):
                return None
            s = s.replace(',', '.')
            try:
                return float(s)
            except (ValueError, TypeError):
                cleaned = ''.join(c for c in s if c.isdigit() or c in ('.', '-'))
                try:
                    return float(cleaned) if cleaned else None
                except ValueError:
                    return None

        # Resolve collar point layer & join strategy for non-spatial assay tables
        collar_layer_obj = self.cb_collar_layer.currentLayer()
        collar_map = {}
        join_key_assay = None
        join_key_collar = None

        candidate_keys = ['hole_id', 'bhid', 'dhid', 'id', 'collar', 'borehole', 'hole', 'sample_id']

        for fld in layer.fields():
            fn_lower = fld.name().lower()
            if fn_lower in candidate_keys or 'hole' in fn_lower or 'dh' in fn_lower:
                join_key_assay = fld.name()
                break

        # Auto-detect collar layer if not set
        if not collar_layer_obj:
            for l in QgsProject.instance().mapLayers().values():
                if isinstance(l, QgsVectorLayer) and l.isSpatial() and l.geometryType() == 0 and l.isValid():
                    if join_key_assay:
                        for fld in l.fields():
                            if fld.name().lower() == join_key_assay.lower() or fld.name().lower() in candidate_keys:
                                collar_layer_obj = l
                                join_key_collar = fld.name()
                                break
                    if collar_layer_obj:
                        break

        # Resolve collar point layer & join strategy for non-spatial assay tables
        collar_layer_obj = self.cb_collar_layer.currentLayer()
        survey_layer_obj = self.cb_survey_layer.currentLayer()

        collar_map = {}
        survey_map = {}
        join_key_assay = None
        join_key_collar = None

        candidate_keys = ['hole_id', 'bhid', 'dhid', 'id', 'collar', 'borehole', 'hole', 'sample_id']

        for fld in layer.fields():
            fn_lower = fld.name().lower()
            if fn_lower in candidate_keys or 'hole' in fn_lower or 'dh' in fn_lower:
                join_key_assay = fld.name()
                break

        # Auto-detect collar layer if not set
        if not collar_layer_obj:
            for l in QgsProject.instance().mapLayers().values():
                if isinstance(l, QgsVectorLayer) and l.isSpatial() and l.geometryType() == 0 and l.isValid():
                    if join_key_assay:
                        for fld in l.fields():
                            if fld.name().lower() == join_key_assay.lower() or fld.name().lower() in candidate_keys:
                                collar_layer_obj = l
                                join_key_collar = fld.name()
                                break
                    if collar_layer_obj:
                        break

        # Auto-detect survey layer if not set
        if not survey_layer_obj:
            for l in QgsProject.instance().mapLayers().values():
                if isinstance(l, QgsVectorLayer) and l.isValid() and ('survey' in l.name().lower() or 'devia' in l.name().lower()):
                    survey_layer_obj = l
                    break

        # Build collar dictionary lookup mapping join_key -> (QgsPointXY, z_collar)
        if collar_layer_obj and join_key_assay:
            if not join_key_collar:
                for fld in collar_layer_obj.fields():
                    if fld.name().lower() == join_key_assay.lower() or fld.name().lower() in candidate_keys:
                        join_key_collar = fld.name()
                        break

            if join_key_collar:
                c_id_idx = collar_layer_obj.fields().indexOf(join_key_collar)
                c_z_idx = -1
                for idx, fld in enumerate(collar_layer_obj.fields()):
                    if fld.name().lower() in ('z', 'elevation', 'zcollar', 'alt'):
                        c_z_idx = idx
                        break

                for c_feat in collar_layer_obj.getFeatures():
                    c_val = c_feat.attribute(c_id_idx)
                    if c_val is not None and c_val != QVariant():
                        c_geom = c_feat.geometry()
                        if c_geom and not c_geom.isEmpty():
                            pt = c_geom.asPoint() if not c_geom.isMultipart() else (c_geom.asMultiPoint()[0] if c_geom.asMultiPoint() else None)
                            if pt:
                                z_c = safe_float(c_feat.attribute(c_z_idx)) if c_z_idx != -1 else 0.0
                                collar_map[str(c_val).strip().lower()] = (pt, z_c or 0.0)

        # Build survey dictionary lookup mapping hole_id -> (azimuth, dip)
        if survey_layer_obj:
            s_id_idx = -1
            s_az_idx = -1
            s_dip_idx = -1

            for idx, fld in enumerate(survey_layer_obj.fields()):
                fn = fld.name().lower()
                if (fn in candidate_keys or 'hole' in fn or 'dh' in fn) and s_id_idx == -1:
                    s_id_idx = idx
                elif fn in ('az', 'azimuth', 'bearing', 'dir') and s_az_idx == -1:
                    s_az_idx = idx
                elif fn in ('dip', 'inclination', 'inc', 'plunge') and s_dip_idx == -1:
                    s_dip_idx = idx

            if s_id_idx != -1 and (s_az_idx != -1 or s_dip_idx != -1):
                for s_feat in survey_layer_obj.getFeatures():
                    s_val = s_feat.attribute(s_id_idx)
                    if s_val is not None and s_val != QVariant():
                        az_v = safe_float(s_feat.attribute(s_az_idx)) if s_az_idx != -1 else 0.0
                        dip_v = safe_float(s_feat.attribute(s_dip_idx)) if s_dip_idx != -1 else 90.0
                        survey_map[str(s_val).strip().lower()] = (az_v or 0.0, dip_v if dip_v is not None else 90.0)

        # Check attribute indices in assay layer
        x_field_idx = -1
        y_field_idx = -1
        from_idx = -1
        to_idx = -1
        z_idx = -1
        hole_id_idx = -1

        for idx, fld in enumerate(layer.fields()):
            fn = fld.name().lower()
            if fn in ('x', 'xcollar', 'east', 'easting', 'lon', 'longitude') and x_field_idx == -1:
                x_field_idx = idx
            elif fn in ('y', 'ycollar', 'north', 'northing', 'lat', 'latitude') and y_field_idx == -1:
                y_field_idx = idx
            elif fn in ('from', 'from_m', 'dept_from', 'depth_from') and from_idx == -1:
                from_idx = idx
            elif fn in ('to', 'to_m', 'dept_to', 'depth_to') and to_idx == -1:
                to_idx = idx
            elif fn in ('z', 'elevation', 'zcollar', 'alt', 'depth') and z_idx == -1:
                z_idx = idx
            elif (fn in candidate_keys or 'hole' in fn or 'dh' in fn) and hole_id_idx == -1:
                hole_id_idx = idx

        # Extract matching features and spatial coordinates
        valid_features = []
        coords = []
        all_parsed_values = []
        raw_samples = []

        import math

        for feature in layer.getFeatures():
            val = feature.attribute(field_idx)
            val_float = safe_float(val)

            if len(raw_samples) < 5 and val is not None and val != QVariant():
                raw_samples.append(str(val))

            if val_float is None:
                continue

            all_parsed_values.append(val_float)

            if val_float >= cutoff:
                pt = None
                z_collar = 0.0
                geom = feature.geometry()

                # Extract hole_id string
                h_id = str(feature.attribute(hole_id_idx)).strip() if hole_id_idx != -1 and feature.attribute(hole_id_idx) is not None else "DH"

                # Calculate mid-depth
                fm = safe_float(feature.attribute(from_idx)) if from_idx != -1 else None
                tm = safe_float(feature.attribute(to_idx)) if to_idx != -1 else None
                if fm is not None and tm is not None:
                    mid_depth = (fm + tm) / 2.0
                elif fm is not None:
                    mid_depth = fm
                else:
                    mid_depth = 0.0

                # Strategy 1: Direct feature geometry
                if geom and not geom.isEmpty():
                    pt = geom.asPoint() if not geom.isMultipart() else (geom.asMultiPoint()[0] if geom.asMultiPoint() else None)
                    if not pt:
                        pt = geom.centroid().asPoint()

                # Strategy 2: Attribute fields X / Y
                if not pt and x_field_idx != -1 and y_field_idx != -1:
                    xv = safe_float(feature.attribute(x_field_idx))
                    yv = safe_float(feature.attribute(y_field_idx))
                    if xv is not None and yv is not None:
                        pt = QgsPointXY(xv, yv)

                # Strategy 3: Collar join key lookup (e.g. HOLE_ID)
                if not pt and collar_map:
                    c_info = collar_map.get(h_id.lower())
                    if c_info:
                        pt, z_collar = c_info

                if not pt:
                    continue

                # Apply Survey 3D Trajectory Deviation if survey parameters exist
                if h_id.lower() in survey_map:
                    az_deg, dip_deg = survey_map[h_id.lower()]
                    dip_rad = math.radians(abs(dip_deg))
                    az_rad = math.radians(az_deg)

                    horiz_dist = mid_depth * math.cos(dip_rad)
                    dz = -mid_depth * math.sin(dip_rad)
                    dx = horiz_dist * math.sin(az_rad)
                    dy = horiz_dist * math.cos(az_rad)

                    pt = QgsPointXY(pt.x() + dx, pt.y() + dy)
                    zv = z_collar + dz
                else:
                    # Compute standard Z elevation
                    if z_idx != -1 and safe_float(feature.attribute(z_idx)) is not None:
                        zv = safe_float(feature.attribute(z_idx))
                    elif z_collar != 0.0:
                        zv = z_collar - mid_depth
                    else:
                        zv = -mid_depth

                valid_features.append((feature, val_float, pt, zv, h_id, mid_depth))
                coords.append([pt.x(), pt.y()])

        if not coords:
            if all_parsed_values:
                min_v = min(all_parsed_values)
                max_v = max(all_parsed_values)
                above_cutoff_count = sum(1 for v in all_parsed_values if v >= cutoff)

                if above_cutoff_count == 0:
                    msg = (
                        f"Aucun échantillon ne dépasse le seuil minimum de teneur ({cutoff}) pour le champ '{field_name}'.\n\n"
                        f"📊 Statistiques lues ({len(all_parsed_values)} valeurs) :\n"
                        f"• Teneur minimale : {min_v}\n"
                        f"• Teneur maximale : {max_v}\n"
                        f"• Exemples : {', '.join(raw_samples[:5])}"
                    )
                else:
                    msg = (
                        f"⚠️ {above_cutoff_count} échantillons dépassent le seuil ({cutoff}) pour '{field_name}', "
                        f"mais aucune géométrie spatiale (X, Y) n'a pu leur être associée.\n\n"
                        f"💡 Raison : La couche sélectionnée ('{layer.name()}') est une table sans géométrie (Assays).\n"
                        f"Sélectionnez la couche de colliers dans le champ 'Couche de colliers' ci-dessus (ex: collar_BABBITT)."
                    )
            else:
                msg = (
                    f"Aucun échantillon n'a pu être lu dans le champ '{field_name}'.\n"
                    f"Vérifiez que le champ sélectionné contient bien des valeurs numériques."
                )

            QMessageBox.information(self, "Aucun Résultat", msg)
            return

        # Run DBSCAN Clustering (Try scikit-learn first, fallback to pure Python)
        try:
            from sklearn.cluster import DBSCAN
            if np is not None:
                coords_arr = np.array(coords, dtype=np.float64)
                db = DBSCAN(eps=eps, min_samples=min_samples).fit(coords_arr)
                labels = list(db.labels_)
            else:
                labels = pure_python_dbscan(coords, eps, min_samples)
        except Exception:
            labels = pure_python_dbscan(coords, eps, min_samples)

        # Prepare 3D QGIS Memory Vector Layer (PointZ)
        from qgis.core import QgsPoint
        crs_authid = layer.crs().authid() if layer.crs().isValid() else "EPSG:4326"
        out_layer_name = f"Clusters_DBSCAN_{layer.name()}_{field_name}"
        out_layer = QgsVectorLayer(f"PointZ?crs={crs_authid}", out_layer_name, "memory")
        dp = out_layer.dataProvider()

        # Add fields: original fields + cluster attributes + elevation
        new_fields = [f for f in layer.fields().toList()]
        new_fields.append(QgsField("cluster_id", QVariant.Int))
        new_fields.append(QgsField("is_noise", QVariant.Int))
        new_fields.append(QgsField("grade_val", QVariant.Double))
        new_fields.append(QgsField("z_elevation", QVariant.Double))

        dp.addAttributes(new_fields)
        out_layer.updateFields()

        # Create 3D output features
        out_features = []
        cluster_counts = {}

        for idx, (orig_feat, val_float, pt, zv, h_id, mid_depth) in enumerate(valid_features):
            cid = int(labels[idx])
            is_noise = 1 if cid == -1 else 0

            if cid != -1:
                cluster_counts[cid] = cluster_counts.get(cid, 0) + 1

            new_feat = QgsFeature(out_layer.fields())
            new_feat.setGeometry(QgsGeometry(QgsPoint(pt.x(), pt.y(), zv)))

            attrs = list(orig_feat.attributes())
            attrs.extend([cid, is_noise, val_float, zv])
            new_feat.setAttributes(attrs)

            out_features.append(new_feat)

        dp.addFeatures(out_features)
        out_layer.updateExtents()

        # Apply Categorized Symbology for clusters
        self._apply_cluster_symbology(out_layer, cluster_counts)

        # Add result layer to QGIS Map Canvas
        QgsProject.instance().addMapLayer(out_layer)

        # Construct GeoResult object for 3D HTML Export with ConvexHull geometries
        try:
            from geocongoai.results import GeoResult
            points_3d = []
            clusters_dict = {}

            for idx, (orig_feat, val_float, pt, zv, h_id, mid_depth) in enumerate(valid_features):
                cid = int(labels[idx])

                p_item = {
                    "x": float(pt.x()),
                    "y": float(pt.y()),
                    "z": float(zv),
                    "hole_id": h_id,
                    "mid_depth": float(mid_depth),
                    "cluster": cid,
                    "value": float(val_float),
                    field_name: float(val_float)
                }
                points_3d.append(p_item)
                if cid != -1:
                    if cid not in clusters_dict:
                        clusters_dict[cid] = []
                    clusters_dict[cid].append(p_item)

            # Compute 3D Mesh / ConvexHull Envelopes for clusters if scipy is available
            geometries_list = []
            palette = [
                "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
                "#ffff33", "#a65628", "#f781bf", "#00ced1", "#ff1493",
                "#7fff00", "#00bfff", "#ff8c00", "#9932cc", "#808000"
            ]
            try:
                from scipy.spatial import ConvexHull
                for cid, c_pts in clusters_dict.items():
                    if len(c_pts) >= 4 and np is not None:
                        pts_arr = np.array([[p["x"], p["y"], p["z"]] for p in c_pts])
                        if np.linalg.matrix_rank(pts_arr - pts_arr[0]) >= 3:
                            hull = ConvexHull(pts_arr)
                            geometries_list.append({
                                "cluster_id": cid,
                                "volume_m3": float(hull.volume),
                                "color": palette[cid % len(palette)],
                                "vertices": {
                                    "x": pts_arr[:, 0].tolist(),
                                    "y": pts_arr[:, 1].tolist(),
                                    "z": pts_arr[:, 2].tolist()
                                },
                                "simplices": {
                                    "i": hull.simplices[:, 0].tolist(),
                                    "j": hull.simplices[:, 1].tolist(),
                                    "k": hull.simplices[:, 2].tolist()
                                }
                            })
            except Exception:
                pass

            max_g = max((p["value"] for p in points_3d), default=0.0)

            self._last_geo_result = GeoResult(
                points=points_3d,
                geometries=geometries_list,
                statistics={"total_samples": len(points_3d), "clusters_count": len(clusters_dict), "max": max_g},
                metadata={
                    "title": f"GeoCongo AI — Visualisation 3D (Champ {field_name})",
                    "analysis_type": "dbscan_3d",
                    "element": field_name,
                    "cluster_count": len(clusters_dict),
                    "filtered_intervals": len(points_3d),
                    "grade_threshold": cutoff,
                    "eps": eps,
                    "min_samples": min_samples
                }
            )
            self.btn_export_3d.setEnabled(True)
        except Exception:
            self._last_geo_result = None
            self.btn_export_3d.setEnabled(True)
        except Exception:
            self._last_geo_result = None

        # Display summary report
        n_clusters = len(cluster_counts)
        n_noise = list(labels).count(-1)
        n_total = len(valid_features)

        QMessageBox.information(
            self,
            "Analyse DBSCAN Terminée",
            f"✅ Clustering DBSCAN terminé avec succès !\n\n"
            f"• Couche source : {layer.name()}\n"
            f"• Champ analysé : {field_name} (seuil >= {cutoff})\n"
            f"• Échantillons filtrés : {n_total} sur {layer.featureCount()}\n"
            f"• Clusters identifiés : {n_clusters}\n"
            f"• Points de bruit géochimique (-1) : {n_noise}\n\n"
            f"La nouvelle couche '{out_layer_name}' a été ajoutée à votre projet QGIS.\n"
            f"Vous pouvez également cliquer sur 'Exporter 3D (HTML)' pour visualiser en 3D dans votre navigateur."
        )

    def export_3d_html(self):
        """
        Exports current GeoResult to standalone interactive 3D HTML and launches default web browser.
        """
        if not getattr(self, '_last_geo_result', None):
            QMessageBox.warning(self, "Export 3D", "Veuillez d'abord calculer les clusters.")
            return

        from qgis.PyQt.QtWidgets import QFileDialog
        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtGui import QDesktopServices

        filePath, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer la visualisation 3D HTML",
            "dbscan_clusters_3d.html",
            "Fichiers HTML (*.html)"
        )

        if not filePath:
            return

        try:
            self._last_geo_result.to_html(output_path=filePath)
            QMessageBox.information(
                self,
                "Export 3D Réussi",
                f"✅ Visualisation 3D HTML générée avec succès :\n\n{filePath}\n\n"
                "Ouverture dans votre navigateur web..."
            )
            QDesktopServices.openUrl(QUrl.fromLocalFile(filePath))
        except Exception as e:
            QMessageBox.critical(self, "Erreur Export 3D", f"Impossible d'exporter le fichier HTML 3D :\n{e}")

    def _apply_cluster_symbology(self, layer, cluster_counts):
        """
        Applies a categorized renderer with distinct vibrant colors for each cluster and muted gray for noise.
        """
        from qgis.core import QgsCategorizedSymbolRenderer, QgsRendererCategory, QgsSymbol
        from qgis.PyQt.QtGui import QColor

        categories = []

        # Noise (-1) styling
        sym_noise = QgsSymbol.defaultSymbol(layer.geometryType())
        sym_noise.setColor(QColor(140, 140, 140, 130))
        sym_noise.setSize(2.5)
        categories.append(QgsRendererCategory(-1, sym_noise, "Bruit (-1)"))

        # Cluster palette
        palette = [
            "#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00",
            "#ffff33", "#a65628", "#f781bf", "#00ced1", "#ff1493",
            "#7fff00", "#00bfff", "#ff8c00", "#9932cc", "#808000"
        ]

        for i, cid in enumerate(sorted(cluster_counts.keys())):
            color_hex = palette[i % len(palette)]
            sym = QgsSymbol.defaultSymbol(layer.geometryType())
            sym.setColor(QColor(color_hex))
            sym.setSize(4.5)
            categories.append(QgsRendererCategory(cid, sym, f"Cluster {cid} ({cluster_counts[cid]} pts)"))

        renderer = QgsCategorizedSymbolRenderer("cluster_id", categories)
        layer.setRenderer(renderer)
        layer.triggerRepaint()


