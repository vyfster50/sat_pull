# V9 Roadmap: Interactive Map-Based Field Selection GUI

## Overview

Replace CLI coordinate input with an interactive GUI where users:
1. View an ESRI satellite basemap
2. Draw a rectangle or circle to define their field of interest
3. Run analysis on the selected area
4. View results with the field boundary overlaid on raster data

**Target User Experience:**
```
User runs: python app.py
→ Map window opens with ESRI satellite imagery
→ User selects drawing tool (rectangle/circle)
→ User draws field boundary on map
→ User clicks "Analyze" button
→ Analysis runs, results displayed with field overlay
```

---

## Architecture Decision

**Chosen Stack: Matplotlib + contextily + widgets**

Why this over alternatives:
- **Folium**: Browser-based, harder to integrate with existing Matplotlib plots
- **ipyleaflet**: Requires Jupyter, not standalone
- **Matplotlib**: Already in codebase, works standalone, has built-in selectors

---

## Phase A: Map Window Foundation (✅ COMPLETE)

**Goal:** Open a window displaying an ESRI satellite basemap at a default location.

### A.1: Create the GUI Module Structure (✅ Done)

Create new file: `src/sat_mon/gui/__init__.py`

```python
"""GUI module for interactive map-based field selection."""

from .map_window import MapWindow
from .field_selector import FieldSelector

__all__ = ['MapWindow', 'FieldSelector']
```

### A.2: Basic Map Window Class (✅ Done)

Create new file: `src/sat_mon/gui/map_window.py`

```python
"""
Interactive map window for field selection.

This module provides a Matplotlib-based map window with ESRI satellite
basemap for users to visually select their field of interest.
"""

import matplotlib.pyplot as plt
from matplotlib.widgets import Button, RadioButtons
import contextily as ctx
import numpy as np


class MapWindow:
    """
    Main window class for displaying interactive ESRI basemap.
    
    Attributes:
        fig: Matplotlib figure object
        ax: Matplotlib axes object
        center_lat: Initial center latitude (default: Kenya)
        center_lon: Initial center longitude
        zoom_level: Initial zoom level for basemap
    """
    
    # ESRI Satellite tile URL
    ESRI_SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    
    def __init__(self, center_lat=-1.0, center_lon=37.0, zoom_level=10):
        """
        Initialize the map window.
        
        Args:
            center_lat: Center latitude in decimal degrees
            center_lon: Center longitude in decimal degrees  
            zoom_level: Zoom level (1-18, higher = more detail)
        """
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.zoom_level = zoom_level
        
        # Will be set in create_window()
        self.fig = None
        self.ax = None
        
    def create_window(self):
        """
        Create the Matplotlib figure and axes.
        
        Returns:
            tuple: (fig, ax) Matplotlib figure and axes objects
        """
        # Create figure with specific size
        self.fig, self.ax = plt.subplots(figsize=(12, 10))
        
        # Set initial extent (in Web Mercator, EPSG:3857)
        # We need to convert lat/lon to Web Mercator coordinates
        extent = self._calculate_extent()
        self.ax.set_xlim(extent[0], extent[1])
        self.ax.set_ylim(extent[2], extent[3])
        
        # Add ESRI satellite basemap
        self._add_basemap()
        
        # Configure axes
        self.ax.set_aspect('equal')
        self.ax.set_title('Draw your field boundary (Rectangle or Circle)', fontsize=14)
        
        return self.fig, self.ax
    
    def _calculate_extent(self):
        """
        Calculate map extent in Web Mercator coordinates.
        
        The extent determines what area of the map is visible.
        Larger delta = more zoomed out.
        
        Returns:
            tuple: (xmin, xmax, ymin, ymax) in EPSG:3857
        """
        from pyproj import Transformer
        
        # Transform center point from WGS84 to Web Mercator
        transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        center_x, center_y = transformer.transform(self.center_lon, self.center_lat)
        
        # Calculate extent based on zoom level
        # At zoom 10, show roughly 50km x 50km area
        # Each zoom level halves/doubles the area
        base_size = 50000  # 50km at zoom 10
        scale_factor = 2 ** (10 - self.zoom_level)
        delta = base_size * scale_factor
        
        return (
            center_x - delta,  # xmin
            center_x + delta,  # xmax
            center_y - delta,  # ymin
            center_y + delta   # ymax
        )
    
    def _add_basemap(self):
        """
        Add ESRI satellite imagery as basemap.
        
        Uses contextily to fetch and render map tiles.
        """
        try:
            ctx.add_basemap(
                self.ax,
                source=self.ESRI_SATELLITE,
                crs="EPSG:3857",
                attribution=""  # Clean display
            )
        except Exception as e:
            print(f"Warning: Could not load basemap: {e}")
            # Add a placeholder background
            self.ax.set_facecolor('#1a1a2e')
    
    def show(self):
        """Display the map window."""
        plt.tight_layout()
        plt.show()


# Quick test
if __name__ == "__main__":
    window = MapWindow(center_lat=-1.286389, center_lon=36.817223)  # Nairobi
    window.create_window()
    window.show()
```

