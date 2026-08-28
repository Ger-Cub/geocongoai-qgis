"""
Area Selector Widget for GeoCongo AI.
Allows defining an analysis Bounding Box dynamically from Canvas Extent, QGIS Layer, or Manual Entry,
with support for overriding the Source CRS to ensure valid WGS84 reprojection.
"""

from qgis.PyQt.QtWidgets import (
    QGroupBox, QVBoxLayout, QHBoxLayout, QGridLayout,
    QRadioButton, QLabel, QDoubleSpinBox, QPushButton,
    QButtonGroup, QMessageBox
)
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.gui import QgsMapLayerComboBox, QgsProjectionSelectionWidget
from qgis.core import QgsProject, QgsCoordinateReferenceSystem

from ...utils.crs_utils import (
    get_canvas_extent_wgs84,
    get_layer_extent_wgs84,
    validate_wgs84_bbox
)


class AreaSelectorWidget(QGroupBox):
    """
    Form component for selecting the spatial analysis zone (BBOX WGS84).
    Supports overriding source CRS if canvas/layer CRS differs from actual coordinate values.
    """
    bboxChanged = pyqtSignal(list)

    MODE_CANVAS = 0
    MODE_LAYER = 1
    MODE_MANUAL = 2

    def __init__(self, iface, parent=None):
        super().__init__("📍 Zone d'analyse (Bounding Box WGS84)", parent)
        self.iface = iface
        self._updating_crs = False

        self._init_ui()
        self._connect_signals()
        self.refresh_canvas_extent()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        # Mode Selection Radio Buttons
        mode_layout = QHBoxLayout()
        self.rb_canvas = QRadioButton("Vue carte (Canvas)")
        self.rb_layer = QRadioButton("Couche QGIS")
        self.rb_manual = QRadioButton("Saisie manuelle")
        
        self.rb_canvas.setChecked(True)

        self.mode_group = QButtonGroup(self)
        self.mode_group.addButton(self.rb_canvas, self.MODE_CANVAS)
        self.mode_group.addButton(self.rb_layer, self.MODE_LAYER)
        self.mode_group.addButton(self.rb_manual, self.MODE_MANUAL)

        mode_layout.addWidget(self.rb_canvas)
        mode_layout.addWidget(self.rb_layer)
        mode_layout.addWidget(self.rb_manual)
        layout.addLayout(mode_layout)

        # Layer Selector Dropdown (Hidden unless Layer Mode is active)
        self.layer_container = QGroupBox("Sélectionner la couche de référence")
        layer_layout = QHBoxLayout(self.layer_container)
        self.cb_layers = QgsMapLayerComboBox(self)
        layer_layout.addWidget(self.cb_layers)
        self.layer_container.setVisible(False)
        layout.addWidget(self.layer_container)

        # Source CRS Selection Widget
        crs_layout = QHBoxLayout()
        crs_layout.addWidget(QLabel("🌐 CRS Source (Système originel) :"))
        self.crs_selector = QgsProjectionSelectionWidget(self)
        self.crs_selector.setOptionVisible(QgsProjectionSelectionWidget.LayerCrs, True)
        self.crs_selector.setToolTip(
            "Système de coordonnées originel du canvas ou de la couche.\n"
            "Modifiez ce champ si vos coordonnées sont métriques (ex: UTM) afin de les convertir correctement en WGS84."
        )
        crs_layout.addWidget(self.crs_selector)
        layout.addLayout(crs_layout)

        # Warning banner for invalid/out-of-bounds WGS84 coordinates
        self.lbl_crs_warning = QLabel("")
        self.lbl_crs_warning.setStyleSheet(
            "color: #b71c1c; background-color: #ffebee; border: 1px solid #ffcdd2; "
            "border-radius: 4px; padding: 6px; font-size: 11px;"
        )
        self.lbl_crs_warning.setWordWrap(True)
        self.lbl_crs_warning.setMinimumHeight(40)
        from qgis.PyQt.QtWidgets import QSizePolicy
        self.lbl_crs_warning.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
        self.lbl_crs_warning.setVisible(False)
        layout.addWidget(self.lbl_crs_warning)

        # Coordinates Display / Manual Inputs (BBOX SpinBoxes)
        grid = QGridLayout()

        self.sb_xmin = QDoubleSpinBox()
        self.sb_ymin = QDoubleSpinBox()
        self.sb_xmax = QDoubleSpinBox()
        self.sb_ymax = QDoubleSpinBox()

        for sb in (self.sb_xmin, self.sb_ymin, self.sb_xmax, self.sb_ymax):
            sb.setRange(-20000000.0, 20000000.0)  # Accepte les coordonnées projetées (UTM) sans troncature
            sb.setDecimals(3)
            sb.setSingleStep(0.001)
            sb.setMinimumWidth(110)

        grid.addWidget(QLabel("Nord (Lat Max):"), 0, 0)
        grid.addWidget(self.sb_ymax, 0, 1)
        grid.addWidget(QLabel("Sud (Lat Min):"), 0, 2)
        grid.addWidget(self.sb_ymin, 0, 3)

        grid.addWidget(QLabel("Ouest (Lon Min):"), 1, 0)
        grid.addWidget(self.sb_xmin, 1, 1)
        grid.addWidget(QLabel("Est (Lon Max):"), 1, 2)
        grid.addWidget(self.sb_xmax, 1, 3)

        layout.addLayout(grid)

        # Action Buttons Layout
        btn_layout = QHBoxLayout()
        self.btn_refresh = QPushButton("🔄 Actualiser depuis l'emprise carte")
        self.btn_refresh.setToolTip("Met à jour le BBOX en fonction de l'emprise courante affichée dans QGIS")
        btn_layout.addWidget(self.btn_refresh)
        
        layout.addLayout(btn_layout)
        self._update_read_only_states()

    def _connect_signals(self):
        self.mode_group.buttonToggled.connect(self._on_mode_changed)
        self.btn_refresh.clicked.connect(self.refresh_canvas_extent)
        self.cb_layers.layerChanged.connect(self._on_layer_changed)
        self.crs_selector.crsChanged.connect(self._on_crs_changed)

        for sb in (self.sb_xmin, self.sb_ymin, self.sb_xmax, self.sb_ymax):
            sb.valueChanged.connect(self._on_spinbox_changed)

        # Auto refresh if canvas extent changes while canvas mode is active
        if hasattr(self.iface, "mapCanvas"):
            self.iface.mapCanvas().extentsChanged.connect(self._on_canvas_extents_changed)

    def _on_mode_changed(self):
        mode = self.mode_group.checkedId()
        self.layer_container.setVisible(mode == self.MODE_LAYER)
        self.crs_selector.setEnabled(mode != self.MODE_MANUAL)
        self._update_read_only_states()

        if mode == self.MODE_CANVAS:
            self._updating_crs = True
            if hasattr(self.iface, "mapCanvas"):
                self.crs_selector.setCrs(self.iface.mapCanvas().mapSettings().destinationCrs())
            self._updating_crs = False
            self.refresh_canvas_extent()
        elif mode == self.MODE_LAYER:
            layer = self.cb_layers.currentLayer()
            if layer:
                self._updating_crs = True
                self.crs_selector.setCrs(layer.crs())
                self._updating_crs = False
            self._on_layer_changed(layer)

    def _on_crs_changed(self, crs: QgsCoordinateReferenceSystem):
        if self._updating_crs:
            return
        mode = self.mode_group.checkedId()
        if mode == self.MODE_CANVAS:
            self.refresh_canvas_extent()
        elif mode == self.MODE_LAYER:
            self._on_layer_changed(self.cb_layers.currentLayer())

    def _update_read_only_states(self):
        is_manual = (self.mode_group.checkedId() == self.MODE_MANUAL)
        for sb in (self.sb_xmin, self.sb_ymin, self.sb_xmax, self.sb_ymax):
            sb.setReadOnly(not is_manual)

    def _on_canvas_extents_changed(self):
        if self.mode_group.checkedId() == self.MODE_CANVAS:
            self.refresh_canvas_extent()

    def refresh_canvas_extent(self):
        """
        Calculates current canvas extent converted to WGS84 using current CRS selection and updates spinboxes.
        """
        try:
            custom_crs = self.crs_selector.crs()
            bbox = get_canvas_extent_wgs84(self.iface, custom_crs=custom_crs)
            self._set_spinbox_values(bbox)
        except Exception as e:
            QMessageBox.warning(self, "Erreur BBOX", f"Impossible d'extraire l'emprise de la carte: {e}")

    def _on_layer_changed(self, layer):
        if self.mode_group.checkedId() == self.MODE_LAYER and layer:
            try:
                custom_crs = self.crs_selector.crs()
                bbox = get_layer_extent_wgs84(layer, custom_crs=custom_crs)
                self._set_spinbox_values(bbox)
            except Exception as e:
                QMessageBox.warning(self, "Erreur Couche", f"Impossible d'obtenir l'emprise de la couche: {e}")

    def _on_spinbox_changed(self):
        bbox = self.get_bbox()
        self._validate_and_display_warning(bbox)
        self.bboxChanged.emit(bbox)

    def _validate_and_display_warning(self, bbox: list):
        is_valid, msg = validate_wgs84_bbox(bbox)
        if not is_valid:
            self.lbl_crs_warning.setText(
                f"⚠️ <b>Coordonnées Invalides</b> : {msg}<br/>"
                f"<i>Conseil : Modifiez le <b>CRS Source</b> ci-dessus pour correspondre à votre projection originelle (ex: UTM Zone 33S).</i>"
            )
            self.lbl_crs_warning.setVisible(True)
        else:
            self.lbl_crs_warning.setVisible(False)

    def _set_spinbox_values(self, bbox: list):
        self.sb_xmin.blockSignals(True)
        self.sb_ymin.blockSignals(True)
        self.sb_xmax.blockSignals(True)
        self.sb_ymax.blockSignals(True)

        self.sb_xmin.setValue(bbox[0])
        self.sb_ymin.setValue(bbox[1])
        self.sb_xmax.setValue(bbox[2])
        self.sb_ymax.setValue(bbox[3])

        self.sb_xmin.blockSignals(False)
        self.sb_ymin.blockSignals(False)
        self.sb_xmax.blockSignals(False)
        self.sb_ymax.blockSignals(False)

        self._validate_and_display_warning(bbox)
        self.bboxChanged.emit(bbox)

    def get_bbox(self) -> list:
        """
        Returns [xmin, ymin, xmax, ymax] in WGS84 coordinates.
        """
        return [
            round(self.sb_xmin.value(), 6),
            round(self.sb_ymin.value(), 6),
            round(self.sb_xmax.value(), 6),
            round(self.sb_ymax.value(), 6)
        ]

