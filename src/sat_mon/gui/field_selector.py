"""
Field boundary selection tools.

Provides rectangle and circle selectors for defining field boundaries
on the interactive map.
"""

import numpy as np
from matplotlib.widgets import RectangleSelector, EllipseSelector, RadioButtons
from matplotlib.patches import Rectangle, Circle
from pyproj import Transformer


class FieldSelector:
    """
    Handles field boundary selection via drawing tools.
    
    Supports rectangle and circle shapes. Stores the selected
    geometry in both Web Mercator (display) and WGS84 (analysis).
    
    Attributes:
        ax: Matplotlib axes to draw on
        shape_type: Current shape type ('rectangle' or 'circle')
        selection: Current selection in WGS84 coordinates
    """
    
    def __init__(self, ax):
        """
        Initialize the field selector.
        
        Args:
            ax: Matplotlib axes object to attach selectors to
        """
        self.ax = ax
        self.shape_type = 'rectangle'  # Default
        self.selection = None  # Will hold {'type': ..., 'coordinates': ...}
        
        # Coordinate transformer (Web Mercator -> WGS84)
        self._transformer = Transformer.from_crs(
            "EPSG:3857", "EPSG:4326", always_xy=True
        )
        
        # Selector objects (created in setup_selectors)
        self._rect_selector = None
        self._ellipse_selector = None
        self._active_selector = None
        
        # Visual feedback patch
        self._current_patch = None
        
    def setup_selectors(self):
        """
        Create and configure the drawing selectors.
        
        Call this after the axes is fully configured.
        """
        # Rectangle selector
        self._rect_selector = RectangleSelector(
            self.ax,
            self._on_rectangle_select,
            useblit=True,
            button=[1],  # Left mouse button only
            minspanx=5,
            minspany=5,
            spancoords='pixels',
            interactive=True,
            props=dict(facecolor='cyan', edgecolor='white', alpha=0.3, linewidth=2)
        )
        
        # Ellipse selector (for circles, we'll constrain to square bounds)
        self._ellipse_selector = EllipseSelector(
            self.ax,
            self._on_ellipse_select,
            useblit=True,
            button=[1],
            minspanx=5,
            minspany=5,
            spancoords='pixels',
            interactive=True,
            props=dict(facecolor='cyan', edgecolor='white', alpha=0.3, linewidth=2)
        )
        
        # Start with rectangle active
        self._set_active_selector('rectangle')
    
    def _set_active_selector(self, shape_type):
        """
        Activate the specified selector, deactivate others.
        
        Args:
            shape_type: 'rectangle' or 'circle'
        """
        self.shape_type = shape_type
        
        # Deactivate and clear both selectors to ensure only one shape is visible
        if self._rect_selector:
            self._rect_selector.set_active(False)
            self._rect_selector.clear()
            
        if self._ellipse_selector:
            self._ellipse_selector.set_active(False)
            self._ellipse_selector.clear()
        
        # Activate the requested one
        if shape_type == 'rectangle':
            self._rect_selector.set_active(True)
            self._active_selector = self._rect_selector
        else:  # circle
            self._ellipse_selector.set_active(True)
            self._active_selector = self._ellipse_selector
        
        # Reset selection data
        self.selection = None
        
        # Clear previous selection visual
        self._clear_patch()
    
    def _on_rectangle_select(self, eclick, erelease):
        """
        Callback when rectangle selection is complete.
        
        Args:
            eclick: Mouse press event
            erelease: Mouse release event
        """
        # Get coordinates in Web Mercator
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        
        # Ensure proper ordering (min, max)
        xmin, xmax = min(x1, x2), max(x1, x2)
        ymin, ymax = min(y1, y2), max(y1, y2)
        
        # Convert to WGS84
        lon_min, lat_min = self._transformer.transform(xmin, ymin)
        lon_max, lat_max = self._transformer.transform(xmax, ymax)
        
        # Store selection
        self.selection = {
            'type': 'rectangle',
            'bounds': {
                'lat_min': lat_min,
                'lat_max': lat_max,
                'lon_min': lon_min,
                'lon_max': lon_max
            },
            'center': {
                'lat': (lat_min + lat_max) / 2,
                'lon': (lon_min + lon_max) / 2
            },
            # For compatibility with existing code
            'bbox': [lon_min, lat_min, lon_max, lat_max]
        }
        
        print(f"Rectangle selected:")
        print(f"  Bounds: {lat_min:.6f}°N to {lat_max:.6f}°N, {lon_min:.6f}°E to {lon_max:.6f}°E")
        print(f"  Center: {self.selection['center']['lat']:.6f}°N, {self.selection['center']['lon']:.6f}°E")
    
    def _on_ellipse_select(self, eclick, erelease):
        """
        Callback when ellipse/circle selection is complete.
        
        We treat this as a circle using the average of width/height as radius.
        
        Args:
            eclick: Mouse press event
            erelease: Mouse release event
        """
        # Get coordinates in Web Mercator
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        
        # Calculate center and radius in Web Mercator
        center_x = (x1 + x2) / 2
        center_y = (y1 + y2) / 2
        radius_x = abs(x2 - x1) / 2
        radius_y = abs(y2 - y1) / 2
        radius = (radius_x + radius_y) / 2  # Average for circle
        
        # Convert center to WGS84
        center_lon, center_lat = self._transformer.transform(center_x, center_y)
        
        # Convert radius to approximate degrees
        # At equator, 1 degree ≈ 111km. Adjust for latitude.
        meters_per_degree = 111000 * np.cos(np.radians(center_lat))
        radius_degrees = radius / meters_per_degree
        
        # Also calculate radius in km for display
        radius_km = radius / 1000
        
        # Store selection
        self.selection = {
            'type': 'circle',
            'center': {
                'lat': center_lat,
                'lon': center_lon
            },
            'radius_degrees': radius_degrees,
            'radius_km': radius_km,
            # For compatibility - create bounding box
            'bbox': [
                center_lon - radius_degrees,
                center_lat - radius_degrees,
                center_lon + radius_degrees,
                center_lat + radius_degrees
            ]
        }
        
        print(f"Circle selected:")
        print(f"  Center: {center_lat:.6f}°N, {center_lon:.6f}°E")
        print(f"  Radius: {radius_km:.2f} km ({radius_degrees:.4f}°)")
    
    def _clear_patch(self):
        """Remove the current selection visualization."""
        if self._current_patch is not None:
            self._current_patch.remove()
            self._current_patch = None
            self.ax.figure.canvas.draw_idle()
    
    def get_selection(self):
        """
        Get the current selection.
        
        Returns:
            dict: Selection data with type, coordinates, bbox
            None: If no selection made
        """
        return self.selection
    
    def clear_selection(self):
        """Clear the current selection."""
        self.selection = None
        self._clear_patch()
        
        # Reset selectors
        if self._rect_selector:
            self._rect_selector.clear()
        if self._ellipse_selector:
            self._ellipse_selector.clear()


# Quick test
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots(figsize=(10, 8))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_title("Test: Draw a rectangle or circle")
    
    selector = FieldSelector(ax)
    selector.setup_selectors()
    
    plt.show()
    
    print("Final selection:", selector.get_selection())