### A.3: Test the Basic Window (✅ Done)

Create test file: `tests/test_gui_map.py`

```python
"""Tests for GUI map window."""

import unittest
from unittest.mock import patch, MagicMock


class TestMapWindow(unittest.TestCase):
    """Test MapWindow class."""
    
    def test_init_default_values(self):
        """Test default initialization values."""
        from src.sat_mon.gui.map_window import MapWindow
        
        window = MapWindow()
        self.assertEqual(window.center_lat, -1.0)
        self.assertEqual(window.center_lon, 37.0)
        self.assertEqual(window.zoom_level, 10)
    
    def test_init_custom_values(self):
        """Test custom initialization values."""
        from src.sat_mon.gui.map_window import MapWindow
        
        window = MapWindow(center_lat=-2.5, center_lon=38.0, zoom_level=12)
        self.assertEqual(window.center_lat, -2.5)
        self.assertEqual(window.center_lon, 38.0)
        self.assertEqual(window.zoom_level, 12)
    
    def test_calculate_extent(self):
        """Test extent calculation returns 4 values."""
        from src.sat_mon.gui.map_window import MapWindow
        
        window = MapWindow()
        extent = window._calculate_extent()
        
        self.assertEqual(len(extent), 4)
        self.assertLess(extent[0], extent[1])  # xmin < xmax
        self.assertLess(extent[2], extent[3])  # ymin < ymax


if __name__ == "__main__":
    unittest.main()
```

### A.4: Dependencies to Add (✅ Done)

Add to `requirements.txt`:
```
pyproj>=3.0.0
```

**Checkpoint A:** Run `python -m src.sat_mon.gui.map_window` - should display ESRI satellite map of Kenya.

---

## Phase B: Drawing Tools (Rectangle & Circle) (✅ COMPLETE)

**Goal:** Add interactive drawing tools for field boundary selection.

### B.1: Field Selector Class (✅ Done)

Create new file: `src/sat_mon/gui/field_selector.py`

```python
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
        
        if shape_type == 'rectangle':
            self._rect_selector.set_active(True)
            self._ellipse_selector.set_active(False)
            self._active_selector = self._rect_selector
        else:  # circle
            self._rect_selector.set_active(False)
            self._ellipse_selector.set_active(True)
            self._active_selector = self._ellipse_selector
        
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
```

### B.2: Integrate Selector with Map Window (✅ Done)

Update `src/sat_mon/gui/map_window.py` - add these methods:

```python
# Add to imports at top:
from matplotlib.widgets import RadioButtons, Button

# Add to __init__:
self.field_selector = None
self.tool_radio = None
self.analyze_button = None

# Add new method after create_window():
def setup_controls(self):
    """
    Add control widgets to the map window.
    
    Creates:
    - Radio buttons for tool selection (Rectangle/Circle)
    - Analyze button to run analysis
    - Clear button to reset selection
    """
    from .field_selector import FieldSelector
    
    # Create field selector
    self.field_selector = FieldSelector(self.ax)
    self.field_selector.setup_selectors()
    
    # Tool selection radio buttons (left side)
    tool_ax = self.fig.add_axes([0.02, 0.7, 0.12, 0.15])
    tool_ax.set_title('Draw Tool', fontsize=10)
    self.tool_radio = RadioButtons(
        tool_ax,
        ('Rectangle', 'Circle'),
        active=0
    )
    self.tool_radio.on_clicked(self._on_tool_change)
    
    # Analyze button (bottom)
    analyze_ax = self.fig.add_axes([0.3, 0.02, 0.2, 0.05])
    self.analyze_button = Button(analyze_ax, 'Analyze Field', color='lightgreen')
    self.analyze_button.on_clicked(self._on_analyze_click)
    
    # Clear button
    clear_ax = self.fig.add_axes([0.55, 0.02, 0.15, 0.05])
    self.clear_button = Button(clear_ax, 'Clear', color='lightcoral')
    self.clear_button.on_clicked(self._on_clear_click)

def _on_tool_change(self, label):
    """Handle tool selection change."""
    tool_map = {
        'Rectangle': 'rectangle',
        'Circle': 'circle'
    }
    self.field_selector._set_active_selector(tool_map[label])
    print(f"Switched to {label} tool")

def _on_analyze_click(self, event):
    """Handle analyze button click."""
    selection = self.field_selector.get_selection()
    if selection is None:
        print("No field selected! Draw a rectangle or circle first.")
        return
    
    print("\n" + "="*50)
    print("STARTING ANALYSIS")
    print("="*50)
    print(f"Field type: {selection['type']}")
    print(f"Bounding box: {selection['bbox']}")
    
    # Close the map window and return selection
    self._analysis_requested = True
    self._selection_result = selection
    plt.close(self.fig)

def _on_clear_click(self, event):
    """Handle clear button click."""
    self.field_selector.clear_selection()
    print("Selection cleared")

def get_result(self):
    """
    Get the selection result after window closes.
    
    Returns:
        dict: Selection data if analysis was requested
        None: If window was closed without analysis
    """
    if hasattr(self, '_analysis_requested') and self._analysis_requested:
        return self._selection_result
    return None
```

