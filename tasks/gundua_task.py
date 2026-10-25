"""
QgsTask implementation for non-blocking Gundua Engine API analysis requests.
"""

from qgis.core import QgsTask, QgsMessageLog, Qgis
from qgis.PyQt.QtCore import pyqtSignal

from geocongoai.gundua_engine import GunduaEngineClient


class GunduaAnalysisTask(QgsTask):
    """
    Background task executing GunduaEngineClient.analyze without freezing QGIS UI.
    """
    analysisFinished = pyqtSignal(dict)
    analysisFailed = pyqtSignal(str)

    def __init__(self, analysis_type: str, bbox: list, months: int = 3, api_key: str = None):
        super().__init__(f"GeoCongo AI - Analyse Gundua ({analysis_type})", QgsTask.CanCancel)
        self.analysis_type = analysis_type
        self.bbox = bbox
        self.months = months
        self.api_key = api_key
        self.result = None
        self.exception = None
        self.client = None

    def run(self):
        """
        Executed in background thread.
        """
        try:
            QgsMessageLog.logMessage(
                f"Lancement analyse Gundua {self.analysis_type} sur BBOX={self.bbox} ({self.months} mois)...",
                "GeoCongoAI",
                Qgis.Info
            )
            
            # Initialize client
            self.client = GunduaEngineClient()
            if self.api_key:
                self.client.api_key = self.api_key
                
            self.result = self.client.analyze(
                self.analysis_type,
                bbox=self.bbox,
                months=self.months
            )
            
            # Attach base_url for convenience in UI layer loading
            if self.result and isinstance(self.result, dict):
                self.result["_base_url"] = self.client.base_url
                
            return True
        except Exception as e:
            self.exception = str(e)
            QgsMessageLog.logMessage(
                f"Erreur lors de l'analyse Gundua: {self.exception}",
                "GeoCongoAI",
                Qgis.Critical
            )
            return False

    def finished(self, result: bool):
        """
        Executed on main thread upon completion.
        """
        if result and self.result:
            self.analysisFinished.emit(self.result)
        else:
            err_msg = self.exception or "Erreur inconnue lors de l'exécution de la tâche Gundua Engine."
            self.analysisFailed.emit(err_msg)
