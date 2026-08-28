"""
Main plugin module for GeoCongo AI QGIS Plugin.
Integrates GUI panels, menu items, toolbar buttons, dynamic BBOX handling, and Gundua Engine.
"""

from qgis.PyQt.QtWidgets import QAction, QMessageBox, QMenu
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QIcon

from .gui.main_dock import GeoCongoAIDockWidget
from .gui.gundua_dialog import GunduaEngineDialog
from .gui.drillhole_dialog import DrillholeAnalysisDialog
from .gui.settings_dialog import SettingsDialog


class GeoCongoAI:
    """
    QGIS Plugin main manager class for GeoCongo AI.
    """

    def __init__(self, iface):
        self.iface = iface
        self.dock_widget = None
        self.menu = None

        # Actions
        self.action_greenfield = None
        self.action_drillholes = None
        self.action_dock = None
        self.action_settings = None
        self.action_about = None

    def initGui(self):
        import os
        plugin_dir = os.path.dirname(__file__)
        icon_path = os.path.join(plugin_dir, "icon.png")
        icon = QIcon(icon_path) if os.path.exists(icon_path) else QIcon()

        # 1. Create Actions
        self.action_greenfield = QAction(
            icon,
            "🛰️ Analyse Greenfield (Gundua Engine)",
            self.iface.mainWindow()
        )
        self.action_greenfield.setToolTip("Lancer une analyse Greenfield avec BBOX dynamique")
        self.action_greenfield.triggered.connect(self.run_greenfield)

        self.action_drillholes = QAction(
            icon,
            "⛏️ Forages & Géochimie (DBSCAN 3D)",
            self.iface.mainWindow()
        )
        self.action_drillholes.setToolTip("Ouvrir l'outil de clustering géochimique DBSCAN")
        self.action_drillholes.triggered.connect(self.run_drillholes)

        self.action_dock = QAction(
            icon,
            "📐 Panneau Latéral GeoCongo AI",
            self.iface.mainWindow()
        )
        self.action_dock.setCheckable(True)
        self.action_dock.setToolTip("Afficher ou masquer le panneau latéral GeoCongo AI")
        self.action_dock.triggered.connect(self.toggle_dock)

        self.action_settings = QAction(
            icon,
            "⚙️ Paramètres API & Serveur",
            self.iface.mainWindow()
        )
        self.action_settings.triggered.connect(self.open_settings)

        self.action_about = QAction(
            icon,
            "ℹ️ À propos de GeoCongo AI",
            self.iface.mainWindow()
        )
        self.action_about.triggered.connect(self.show_about)

        # 2. Add Plugin Menu & Submenus
        self.iface.addPluginToMenu("&GeoCongo AI", self.action_greenfield)
        self.iface.addPluginToMenu("&GeoCongo AI", self.action_drillholes)
        self.iface.addPluginToMenu("&GeoCongo AI", self.action_dock)
        self.iface.addPluginToMenu("&GeoCongo AI", self.action_settings)
        self.iface.addPluginToMenu("&GeoCongo AI", self.action_about)

        # 3. Add Main Action to Toolbar
        self.iface.addToolBarIcon(self.action_greenfield)

        # 4. Instantiate DockWidget
        self.dock_widget = GeoCongoAIDockWidget(self.iface)
        self.dock_widget.visibilityChanged.connect(self.action_dock.setChecked)
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.hide()

    def unload(self):
        # Remove actions from Menu & Toolbar
        if self.action_greenfield:
            self.iface.removePluginMenu("&GeoCongo AI", self.action_greenfield)
            self.iface.removeToolBarIcon(self.action_greenfield)
        if self.action_drillholes:
            self.iface.removePluginMenu("&GeoCongo AI", self.action_drillholes)
        if self.action_dock:
            self.iface.removePluginMenu("&GeoCongo AI", self.action_dock)
        if self.action_settings:
            self.iface.removePluginMenu("&GeoCongo AI", self.action_settings)
        if self.action_about:
            self.iface.removePluginMenu("&GeoCongo AI", self.action_about)

        # Remove DockWidget
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget.deleteLater()
            self.dock_widget = None

    def run_greenfield(self):
        dlg = GunduaEngineDialog(self.iface)
        dlg.exec_()

    def run_drillholes(self):
        dlg = DrillholeAnalysisDialog(self.iface)
        dlg.exec_()

    def toggle_dock(self):
        if self.dock_widget:
            if self.dock_widget.isVisible():
                self.dock_widget.hide()
            else:
                self.dock_widget.show()

    def open_settings(self):
        dlg = SettingsDialog(self.iface.mainWindow())
        dlg.exec_()

    def show_about(self):
        import os
        from qgis.PyQt.QtGui import QIcon, QPixmap
        plugin_dir = os.path.dirname(__file__)
        icon_path = os.path.join(plugin_dir, "icon.png")

        msg = QMessageBox(self.iface.mainWindow())
        msg.setWindowTitle("À propos - GeoCongo AI")
        if os.path.exists(icon_path):
            msg.setWindowIcon(QIcon(icon_path))
            msg.setIconPixmap(QPixmap(icon_path).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        msg.setText("<h3>GeoCongo AI - Extension QGIS v0.2.0</h3>")
        msg.setInformativeText(
            "<p>Plateforme d'intelligence artificielle et d'analyse géospatiale avancée "
            "dédiée à l'exploration minière et la télédétection en République Démocratique du Congo.</p>"
            "<p><b>Propulsé par :</b></p>"
            "<ul>"
            "<li>Gundua Engine Remote API</li>"
            "<li>geocongoai (SDK Python v0.2.0)</li>"
            "<li>QGIS 3.x API & PyQt5</li>"
            "</ul>"
            "<p><i>Statut SDK : Connecté et opérationnel</i></p>"
        )
        msg.exec_()