### B.3: Updated Test (✅ Done)

Update `tests/test_gui_map.py`:

```python
def test_field_selector_init(self):
    """Test FieldSelector initialization."""
    from src.sat_mon.gui.field_selector import FieldSelector
    import matplotlib.pyplot as plt
    
    fig, ax = plt.subplots()
    selector = FieldSelector(ax)
    
    self.assertEqual(selector.shape_type, 'rectangle')
    self.assertIsNone(selector.selection)
    
    plt.close(fig)

def test_field_selector_shape_switch(self):
    """Test switching between shapes."""
    from src.sat_mon.gui.field_selector import FieldSelector
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
```

**Checkpoint B:** Run `python -m src.sat_mon.gui.map_window` - should display map with radio buttons and be able to draw shapes.

---

## Phase C: Raster Display with Field Overlay (✅ COMPLETE)

**Goal:** Display analysis results (NDVI, etc.) with field boundary overlay and transparency masking.

### C.1: Create Raster Overlay Module (✅ Done)

Create new file: `src/sat_mon/gui/raster_overlay.py`

```python
"""
Raster data overlay with field boundary masking.

Displays satellite data (NDVI, LST, etc.) with the selected
field boundary highlighted and areas outside masked with transparency.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, Polygon
from matplotlib.colors import Normalize, LinearSegmentedColormap
from pyproj import Transformer
import contextily as ctx


class RasterOverlay:
    """
    Displays raster data with field boundary overlay.
    
    Features:
    - Shows raster data within field boundary
    - Applies transparency to areas outside the field
    - Draws field boundary outline
    - Adds colorbar and legend
    """
    
    # NDVI colormap: brown -> yellow -> green
    NDVI_COLORS = [
        (0.6, 0.4, 0.2),   # Brown (bare soil)
        (0.8, 0.8, 0.4),   # Yellow (sparse vegetation)
        (0.4, 0.8, 0.4),   # Light green
        (0.0, 0.6, 0.0),   # Dark green (dense vegetation)
    ]
    
    def __init__(self, field_selection):
        """
        Initialize the raster overlay.
        
        Args:
            field_selection: dict from FieldSelector with type, bbox, center
        """
        self.field = field_selection
        self.fig = None
        self.ax = None
        
        # Transformers
        self._to_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
        self._to_wgs84 = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)
    
    def display_ndvi(self, ndvi_data, dates=None, title="NDVI Analysis"):
        """
        Display NDVI raster with field overlay.
        
        Args:
            ndvi_data: dict with 'values' (2D array) and 'bounds' (bbox)
                       OR dict with 'ndvi' list from timeseries
            dates: Optional list of dates for the data
            title: Plot title
        """
        self.fig, self.ax = plt.subplots(figsize=(12, 10))
        
        # Handle different data formats
        if 'values' in ndvi_data:
            # Single raster image
            self._display_single_raster(ndvi_data['values'], ndvi_data.get('bounds'))
        elif 'ndvi' in ndvi_data:
            # Timeseries summary - show mean NDVI as single value
            mean_ndvi = np.mean(ndvi_data['ndvi'])
            self._display_summary_view(mean_ndvi, title)
        
        # Add field boundary overlay
        self._add_field_boundary()
        
        # Add basemap underneath
        self._add_basemap()
        
        self.ax.set_title(title, fontsize=14, fontweight='bold')
        
        return self.fig, self.ax
    
    def _display_single_raster(self, values, bounds):
        """Display a single 2D raster image."""
        if bounds is None:
            bounds = self.field['bbox']
        
        # Convert bounds to Web Mercator for display
        x_min, y_min = self._to_mercator.transform(bounds[0], bounds[1])
        x_max, y_max = self._to_mercator.transform(bounds[2], bounds[3])
        
        # Create NDVI colormap
        ndvi_cmap = LinearSegmentedColormap.from_list('ndvi', self.NDVI_COLORS)
        
        # Create mask for outside field boundary
        masked_values = self._apply_field_mask(values, bounds)
        
        # Display the raster
        im = self.ax.imshow(
            masked_values,
            extent=[x_min, x_max, y_min, y_max],
            cmap=ndvi_cmap,
            vmin=-0.2,
            vmax=0.9,
            alpha=0.8,
            origin='upper'
        )
        
        # Add colorbar
        cbar = plt.colorbar(im, ax=self.ax, shrink=0.8, pad=0.02)
        cbar.set_label('NDVI Value', fontsize=11)
        
        # Set extent to show the field with some padding
        padding = (x_max - x_min) * 0.2
        self.ax.set_xlim(x_min - padding, x_max + padding)
        self.ax.set_ylim(y_min - padding, y_max + padding)
    
    def _display_summary_view(self, mean_value, title):
        """Display a summary view when no raster available."""
        # Get field center in Web Mercator
        center_lon = self.field['center']['lon']
        center_lat = self.field['center']['lat']
        center_x, center_y = self._to_mercator.transform(center_lon, center_lat)
        
        # Create a colored circle/rectangle showing mean value
        ndvi_cmap = LinearSegmentedColormap.from_list('ndvi', self.NDVI_COLORS)
        color = ndvi_cmap((mean_value + 0.2) / 1.1)  # Normalize to 0-1 range
        
        if self.field['type'] == 'circle':
            # Draw filled circle
            radius_deg = self.field.get('radius_degrees', 0.01)
            radius_m = radius_deg * 111000 * np.cos(np.radians(center_lat))
            patch = Circle(
                (center_x, center_y),
                radius=radius_m,
                facecolor=color,
                edgecolor='white',
                linewidth=3,
                alpha=0.7
            )
        else:
            # Draw filled rectangle
            bbox = self.field['bbox']
            x_min, y_min = self._to_mercator.transform(bbox[0], bbox[1])
            x_max, y_max = self._to_mercator.transform(bbox[2], bbox[3])
            width = x_max - x_min
            height = y_max - y_min
            patch = Rectangle(
                (x_min, y_min),
                width,
                height,
                facecolor=color,
                edgecolor='white',
                linewidth=3,
                alpha=0.7
            )
        
        self.ax.add_patch(patch)
        
        # Add text annotation with mean value
        self.ax.annotate(
            f'Mean NDVI: {mean_value:.3f}',
            (center_x, center_y),
            fontsize=14,
            fontweight='bold',
            color='white',
            ha='center',
            va='center',
            bbox=dict(boxstyle='round', facecolor='black', alpha=0.7)
        )
        
        # Set extent
        bbox = self.field['bbox']
        x_min, y_min = self._to_mercator.transform(bbox[0], bbox[1])
        x_max, y_max = self._to_mercator.transform(bbox[2], bbox[3])
        padding = max(x_max - x_min, y_max - y_min) * 0.5
        self.ax.set_xlim(x_min - padding, x_max + padding)
        self.ax.set_ylim(y_min - padding, y_max + padding)
    
    def _apply_field_mask(self, values, bounds):
        """
        Apply mask to make areas outside field transparent.
        
        Args:
            values: 2D numpy array of raster values
            bounds: [lon_min, lat_min, lon_max, lat_max]
        
        Returns:
            numpy.ma.MaskedArray with outside areas masked
        """
        rows, cols = values.shape
        
        if self.field['type'] == 'circle':
            # Create circular mask
            center_lat = self.field['center']['lat']
            center_lon = self.field['center']['lon']
            radius_deg = self.field.get('radius_degrees', 0.01)
            
            # Create coordinate grids
            lon_range = np.linspace(bounds[0], bounds[2], cols)
            lat_range = np.linspace(bounds[3], bounds[1], rows)  # Note: reversed for image coords
            lon_grid, lat_grid = np.meshgrid(lon_range, lat_range)
            
            # Calculate distance from center
            distance = np.sqrt(
                (lon_grid - center_lon)**2 + (lat_grid - center_lat)**2
            )
            
            # Mask outside circle
            mask = distance > radius_deg
            
        else:  # rectangle
            # For rectangle, only mask if raster bounds are larger than field
            # In most cases, raster matches field, so no masking needed
            mask = np.zeros((rows, cols), dtype=bool)
        
        return np.ma.masked_array(values, mask=mask)
    
    def _add_field_boundary(self):
        """Draw the field boundary outline."""
        if self.field['type'] == 'circle':
            center_lon = self.field['center']['lon']
            center_lat = self.field['center']['lat']
            center_x, center_y = self._to_mercator.transform(center_lon, center_lat)
            
            radius_deg = self.field.get('radius_degrees', 0.01)
            radius_m = radius_deg * 111000 * np.cos(np.radians(center_lat))
            
            boundary = Circle(
                (center_x, center_y),
                radius=radius_m,
                fill=False,
                edgecolor='white',
                linewidth=2,
                linestyle='--'
            )
        else:
            bbox = self.field['bbox']
            x_min, y_min = self._to_mercator.transform(bbox[0], bbox[1])
            x_max, y_max = self._to_mercator.transform(bbox[2], bbox[3])
            
            boundary = Rectangle(
                (x_min, y_min),
                x_max - x_min,
                y_max - y_min,
                fill=False,
                edgecolor='white',
                linewidth=2,
                linestyle='--'
            )
        
        self.ax.add_patch(boundary)
    
    def _add_basemap(self):
        """Add ESRI satellite basemap."""
        ESRI_SATELLITE = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
        
        try:
            ctx.add_basemap(
                self.ax,
                source=ESRI_SATELLITE,
                crs="EPSG:3857",
                attribution="",
                zorder=0  # Behind the raster
            )
        except Exception as e:
            print(f"Warning: Could not load basemap: {e}")
    
    def show(self):
        """Display the overlay figure."""
        self.ax.set_aspect('equal')
        plt.tight_layout()
        plt.show()


# Quick test
if __name__ == "__main__":
    # Simulate a field selection
    test_field = {
        'type': 'rectangle',
        'bbox': [36.8, -1.3, 36.85, -1.25],
        'center': {'lat': -1.275, 'lon': 36.825}
    }
    
    # Simulate NDVI timeseries result
    test_data = {
        'ndvi': [0.3, 0.35, 0.4, 0.45, 0.5, 0.55, 0.6]
    }
    
    overlay = RasterOverlay(test_field)
    overlay.display_ndvi(test_data, title="Test NDVI Display")
    overlay.show()
```

