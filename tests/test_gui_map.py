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

    def test_validation_too_small_rectangle(self):
        """Test validation for a rectangle that is too small."""
        from sat_mon.gui.field_selector import FieldSelector
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots()
        selector = FieldSelector(ax)
        
        # Manually create a tiny selection (approx 1m x 1m)
        selector.selection = {
            'type': 'rectangle',
            'bbox': [36.825, -1.275, 36.82500001, -1.27500001],
            'center': {'lat': -1.275, 'lon': 36.825}
        }
        
        is_valid, msg = selector.validate_selection()
        # Should be invalid because < 100m
        self.assertFalse(is_valid)
        self.assertIn("Field too small", str(msg))
        
        plt.close(fig)

    def test_validation_too_large_circle(self):
        """Test validation for a circle that is too large."""
        from sat_mon.gui.field_selector import FieldSelector
        import matplotlib.pyplot as plt
        
        fig, ax = plt.subplots()
        selector = FieldSelector(ax)
        
        # Manually create a huge selection (radius 200km -> diameter 400km)
        selector.selection = {
            'type': 'circle',
            'center': {'lat': -1.275, 'lon': 36.825},
            'radius_km': 200.0,
            'bbox': [35.0, -3.0, 38.0, 0.0] # Dummy bbox
        }
        
        is_valid, msg = selector.validate_selection()
        # Should be invalid because > 100km
        self.assertFalse(is_valid)
        self.assertIn("Field too large", str(msg))
        
        plt.close(fig)

    @patch('matplotlib.pyplot.show')
    def test_analyze_without_selection_shows_error(self, mock_show):
        """Test that clicking analyze without selection shows an error."""
        from sat_mon.gui.map_window import MapWindow
        import matplotlib.pyplot as plt
        
        window = MapWindow()
        window.create_window()
        window.setup_controls()
        
        # Mock _show_error to verify it's called
        window._show_error = MagicMock()
        
        # Click analyze without selecting anything
        # The event argument can be None for testing
        window._on_analyze_click(None)
        
        window._show_error.assert_called_with("No field selected! Draw a rectangle or circle first.")
        # Analysis should NOT be requested
        self.assertFalse(hasattr(window, '_analysis_requested'))
        
        plt.close(window.fig)

if __name__ == "__main__":
    unittest.main()
