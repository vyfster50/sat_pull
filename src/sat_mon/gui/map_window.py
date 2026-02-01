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
        
        # Controls
        self.field_selector = None
        self.tool_radio = None
        self.analyze_button = None
        self.clear_button = None
        
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

    def show(self):
        """Display the map window."""
        plt.tight_layout()
        plt.show()


# Quick test
if __name__ == "__main__":
    window = MapWindow(center_lat=-1.286389, center_lon=36.817223)  # Nairobi
    window.create_window()
    window.setup_controls()  # Initialize the GUI controls
    window.show()
