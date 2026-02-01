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
    
    def __init__(self, center_lat=-1.0, center_lon=37.0, zoom_level=10, initial_bbox=None):
        """
        Initialize the map window.
        
        Args:
            center_lat: Center latitude in decimal degrees
            center_lon: Center longitude in decimal degrees  
            zoom_level: Zoom level (1-18, higher = more detail)
            initial_bbox: Optional [min_lon, min_lat, max_lon, max_lat] to pre-select
        """
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.zoom_level = zoom_level
        self.initial_bbox = initial_bbox
        
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

        # Add navigation and drawing instructions (non-blocking help)
        instructions = (
            "Navigation:\n"
            "• Scroll to zoom\n"
            "• Click+drag to pan (when not drawing)\n\n"
            "Drawing:\n"
            "• Select tool with radio buttons\n"
            "• Click+drag to draw field boundary\n"
            "• Click 'Analyze' when ready"
        )
        self.fig.text(
            0.02, 0.40, instructions,
            fontsize=9,
            family='monospace', va='top',
            bbox=dict(boxstyle='round', facecolor='lightyellow', alpha=0.9)
        )
        
        return self.fig, self.ax

    def display_results(self, analysis_results, selection):
        """
        Display analysis results with field overlay.
        
        Args:
            analysis_results: dict with 'ndvi', 'lst', etc.
            selection: Field selection from FieldSelector
        """
        try:
            from .raster_overlay import RasterOverlay
        except Exception as e:
            print(f"Warning: RasterOverlay unavailable: {e}")
            return

        overlay = RasterOverlay(selection)

        # Display NDVI if available
        if 'ndvi' in analysis_results or 'ndvi_values' in analysis_results or 'values' in analysis_results:
            # Support both timeseries and single raster style inputs
            if 'values' in analysis_results:
                ndvi_data = {
                    'values': analysis_results['values'],
                    'bounds': analysis_results.get('bounds', selection.get('bbox'))
                }
            else:
                ndvi_list = analysis_results.get('ndvi', analysis_results.get('ndvi_values', []))
                ndvi_data = {'ndvi': ndvi_list}

            overlay.display_ndvi(ndvi_data, title="NDVI Analysis Results")
            overlay.show()
    
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
        
        # Apply initial selection if provided
        if self.initial_bbox:
            try:
                self.field_selector.set_selection(self.initial_bbox)
                print(f"Applied initial selection: {self.initial_bbox}")
            except Exception as e:
                print(f"Failed to apply initial selection: {e}")

        # Ensure we deactivate selectors when the window closes
        try:
            self._close_cid = self.fig.canvas.mpl_connect('close_event', self._on_close)
        except Exception:
            self._close_cid = None
        
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
        # 1. Check if selection exists
        if self.field_selector.selection is None:
            self._show_error("No field selected! Draw a rectangle or circle first.")
            return

        # 2. Validate selection
        is_valid, error_msg = self.field_selector.validate_selection()
        if not is_valid:
            self._show_error(error_msg)
            return
        
        selection = self.field_selector.get_selection()
        
        print("\n" + "="*50)
        print("STARTING ANALYSIS")
        print("="*50)
        print(f"Field type: {selection['type']}")
        print(f"Bounding box: {selection['bbox']}")
        
        # Show loading state
        self._show_loading()
        
        # Close the map window and return selection
        self._analysis_requested = True
        self._selection_result = selection
        
        # Small delay to show loading state before close (optional, effectively immediate here)
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

    def _show_loading(self, message="Analyzing field..."):
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
        """Remove loading message if present."""
        if hasattr(self, '_loading_text') and self._loading_text is not None:
            try:
                self._loading_text.remove()
            except Exception:
                pass
            self._loading_text = None
            self.fig.canvas.draw_idle()

    def _show_error(self, message):
        """Display error message in a popup-like box."""
        # Clean up any existing error
        if hasattr(self, '_error_ax') and self._error_ax:
            self._error_ax.remove()
        
        # Create error panel
        self._error_ax = self.fig.add_axes([0.2, 0.4, 0.6, 0.2])
        self._error_ax.set_xlim(0, 1)
        self._error_ax.set_ylim(0, 1)
        self._error_ax.axis('off')
        
        # Add background rect
        rect = plt.Rectangle((0, 0), 1, 1, transform=self._error_ax.transAxes, 
                             facecolor='mistyrose', edgecolor='darkred', linewidth=2)
        self._error_ax.add_patch(rect)
        
        self._error_ax.text(0.5, 0.7, "⚠️ Error", fontsize=14, fontweight='bold',
                      ha='center', color='darkred')
        self._error_ax.text(0.5, 0.4, message, fontsize=11,
                      ha='center', wrap=True)
        
        # Add dismiss button (its own axes in figure coords)
        self._dismiss_btn_ax = self.fig.add_axes([0.4, 0.42, 0.2, 0.05])
        self._dismiss_btn = Button(self._dismiss_btn_ax, 'OK')
        self._dismiss_btn.on_clicked(self._dismiss_error)
        
        self.fig.canvas.draw_idle()

    def _dismiss_error(self, event):
        """Dismiss error popup."""
        if hasattr(self, '_error_ax') and self._error_ax:
            self._error_ax.remove()
            self._error_ax = None
        if hasattr(self, '_dismiss_btn_ax') and self._dismiss_btn_ax:
            self._dismiss_btn_ax.remove()
            self._dismiss_btn_ax = None
        self.fig.canvas.draw_idle()

    def _on_close(self, event):
        """Figure close handler: deactivate selectors to prevent widget errors."""
        try:
            if self.field_selector:
                self.field_selector.deactivate()
        except Exception:
            pass

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