### C.2: Add Display Method to MapWindow (✅ Done)

Add to `src/sat_mon/gui/map_window.py`:

```python
def display_results(self, analysis_results, selection):
    """
    Display analysis results with field overlay.
    
    Args:
        analysis_results: dict with 'ndvi', 'lst', etc.
        selection: Field selection from FieldSelector
    """
    from .raster_overlay import RasterOverlay
    
    overlay = RasterOverlay(selection)
    
    # Display NDVI if available
    if 'ndvi' in analysis_results or 'ndvi_values' in analysis_results:
        ndvi_data = {'ndvi': analysis_results.get('ndvi', analysis_results.get('ndvi_values', []))}
        overlay.display_ndvi(ndvi_data, title="NDVI Analysis Results")
        overlay.show()
```

**Checkpoint C:** Can display mock NDVI data with field boundary overlay on ESRI basemap.

---

## Phase D: Integration with Analysis Pipeline

**Goal:** Connect the GUI to the existing analysis functions.

### D.1: Create GUI Orchestrator

Create new file: `src/sat_mon/gui/orchestrator.py`

```python
"""
GUI orchestrator - connects map interface to analysis pipeline.

This module handles the flow:
1. User draws field on map
2. Selection is converted to analysis parameters
3. Analysis runs
4. Results displayed with overlay
"""

import sys
from datetime import datetime, timedelta

# Import existing analysis modules
from ..data.timeseries import (
    fetch_ndvi_timeseries,
    fetch_rainfall_timeseries,
    fetch_lst_timeseries
)
from ..visualization.reports import generate_daily_report, generate_historical_report
from .map_window import MapWindow
from .raster_overlay import RasterOverlay


class GUIOrchestrator:
    """
    Orchestrates the GUI workflow.
    
    Handles the complete user flow from field selection to results display.
    """
    
    def __init__(self):
        """Initialize the orchestrator."""
        self.field_selection = None
        self.analysis_results = None
    
    def run(self):
        """
        Run the complete GUI workflow.
        
        Returns:
            dict: Analysis results, or None if cancelled
        """
        print("\n" + "="*60)
        print("SATELLITE CROP MONITOR - Interactive Mode")
        print("="*60)
        
        # Step 1: Get field selection from map
        self.field_selection = self._get_field_selection()
        
        if self.field_selection is None:
            print("No field selected. Exiting.")
            return None
        
        # Step 2: Get analysis parameters
        params = self._get_analysis_parameters()
        
        # Step 3: Run analysis
        print("\nRunning analysis...")
        self.analysis_results = self._run_analysis(params)
        
        # Step 4: Display results
        self._display_results()
        
        return self.analysis_results
    
    def _get_field_selection(self):
        """
        Open map window and get field selection.
        
        Returns:
            dict: Field selection data, or None if cancelled
        """
        print("\nStep 1: Select your field")
        print("-" * 40)
        print("A map window will open.")
        print("1. Use the radio buttons to select Rectangle or Circle tool")
        print("2. Click and drag on the map to draw your field boundary")
        print("3. Click 'Analyze Field' when ready")
        print("-" * 40)
        
        # Create and show map window
        # Default to Kenya agricultural region
        window = MapWindow(center_lat=-0.5, center_lon=37.5, zoom_level=8)
        window.create_window()
        window.setup_controls()
        window.show()
        
        # Get the selection result
        return window.get_result()
    
    def _get_analysis_parameters(self):
        """
        Determine analysis parameters from selection.
        
        Returns:
            dict: Parameters for analysis functions
        """
        bbox = self.field_selection['bbox']
        center = self.field_selection['center']
        
        # Calculate radius for circle, or from bbox for rectangle
        if self.field_selection['type'] == 'circle':
            radius_km = self.field_selection.get('radius_km', 5.0)
        else:
            # Approximate radius from bbox diagonal
            lat_diff = bbox[3] - bbox[1]
            lon_diff = bbox[2] - bbox[0]
            radius_deg = max(lat_diff, lon_diff) / 2
            radius_km = radius_deg * 111  # Approximate
        
        # Default to last 30 days for quick analysis
        end_date = datetime.now()
        start_date = end_date - timedelta(days=30)
        
        return {
            'lat': center['lat'],
            'lon': center['lon'],
            'radius_km': radius_km,
            'bbox': bbox,
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d'),
        }
    
    def _run_analysis(self, params):
        """
        Run the satellite data analysis.
        
        Args:
            params: dict with lat, lon, radius_km, start_date, end_date
        
        Returns:
            dict: Analysis results
        """
        lat = params['lat']
        lon = params['lon']
        radius = params['radius_km'] / 111  # Convert to degrees
        
        results = {
            'field': self.field_selection,
            'params': params
        }
        
        # Fetch NDVI
        print("  Fetching NDVI data...")
        try:
            ndvi_data = fetch_ndvi_timeseries(
                lat, lon, radius,
                params['start_date'],
                params['end_date']
            )
            results['ndvi'] = ndvi_data.get('ndvi', [])
            results['ndvi_dates'] = ndvi_data.get('dates', [])
            print(f"    Got {len(results['ndvi'])} NDVI observations")
        except Exception as e:
            print(f"    NDVI fetch failed: {e}")
            results['ndvi'] = []
            results['ndvi_dates'] = []
        
        # Fetch Rainfall
        print("  Fetching rainfall data...")
        try:
            rain_data = fetch_rainfall_timeseries(
                lat, lon,
                params['start_date'],
                params['end_date']
            )
            results['rainfall'] = rain_data.get('rainfall', [])
            results['rainfall_dates'] = rain_data.get('dates', [])
            print(f"    Got {len(results['rainfall'])} rainfall observations")
        except Exception as e:
            print(f"    Rainfall fetch failed: {e}")
            results['rainfall'] = []
            results['rainfall_dates'] = []
        
        # Fetch LST
        print("  Fetching temperature data...")
        try:
            lst_data = fetch_lst_timeseries(
                lat, lon, radius,
                params['start_date'],
                params['end_date']
            )
            results['lst'] = lst_data.get('lst', [])
            results['lst_dates'] = lst_data.get('dates', [])
            print(f"    Got {len(results['lst'])} temperature observations")
        except Exception as e:
            print(f"    LST fetch failed: {e}")
            results['lst'] = []
            results['lst_dates'] = []
        
        return results
    
    def _display_results(self):
        """Display analysis results with field overlay."""
        print("\n" + "="*60)
        print("ANALYSIS RESULTS")
        print("="*60)
        
        # Print text summary
        self._print_summary()
        
        # Display graphical results
        if self.analysis_results.get('ndvi'):
            print("\nDisplaying NDVI visualization...")
            overlay = RasterOverlay(self.field_selection)
            overlay.display_ndvi(
                {'ndvi': self.analysis_results['ndvi']},
                title=f"NDVI Analysis - {self.analysis_results['params']['start_date']} to {self.analysis_results['params']['end_date']}"
            )
            overlay.show()
    
    def _print_summary(self):
        """Print text summary of results."""
        field = self.field_selection
        params = self.analysis_results['params']
        
        print(f"\nField Type: {field['type'].title()}")
        print(f"Center: {field['center']['lat']:.4f}°N, {field['center']['lon']:.4f}°E")
        print(f"Analysis Period: {params['start_date']} to {params['end_date']}")
        
        if self.analysis_results.get('ndvi'):
            ndvi_vals = self.analysis_results['ndvi']
            print(f"\nNDVI Statistics:")
            print(f"  Observations: {len(ndvi_vals)}")
            print(f"  Mean: {sum(ndvi_vals)/len(ndvi_vals):.3f}")
            print(f"  Min: {min(ndvi_vals):.3f}")
            print(f"  Max: {max(ndvi_vals):.3f}")
        
        if self.analysis_results.get('rainfall'):
            rain_vals = self.analysis_results['rainfall']
            print(f"\nRainfall Statistics:")
            print(f"  Observations: {len(rain_vals)}")
            print(f"  Total: {sum(rain_vals):.1f} mm")
            print(f"  Mean per observation: {sum(rain_vals)/len(rain_vals):.1f} mm")
        
        if self.analysis_results.get('lst'):
            lst_vals = self.analysis_results['lst']
            print(f"\nLand Surface Temperature:")
            print(f"  Observations: {len(lst_vals)}")
            print(f"  Mean: {sum(lst_vals)/len(lst_vals):.1f}°C")


def run_gui_mode():
    """Entry point for GUI mode."""
    orchestrator = GUIOrchestrator()
    return orchestrator.run()


# Test
if __name__ == "__main__":
    run_gui_mode()
```

