"""
Main DockWidget for GeoCongo AI QGIS Plugin.
Serves as the primary control panel docked inside QGIS workspace.
"""

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget,
    QGroupBox, QPushButton, QLabel, QTextEdit, QMessageBox
)
from qgis.PyQt.QtCore import Qt

from .gundua_dialog import GunduaEngineDialog
from .drillhole_dialog import DrillholeAnalysisDialog
from .settings_dialog import SettingsDialog
from ..utils.crs_utils import get_canvas_extent_wgs84, validate_wgs84_bbox


class GeoCongoAIDockWidget(QDockWidget):
    """
    Main Dock Widget for GeoCongo AI plugin in QGIS.
    """

    def __init__(self, iface, parent=None):
        super().__init__("GeoCongo AI", parent or iface.mainWindow())
        self.iface = iface
        self.setObjectName("GeoCongoAIDockWidget")
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self._init_ui()

    def _init_ui(self):
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Title / Brand Header
        header_layout = QHBoxLayout()
        
        import os
        from qgis.PyQt.QtGui import QIcon, QPixmap
        plugin_dir = os.path.dirname(os.path.dirname(__file__))
        logo_path = os.path.join(plugin_dir, "icon.png")
        if os.path.exists(logo_path):
            self.setWindowIcon(QIcon(logo_path))
            lbl_logo = QLabel()
            lbl_logo.setPixmap(QPixmap(logo_path).scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            header_layout.addWidget(lbl_logo)

        lbl_title = QLabel("<b>GeoCongo AI</b> v0.2.0")
        lbl_title.setStyleSheet("font-size: 14px; color: #1b5e20;")
        header_layout.addWidget(lbl_title)
        header_layout.addStretch()

        btn_settings = QPushButton("⚙️ Paramètres")
        btn_settings.setToolTip("Configurer les clés API et serveurs")
        btn_settings.clicked.connect(self.open_settings)
        header_layout.addWidget(btn_settings)

        layout.addLayout(header_layout)

        # Tab Widget for Modules
        self.tabs = QTabWidget()

        # Tab 1: Gundua Engine & Greenfield
        tab_gundua = QWidget()
        layout_gundua = QVBoxLayout(tab_gundua)

        box_gundua = QGroupBox("🛰️ Gundua Engine API")
        box_gundua_layout = QVBoxLayout(box_gundua)
        
        lbl_gundua_desc = QLabel("Télédétection et prédiction des anomalies géologiques via l'API Gundua.")
        lbl_gundua_desc.setWordWrap(True)
        box_gundua_layout.addWidget(lbl_gundua_desc)

        btn_open_gundua = QPushButton("Lancer l'analyse Greenfield (BBOX Dynamique)")
        btn_open_gundua.setStyleSheet("font-weight: bold; background-color: #2e7d32; color: white; padding: 8px;")
        btn_open_gundua.clicked.connect(self.open_gundua_dialog)
        box_gundua_layout.addWidget(btn_open_gundua)

        layout_gundua.addWidget(box_gundua)

        # BBOX Dynamic Status Preview Box
        box_bbox = QGroupBox("📍 Emprise Carte Courante (WGS84)")
        box_bbox_layout = QVBoxLayout(box_bbox)
        
        self.lbl_bbox_preview = QLabel("Calcul de l'emprise...")
        self.lbl_bbox_preview.setStyleSheet("font-family: monospace; color: #333;")
        box_bbox_layout.addWidget(self.lbl_bbox_preview)

        btn_refresh_bbox = QPushButton("🔄 Actualiser Emprise")
        btn_refresh_bbox.clicked.connect(self.update_bbox_preview)
        box_bbox_layout.addWidget(btn_refresh_bbox)

        layout_gundua.addWidget(box_bbox)
        layout_gundua.addStretch()
        self.tabs.addTab(tab_gundua, "Gundua Engine")

        # Tab 2: Drillholes & DBSCAN 3D
        tab_drill = QWidget()
        layout_drill = QVBoxLayout(tab_drill)

        box_drill = QGroupBox("⛏️ Forages & Géochimie")
        box_drill_layout = QVBoxLayout(box_drill)
        
        lbl_drill_desc = QLabel("Clustering spatial DBSCAN et filtrage par seuil de teneur sur données de forages.")
        lbl_drill_desc.setWordWrap(True)
        box_drill_layout.addWidget(lbl_drill_desc)

        btn_open_drill = QPushButton("Ouvrir l'analyseur DBSCAN 3D")
        btn_open_drill.setStyleSheet("font-weight: bold; background-color: #1976d2; color: white; padding: 8px;")
        btn_open_drill.clicked.connect(self.open_drillhole_dialog)
        box_drill_layout.addWidget(btn_open_drill)

        layout_drill.addWidget(box_drill)
        layout_drill.addStretch()
        self.tabs.addTab(tab_drill, "Forages / 3D")

        # Tab 3: Logs & Output Panel
        tab_logs = QWidget()
        layout_logs = QVBoxLayout(tab_logs)
        layout_logs.addWidget(QLabel("📜 Journal des opérations :"))
        self.txt_logs = QTextEdit()
        self.txt_logs.setReadOnly(True)
        self.txt_logs.setText("GeoCongo AI Plugin initialisé avec succès.\nPrêt à traiter les données géospatiales.\n")
        layout_logs.addWidget(self.txt_logs)
        self.tabs.addTab(tab_logs, "Journal & Résultats")

        layout.addWidget(self.tabs)
        self.setWidget(main_widget)

        # Update initial bbox preview
        self.update_bbox_preview()

        # Connect canvas navigation signals
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().extentsChanged.connect(self.update_bbox_preview)

    def update_bbox_preview(self):
        try:
            bbox = get_canvas_extent_wgs84(self.iface)
            is_valid, msg = validate_wgs84_bbox(bbox)
            text = (
                f"XMin (Lon): {bbox[0]}\n"
                f"YMin (Lat): {bbox[1]}\n"
                f"XMax (Lon): {bbox[2]}\n"
                f"YMax (Lat): {bbox[3]}"
            )
            if not is_valid:
                text += f"\n\n⚠️ Coordonnées non-WGS84 (métriques)\nOuvrez la boîte de dialogue pour spécifier le CRS source."
            self.lbl_bbox_preview.setText(text)
        except Exception as e:
            self.lbl_bbox_preview.setText(f"Erreur d'emprise: {e}")


    def log(self, message: str):
        self.txt_logs.append(message)

    def open_gundua_dialog(self):
        dlg = GunduaEngineDialog(self.iface, self)
        dlg.exec_()

    def open_drillhole_dialog(self):
        dlg = DrillholeAnalysisDialog(self.iface, self)
        dlg.exec_()

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec_()
