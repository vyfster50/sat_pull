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
        
        # Layer configurations for Overlay Mode
        # Format: (key, label, default_alpha, cmap, vmin, vmax)
        self.layers_config = [
            ("rgb", "RGB (Base)", 1.0, None, None, None),
            ("crop_mask_plot", "Crop Mask", 0.3, "autumn_r", 0, 1),
            ("lst", "LST (Temp)", 0.0, "inferno", 15, 50),
            ("ndvi", "NDVI", 0.0, "RdYlGn", -0.2, 0.8),
            ("flood_mask", "Flood Mask", 0.5, "Blues", 0, 1),
        ]
        
        # Initialize layer states (visibility, opacity)
        self.layer_states = {
            key: {'visible': (default_alpha > 0), 'alpha': default_alpha}
            for key, _, default_alpha, _, _, _ in self.layers_config
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

    def draw_overlay_view(self):
        """Renders the Single Image Overlay view."""
        # Layout: Main Map (Top), Controls (Right/Side), Rainfall (Bottom)
        # Using GridSpec: 
        # Rows: 0-3 (Map), 4 (Rainfall)
        # Cols: 0-2 (Map), 3 (Controls - conceptual, handled via axes placement)
        
        gs = gridspec.GridSpec(5, 4, figure=self.fig, width_ratios=[1, 1, 1, 0.8], height_ratios=[1,1,1,1, 0.8])
        
        # 1. Main Map Axis (Spans first 3 cols, first 4 rows)
        ax_map = self.fig.add_subplot(gs[0:4, 0:3])
        ax_map.set_title("Composite Overlay Analysis", fontsize=14)
        ax_map.axis('off')
        
        # Render Layers
        # We render iteratively. Base layer first.
        
        # Store plot objects to update opacity later if needed (simple redraw is easier for now)
        for key, label, default_alpha, cmap, vmin, vmax in self.layers_config:
            state = self.layer_states[key]
            if state['visible'] and key in self.processed_data:
                # Alpha for the plot
                alpha = state['alpha']
                data = self.processed_data[key]
                
                # Special handling: if it's RGB, we don't use cmap/vmin/vmax usually, 
                # but standard imshow logic applies
                if key == 'rgb':
                    ax_map.imshow(data, alpha=alpha)
                else:
                    ax_map.imshow(data, cmap=cmap, vmin=vmin, vmax=vmax, alpha=alpha)

        # 2. Control Panel (Right Side)
        # We manually place axes for controls relative to the map
        self.add_layer_controls()

        # 3. Rainfall/Weather (Bottom Row)
        # Spans all columns (or just first 3 to align with map)
        self.draw_rainfall_row(gs, row_idx=4, col_span=4)

    def add_layer_controls(self):
        """Adds toggle switches and sliders for layers in Overlay mode."""
        start_y = 0.80
        step_y = 0.08
        
        # Label
        self.fig.text(0.77, 0.88, "Layer Controls", fontsize=12, fontweight='bold')

        for i, (key, label, _, _, _, _) in enumerate(self.layers_config):
            y_pos = start_y - (i * step_y)
            
            # Checkbox for Visibility
            # [left, bottom, width, height]
            ax_check = self.fig.add_axes([0.77, y_pos, 0.08, 0.05], frameon=False)
            check = CheckButtons(ax_check, [label], [self.layer_states[key]['visible']])
            
            # Slider for Opacity
            ax_slider = self.fig.add_axes([0.86, y_pos + 0.01, 0.10, 0.03])
            slider = Slider(ax_slider, '', 0.0, 1.0, valinit=self.layer_states[key]['alpha'], valfmt='%.1f')
            
            # Callbacks
            # We need to capture 'key' in the closure. 
            # In Python loops, lambda captures variable reference, not value. Use default arg or functools.partial.
            
            def on_check(label, k=key):
                self.layer_states[k]['visible'] = not self.layer_states[k]['visible']
                self.render() # Redraw full figure to apply order/alpha correctly
            
            def on_slider(val, k=key):
                self.layer_states[k]['alpha'] = val
                # Optimization: Could just update the specific artist alpha, but for MVP re-render is safer
                # To implement "live" sliding, we'd need to store the image artists in a dictionary
                # For now, let's redraw on release or just accept re-render lag
                self.render()

            check.on_clicked(on_check)
            slider.on_changed(on_slider)
            
            self.widgets[f'check_{key}'] = check
            self.widgets[f'slider_{key}'] = slider

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

