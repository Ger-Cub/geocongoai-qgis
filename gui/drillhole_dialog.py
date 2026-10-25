"""
Drillhole and geochemical DBSCAN analysis dialog for GeoCongo AI.
"""

import os

from qgis.PyQt.QtCore import QVariant, Qt
from qgis.PyQt.QtGui import QPixmap
from qgis.PyQt.QtWidgets import (
    QDialog,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from qgis.core import QgsFeature, QgsField, QgsGeometry, QgsMapLayerProxyModel, QgsProject, QgsVectorLayer
from qgis.gui import QgsFieldComboBox, QgsMapLayerComboBox

from ..utils.chimbua_visualization import apply_cluster_symbology, export_interactive_chimbua_html
from ..utils.drillhole_adapter import (
    build_no_result_message,
    detect_support_layers,
    infer_grade_field_name,
    prepare_drillhole_dataset,
)


def pure_python_dbscan(coords, eps, min_samples):
    """
    Pure Python DBSCAN implementation fallback when scikit-learn is not installed.
    """
    import math

    count = len(coords)
    labels = [-1] * count
    cluster_id = 0
    visited = [False] * count

    def region_query(point_idx):
        point = coords[point_idx]
        return [idx for idx in range(count) if math.hypot(point[0] - coords[idx][0], point[1] - coords[idx][1]) <= eps]

    for idx in range(count):
        if visited[idx]:
            continue
        visited[idx] = True
        neighbors = region_query(idx)

        if len(neighbors) < min_samples:
            labels[idx] = -1
            continue

        labels[idx] = cluster_id
        seeds = [neighbor for neighbor in neighbors if neighbor != idx]
        seed_index = 0
        while seed_index < len(seeds):
            current = seeds[seed_index]
            if not visited[current]:
                visited[current] = True
                current_neighbors = region_query(current)
                if len(current_neighbors) >= min_samples:
                    for neighbor in current_neighbors:
                        if neighbor not in seeds:
                            seeds.append(neighbor)
            if labels[current] == -1:
                labels[current] = cluster_id
            seed_index += 1

        cluster_id += 1

    return labels


class DrillholeAnalysisDialog(QDialog):
    """
    Dialog for drillholes and assay vector clustering using GeoCongo AI utilities.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self._last_geo_result = None
        self._last_prepared_dataset = None
        self._auto_updating_support_layers = False
        self._user_selected_collar_layer = False
        self._user_selected_survey_layer = False

        self.setWindowTitle("GeoCongo AI - Drillhole & Géochimie DBSCAN")
        self.resize(520, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header_box = QGroupBox("⛏️ Analyse Spatiale des Forages & Géochimie")
        header_layout = QHBoxLayout(header_box)

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

        selectors_box = QGroupBox("🗺️ Couches et Attributs QGIS")
        selectors_layout = QVBoxLayout(selectors_box)

        selectors_layout.addWidget(QLabel("Couche d'échantillons / Forages (Assays / Collars) :"))
        self.cb_layer = QgsMapLayerComboBox(self)
        self.cb_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        selectors_layout.addWidget(self.cb_layer)

        selectors_layout.addWidget(QLabel("Couche de colliers / Surface (Collars - optionnel si table sans géométrie) :"))
        self.cb_collar_layer = QgsMapLayerComboBox(self)
        self.cb_collar_layer.setFilters(QgsMapLayerProxyModel.PointLayer)
        self.cb_collar_layer.setAllowEmptyLayer(True)
        self.cb_collar_layer.setLayer(None)
        selectors_layout.addWidget(self.cb_collar_layer)

        selectors_layout.addWidget(QLabel("Couche de trajectoires / Déviation (Surveys - optionnel) :"))
        self.cb_survey_layer = QgsMapLayerComboBox(self)
        self.cb_survey_layer.setFilters(QgsMapLayerProxyModel.VectorLayer)
        self.cb_survey_layer.setAllowEmptyLayer(True)
        self.cb_survey_layer.setLayer(None)
        selectors_layout.addWidget(self.cb_survey_layer)

        self.lbl_no_layers = QLabel(
            "<font color='#d32f2f'>⚠️ Aucune couche vectorielle chargée dans QGIS. "
            "Veuillez ajouter une couche de données (GeoJSON, Shapefile, CSV) dans votre projet.</font>"
        )
        self.lbl_no_layers.setWordWrap(True)
        self.lbl_no_layers.setVisible(False)
        selectors_layout.addWidget(self.lbl_no_layers)

        selectors_layout.addWidget(QLabel("Élément / Teneur à analyser (ex: Cu, Au) :"))
        self.cb_field = QgsFieldComboBox(self)
        self.cb_field.setLayer(self.cb_layer.currentLayer())
        selectors_layout.addWidget(self.cb_field)
        layout.addWidget(selectors_box)

        params_box = QGroupBox("⚙️ Paramètres DBSCAN")
        params_layout = QVBoxLayout(params_box)

        cutoff_layout = QHBoxLayout()
        cutoff_layout.addWidget(QLabel("Seuil minimum de teneur :"))
        self.spn_cutoff = QDoubleSpinBox()
        self.spn_cutoff.setRange(0.0, 100.0)
        self.spn_cutoff.setDecimals(3)
        self.spn_cutoff.setValue(0.5)
        cutoff_layout.addWidget(self.spn_cutoff)
        params_layout.addLayout(cutoff_layout)

        eps_layout = QHBoxLayout()
        eps_layout.addWidget(QLabel("Eps (Distance de recherche en m) :"))
        self.spn_eps = QDoubleSpinBox()
        self.spn_eps.setRange(0.1, 10000.0)
        self.spn_eps.setValue(25.0)
        eps_layout.addWidget(self.spn_eps)
        params_layout.addLayout(eps_layout)

        min_samples_layout = QHBoxLayout()
        min_samples_layout.addWidget(QLabel("Minimum d'échantillons par cluster :"))
        self.spn_min_samples = QSpinBox()
        self.spn_min_samples.setRange(1, 1000)
        self.spn_min_samples.setValue(5)
        min_samples_layout.addWidget(self.spn_min_samples)
        params_layout.addLayout(min_samples_layout)

        layout.addWidget(params_box)

        btn_layout = QHBoxLayout()

        self.btn_run = QPushButton("Calculer les Clusters")
        self.btn_run.setStyleSheet(
            """
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
            """
        )
        self.btn_run.clicked.connect(self.run_clustering)
        btn_layout.addWidget(self.btn_run)

        self.btn_export_3d = QPushButton("Exporter 3D (HTML)")
        self.btn_export_3d.setEnabled(False)
        self.btn_export_3d.setStyleSheet(
            """
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
            """
        )
        self.btn_export_3d.clicked.connect(self.export_3d_html)
        btn_layout.addWidget(self.btn_export_3d)

        btn_close = QPushButton("Fermer")
        btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(btn_close)

        layout.addLayout(btn_layout)
        self._connect_layer_combo_signal()
        self._connect_support_combo_signals()
        self._on_layer_changed()

    def _connect_layer_combo_signal(self):
        if hasattr(self.cb_layer, "layerChanged"):
            self.cb_layer.layerChanged.connect(self._on_layer_changed)
            return
        if hasattr(self.cb_layer, "currentIndexChanged"):
            self.cb_layer.currentIndexChanged.connect(self._on_layer_changed)

    def _connect_support_combo_signals(self):
        for combo, handler in (
            (self.cb_collar_layer, self._on_collar_layer_changed),
            (self.cb_survey_layer, self._on_survey_layer_changed),
        ):
            if hasattr(combo, "layerChanged"):
                combo.layerChanged.connect(handler)
            elif hasattr(combo, "currentIndexChanged"):
                combo.currentIndexChanged.connect(handler)

    def _on_collar_layer_changed(self, *_args):
        if not self._auto_updating_support_layers:
            self._user_selected_collar_layer = True

    def _on_survey_layer_changed(self, *_args):
        if not self._auto_updating_support_layers:
            self._user_selected_survey_layer = True

    def _set_preferred_grade_field(self, layer):
        if not layer or not hasattr(self, "cb_field"):
            return
        preferred_field = infer_grade_field_name(layer)
        if not preferred_field:
            return
        if hasattr(self.cb_field, "setField"):
            self.cb_field.setField(preferred_field)
            return
        index = self.cb_field.findText(preferred_field) if hasattr(self.cb_field, "findText") else -1
        if index >= 0 and hasattr(self.cb_field, "setCurrentIndex"):
            self.cb_field.setCurrentIndex(index)

    def _on_layer_changed(self, *_args):
        layer = self.cb_layer.currentLayer()
        if hasattr(self, "cb_field"):
            self.cb_field.setLayer(layer)
        if not layer:
            self.lbl_no_layers.setVisible(True)
            if hasattr(self, "btn_run"):
                self.btn_run.setEnabled(False)
            return

        self.lbl_no_layers.setVisible(False)
        if hasattr(self, "btn_run"):
            self.btn_run.setEnabled(True)
        self._set_preferred_grade_field(layer)
        collar_layer, survey_layer = detect_support_layers(
            layer,
            project_or_layers=QgsProject.instance(),
            collar_layer=self.cb_collar_layer.currentLayer() if self._user_selected_collar_layer else None,
            survey_layer=self.cb_survey_layer.currentLayer() if self._user_selected_survey_layer else None,
        )
        self._auto_updating_support_layers = True
        try:
            self.cb_collar_layer.setLayer(collar_layer)
            self.cb_survey_layer.setLayer(survey_layer)
        finally:
            self._auto_updating_support_layers = False

    def run_clustering(self):
        try:
            import numpy as np
        except ImportError:
            np = None

        from qgis.core import QgsPoint

        layer = self.cb_layer.currentLayer()
        if not layer or not layer.isValid():
            QMessageBox.warning(
                self,
                "Erreur Couche",
                "Aucune couche sélectionnée. Veuillez d'abord ajouter une couche de données dans QGIS.",
            )
            return

        field_name = self.cb_field.currentField()
        if not field_name:
            QMessageBox.warning(
                self,
                "Erreur Attribut",
                "Veuillez sélectionner un champ d'attribut valide dans la liste déroulante.",
            )
            return

        cutoff = self.spn_cutoff.value()
        eps = self.spn_eps.value()
        min_samples = self.spn_min_samples.value()

        self.btn_export_3d.setEnabled(False)
        self._last_geo_result = None

        try:
            prepared = prepare_drillhole_dataset(
                assay_layer=layer,
                grade_field=field_name,
                cutoff=cutoff,
                collar_layer=self.cb_collar_layer.currentLayer(),
                survey_layer=self.cb_survey_layer.currentLayer(),
                project_or_layers=QgsProject.instance(),
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Préparation des données", str(exc))
            return

        self._last_prepared_dataset = prepared
        records = prepared["records"]
        coords = prepared["coords"]
        if not coords:
            QMessageBox.information(self, "Aucun Résultat", build_no_result_message(prepared))
            return

        try:
            from sklearn.cluster import DBSCAN

            if np is not None:
                coords_arr = np.array(coords, dtype=float)
                labels = list(DBSCAN(eps=eps, min_samples=min_samples).fit(coords_arr).labels_)
            else:
                labels = pure_python_dbscan(coords, eps, min_samples)
        except Exception:
            labels = pure_python_dbscan(coords, eps, min_samples)

        crs_authid = layer.crs().authid() if layer.crs().isValid() else "EPSG:4326"
        out_layer_name = f"Clusters_DBSCAN_{layer.name()}_{field_name}"
        out_layer = QgsVectorLayer(f"PointZ?crs={crs_authid}", out_layer_name, "memory")
        provider = out_layer.dataProvider()

        new_fields = [field for field in layer.fields().toList()]
        new_fields.append(QgsField("cluster_id", QVariant.Int))
        new_fields.append(QgsField("is_noise", QVariant.Int))
        new_fields.append(QgsField("grade_val", QVariant.Double))
        new_fields.append(QgsField("z_elevation", QVariant.Double))
        provider.addAttributes(new_fields)
        out_layer.updateFields()

        out_features = []
        cluster_counts = {}
        for idx, record in enumerate(records):
            cluster_id = int(labels[idx])
            is_noise = 1 if cluster_id == -1 else 0
            if cluster_id != -1:
                cluster_counts[cluster_id] = cluster_counts.get(cluster_id, 0) + 1

            feature = QgsFeature(out_layer.fields())
            feature.setGeometry(QgsGeometry(QgsPoint(record["point"].x(), record["point"].y(), record["z_value"])))

            attrs = list(record["feature"].attributes())
            attrs.extend([cluster_id, is_noise, record["grade_value"], record["z_value"]])
            feature.setAttributes(attrs)
            out_features.append(feature)

        provider.addFeatures(out_features)
        out_layer.updateExtents()
        self._apply_cluster_symbology(out_layer, cluster_counts)
        QgsProject.instance().addMapLayer(out_layer)

        try:
            from geocongoai.results import GeoResult

            points_3d = []
            clusters_dict = {}
            for idx, record in enumerate(records):
                cluster_id = int(labels[idx])
                point_item = {
                    "x": float(record["point"].x()),
                    "y": float(record["point"].y()),
                    "z": float(record["z_value"]),
                    "hole_id": record["hole_id"],
                    "mid_depth": float(record["mid_depth"]),
                    "cluster": cluster_id,
                    "value": float(record["grade_value"]),
                    field_name: float(record["grade_value"]),
                }
                points_3d.append(point_item)
                if cluster_id != -1:
                    clusters_dict.setdefault(cluster_id, []).append(point_item)

            geometries_list = []
            palette = [
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
            try:
                from scipy.spatial import ConvexHull

                for cluster_id, cluster_points in clusters_dict.items():
                    if len(cluster_points) >= 4 and np is not None:
                        points_array = np.array([[item["x"], item["y"], item["z"]] for item in cluster_points])
                        if np.linalg.matrix_rank(points_array - points_array[0]) >= 3:
                            hull = ConvexHull(points_array)
                            geometries_list.append(
                                {
                                    "cluster_id": cluster_id,
                                    "volume_m3": float(hull.volume),
                                    "color": palette[cluster_id % len(palette)],
                                    "vertices": {
                                        "x": points_array[:, 0].tolist(),
                                        "y": points_array[:, 1].tolist(),
                                        "z": points_array[:, 2].tolist(),
                                    },
                                    "simplices": {
                                        "i": hull.simplices[:, 0].tolist(),
                                        "j": hull.simplices[:, 1].tolist(),
                                        "k": hull.simplices[:, 2].tolist(),
                                    },
                                }
                            )
            except ImportError:
                geometries_list = []
            except Exception as hull_error:
                import logging

                logging.getLogger(__name__).warning("ConvexHull skipped: %s", hull_error)
                geometries_list = []

            max_grade = max((point["value"] for point in points_3d), default=0.0)
            self._last_geo_result = GeoResult(
                points=points_3d,
                geometries=geometries_list,
                statistics={"total_samples": len(points_3d), "clusters_count": len(clusters_dict), "max": max_grade},
                metadata={
                    "title": f"GeoCongo AI — Visualisation 3D (Champ {field_name})",
                    "analysis_type": "dbscan_3d",
                    "element": field_name,
                    "cluster_count": len(clusters_dict),
                    "filtered_intervals": len(points_3d),
                    "grade_threshold": cutoff,
                    "eps": eps,
                    "min_samples": min_samples,
                },
                collars=(prepared.get("sdk_inputs") or {}).get("collars") or [],
            )
            self.btn_export_3d.setEnabled(True)
        except Exception as geo_error:
            import logging

            logging.getLogger(__name__).warning("GeoResult build failed: %s", geo_error)
            self._last_geo_result = None
            self.btn_export_3d.setEnabled(False)

        n_clusters = len(cluster_counts)
        n_noise = list(labels).count(-1)
        n_total = len(records)

        QMessageBox.information(
            self,
            "Analyse DBSCAN Terminée",
            f"✅ Clustering DBSCAN terminé avec succès !\n\n"
            f"• Couche source : {layer.name()}\n"
            f"• Champ analysé : {field_name} (seuil >= {cutoff})\n"
            f"• Échantillons filtrés : {n_total} sur {prepared['stats']['source_feature_count']}\n"
            f"• Clusters identifiés : {n_clusters}\n"
            f"• Points de bruit géochimique (-1) : {n_noise}\n\n"
            f"La nouvelle couche '{out_layer_name}' a été ajoutée à votre projet QGIS.\n"
            f"Vous pouvez également cliquer sur 'Exporter 3D (HTML)' pour visualiser en 3D dans votre navigateur.",
        )

    def export_3d_html(self):
        """
        Exports current GeoResult to standalone interactive 3D HTML and launches default web browser.
        """
        if not self._last_geo_result:
            QMessageBox.warning(self, "Export 3D", "Veuillez d'abord calculer les clusters.")
            return

        from qgis.PyQt.QtCore import QUrl
        from qgis.PyQt.QtGui import QDesktopServices
        from qgis.PyQt.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Enregistrer la visualisation 3D HTML",
            "dbscan_clusters_3d.html",
            "Fichiers HTML (*.html)",
        )
        if not file_path:
            return

        try:
            export_interactive_chimbua_html(self._last_geo_result, output_path=file_path)
            QMessageBox.information(
                self,
                "Export 3D Réussi",
                f"✅ Visualisation 3D HTML générée avec succès :\n\n{file_path}\n\n"
                "Ouverture dans votre navigateur web...",
            )
            QDesktopServices.openUrl(QUrl.fromLocalFile(file_path))
        except Exception as exc:
            QMessageBox.critical(self, "Erreur Export 3D", f"Impossible d'exporter le fichier HTML 3D :\n{exc}")

    def _apply_cluster_symbology(self, layer, cluster_counts):
        apply_cluster_symbology(layer, cluster_counts=cluster_counts, cluster_field="cluster_id")
