"""Tests for GUI map window."""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))


class TestMapWindow(unittest.TestCase):
    """Test MapWindow class."""
    
    def test_init_default_values(self):
        """Test default initialization values."""
        from sat_mon.gui.map_window import MapWindow
        
        window = MapWindow()
        self.assertEqual(window.center_lat, -1.0)
        self.assertEqual(window.center_lon, 37.0)
        self.assertEqual(window.zoom_level, 10)
    
    def test_init_custom_values(self):
        """Test custom initialization values."""
        from sat_mon.gui.map_window import MapWindow
        
        window = MapWindow(center_lat=-2.5, center_lon=38.0, zoom_level=12)
        self.assertEqual(window.center_lat, -2.5)
        self.assertEqual(window.center_lon, 38.0)
        self.assertEqual(window.zoom_level, 12)
    
    def test_calculate_extent(self):
        """Test extent calculation returns 4 values."""
        from sat_mon.gui.map_window import MapWindow
        
        window = MapWindow()
        extent = window._calculate_extent()
        
        self.assertEqual(len(extent), 4)
        self.assertLess(extent[0], extent[1])  # xmin < xmax
        self.assertLess(extent[2], extent[3])  # ymin < ymax

    def test_field_selector_init(self):
        """Test FieldSelector initialization."""
        from sat_mon.gui.field_selector import FieldSelector
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots()
        selector = FieldSelector(ax)
        
        self.assertEqual(selector.shape_type, 'rectangle')
        self.assertIsNone(selector.selection)
        
        plt.close(fig)

    def test_field_selector_shape_switch(self):
        """Test switching between shapes."""
        from sat_mon.gui.field_selector import FieldSelector
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots()
        ax.set_xlim(0, 100)
        ax.set_ylim(0, 100)
        
        selector = FieldSelector(ax)
        selector.setup_selectors()
        
        # Default is rectangle
        self.assertEqual(selector.shape_type, 'rectangle')
        
        # Switch to circle
        selector._set_active_selector('circle')
        self.assertEqual(selector.shape_type, 'circle')
        
        plt.close(fig)


if __name__ == "__main__":
    unittest.main()
