import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.widgets import RadioButtons, CheckButtons, Slider
import numpy as np
import contextily as cx
from rasterio.crs import CRS
from rasterio.warp import transform_bounds
import os
from pathlib import Path
from typing import List, Optional, Tuple, Any
from datetime import datetime, timedelta
import matplotlib.dates as mdates
from ..analysis.phenology import Season
from pyproj import Transformer

# Optional request caching for basemap tiles (speeds repeated requests / local development)
try:
    import requests_cache
    cache_dir = Path('.cache')
    cache_dir.mkdir(exist_ok=True)
    # Creates .cache/contextily_cache.sqlite with 1 day expiry
    requests_cache.install_cache(str(cache_dir / 'contextily_cache'), backend='sqlite', expire_after=86400)
    print(f"[visualization] requests_cache enabled: {cache_dir / 'contextily_cache.sqlite'}")
except Exception:
    requests_cache = None

class CropMonitorVisualizer:
    def __init__(self, processed_data, raw_data=None):
        self.processed_data = processed_data
        self.raw_data = raw_data
        self.fig = None
        self.view_mode = 'grid'  # 'grid' or 'overlay'
        self.active_overlay_key = 'ndvi' # Default selected overlay
        self.base_layer = 'rgb' # 'rgb' or 'google'
        # Selection/mask
        self.field_selection = (raw_data or {}).get('selection') if raw_data else None
        self._cached_mask = None  # (mask, shape_cached)

        # Layer configurations for Overlay Mode
        # Format: (key, label, default_alpha, cmap, vmin, vmax, colorbar_label, description)
        self.layers_config = [
            ("rgb", "RGB (Composite)", 1.0, None, None, None, None, "True color composite"),
            ("esri_satellite", "ESRI Satellite", 1.0, None, None, None, None, "High-res Basemap"),
            ("evi", "EVI", 0.5, "YlGn", 0, 1, "EVI", "Improved sensitivity in high biomass"),
            ("savi", "SAVI", 0.5, "YlGn", 0, 1, "SAVI", "Corrects for soil brightness"),
            ("ndmi", "NDMI", 0.5, "Blues", -0.5, 0.5, "NDMI", "Vegetation water content"),
            ("ndwi", "NDWI", 0.5, "Blues", -0.5, 0.5, "NDWI", "Surface water detection"),
            ("rvi", "RVI (Radar)", 0.5, "YlGn", 0, 1, "RVI", "Vegetation structure/biomass"),
            ("crop_mask_plot", "Crop Mask", 0.3, "autumn_r", 0, 1, "Class", "Yellow=cropland | Gray=other"),
            ("lst", "LST (Temp)", 0.5, "inferno", 15, 50, "Temp (°C)", "Dark=cooler | Bright=hotter"),
            ("lst_anomaly", "LST Anom.", 0.5, "RdBu_r", -5, 5, "Deviation", "Red=hotter than baseline"),
            ("soil_moisture", "Soil Moisture", 0.5, "YlGn", 0, 100, "Moisture (%)", "Green=adequate | Yellow=dry"),
            ("ndvi", "NDVI", 0.5, "RdYlGn", -0.2, 0.8, "NDVI Index", "Green=healthy (>0.5) | Yellow=stressed (<0.3)"),
            ("flood_mask", "Flood Mask", 0.5, "Blues", 0, 1, "Probability", "VV < -15 dB detection"),
        ]
        
        # Initialize layer alpha states (opacity only, visibility handled by active key)
        self.layer_alphas = {
            key: default_alpha
            for key, _, default_alpha, _, _, _, _, _ in self.layers_config
        }
        
        # Widget references to prevent garbage collection
        self.widgets = {}

    def get_date_short(self, key):
        """Helper to extract date from raw_data metadata."""
        if self.raw_data and self.raw_data.get(key) and self.raw_data[key].get("metadata"):
            props = self.raw_data[key]["metadata"].get("properties", {})
            dt = props.get("datetime") or props.get("start_datetime")
            if dt:
                return dt[:10]
        return "N/A"

    def setup_figure(self):
        """Initializes the figure."""
        self.fig = plt.figure(figsize=(18, 12) if self.view_mode == 'overlay' else (18, 25))
        self.render()

    def clear_figure(self):
        """Clears figure but keeps the window open."""
        self.fig.clear()
        self.widgets = {} # Clear widget references

    def render(self):
        """Main rendering router."""
        self.clear_figure()
        
        if self.view_mode == 'grid':
            self.draw_grid_view()
        else:
            self.draw_overlay_view()
        
        # Add View Switcher (Common to both)
        self.add_view_controls()
        
        self.fig.canvas.draw_idle()

    def add_view_controls(self):
        """Adds the mode switcher radio button."""
        # Place in top left corner or a dedicated sidebar area
        # Using a fixed axis position [left, bottom, width, height]
        ax_mode = self.fig.add_axes([0.02, 0.92, 0.1, 0.06], facecolor='#f0f0f0')
        ax_mode.set_title("View Mode", fontsize=10)
        
        radio = RadioButtons(ax_mode, ('Grid', 'Overlay'), active=(0 if self.view_mode == 'grid' else 1))
        
        def change_mode(label):
            new_mode = label.lower()
            if new_mode != self.view_mode:
                self.view_mode = new_mode
                # Resize figure for better layout fit? 
                # plt.gcf().set_size_inches(...) 
                self.render()

        radio.on_clicked(change_mode)
        self.widgets['view_mode'] = radio

    def draw_grid_view(self):
        """Renders the traditional 5x3 grid."""
        # Use GridSpec to allow room for the control widget
        gs = gridspec.GridSpec(5, 3, figure=self.fig, top=0.90, bottom=0.05, hspace=0.3)

        # Helper for common plotting
        def plot_layer(ax, key, title, cmap=None, vmin=None, vmax=None, label=None, desc=None):
            if key in self.processed_data:
                im = ax.imshow(self.processed_data[key], cmap=cmap, vmin=vmin, vmax=vmax)
                ax.set_title(title)
                if label:
                    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label=label)
            else:
                ax.text(0.5, 0.5, f"{label or key} N/A", ha='center')
            
            if desc:
                ax.text(0.5, -0.05, desc, ha='center', transform=ax.transAxes, 
                        fontsize=9, style='italic', color='gray')
            ax.axis("off")

        # --- Data extraction ---
        date_s2 = self.get_date_short('s2')
        date_ls = self.get_date_short('landsat')
        date_s1 = self.get_date_short('s1')
        date_rain = self.get_date_short('rain')
        date_lc = self.get_date_short('crop_mask')
        date_sm = self.get_date_short('soil_moisture')
        ndvi_source = self.raw_data.get("ndvi_source", "S2") if self.raw_data else "S2"
        ndvi_date = date_s2 if ndvi_source == "S2" else date_ls

        # --- ROW 1 ---
        plot_layer(self.fig.add_subplot(gs[0, 0]), "rgb", f"Sentinel-2 RGB\n{date_s2}", 
                   desc="True color composite")
        plot_layer(self.fig.add_subplot(gs[0, 1]), "ndvi", f"NDVI ({ndvi_source})\n{ndvi_date}", 
                   "RdYlGn", -0.2, 0.8, "NDVI Index", "Green=healthy | Yellow=stressed")
        plot_layer(self.fig.add_subplot(gs[0, 2]), "evi", f"EVI\n{date_s2}", 
                   "YlGn", 0, 1, "EVI", "High biomass sensitivity")

        # --- ROW 2 ---
        plot_layer(self.fig.add_subplot(gs[1, 0]), "savi", f"SAVI\n{date_s2}", 
                   "YlGn", 0, 1, "SAVI", "Soil brightness corrected")
        plot_layer(self.fig.add_subplot(gs[1, 1]), "ndmi", f"NDMI\n{date_s2}", 
                   "Blues", -0.5, 0.5, "NDMI", "Vegetation water content")
        plot_layer(self.fig.add_subplot(gs[1, 2]), "ndwi", f"NDWI\n{date_s2}", 
                   "Blues", -0.5, 0.5, "NDWI", "Surface water detection")

        # --- ROW 3 ---
        plot_layer(self.fig.add_subplot(gs[2, 0]), "flood_mask", f"Flood Mask (S1)\n{date_s1}", 
                   "Blues", 0, 1, "Probability", "VV < -15 dB")
        plot_layer(self.fig.add_subplot(gs[2, 1]), "rvi", f"RVI (Radar)\n{date_s1}", 
                   "YlGn", 0, 1, "RVI", "Structure/Biomass")
        
        # Crop mask special handling for cmap
        ax_cm = self.fig.add_subplot(gs[2, 2])
        if self.processed_data.get("crop_mask_plot") is not None:
            cmap_cm = plt.cm.get_cmap("viridis").copy()
            cmap_cm.set_bad(color='lightgray')
            ax_cm.imshow(self.processed_data["crop_mask_plot"], cmap='autumn_r', interpolation='nearest', vmin=0, vmax=1)
            ax_cm.set_title(f"Crop Mask\n{date_lc}")
        else:
            ax_cm.text(0.5, 0.5, "Crop Mask N/A", ha='center')
        ax_cm.axis("off")

        # --- ROW 4 ---
        plot_layer(self.fig.add_subplot(gs[3, 0]), "lst", f"LST\n{date_ls}", 
                   "inferno", 15, 50, "Temp (°C)", "Land Surface Temp")
        plot_layer(self.fig.add_subplot(gs[3, 1]), "lst_anomaly", f"LST Anomaly\n{date_ls}", 
                   "RdBu_r", -5, 5, "Deviation", "Red=hotter than baseline")
        plot_layer(self.fig.add_subplot(gs[3, 2]), "soil_moisture", f"Soil Moisture\n{date_sm}", 
                   "YlGn", 0, 100, "Moisture (%)", "WaPOR Data")

        # --- ROW 5 (Weather) ---
        self.draw_rainfall_row(gs, row_idx=4)

    def get_layer_title(self, key, base_label):
        """Generates dynamic title with date."""
        date_map = {
            'rgb': 's2', 'ndvi': 's2', 'evi': 's2', 'savi': 's2', 'ndmi': 's2', 'ndwi': 's2',
            'flood_mask': 's1', 'rvi': 's1',
            'crop_mask_plot': 'crop_mask',
            'lst': 'landsat', 'lst_anomaly': 'landsat',
            'soil_moisture': 'soil_moisture',
            'rain_7d': 'rain', 'rain_30d': 'rain'
        }
        
        # Special logic for NDVI source
        if key == 'ndvi':
            source = self.raw_data.get("ndvi_source", "S2") if self.raw_data else "S2"
            d_key = 's2' if source == "S2" else 'landsat'
            date = self.get_date_short(d_key)
            return f"{base_label} ({source}) - {date}"

        date_key = date_map.get(key, key)
        date = self.get_date_short(date_key)
        return f"{base_label} - {date}"

    def get_extent(self):
        """Calculates the extent (left, right, bottom, top) in native CRS."""
        if not self.raw_data or not self.raw_data.get('bbox'):
            return None, None
        
        bbox_wgs84 = self.raw_data['bbox']
        
        # Defensive EPSG extraction with fallback
        epsg = self.raw_data.get('s2', {}).get('epsg')
        if epsg is None:
            print("[get_extent] Warning: No EPSG found, using Web Mercator (3857)")
            epsg = 3857
        
        try:
            epsg = int(epsg)  # Coerce string to int
            native_crs = CRS.from_epsg(epsg)
        except (ValueError, TypeError, Exception) as e:
            print(f"[get_extent] CRS error ({e}), falling back to EPSG:3857")
            epsg = 3857
            native_crs = CRS.from_epsg(3857)
        
        # Transform WGS84 bbox to Native CRS
        # transform_bounds takes (left, bottom, right, top)
        # bbox is [min_lon, min_lat, max_lon, max_lat] which is (left, bottom, right, top)
        try:
            left, bottom, right, top = transform_bounds(CRS.from_epsg(4326), native_crs, *bbox_wgs84)
            return [left, right, bottom, top], f"EPSG:{epsg}"
        except Exception as e:
            print(f"[get_extent] Transform error: {e}")
            return None, None

    def _pad_bounds(self, bounds, frac: float = 0.15):
        """Pad [left, right, bottom, top] by a fraction on each side.

        Args:
            bounds: [left, right, bottom, top]
            frac: fraction of width/height to add on each side (0.15 = 15%)

        Returns:
            [left, right, bottom, top] with padding applied
        """
        if not bounds:
            return bounds
        left, right, bottom, top = bounds
        width = right - left
        height = top - bottom
        dx = width * frac
        dy = height * frac
        return [left - dx, right + dx, bottom - dy, top + dy]

    def _calculate_zoom(self, bounds):
        """Calculate appropriate zoom level based on extent width in meters.
        
        Args:
            bounds: [left, right, bottom, top] in projected CRS (meters)
        
        Returns:
            int: Zoom level (10-18)
        """
        width = abs(bounds[1] - bounds[0])  # right - left
        
        # Heuristic: smaller extent = higher zoom
        # At zoom 18, each tile covers ~150m at equator
        # At zoom 14, each tile covers ~2.4km
        if width < 500:
            return 18
        elif width < 1000:
            return 17
        elif width < 2000:
            return 16
        elif width < 5000:
            return 15
        elif width < 10000:
            return 14
        elif width < 20000:
            return 13
        elif width < 50000:
            return 12
        else:
            return 11

    def fetch_basemap_tiles(self, ax, bounds=None, crs=None, alpha=1.0, source='esri'):
        """Fetches and plots basemap tiles.

        Args:
            ax: matplotlib axis to draw onto.
            bounds: list-like [left, right, bottom, top] in the provided `crs`.
            crs: rasterio CRS or EPSG string/int for the bounds.
            alpha: opacity for the basemap.
            source: (optional) can be 'esri', 'google' or a tile URL template.
        """
        if bounds is None or crs is None:
            return

        # CRITICAL: Set axis limits BEFORE calling add_basemap so contextily knows extent
        left, right, bottom, top = bounds
        ax.set_xlim(left, right)
        ax.set_ylim(bottom, top)

        # Calculate appropriate zoom level based on extent size
        zoom = self._calculate_zoom(bounds)

        try:
            # Choose URL template based on source
            if source == 'esri':
                url = 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'
                attribution = 'ESRI World Imagery'
            elif source == 'google':
                url = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
                attribution = 'Google Maps'
            else:
                # If a custom URL was supplied as the `source` variable, use it directly
                url = source
                attribution = ''

            cx.add_basemap(
                ax,
                crs=crs,
                source=url,
                attribution=attribution,
                alpha=alpha,
                zoom=zoom,
            )
        except Exception as e:
            print(f"Error fetching basemap: {e}")

    def draw_overlay_view(self):
        """Renders the Single Image Overlay view."""
        # Layout: Main Map (Top), Controls (Right/Side), Rainfall (Bottom)
        
        # Adjusted GridSpec: 
        # - Increased last column width ratio (1.2) for controls
        # - Added explicit margins (top/bottom/left/right)
        # - Added hspace=0.4 to prevent overlap between map and rainfall rows
        gs = gridspec.GridSpec(5, 4, figure=self.fig, 
                               width_ratios=[1, 1, 1, 1.2], 
                               height_ratios=[1, 1, 1, 1, 0.8],
                               top=0.90, bottom=0.05, left=0.05, right=0.95, hspace=0.4)
        
        # 1. Main Map Axis (Spans first 3 cols, first 4 rows)
        ax_map = self.fig.add_subplot(gs[0:4, 0:3])
        
        # Calculate extent for georeferencing
        extent, crs = self.get_extent()
        padded = self._pad_bounds(extent, 0.15) if extent else None
        
        # --- RENDER BASE LAYER ---
        if self.base_layer == 'google':
            if padded and crs:
                self.fetch_basemap_tiles(ax_map, bounds=padded, crs=crs, alpha=1.0, source='google')
                ax_map.text(0.5, 0.02, "Base: Google Satellite", ha='center', va='bottom', transform=ax_map.transAxes, 
                            fontsize=11, style='italic', backgroundcolor='#ffffffaa')
            else:
                ax_map.text(0.5, 0.5, "Google Maps Unavailable (Missing CRS/Extent)", ha='center', color='red')
        elif self.base_layer == 'esri':
            if padded and crs:
                self.fetch_basemap_tiles(ax_map, bounds=padded, crs=crs, alpha=1.0, source='esri')
                ax_map.text(0.5, 0.02, "Base: ESRI Satellite", ha='center', va='bottom', transform=ax_map.transAxes, 
                            fontsize=11, style='italic', backgroundcolor='#ffffffaa')
            else:
                ax_map.text(0.5, 0.5, "ESRI Basemap Unavailable (Missing CRS/Extent)", ha='center', color='red')
        else: # Default to RGB
            if "rgb" in self.processed_data:
                # Keep axes padded, but draw RGB to the exact analysis extent
                if padded is not None:
                    # Set axes to padded bounds to create margin
                    left, right, bottom, top = padded
                    ax_map.set_xlim(left, right)
                    ax_map.set_ylim(bottom, top)
                ax_map.imshow(self.processed_data["rgb"], extent=extent)
                ax_map.text(0.5, 0.02, "Base: Sentinel-2 RGB", ha='center', va='bottom', transform=ax_map.transAxes, 
                            fontsize=11, style='italic', backgroundcolor='#ffffffaa')
            else:
                ax_map.text(0.5, 0.5, "RGB Base Not Available", ha='center', color='white')

        # --- RENDER ACTIVE OVERLAY ---
        key = self.active_overlay_key
        # Find config for active key
        config = next((item for item in self.layers_config if item[0] == key), None)
        
        if config:
            key, label, _, cmap, vmin, vmax, cb_label, desc = config
            alpha = self.layer_alphas[key]
            
            # Special check: Don't draw RGB overlay if RGB is already base (unless user wants to, but usually redundant)
            if key == 'rgb' and self.base_layer == 'rgb':
                pass # Already drawn
            
            elif key in self.processed_data:
                # Standard Array Overlay (masked to field if available)
                arr = self.processed_data[key]
                arr_to_show = self._apply_field_mask(arr)
                im = ax_map.imshow(arr_to_show, cmap=cmap, vmin=vmin, vmax=vmax, alpha=alpha, extent=extent)
                
                # Title
                title = self.get_layer_title(key, label)
                ax_map.set_title(f"{title}", fontsize=14)
                
                # Desc (override base desc if visible)
                if alpha > 0.1:
                    ax_map.text(0.5, 0.05, desc, ha='center', va='bottom', transform=ax_map.transAxes, 
                                fontsize=10, style='italic', backgroundcolor='#ffffffaa')
                
                # Colorbar (Right side of map axis)
                if key != 'rgb': # No colorbar for RGB
                    plt.colorbar(im, ax=ax_map, fraction=0.03, pad=0.02, label=cb_label)
        
        # Persist field boundary overlay (dotted)
        try:
            self._draw_field_boundary(ax_map)
        except Exception as e:
            print(f"[overlay] Boundary draw warning: {e}")

        ax_map.axis('off')

        # 2. Control Panel (Right Side)
        self.add_layer_controls()

        # 3. Rainfall/Weather (Bottom Row)
        self.draw_rainfall_row(gs, row_idx=4, col_span=4)

    def _apply_field_mask(self, arr):
        """Return array masked outside the selected field, if selection present."""
        if self.field_selection is None or self.raw_data is None or self.raw_data.get('bbox') is None:
            return arr
        # Build/cached mask for current array shape
        mask = self._get_mask_for_shape(arr.shape)
        if mask is None:
            return arr
        # Use masked array then fill outside with NaN for transparency
        try:
            masked = np.where(mask, arr, np.nan)
            return masked
        except Exception:
            return arr

    def _get_mask_for_shape(self, shape):
        """Compute or reuse a boolean mask (True inside field) for given raster shape."""
        try:
            if self._cached_mask is not None and self._cached_mask[1] == shape:
                return self._cached_mask[0]

            bbox = self.raw_data.get('bbox')
            if bbox is None:
                return None
            min_lon, min_lat, max_lon, max_lat = bbox[0], bbox[1], bbox[2], bbox[3]
            nrows, ncols = shape[0], shape[1]
            # Build coordinate grids (pixel centers) in WGS84
            lons = np.linspace(min_lon, max_lon, ncols)
            lats = np.linspace(min_lat, max_lat, nrows)
            lon_grid, lat_grid = np.meshgrid(lons, lats)

            sel = self.field_selection
            if sel is None:
                return None

            if sel.get('type') == 'circle':
                c = sel.get('center', {})
                center_lat = float(c.get('lat'))
                center_lon = float(c.get('lon'))
                radius_m = float(sel.get('radius_m') or 0.0)
                # If radius_m not present (older selections), fall back to degrees approximation
                if radius_m <= 0.0:
                    radius_deg = float(sel.get('radius_degrees') or 0.0)
                    if radius_deg <= 0.0:
                        sb = sel.get('bbox', [center_lon, center_lat, center_lon, center_lat])
                        radius_deg = max(abs(sb[2]-sb[0]), abs(sb[3]-sb[1]))/2.0
                    lon_scale = np.cos(np.radians(center_lat))
                    dlat = lat_grid - center_lat
                    dlon = (lon_grid - center_lon) * lon_scale
                    dist_deg = np.sqrt(dlat*dlat + dlon*dlon)
                    inside = dist_deg <= radius_deg
                else:
                    # Compute distance in the native projected CRS to match boundary drawing
                    try:
                        epsg = int((self.raw_data.get('s2', {}) or {}).get('epsg') or 3857)
                    except Exception:
                        epsg = 3857
                    to_native = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
                    # Project grids and center
                    X, Y = to_native.transform(lon_grid, lat_grid)
                    cx, cy = to_native.transform(center_lon, center_lat)
                    dist_m = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
                    inside = dist_m <= radius_m
            else:
                # Rectangle: inside if within selection bbox
                sb = sel.get('bbox') or []
                if len(sb) != 4:
                    return None
                lon_min_s, lat_min_s, lon_max_s, lat_max_s = map(float, sb)
                inside = (lon_grid >= lon_min_s) & (lon_grid <= lon_max_s) & (lat_grid >= lat_min_s) & (lat_grid <= lat_max_s)

            self._cached_mask = (inside, shape)
            return inside
        except Exception as e:
            print(f"[mask] Mask computation error: {e}")
            return None

    def _draw_field_boundary(self, ax):
        """Draw a dashed boundary of the selected field on the given axis."""
        if self.field_selection is None or self.raw_data is None:
            return
        extent, crs = self.get_extent()
        if extent is None:
            return
        # Transform selection bbox to same projected CRS as extent for drawing
        from rasterio.crs import CRS as _CRS
        try:
            epsg = int((self.raw_data.get('s2', {}) or {}).get('epsg') or 3857)
        except Exception:
            epsg = 3857
        native_crs = _CRS.from_epsg(epsg)
        sel = self.field_selection
        import matplotlib.patches as mpatches

        if sel.get('type') == 'circle':
            # Draw a true circle using projected center and radius in meters
            c = sel.get('center', {})
            center_lon = float(c.get('lon'))
            center_lat = float(c.get('lat'))
            radius_m = float(sel.get('radius_m') or 0.0)

            # Transform center to native CRS
            try:
                to_native = Transformer.from_crs("EPSG:4326", native_crs, always_xy=True)
                cx, cy = to_native.transform(center_lon, center_lat)
            except Exception:
                # Fallback: draw in WGS84 degrees with approximate radius (will look off)
                cx, cy = center_lon, center_lat
            # If radius_m missing, approximate from bbox width
            if radius_m <= 0.0:
                sb = sel.get('bbox') or [center_lon, center_lat, center_lon, center_lat]
                try:
                    left, bottom, right, top = transform_bounds(CRS.from_epsg(4326), native_crs, sb[0], sb[1], sb[2], sb[3])
                    radius_m = max(abs(right - left), abs(top - bottom)) / 2.0
                except Exception:
                    radius_m = 0.0

            # Compensate for half-pixel shrink in the mask (pixel-center criterion)
            # Estimate pixel sizes from analysis extent and raster shape
            # Use NDVI shape if available, else fall back to RGB or any 2D layer
            nrows = ncols = None
            try:
                if 'ndvi' in self.processed_data and self.processed_data['ndvi'] is not None:
                    nrows, ncols = self.processed_data['ndvi'].shape[:2]
                elif 'rgb' in self.processed_data and self.processed_data['rgb'] is not None:
                    nrows, ncols = self.processed_data['rgb'].shape[:2]
                else:
                    # Pick first 2D array available
                    for v in self.processed_data.values():
                        if isinstance(v, np.ndarray) and v.ndim >= 2:
                            nrows, ncols = v.shape[:2]
                            break
            except Exception:
                nrows = ncols = None

            try:
                left, right, bottom, top = extent
                if nrows and ncols and nrows > 0 and ncols > 0:
                    px_x = abs(right - left) / float(ncols)
                    px_y = abs(top - bottom) / float(nrows)
                    half_diag = 0.5 * (px_x ** 2 + px_y ** 2) ** 0.5
                else:
                    half_diag = 0.0
            except Exception:
                half_diag = 0.0

            draw_radius = max(0.0, radius_m - half_diag)
            circ = mpatches.Circle((cx, cy), radius=draw_radius, fill=False, linestyle='--', linewidth=2, edgecolor='white')
            ax.add_patch(circ)
        else:
            # Rectangle selection: draw bbox rectangle
            sb = sel.get('bbox') if sel else None
            if not sb or len(sb) != 4:
                return
            try:
                left, bottom, right, top = transform_bounds(CRS.from_epsg(4326), native_crs, sb[0], sb[1], sb[2], sb[3])
            except Exception:
                # Fallback: draw in data coords assuming extent uses WGS84
                left, bottom, right, top = sb[0], sb[1], sb[2], sb[3]

            width = right - left
            height = top - bottom
            rect = mpatches.Rectangle((left, bottom), width, height, fill=False, linestyle='--', linewidth=2, edgecolor='white')
            ax.add_patch(rect)

    def add_layer_controls(self):
        """Adds RadioButtons for overlay selection, Base Layer selection, and Slider for opacity."""
        
        # --- 1. Base Layer Selection (Radio) ---
        self.fig.text(0.82, 0.88, "Base Layer", fontsize=12, fontweight='bold')
        ax_base = self.fig.add_axes([0.82, 0.81, 0.15, 0.06], facecolor='#f0f0f0')
        base_labels = ['Sentinel-2 RGB', 'Google Maps', 'ESRI Satellite']
        # compute active index safely
        if self.base_layer == 'rgb':
            active_idx = 0
        elif self.base_layer == 'google':
            active_idx = 1
        else:
            active_idx = 2

        radio_base = RadioButtons(ax_base, base_labels, active=active_idx)

        def on_base_click(label):
            if 'Sentinel' in label:
                self.base_layer = 'rgb'
            elif 'Google' in label:
                self.base_layer = 'google'
            else:
                self.base_layer = 'esri'
            self.render()

        radio_base.on_clicked(on_base_click)
        self.widgets['base_radio'] = radio_base

        # --- 2. Overlay Selection (Radio) ---
        # Get labels excluding Google (as it's a base now) and optionally RGB (if we treat it as pure base)
        # But we allow RGB as overlay to compare against Google
        overlay_choices = self.layers_config # All config layers are valid overlays
        labels = [item[1] for item in overlay_choices]
        keys = [item[0] for item in overlay_choices]
        
        # Find index of current active key
        try:
            active_idx = keys.index(self.active_overlay_key)
        except ValueError:
            active_idx = 0 # Default if rgb or invalid
            self.active_overlay_key = keys[0]

        self.fig.text(0.82, 0.78, "Overlay Layer", fontsize=12, fontweight='bold')
        
        # Radio Axis - adjusted position and height
        ax_radio = self.fig.add_axes([0.82, 0.35, 0.15, 0.42], facecolor='#f0f0f0')
        radio = RadioButtons(ax_radio, labels, active=active_idx)
        
        def on_radio_click(label):
            # Find key from label
            idx = labels.index(label)
            self.active_overlay_key = keys[idx]
            self.render()

        radio.on_clicked(on_radio_click)
        self.widgets['overlay_radio'] = radio
        
        # --- 3. Opacity Slider (Single) ---
        self.fig.text(0.82, 0.30, "Overlay Opacity", fontsize=10, fontweight='bold')
        ax_slider = self.fig.add_axes([0.82, 0.27, 0.15, 0.02])
        
        current_alpha = self.layer_alphas.get(self.active_overlay_key, 0.5)
        slider = Slider(ax_slider, '', 0.0, 1.0, valinit=current_alpha, valfmt='%.1f')
        
        def on_slider_change(val):
            self.layer_alphas[self.active_overlay_key] = val
            # For immediate feedback we could just update the artist, but full render handles colorbars cleanly
            # We can optimize later if laggy.
            # self.render() # CAUTION: Full render on slider drag is heavy.
            pass 
        
        # Use simple update on release for performance, or update artist directly
        # For now, let's update on release event (MouseUp) which Slider doesn't natively expose easily without event hooks
        # Simplest: Update on change, but maybe throttle?
        # Actually, matplotlib slider updates continuously. 
        # Let's attach a separate 'update' call or just redraw.
        
        # Let's try direct artist update logic for smoothness
        def on_slider_update(val):
            self.layer_alphas[self.active_overlay_key] = val
            # Trigger full re-render
            self.render()

        slider.on_changed(on_slider_update)
        self.widgets['opacity_slider'] = slider

    def draw_rainfall_row(self, gs, row_idx, col_span=3):
        """Draws the rainfall and weather charts at the bottom."""
        date_rain = self.get_date_short('rain')
        
        # We need to split the grid spec row into sub-axes manually or use sub-gridspec
        # Simple approach: if col_span=3 (Grid mode), it matches the 3 columns.
        # If col_span=4 (Overlay mode), we need to fit 3 plots into that width.
        
        # Let's just create a sub-gridspec for this row area
        gs_row = gridspec.GridSpecFromSubplotSpec(1, 3, subplot_spec=gs[row_idx, 0:col_span], wspace=0.3)

        # 1. 7-day Rain
        ax1 = self.fig.add_subplot(gs_row[0, 0])
        if "rain_7d" in self.processed_data:
            im = ax1.imshow(self.processed_data["rain_7d"], cmap='Blues')
            ax1.set_title(f"Rainfall 7-day (CHIRPS)\n{date_rain}")
            plt.colorbar(im, ax=ax1, fraction=0.046, pad=0.04, label="mm")
        else:
            ax1.text(0.5, 0.5, "7-d Rain N/A", ha='center')
        ax1.axis('off')

        # 2. 30-day Rain
        ax2 = self.fig.add_subplot(gs_row[0, 1])
        if "rain_30d" in self.processed_data:
            im = ax2.imshow(self.processed_data["rain_30d"], cmap='Blues')
            ax2.set_title(f"Rainfall 30-day (CHIRPS)\n{date_rain}")
            plt.colorbar(im, ax=ax2, fraction=0.046, pad=0.04, label="mm")
        else:
            ax2.text(0.5, 0.5, "30-d Rain N/A", ha='center')
        ax2.axis('off')

        # 3. Weather Forecast
        ax3 = self.fig.add_subplot(gs_row[0, 2])
        if "weather" in self.processed_data and self.processed_data["weather"]:
            weather = self.processed_data["weather"]
            dates = [d[5:] for d in weather["dates"]] # MM-DD
            
            ax3.plot(dates, weather["temp_max"], color='red', label='Max', marker='o', markersize=4)
            ax3.plot(dates, weather["temp_min"], color='blue', label='Min', marker='o', markersize=4)
            
            ax_rain = ax3.twinx()
            ax_rain.bar(dates, weather["precip"], color='skyblue', alpha=0.3, label='Precip')
            
            ax3.set_title("7-Day Forecast")
            
            # Simple Legend
            lines1, labels1 = ax3.get_legend_handles_labels()
            lines2, labels2 = ax_rain.get_legend_handles_labels()
            ax3.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize='x-small')
            
            ax3.tick_params(axis='x', rotation=45, labelsize=8)
        else:
            ax3.text(0.5, 0.5, "Weather N/A", ha='center')
            ax3.axis('off')

