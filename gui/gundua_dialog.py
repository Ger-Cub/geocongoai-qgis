"""
Gundua Engine Greenfield Analysis Dialog for GeoCongo AI.
Provides form for spatial analysis parameters, dynamic BBOX selection, background execution, and layer rendering.
"""

from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QComboBox, QSpinBox, QCheckBox, QPushButton,
    QProgressBar, QLabel, QMessageBox
)
from qgis.PyQt.QtCore import Qt
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer, QgsApplication, QgsMessageLog, Qgis
)

from .components.area_selector import AreaSelectorWidget
from ..tasks.gundua_task import GunduaAnalysisTask
from ..utils.crs_utils import validate_wgs84_bbox


class GunduaEngineDialog(QDialog):
    """
    Dialog for running Gundua Engine analyses with dynamic bounding box and background task execution.
    """

    def __init__(self, iface, parent=None):
        super().__init__(parent or iface.mainWindow())
        self.iface = iface
        self.active_task = None

        self.setWindowTitle("GeoCongo AI - Analyse Gundua Engine")
        self.setMinimumSize(540, 400)
        self.setSizeGripEnabled(True)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Header / Description Banner
        header_box = QGroupBox("🛰️ Client Gundua Engine")
        header_layout = QHBoxLayout(header_box)

        # Logo display
        import os
        from qgis.PyQt.QtGui import QIcon, QPixmap
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(logo_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(lbl_logo)

        lbl_info = QLabel(
            "Exécutez des algorithmes de télédétection et prospection minérale "
            "directement sur l'emprise dynamique de votre projet QGIS. "
            "Les analyses STAC (🌱 MSV, 🪨 ASTER, 🔥 Feux, 💧 Inondations) "
            "requièrent le SDK v0.4.5 avec l'extra [stac] installé."
        )
        lbl_info.setWordWrap(True)
        header_layout.addWidget(lbl_info)
        main_layout.addWidget(header_box)

        # Spatial Area Selector Component (Dynamic BBOX)
        self.area_selector = AreaSelectorWidget(self.iface, self)
        main_layout.addWidget(self.area_selector)

        # Analysis Parameters Box
        params_box = QGroupBox("⚙️ Paramètres de l'analyse")
        params_layout = QVBoxLayout(params_box)

        # Analysis Type Choice
        type_layout = QHBoxLayout()
        type_layout.addWidget(QLabel("Type d'analyse :"))
        self.cb_analysis_type = QComboBox()
        self.cb_analysis_type.addItem("Greenfield (Détection Cibles)", "greenfield")
        self.cb_analysis_type.addItem("Land Cover (Occupation Sol)", "landcover")
        self.cb_analysis_type.addItem("Extraction Illégale (Minière)", "illegal_mining")
        self.cb_analysis_type.addItem("Glissement de Terrain", "landslide")
        self.cb_analysis_type.addItem("Linéaments Géologiques", "lineaments")
        self.cb_analysis_type.addItem("🌱 MSV — Stress Métallique Végétal (STAC)", "msv_stac")
        self.cb_analysis_type.addItem("🪨 Altération Hydrothermale ASTER (STAC)", "aster_hydrothermal")
        self.cb_analysis_type.addItem("🔥 Cartographie Incendies dNBR (STAC)", "burn_stac")
        self.cb_analysis_type.addItem("💧 Détection Inondations SAR (STAC)", "flood_stac")
        type_layout.addWidget(self.cb_analysis_type)
        params_layout.addLayout(type_layout)

        # Duration Months Input
        months_layout = QHBoxLayout()
        months_layout.addWidget(QLabel("Période (Mois) :"))
        self.spn_months = QSpinBox()
        self.spn_months.setRange(1, 24)
        self.spn_months.setValue(3)
        self.spn_months.setSuffix(" mois")
        months_layout.addWidget(self.spn_months)
        params_layout.addLayout(months_layout)

        # Options Checkboxes
        self.chk_add_vector = QCheckBox("Ajouter la couche Vectorielle (GeoJSON)")
        self.chk_add_vector.setChecked(True)
        self.chk_add_raster = QCheckBox("Ajouter la couche Raster (GeoTIFF)")
        self.chk_add_raster.setChecked(True)

        params_layout.addWidget(self.chk_add_vector)
        params_layout.addWidget(self.chk_add_raster)

        main_layout.addWidget(params_box)

        # Progress and Status Layout
        self.status_lbl = QLabel("Prêt pour l'analyse.")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0) # Indeterminate progress when running
        self.progress_bar.setVisible(False)

        main_layout.addWidget(self.status_lbl)
        main_layout.addWidget(self.progress_bar)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_run = QPushButton("Lancer l'analyse")
        self.btn_run.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white; padding: 6px;")
        self.btn_close = QPushButton("Fermer")

        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_close)
        main_layout.addLayout(btn_layout)

        # Signals
        self.btn_run.clicked.connect(self.run_analysis)
        self.btn_close.clicked.connect(self.accept)

    def run_analysis(self):
        """
        Validates inputs and launches non-blocking QgsTask.
        """
        bbox = self.area_selector.get_bbox()

        # Validate bounding box coordinates
        is_valid, msg = validate_wgs84_bbox(bbox)
        if not is_valid:
            QMessageBox.warning(
                self,
                "BBOX Invalide",
                f"Les coordonnées BBOX sont invalides :\n\n{msg}\n\n"
                "💡 Conseil : Modifiez le 'CRS Source' dans la zone de sélection de carte "
                "pour faire correspondre le système de coordonnées originel (ex: UTM Zone 33S) et convertir les valeurs en WGS84."
            )
            return


        analysis_type = self.cb_analysis_type.currentData()
        months = self.spn_months.value()

        # Lock UI controls
        self.btn_run.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.status_lbl.setText(f"Exécution en cours ({analysis_type}). Veuillez patienter...")

        # Create and start task
        self.active_task = GunduaAnalysisTask(analysis_type, bbox, months)
        self.active_task.analysisFinished.connect(self.on_analysis_finished)
        self.active_task.analysisFailed.connect(self.on_analysis_failed)

        QgsApplication.taskManager().addTask(self.active_task)

    def on_analysis_finished(self, result: dict):
        """
        Handles success result from background task and loads QGIS layers.
        """
        self.progress_bar.setVisible(False)
        self.btn_run.setEnabled(True)
        self.status_lbl.setText("✅ Analyse terminée avec succès !")

        base_url = result.get("_base_url", "")
        layers_added = 0

        # Load GeoJSON Vector Layer
        if self.chk_add_vector.isChecked() and "geojson_url" in result:
            vector_url = base_url + result["geojson_url"]
            vector_layer = QgsVectorLayer(vector_url, f"GeoCongo AI - {self.cb_analysis_type.currentText()}", "ogr")

            if vector_layer.isValid():
                QgsProject.instance().addMapLayer(vector_layer)
                layers_added += 1
            else:
                QgsMessageLog.logMessage(
                    f"Impossible de charger le GeoJSON depuis: {vector_url}", "GeoCongoAI", Qgis.Warning
                )

        # Load GDAL Raster Layer
        if self.chk_add_raster.isChecked() and "raster_url" in result:
            raster_url = base_url + result["raster_url"]
            raster_layer = QgsRasterLayer(raster_url, f"GeoCongo AI - Raster {self.cb_analysis_type.currentText()}", "gdal")

            if raster_layer.isValid():
                QgsProject.instance().addMapLayer(raster_layer)
                layers_added += 1
            else:
                QgsMessageLog.logMessage(
                    f"Impossible de charger le Raster depuis: {raster_url}", "GeoCongoAI", Qgis.Warning
                )

        QMessageBox.information(
            self,
            "Succès GeoCongo AI",
            f"L'analyse '{self.cb_analysis_type.currentText()}' s'est terminée avec succès.\n\n"
            f"Couches ajoutées à QGIS : {layers_added}\n"
            f"Zone (BBOX) : {self.area_selector.get_bbox()}"
        )

    def on_analysis_failed(self, error_msg: str):
        """
        Handles failure from background task.
        """
        self.progress_bar.setVisible(False)
        self.btn_run.setEnabled(True)
        self.status_lbl.setText("❌ Échec de l'analyse.")

        QMessageBox.critical(
            self,
            "Erreur Gundua Engine",
            f"Une erreur est survenue pendant l'analyse :\n\n{error_msg}"
        )
