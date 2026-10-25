"""
CRS and Spatial Extent utilities for GeoCongo AI QGIS Plugin.
Provides robust reprojection of extents to WGS84 (EPSG:4326) for Gundua Engine API calls.
"""

from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransform,
    QgsProject,
    QgsRectangle,
    QgsMapLayer
)


def transform_extent_to_wgs84(extent: QgsRectangle, source_crs: QgsCoordinateReferenceSystem) -> list:
    """
    Transforms a QgsRectangle from source_crs to WGS84 (EPSG:4326).
    Returns [xmin, ymin, xmax, ymax] as floats rounded to 6 decimals.
    """
    target_crs = QgsCoordinateReferenceSystem("EPSG:4326")

    if not source_crs or not source_crs.isValid():
        source_crs = target_crs

    if source_crs != target_crs:
        transform = QgsCoordinateTransform(source_crs, target_crs, QgsProject.instance())
        try:
            wgs84_extent = transform.transformBoundingBox(extent)
        except Exception:
            # Fallback if transformation fails
            wgs84_extent = extent
    else:
        wgs84_extent = extent

    return [
        round(wgs84_extent.xMinimum(), 6),
        round(wgs84_extent.yMinimum(), 6),
        round(wgs84_extent.xMaximum(), 6),
        round(wgs84_extent.yMaximum(), 6)
    ]


def validate_wgs84_bbox(bbox: list) -> tuple[bool, str]:
    """
    Validates whether a BBOX [xmin, ymin, xmax, ymax] is valid for WGS84 (EPSG:4326).
    Returns (is_valid, error_message).
    """
    if not bbox or len(bbox) != 4:
        return False, "Le BBOX doit contenir 4 coordonnées [xmin, ymin, xmax, ymax]."

    xmin, ymin, xmax, ymax = bbox

    if xmin >= xmax:
        return False, f"XMin ({xmin}) doit être inférieur à XMax ({xmax})."

    if ymin >= ymax:
        return False, f"YMin ({ymin}) doit être inférieur à YMax ({ymax})."

    if not (-180.0 <= xmin <= 180.0 and -180.0 <= xmax <= 180.0):
        return False, f"Les longitudes ({xmin}, {xmax}) dépassent [-180, 180]. Le CRS source est probablement métrique (UTM/Projeté)."

    if not (-90.0 <= ymin <= 90.0 and -90.0 <= ymax <= 90.0):
        return False, f"Les latitudes ({ymin}, {ymax}) dépassent [-90, 90]. Le CRS source est probablement métrique (UTM/Projeté)."

    return True, "BBOX valide."


def get_canvas_extent_wgs84(iface, custom_crs: QgsCoordinateReferenceSystem = None) -> list:
    """
    Retrieves the current QGIS map canvas extent reprojected to WGS84 (EPSG:4326).
    """
    canvas = iface.mapCanvas()
    extent = canvas.extent()
    source_crs = custom_crs if (custom_crs and custom_crs.isValid()) else canvas.mapSettings().destinationCrs()
    return transform_extent_to_wgs84(extent, source_crs)


def get_layer_extent_wgs84(layer: QgsMapLayer, custom_crs: QgsCoordinateReferenceSystem = None) -> list:
    """
    Retrieves a layer's spatial extent reprojected to WGS84 (EPSG:4326).
    """
    if not layer or not layer.isValid():
        raise ValueError("La couche spécifiée est invalide.")

    extent = layer.extent()
    source_crs = custom_crs if (custom_crs and custom_crs.isValid()) else layer.crs()
    return transform_extent_to_wgs84(extent, source_crs)