### D.2: Update Main app.py

Replace the current CLI logic in `app.py` with GUI as default:

```python
#!/usr/bin/env python3
"""
Satellite Crop Monitor - Main Application

V9: GUI-based field selection with ESRI map interface.

Usage:
    python app.py           # Opens interactive map GUI
    python app.py --help    # Show help
"""

import argparse
import sys


def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Satellite Crop Monitor - Agricultural Analysis Tool',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python app.py                    # Open interactive map GUI
    python app.py --help             # Show this help message

The application will open a map window where you can:
  1. Pan and zoom to your area of interest
  2. Draw a rectangle or circle around your field
  3. Click 'Analyze' to run satellite data analysis
  4. View results overlaid on the map
        """
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()
    
    print("\n" + "="*60)
    print("  SATELLITE CROP MONITOR v9")
    print("  Interactive Map-Based Field Selection")
    print("="*60)
    
    # Import and run GUI mode
    try:
        from src.sat_mon.gui.orchestrator import run_gui_mode
        result = run_gui_mode()
        
        if result:
            print("\n✓ Analysis complete!")
        else:
            print("\n✗ Analysis cancelled or no field selected.")
            
    except ImportError as e:
        print(f"\nError: GUI module not found. {e}")
        print("Make sure all dependencies are installed:")
        print("  pip install matplotlib contextily pyproj")
        sys.exit(1)
    except Exception as e:
        print(f"\nError during analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
```

