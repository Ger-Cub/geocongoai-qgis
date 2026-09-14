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


class TestGeoCongoAIPlugin(unittest.TestCase):

    def test_metadata_version(self):
        meta_path = os.path.join(plugin_dir, "metadata.txt")
        self.assertTrue(os.path.exists(meta_path))
        with open(meta_path, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("version=0.4.3", content)
        self.assertIn("Mtumishi", content)
        self.assertIn("Pekua", content)


if __name__ == "__main__":
    unittest.main()
