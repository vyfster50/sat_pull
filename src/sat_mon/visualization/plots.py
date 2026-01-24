import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.widgets import RadioButtons, CheckButtons, Slider
import numpy as np

class CropMonitorVisualizer:
    def __init__(self, processed_data, raw_data=None):
        self.processed_data = processed_data
        self.raw_data = raw_data
        self.fig = None
        self.view_mode = 'grid'  # 'grid' or 'overlay'
        self.active_overlay_key = 'ndvi' # Default selected overlay

        # Layer configurations for Overlay Mode
        # Format: (key, label, default_alpha, cmap, vmin, vmax, colorbar_label, description)
        self.layers_config = [
            ("rgb", "RGB (Base)", 1.0, None, None, None, None, "True color composite"),
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
        
        # --- RENDER RGB BASE (Always On) ---
        if "rgb" in self.processed_data:
            ax_map.imshow(self.processed_data["rgb"])
        else:
            ax_map.text(0.5, 0.5, "RGB Base Not Available", ha='center', color='white')

        # --- RENDER ACTIVE OVERLAY ---
        key = self.active_overlay_key
        # Find config for active key
        config = next((item for item in self.layers_config if item[0] == key), None)
        
        if config and key != 'rgb' and key in self.processed_data:
            key, label, _, cmap, vmin, vmax, cb_label, desc = config
            alpha = self.layer_alphas[key]
            
            # Draw Overlay
            im = ax_map.imshow(self.processed_data[key], cmap=cmap, vmin=vmin, vmax=vmax, alpha=alpha)
            
            # Title & Desc
            title = self.get_layer_title(key, label)
            ax_map.set_title(f"Overlay: {title}", fontsize=14)
            ax_map.text(0.5, 0.02, desc, ha='center', va='bottom', transform=ax_map.transAxes, 
                        fontsize=11, style='italic', backgroundcolor='#ffffffaa')
            
            # Colorbar (Right side of map axis)
            plt.colorbar(im, ax=ax_map, fraction=0.03, pad=0.02, label=cb_label)
        
        elif key == 'rgb':
             # Only RGB selected
             title = self.get_layer_title('rgb', "RGB")
             ax_map.set_title(title, fontsize=14)
             ax_map.text(0.5, 0.02, "True color composite", ha='center', va='bottom', transform=ax_map.transAxes, 
                        fontsize=11, style='italic', backgroundcolor='#ffffffaa')

        ax_map.axis('off')

        # 2. Control Panel (Right Side)
        self.add_layer_controls()

        # 3. Rainfall/Weather (Bottom Row)
        self.draw_rainfall_row(gs, row_idx=4, col_span=4)

    def add_layer_controls(self):
        """Adds RadioButtons for overlay selection and Slider for opacity."""
        
        # --- 1. Overlay Selection (Radio) ---
        # Get labels excluding RGB (base is implied)
        overlay_choices = [item for item in self.layers_config if item[0] != 'rgb']
        labels = [item[1] for item in overlay_choices]
        keys = [item[0] for item in overlay_choices]
        
        # Find index of current active key
        try:
            active_idx = keys.index(self.active_overlay_key)
        except ValueError:
            active_idx = 0 # Default if rgb or invalid
            self.active_overlay_key = keys[0]

        self.fig.text(0.82, 0.88, "Select Overlay", fontsize=12, fontweight='bold')
        
        # Radio Axis
        ax_radio = self.fig.add_axes([0.82, 0.35, 0.15, 0.50], facecolor='#f0f0f0')
        radio = RadioButtons(ax_radio, labels, active=active_idx)
        
        def on_radio_click(label):
            # Find key from label
            idx = labels.index(label)
            self.active_overlay_key = keys[idx]
            self.render()

        radio.on_clicked(on_radio_click)
        self.widgets['overlay_radio'] = radio
        
        # --- 2. Opacity Slider (Single) ---
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

