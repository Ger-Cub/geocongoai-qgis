"""
Unit tests for GeoCongo AI QGIS Plugin.
Tests module imports, dialog instantiations, and metadata.
"""

import unittest
import os
import sys

plugin_dir = os.path.dirname(__file__)
if plugin_dir not in sys.path:
    sys.path.insert(0, plugin_dir)

from utils.drillhole_adapter import (
    compute_downhole_position,
    _pick_survey_station,
    build_resource_sample_points,
    infer_grade_field_name,
    match_field_name,
    safe_float,
    validate_resource_estimation_inputs,
)
from utils.chimbua_visualization import NOISE_COLOR, cluster_color


class TestGeoCongoAIPlugin(unittest.TestCase):

    class _FakeField:
        def __init__(self, name):
            self._name = name

        def name(self):
            return self._name

    class _FakeLayer:
        def __init__(self, names):
            self._fields = [TestGeoCongoAIPlugin._FakeField(name) for name in names]

        def fields(self):
            return self._fields

    class _FakePoint:
        def __init__(self, x_value, y_value):
            self._x = x_value
            self._y = y_value

        def x(self):
            return self._x

        def y(self):
            return self._y

    def test_metadata_version(self):
        meta_path = os.path.join(plugin_dir, "metadata.txt")
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("version=0.4.3", content)
        self.assertIn("Mtumishi", content)
        self.assertIn("Pekua", content)

    def test_safe_float_handles_common_formats(self):
        self.assertEqual(safe_float("1,25"), 1.25)
        self.assertEqual(safe_float(" 2.5 "), 2.5)
        self.assertIsNone(safe_float("N/A"))

    def test_match_field_name_prefers_exact_match(self):
        fields = ["Hole_ID", "depth_from", "cu_pct"]
        self.assertEqual(match_field_name(fields, exact_names=("hole_id",)), "Hole_ID")
        self.assertEqual(match_field_name(fields, contains_tokens=("depth",)), "depth_from")

    def test_infer_grade_field_name_prefers_grade_like_columns(self):
        layer = self._FakeLayer(["hole_id", "depth_from", "depth_to", "cu_pct"])
        self.assertEqual(infer_grade_field_name(layer), "cu_pct")

    def test_cluster_color_uses_noise_color_for_negative_clusters(self):
        self.assertEqual(cluster_color(-1), NOISE_COLOR)
        self.assertEqual(cluster_color("abc"), NOISE_COLOR)
        self.assertNotEqual(cluster_color(0), NOISE_COLOR)

    def test_pick_survey_station_uses_last_station_not_exceeding_depth(self):
        lookup = {
            "bh01": [
                {"depth": 0.0, "azimuth": 10.0, "dip": -90.0, "feature_id": 1},
                {"depth": 50.0, "azimuth": 25.0, "dip": -70.0, "feature_id": 2},
                {"depth": 120.0, "azimuth": 40.0, "dip": -60.0, "feature_id": 3},
            ]
        }
        station = _pick_survey_station(lookup, "BH01", 80.0)
        self.assertIsNotNone(station)
        self.assertEqual(station["azimuth"], 25.0)
        self.assertEqual(station["dip"], -70.0)

    def test_compute_downhole_position_accumulates_segments_from_survey_stations(self):
        collar = {
            "point": self._FakePoint(100.0, 200.0),
            "z": 300.0,
        }
        stations = [
            {"depth": 0.0, "azimuth": 0.0, "dip": -90.0, "feature_id": 1},
            {"depth": 50.0, "azimuth": 90.0, "dip": -45.0, "feature_id": 2},
        ]
        position = compute_downhole_position(collar, stations, 100.0)
        self.assertIsNotNone(position)
        self.assertAlmostEqual(position["x"], 135.3553390593, places=5)
        self.assertAlmostEqual(position["y"], 200.0, places=5)
        self.assertAlmostEqual(position["z"], 214.6446609407, places=5)

    def test_validate_resource_estimation_inputs_accepts_minimal_valid_dataset(self):
        prepared = {
            "grade_field": "cu_pct",
            "schema": {
                "grade_field": "cu_pct",
                "assay_hole_id_field": "hole_id",
                "from_field": "from_m",
                "to_field": "to_m",
                "x_field": "x",
                "y_field": "y",
            },
            "stats": {"above_cutoff_count": 2},
            "records": [
                {
                    "hole_id": "BH01",
                    "grade_value": 1.2,
                    "point": self._FakePoint(10, 20),
                    "z_value": -5,
                    "from_m": 0,
                    "to_m": 10,
                },
                {
                    "hole_id": "BH02",
                    "grade_value": 0.8,
                    "point": self._FakePoint(40, 50),
                    "z_value": -8,
                    "from_m": 0,
                    "to_m": 12,
                },
                {
                    "hole_id": "BH02",
                    "grade_value": 1.0,
                    "point": self._FakePoint(42, 51),
                    "z_value": -15,
                    "from_m": 12,
                    "to_m": 20,
                },
                {
                    "hole_id": "BH01",
                    "grade_value": 1.4,
                    "point": self._FakePoint(12, 22),
                    "z_value": -14,
                    "from_m": 10,
                    "to_m": 18,
                },
            ],
            "collar_layer": object(),
            "survey_layer": None,
        }

        sample_points = build_resource_sample_points(prepared)
        self.assertEqual(len(sample_points), 4)

        validation = validate_resource_estimation_inputs(
            prepared,
            cutoff_grade=0.5,
            density=2.7,
            block_size=(25.0, 25.0, 10.0),
            search_range=100.0,
            min_samples=2,
            method="idw",
        )
        self.assertTrue(validation["ok"])
        self.assertEqual(validation["unique_hole_count"], 2)
        self.assertGreaterEqual(len(validation["warnings"]), 1)


if __name__ == "__main__":
    unittest.main()
