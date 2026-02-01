"""Tests for RasterOverlay visualization logic."""

import os
import sys
import unittest
from unittest.mock import patch

import numpy as np

# Ensure src path is set
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))


class TestRasterOverlay(unittest.TestCase):
    def setUp(self):
        # Minimal rectangle field selection
        self.rect_field = {
            'type': 'rectangle',
            'bbox': [36.8, -1.30, 36.85, -1.25],
            'center': {'lat': -1.275, 'lon': 36.825}
        }
        # Minimal circle field selection
        self.circle_field = {
            'type': 'circle',
            'bbox': [36.8, -1.30, 36.85, -1.25],
            'center': {'lat': -1.275, 'lon': 36.825},
            'radius_degrees': 0.01
        }

    @patch('contextily.add_basemap')
    def test_summary_view_draws_patch(self, mock_base):
        from sat_mon.gui.raster_overlay import RasterOverlay
        ro = RasterOverlay(self.rect_field)
        fig, ax = ro.display_ndvi({'ndvi': [0.3, 0.5, 0.4]}, title="Test")
        # At least one patch (boundary + filled area)
        self.assertGreaterEqual(len(ax.patches), 1)
        self.assertTrue(mock_base.called)

    @patch('contextily.add_basemap')
    def test_apply_field_mask_circle(self, mock_base):
        from sat_mon.gui.raster_overlay import RasterOverlay
        ro = RasterOverlay(self.circle_field)
        values = np.ones((10, 10))
        bounds = (36.8, -1.30, 36.85, -1.25)
        masked = ro._apply_field_mask(values, bounds)
        # Some pixels must be masked but not all
        self.assertGreater(masked.mask.sum(), 0)
        self.assertLess(masked.mask.sum(), values.size)

    @patch('contextily.add_basemap')
    def test_display_single_raster(self, mock_base):
        from sat_mon.gui.raster_overlay import RasterOverlay
        ro = RasterOverlay(self.rect_field)
        values = np.linspace(0, 1, 100).reshape(10, 10)
        fig, ax = ro.display_ndvi({'values': values, 'bounds': (36.8, -1.30, 36.85, -1.25)})
        self.assertIsNotNone(fig)
        self.assertIsNotNone(ax)


if __name__ == '__main__':
    unittest.main()
