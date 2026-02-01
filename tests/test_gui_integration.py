"""Integration test for GUI orchestrator (Phase D)."""

import os
import sys
from unittest.mock import patch, MagicMock
import unittest

# Ensure src on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))


class TestGUIIntegration(unittest.TestCase):
    def test_orchestrator_flow(self):
        # Mock selection from MapWindow
        selection = {
            'type': 'rectangle',
            'bbox': [36.8, -1.30, 36.85, -1.25],
            'center': {'lat': -1.275, 'lon': 36.825}
        }

        # Dummy timeseries returns
        ndvi_resp = {'dates': ['2025-01-01'], 'ndvi': [0.5]}
        rain_resp = {'dates': ['2025-01-01'], 'rainfall': [2.0]}
        lst_resp = {'dates': ['2025-01-01'], 'lst': [300.0]}

        with patch('sat_mon.gui.map_window.MapWindow') as MW, \
             patch('sat_mon.gui.raster_overlay.RasterOverlay.show') as mock_show, \
             patch('sat_mon.gui.orchestrator.fetch_ndvi_timeseries', return_value=ndvi_resp) as mock_ndvi, \
             patch('sat_mon.gui.orchestrator.fetch_rainfall_timeseries', return_value=rain_resp) as mock_rain, \
             patch('sat_mon.gui.orchestrator.fetch_lst_timeseries', return_value=lst_resp) as mock_lst:

            # MapWindow behavior
            mw_instance = MW.return_value
            mw_instance.create_window.return_value = (MagicMock(), MagicMock())
            mw_instance.get_result.return_value = selection

            from sat_mon.gui.orchestrator import GUIOrchestrator
            orch = GUIOrchestrator()
            result = orch.run()

            # Assertions
            self.assertIsNotNone(result)
            self.assertEqual(result['ndvi'], [0.5])
            self.assertEqual(result['rainfall'], [2.0])
            self.assertEqual(result['lst'], [300.0])

            # Ensure fetchers called with lat/lon and radius_m
            args, kwargs = mock_ndvi.call_args
            self.assertIn('radius_m', kwargs)
            self.assertAlmostEqual(kwargs['radius_m'] / 1000.0, 1.0, delta=5.0)  # ~km-scale radius

            # Ensure overlay was shown (but mocked)
            self.assertTrue(mock_show.called)


if __name__ == '__main__':
    unittest.main()