**Checkpoint D:** Full GUI workflow - map selection → analysis → results display.

---

## Phase E: Polish and Error Handling

**Goal:** Add robustness, better UX, and edge case handling.

### E.1: Add Loading Indicator

Update `src/sat_mon/gui/map_window.py`:

```python
def _show_loading(self, message="Loading..."):
    """Show a loading message on the figure."""
    self._loading_text = self.ax.text(
        0.5, 0.5, message,
        transform=self.ax.transAxes,
        fontsize=16,
        ha='center',
        va='center',
        bbox=dict(boxstyle='round', facecolor='white', alpha=0.9),
        zorder=100
    )
    self.fig.canvas.draw_idle()

def _hide_loading(self):
    """Remove loading message."""
    if hasattr(self, '_loading_text') and self._loading_text:
        self._loading_text.remove()
        self._loading_text = None
        self.fig.canvas.draw_idle()
```

### E.2: Add Pan/Zoom Instructions

Add to `map_window.py` in `create_window()`:

```python
# Add instructions text
instructions = """
Navigation:
• Scroll to zoom
• Click+drag to pan (when not drawing)

Drawing:
• Select tool with radio buttons
• Click+drag to draw field boundary
• Click 'Analyze' when ready
"""
self.fig.text(0.02, 0.4, instructions, fontsize=9, 
              family='monospace', va='top',
              bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9))
```

