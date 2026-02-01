"""
Field boundary selection tools.

Provides rectangle and circle selectors for defining field boundaries
on the interactive map.
"""

import numpy as np
from matplotlib.widgets import RectangleSelector, EllipseSelector, RadioButtons
from matplotlib.patches import Rectangle, Circle
from pyproj import Transformer

# Approximate meters per degree at the equator
METERS_PER_DEGREE = 111_000


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
            useblit=False,
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
            useblit=False,
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
    
    def set_selection(self, bbox):
        """
        Programmatically set the selection (e.g. from initial CLI args).
        
        Args:
            bbox: [lon_min, lat_min, lon_max, lat_max]
        """
        # Ensure bbox is float
        lon_min, lat_min, lon_max, lat_max = map(float, bbox)
        
        # Update internal state
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
            'bbox': [lon_min, lat_min, lon_max, lat_max]
        }
        
        # Draw on map
        # Convert to Web Mercator
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        # Transform min/max points
        # Note: transform returns x, y
        x_min, y_min = transformer.transform(lon_min, lat_min)
        x_max, y_max = transformer.transform(lon_max, lat_max)
        
        width = x_max - x_min
        height = y_max - y_min
        
        # Remove old patch if any
        self._clear_patch()
        
        # Add new rectangle patch
        self._current_patch = Rectangle(
            (x_min, y_min), width, height,
            edgecolor='red', facecolor='none', linewidth=2, linestyle='--'
        )
        self.ax.add_patch(self._current_patch)
        self.ax.figure.canvas.draw_idle()

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
        radius = (radius_x + radius_y) / 2  # Average for circle (EPSG:3857 units ~ meters)

        # Ignore accidental clicks with effectively zero radius (< 50 m)
        if radius is None or radius <= 50:
            return
        
        # Convert center to WGS84
        center_lon, center_lat = self._transformer.transform(center_x, center_y)
        
        # Convert radius to degrees (approximate) for compatibility fields
        # At equator, 1 degree ≈ 111km. Adjust for latitude.
        cos_lat = np.cos(np.radians(center_lat))
        meters_per_degree = 111000 * cos_lat
        radius_degrees = radius / max(1e-6, meters_per_degree)
        
        # Calculate true ground radius in meters
        # Web Mercator distorts scale by 1/cos(lat). We must scale down to get true meters.
        radius_m = float(radius * cos_lat)
        radius_km = radius_m / 1000.0
        
        # Store selection
        self.selection = {
            'type': 'circle',
            'center': {
                'lat': center_lat,
                'lon': center_lon
            },
            'radius_degrees': radius_degrees,
            'radius_km': radius_km,
            'radius_m': radius_m,
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
        print(f"  Radius: {radius_km:.2f} km ({radius_degrees:.4f}°) ~ {radius_m:.0f} m")

    def deactivate(self):
        """Deactivate selectors to avoid callbacks after figure closes."""
        try:
            if self._rect_selector:
                self._rect_selector.set_active(False)
            if self._ellipse_selector:
                self._ellipse_selector.set_active(False)
        except Exception:
            pass
    
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

    def validate_selection(self) -> tuple[bool, str | None]:
        """
        Validate the current selection.
        
        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if self.selection is None:
            return False, "No field selected. Please draw a rectangle or circle."
        
        center = self.selection['center']
        
        # Check valid coordinates
        if not (-90 <= center['lat'] <= 90):
            return False, "Invalid latitude. Must be between -90 and 90."
        if not (-180 <= center['lon'] <= 180):
            return False, "Invalid longitude. Must be between -180 and 180."

        # Calculate span in meters
        if self.selection['type'] == 'circle':
            radius_km = self.selection.get('radius_km', 0.0)
            span_m = radius_km * 1000.0 * 2  # diameter
        else:
            bbox = self.selection['bbox']
            lat_span = abs(bbox[3] - bbox[1])
            lon_span = abs(bbox[2] - bbox[0])
            # Convert degrees to meters at current latitude
            lat_m = lat_span * METERS_PER_DEGREE
            lon_m = lon_span * METERS_PER_DEGREE * abs(np.cos(np.radians(center['lat'])))
            span_m = max(lat_m, lon_m)

        # Check minimum size (~100m)
        if span_m < 100:
            return False, f"Field too small ({span_m:.0f}m). Please select at least 100m."
        
        # Check maximum size (~100km)
        if span_m > 100_000:
            return False, f"Field too large ({span_m/1000:.0f}km). Please keep under 100km."
            
        return True, None


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
