"""
Raster data overlay with field boundary masking.

Displays satellite data (NDVI, LST, etc.) with the selected
field boundary highlighted and areas outside masked with transparency.
"""

from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle
from matplotlib.colors import LinearSegmentedColormap
from pyproj import Transformer
import contextily as ctx
from typing import Dict, Any, Tuple, Optional

# Approximate meters per degree at the equator
METERS_PER_DEGREE = 111_000


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

    def __init__(self, field_selection: Dict[str, Any]):
        """
        Initialize the raster overlay.

        Args:
            field_selection: dict from FieldSelector with type, bbox, center
        """
        self.field = field_selection
        self.fig: Optional[plt.Figure] = None
        self.ax: Optional[plt.Axes] = None

        # Transformer (WGS84 -> Web Mercator for display)
        self._to_mercator = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)

    def display_ndvi(self, ndvi_data: Dict[str, Any], dates=None, title: str = "NDVI Analysis") -> Tuple[plt.Figure, plt.Axes]:
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
            mean_ndvi = float(np.mean(ndvi_data['ndvi'])) if ndvi_data['ndvi'] else np.nan
            self._display_summary_view(mean_ndvi, title)
        else:
            # Nothing to display; keep empty axes
            pass

        # Add field boundary overlay
        self._add_field_boundary()

        # Add basemap underneath
        self._add_basemap()

        self.ax.set_title(title, fontsize=14, fontweight='bold')

        return self.fig, self.ax

    def _display_single_raster(self, values: np.ndarray, bounds: Optional[Tuple[float, float, float, float]]):
        """Display a single 2D raster image."""
        if bounds is None:
            bounds = tuple(self.field['bbox'])  # type: ignore

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

    def _display_summary_view(self, mean_value: float, title: str):
        """Display a summary view when no raster available."""
        # Get field center in Web Mercator
        center_lon = self.field['center']['lon']
        center_lat = self.field['center']['lat']
        center_x, center_y = self._to_mercator.transform(center_lon, center_lat)

        # Create a colored circle/rectangle showing mean value
        ndvi_cmap = LinearSegmentedColormap.from_list('ndvi', self.NDVI_COLORS)
        # Normalize to 0-1 range where -0.2 -> 0 and 0.9 -> 1.0
        norm_val = (mean_value + 0.2) / 1.1 if not np.isnan(mean_value) else 0.5
        color = ndvi_cmap(np.clip(norm_val, 0, 1))

        if self.field['type'] == 'circle':
            # Draw filled circle
            radius_deg = self.field.get('radius_degrees', 0.01)
            radius_m = radius_deg * METERS_PER_DEGREE * np.cos(np.radians(center_lat))
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

    def _apply_field_mask(self, values: np.ndarray, bounds: Tuple[float, float, float, float]) -> np.ma.MaskedArray:
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
                (lon_grid - center_lon) ** 2 + (lat_grid - center_lat) ** 2
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
            radius_m = radius_deg * METERS_PER_DEGREE * np.cos(np.radians(center_lat))

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
        if self.ax is not None:
            self.ax.set_aspect('equal')
        plt.tight_layout()
        plt.show()