### E.3: Add Input Validation

Update `src/sat_mon/gui/field_selector.py`:

```python
def validate_selection(self):
    """
    Validate the current selection.
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if self.selection is None:
        return False, "No field selected. Please draw a rectangle or circle."
    
    bbox = self.selection['bbox']
    
    # Check minimum size (at least 100m x 100m approximately)
    lat_span = abs(bbox[3] - bbox[1])
    lon_span = abs(bbox[2] - bbox[0])
    
    min_span = 0.001  # About 100m at equator
    if lat_span < min_span or lon_span < min_span:
        return False, "Field too small. Please select a larger area (at least 100m)."
    
    # Check maximum size (reasonable limit for analysis)
    max_span = 1.0  # About 111km
    if lat_span > max_span or lon_span > max_span:
        return False, "Field too large. Please select a smaller area (max ~100km)."
    
    # Check valid coordinates
    center = self.selection['center']
    if not (-90 <= center['lat'] <= 90):
        return False, "Invalid latitude. Must be between -90 and 90."
    if not (-180 <= center['lon'] <= 180):
        return False, "Invalid longitude. Must be between -180 and 180."
    
    return True, None
```

### E.4: Error Display in GUI

Add to `map_window.py`:

```python
def _show_error(self, message):
    """Display error message in a popup-like box."""
    error_ax = self.fig.add_axes([0.2, 0.4, 0.6, 0.2])
    error_ax.set_xlim(0, 1)
    error_ax.set_ylim(0, 1)
    error_ax.axis('off')
    error_ax.set_facecolor('mistyrose')
    
    error_ax.text(0.5, 0.6, "⚠️ Error", fontsize=14, fontweight='bold',
                  ha='center', color='darkred')
    error_ax.text(0.5, 0.3, message, fontsize=11,
                  ha='center', wrap=True)
    
    # Add dismiss button
    dismiss_ax = self.fig.add_axes([0.4, 0.42, 0.2, 0.05])
    dismiss_btn = Button(dismiss_ax, 'OK')
    dismiss_btn.on_clicked(lambda e: self._dismiss_error(error_ax, dismiss_ax))
    
    self.fig.canvas.draw_idle()

def _dismiss_error(self, error_ax, btn_ax):
    """Dismiss error popup."""
    error_ax.remove()
    btn_ax.remove()
    self.fig.canvas.draw_idle()
```

**Checkpoint E:** App handles errors gracefully, shows loading states, validates input.

---

## Testing Checklist

### Unit Tests to Write

1. **test_map_window.py**
   - [ ] Window creates successfully
   - [ ] Basemap loads (mock contextily)
   - [ ] Extent calculation is correct
   - [ ] Controls are added

2. **test_field_selector.py**
   - [ ] Rectangle selection stores correct bbox
   - [ ] Circle selection stores correct center/radius
   - [ ] Tool switching works
   - [ ] Clear selection works
   - [ ] Validation catches too-small/too-large