def plot_grid(processed_data, raw_data=None):
    """Entry point for the visualization."""
    viz = CropMonitorVisualizer(processed_data, raw_data)
    viz.setup_figure()
    
    print("[Visualization] Interactive window opened. Close to exit.")
    plt.show()

def plot_field_timeseries(
    dates: List[datetime],
    ndvi: List[float],
    sm: List[Optional[float]] = None,
    lst: List[Optional[float]] = None,
    rainfall: List[Optional[float]] = None,
    seasons: List[Season] = None,
    field_name: str = "Field Analysis",
    figsize: Tuple[int, int] = (14, 12),
    save_path: str = None
) -> plt.Figure:
    """
    Creates a multi-panel time series plot for a single field (Phase D).
    
    Panel 1: NDVI with planting/harvest markers
    Panel 2: Soil Moisture (if provided)
    Panel 3: LST (if provided)
    Panel 4: Rainfall (if provided)
    
    Args:
        dates: List of dates for the x-axis.
        ndvi: List of NDVI values corresponding to dates.
        sm: Optional list of Soil Moisture values.
        lst: Optional list of LST values (Kelvin or Celsius).
        rainfall: Optional list of daily rainfall values (mm).
        seasons: List of detected Season objects for markers.
        field_name: Title for the plot.
        figsize: Figure size tuple (width, height).
        save_path: Optional path to save the figure.
        
    Returns:
        The matplotlib Figure object.
    """
    
    # Validate input lengths
    if len(dates) != len(ndvi):
        raise ValueError(f"dates ({len(dates)}) and ndvi ({len(ndvi)}) must have same length")
    if sm is not None and len(sm) != len(dates):
        raise ValueError(f"sm ({len(sm)}) must match dates length ({len(dates)})")
    if lst is not None and len(lst) != len(dates):
        raise ValueError(f"lst ({len(lst)}) must match dates length ({len(dates)})")
    if rainfall is not None and len(rainfall) != len(dates):
        raise ValueError(f"rainfall ({len(rainfall)}) must match dates length ({len(dates)})")
    
    # Determine which panels to show
    has_sm = sm is not None and any(v is not None for v in sm)
    has_lst = lst is not None and any(v is not None for v in lst)
    has_rain = rainfall is not None and any(v is not None for v in rainfall)
    
    active_panels = 1 + int(has_sm) + int(has_lst) + int(has_rain)
    
    # Create figure with shared x-axis
    fig, axes = plt.subplots(active_panels, 1, figsize=figsize, sharex=True)
    if active_panels == 1:
        axes = [axes]
    
    fig.suptitle(f"{field_name} - Time Series Analysis", fontsize=16, y=0.95)
    
    curr_ax_idx = 0
    
    # --- Panel 1: NDVI ---
    ax_ndvi = axes[curr_ax_idx]
    
    # Filter out None values for plotting
    valid_mask = np.array([v is not None for v in ndvi])
    if any(valid_mask):
        plot_dates = np.array(dates)[valid_mask]
        plot_vals = np.array(ndvi)[valid_mask].astype(float)
        
        ax_ndvi.plot(plot_dates, plot_vals, 'g.-', label='NDVI', linewidth=1.5, markersize=8)
        
        # Add smooth trend line if enough data
        if len(plot_vals) > 10:
             # Simple rolling mean for visual trend
             window = min(5, len(plot_vals)//2)
             trend = np.convolve(plot_vals, np.ones(window)/window, mode='valid')
             trend_dates = plot_dates[window//2 : -window//2 + 1] if window % 2 != 0 else plot_dates[window//2 : -window//2]
             
             # Handle length mismatch due to padding logic diffs
             if len(trend) == len(trend_dates):
                ax_ndvi.plot(trend_dates, trend, 'k--', alpha=0.3, label='Trend', linewidth=1)
    
    ax_ndvi.set_ylabel("NDVI")
    ax_ndvi.set_ylim(0, 1.0)
    ax_ndvi.grid(True, alpha=0.3)
    
    # Add season markers
    if seasons:
        legend_elements = []
        added_labels = set()
        
        for i, s in enumerate(seasons):
            # Planting (Start)
            if s.start_date:
                ax_ndvi.axvline(s.start_date, color='green', linestyle='--', alpha=0.6)
                if 'Planting' not in added_labels:
                    ax_ndvi.plot([], [], 'g--', label='Planting')
                    added_labels.add('Planting')
                
                # Label P
                ax_ndvi.text(s.start_date, 0.05, 'P', color='green', 
                             ha='center', va='bottom', fontweight='bold')

            # Harvest (End)
            if s.end_date:
                ax_ndvi.axvline(s.end_date, color='orange', linestyle='--', alpha=0.6)
                if 'Harvest' not in added_labels:
                    ax_ndvi.plot([], [], color='orange', linestyle='--', label='Harvest')
                    added_labels.add('Harvest')
                
                # Label H
                ax_ndvi.text(s.end_date, 0.05, 'H', color='orange', 
                             ha='center', va='bottom', fontweight='bold')
                
            # Peak marker
            if s.peak_date and s.peak_ndvi:
                ax_ndvi.scatter([s.peak_date], [s.peak_ndvi], c='red', s=50, zorder=5)
                # Label health
                ax_ndvi.text(s.peak_date, s.peak_ndvi + 0.02, f"{s.health}\n(pk:{s.peak_ndvi:.2f})", 
                             ha='center', va='bottom', fontsize=8, color='darkred')

        # Shade the seasons
        for s in seasons:
            if s.start_date and s.end_date:
                ax_ndvi.axvspan(s.start_date, s.end_date, color='green', alpha=0.05)

    ax_ndvi.legend(loc='upper left', frameon=True)
    curr_ax_idx += 1
    
    # --- Panel 2: Soil Moisture ---
    if has_sm:
        ax_sm = axes[curr_ax_idx]
        valid_mask = np.array([v is not None for v in sm])
        if any(valid_mask):
            p_dates = np.array(dates)[valid_mask]
            p_vals = np.array(sm)[valid_mask].astype(float)
            ax_sm.plot(p_dates, p_vals, 'b.-', label='Soil Moisture', linewidth=1.5)
            
        ax_sm.set_ylabel("Soil Moisture") # Unit depends on source (e.g., m3/m3 or %)
        ax_sm.grid(True, alpha=0.3)
        ax_sm.legend(loc='upper left')
        curr_ax_idx += 1
        
    # --- Panel 3: LST ---
    if has_lst:
        ax_lst = axes[curr_ax_idx]
        unit = "°C"  # Default unit
        valid_mask = np.array([v is not None for v in lst])
        if any(valid_mask):
            p_dates = np.array(dates)[valid_mask]
            p_vals = np.array(lst)[valid_mask].astype(float)
            
            # Convert Kelvin to Celsius if seemingly in Kelvin range (>200)
            if np.mean(p_vals) > 200:
                p_vals = p_vals - 273.15
            
            ax_lst.plot(p_dates, p_vals, 'r.-', label=f'LST ({unit})', linewidth=1.5)
            
        ax_lst.set_ylabel(f"LST ({unit})")
        ax_lst.grid(True, alpha=0.3)
        ax_lst.legend(loc='upper left')
        curr_ax_idx += 1
        
    # --- Panel 4: Rainfall ---
    if has_rain:
        ax_rain = axes[curr_ax_idx]
        valid_mask = np.array([v is not None for v in rainfall])
        if any(valid_mask):
            p_dates = np.array(dates)[valid_mask]
            p_vals = np.array(rainfall)[valid_mask].astype(float)
            
            # Bar chart for daily rain
            ax_rain.bar(p_dates, p_vals, color='skyblue', label='Daily Rain (mm)', width=1.0)
            
            # Add cumulative line on twin axis
            ax_cum = ax_rain.twinx()
            cum_vals = np.nancumsum(p_vals)
            ax_cum.plot(p_dates, cum_vals, color='navy', linestyle='-', linewidth=1, alpha=0.7, label='Cumulative')
            ax_cum.set_ylabel("Cumul. (mm)", color='navy')
            
        ax_rain.set_ylabel("Daily Rain (mm)")
        ax_rain.grid(True, alpha=0.3)
        ax_rain.legend(loc='upper left')
        curr_ax_idx += 1
        
    # Format x-axis for the bottom plot
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y-%b'))
    axes[-1].xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    plt.setp(axes[-1].xaxis.get_majorticklabels(), rotation=45, ha='right')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"[plots] Saved timeseries chart to {save_path}")
        
    return fig

def plot_season_comparison(
    seasons: List[Season],
    figsize: Tuple[int, int] = (10, 6),
    save_path: str = None
) -> plt.Figure:
    """
    Creates a bar chart comparing season metrics (Peak NDVI, Duration).
    
    Args:
        seasons: List of detected Season objects.
        figsize: Figure size tuple.
        save_path: Optional path to save the figure.
        
    Returns:
        The matplotlib Figure object.
    """
    if not seasons:
        return plt.figure(figsize=figsize)
        
    fig, ax1 = plt.subplots(figsize=figsize)
    
    # Prepare data - use start date for unique labels (handles multiple seasons per year)
    labels = [s.start_date.strftime('%Y-%m') if s.start_date else f"S{i+1}" for i, s in enumerate(seasons)]
    peaks = [s.peak_ndvi for s in seasons]
    durations = [s.duration_days for s in seasons]
    healths = [s.health for s in seasons]
    
    x = np.arange(len(labels))
    width = 0.35
    
    # Health colors
    health_map = {
        'excellent': '#2ca02c', # green
        'good': '#bcbd22',      # yellow-green
        'moderate': '#ff7f0e',  # orange
        'poor': '#d62728',      # red
        'pending': 'gray'
    }
    colors = [health_map.get(h, 'gray') for h in healths]
    
    # Plot Peak NDVI bars
    bars1 = ax1.bar(x - width/2, peaks, width, label='Peak NDVI', color=colors, alpha=0.8)
    
    ax1.set_ylabel('Peak NDVI')
    ax1.set_ylim(0, 1.0)
    ax1.set_title('Season Comparison: Health & Duration')
    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    
    # Plot Duration line on secondary axis
    ax2 = ax1.twinx()
    ax2.plot(x, durations, 'b-o', label='Duration (days)', linewidth=2, markersize=8)
    ax2.set_ylabel('Duration (days)', color='blue')
    ax2.tick_params(axis='y', labelcolor='blue')
    
    # Add labels to bars
    for i, rect in enumerate(bars1):
        height = rect.get_height()
        ax1.annotate(f'{healths[i]}',
                    xy=(rect.get_x() + rect.get_width() / 2, height/2),
                    xytext=(0, 0),
                    textcoords="offset points",
                    ha='center', va='center', rotation=90, color='white', fontweight='bold')

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        print(f"[plots] Saved comparison chart to {save_path}")
        
    return fig