3. **test_raster_overlay.py**
   - [ ] NDVI colormap is correct
   - [ ] Field boundary is drawn
   - [ ] Masking works for circles
   - [ ] Summary view displays mean

4. **test_orchestrator.py**
   - [ ] Full flow completes (mock window)
   - [ ] Analysis functions are called with correct params
   - [ ] Results are displayed

### Integration Tests

```python
# tests/test_gui_integration.py

def test_full_workflow_mock():
    """Test complete workflow with mocked components."""
    from unittest.mock import patch, MagicMock
    
    # Mock the map window to return a test selection
    mock_selection = {
        'type': 'rectangle',
        'bbox': [36.8, -1.3, 36.85, -1.25],
        'center': {'lat': -1.275, 'lon': 36.825}
    }
    
    with patch('src.sat_mon.gui.map_window.MapWindow') as MockWindow:
        instance = MockWindow.return_value
        instance.get_result.return_value = mock_selection
        
        from src.sat_mon.gui.orchestrator import GUIOrchestrator
        
        # Would need more mocking for full test
        # This is a skeleton for the junior dev to expand
```

---

## Dependencies Summary

Add to `requirements.txt`:

```
# GUI dependencies
matplotlib>=3.5.0
contextily>=1.2.0
pyproj>=3.0.0

# Existing
numpy>=1.21.0
requests>=2.25.0
pystac-client>=0.5.0
```

---

## File Structure After V9

```
sat_pull/
├── app.py                          # Updated: GUI entry point
├── requirements.txt                # Updated: GUI dependencies
├── src/
│   └── sat_mon/
│       ├── __init__.py
│       ├── config.py
│       ├── gui/                    # NEW: GUI module
│       │   ├── __init__.py
│       │   ├── map_window.py       # Map display with controls
│       │   ├── field_selector.py   # Drawing tools
│       │   ├── raster_overlay.py   # Results visualization
│       │   └── orchestrator.py     # Workflow coordinator
│       ├── analysis/
│       ├── data/
│       ├── processing/
│       └── visualization/
├── tests/
│   ├── test_gui_map.py             # NEW
│   ├── test_gui_selector.py        # NEW
│   ├── test_gui_overlay.py         # NEW
│   └── test_gui_integration.py     # NEW
└── docs/
    └── v9_roadmap.md               # This file
```

---

## Implementation Order for Junior Dev

1. **Week 1: Phase A**
   - Create `gui/` folder structure
   - Implement basic `MapWindow` class
   - Test that ESRI basemap displays

2. **Week 2: Phase B**
   - Implement `FieldSelector` class
   - Add rectangle selector
   - Add circle selector
   - Test drawing and coordinate conversion

3. **Week 3: Phase C**
   - Implement `RasterOverlay` class
   - Test with mock NDVI data
   - Add field boundary overlay
   - Add masking for areas outside field

4. **Week 4: Phase D**
   - Implement `GUIOrchestrator`
   - Connect to existing analysis functions
   - Update `app.py` entry point
   - End-to-end testing

5. **Week 5: Phase E**
   - Add loading indicators
   - Add error handling
   - Add input validation
   - Polish UX

---

## Common Pitfalls & Solutions

### 1. Coordinate Systems Confusion

**Problem:** Mixing WGS84 (lat/lon) with Web Mercator (meters)

**Solution:** Always be explicit:
```python
# WGS84 for storage/analysis
lat, lon = -1.275, 36.825

# Web Mercator for display
from pyproj import Transformer
transformer = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
x, y = transformer.transform(lon, lat)  # Note: lon first for always_xy=True
```

### 2. Matplotlib Event Loop Blocking

**Problem:** `plt.show()` blocks and window doesn't respond

**Solution:** Use `plt.show(block=True)` and handle all logic in callbacks:
```python
# Don't do this:
plt.show()
result = process()  # Never reached while window is open

# Do this:
def on_button_click(event):
    result = process()
    plt.close()

button.on_clicked(on_button_click)
plt.show()
```

### 3. Selector Not Responding

**Problem:** Rectangle/Ellipse selector doesn't draw

**Solution:** Make sure axes has data range set before creating selector:
```python
ax.set_xlim(xmin, xmax)  # Must be set first!
ax.set_ylim(ymin, ymax)
selector = RectangleSelector(ax, callback, ...)  # Now it works
```

### 4. Basemap Not Loading

**Problem:** contextily fails to load tiles

**Solution:** Check internet, and handle gracefully:
```python
try:
    ctx.add_basemap(ax, source=ESRI_URL)
except Exception as e:
    print(f"Basemap failed: {e}")
    ax.set_facecolor('#2d3436')  # Dark fallback
```

---

## Success Criteria

- [ ] User can open app and see ESRI satellite map
- [ ] User can draw rectangle on map
- [ ] User can draw circle on map
- [ ] User can switch between tools
- [ ] Selection coordinates are accurate (±10m)
- [ ] Analysis runs after clicking Analyze
- [ ] Results display with field overlay
- [ ] Areas outside field are visually distinct
- [ ] Error messages display for invalid selections
- [ ] App doesn't crash on common error cases
