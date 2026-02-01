"""
GUI orchestrator - connects map interface to analysis pipeline.

Flow:
1) User enters coordinates and resolution (CLI style)
2) Map opens centered on location with initial bbox drawn
3) User confirms or redraws field on map
4) Orchestrator runs full analysis pipeline (fetch -> process -> visualize)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .map_window import MapWindow

# Import full pipeline components
# Note: We use relative imports assuming this is run as a module
from ..data.composite import get_satellite_data
from ..processing.indices import process_indices
from ..analysis.alerts import analyze_thresholds
from ..visualization.plots import plot_grid
from ..visualization.reports import generate_report


def run_gui_mode():
    """Entry point called by app.py."""
    orchestrator = GUIOrchestrator()
    orchestrator.run()


class GUIOrchestrator:
    """Orchestrates GUI selection → analysis → visualization."""

    def __init__(self):
        self.field_selection: Optional[Dict[str, Any]] = None
        self.analysis_results: Optional[Dict[str, Any]] = None

    def run(self) -> Optional[Dict[str, Any]]:
        """Run the complete GUI workflow."""
        # 1. Get Selection (Interactive Map)
        self.field_selection = self._get_field_selection()
        
        if not self.field_selection:
            print("No field selected. Exiting GUI mode.")
            return None

        # 2. Run Analysis Pipeline
        print("\n" + "="*50)
        print("RUNNING ANALYSIS PIPELINE")
        print("="*50)
        
        # Calculate buffer from bbox for data fetching
        center = self.field_selection['center']
        bbox = self.field_selection['bbox']
        lat_span = abs(bbox[3] - bbox[1])
        lon_span = abs(bbox[2] - bbox[0])
        # Use simple max dimension for buffer
        buffer = max(lat_span, lon_span) / 2.0
        
        print(f"Fetching satellite data for {center['lat']:.4f}, {center['lon']:.4f}...")
        raw_data = get_satellite_data(
            lat=center['lat'],
            lon=center['lon'],
            buffer=buffer
        )
        
        # 3. Processing
        print("Processing indices...")
        processed_data = process_indices(raw_data)
        
        # 4. Analysis
        analysis_results = analyze_thresholds(processed_data)
        
        # 5. Report Generation (Console)
        print("Generating report...")
        generate_report(processed_data, analysis_results, raw_data=raw_data)
        
        # 6. Visualize Results
        print("Launching visualization window...")
        plot_grid(processed_data, raw_data=raw_data)
             
        return {
            'processed': processed_data,
            'raw': raw_data,
            'analysis': analysis_results
        }

    def _get_gui_input(self):
        """Get location and resolution interactively from user (CLI style)."""
        print(f"\n{'='*50}")
        print("SATELLITE CROP MONITORING - GUI MODE")
        print(f"{'='*50}\n")
        
        # Default values
        default_lat = -28.736214
        default_lon = 29.365144
        
        # Get position
        print("Enter position as: lat, lon")
        print(f"Example: -28.7347, 29.3651")
        print(f"(Press Enter for default: {default_lat}, {default_lon})")
        position_input = input("\nPosition: ").strip()
        
        lat, lon = default_lat, default_lon
        if position_input:
            try:
                parts = position_input.split(",")
                lat = float(parts[0].strip())
                lon = float(parts[1].strip())
            except (ValueError, IndexError):
                print("Invalid format. Using default position.")
        
        # Get resolution/buffer
        print("\nResolution (buffer size in degrees):")
        print("  1 = ~1.1 km  (high zoom)")
        print("  2 = ~5.5 km  (medium area) [default]")
        print("  3 = ~11 km   (large area)")
        print("  4 = ~22 km   (very wide area)")
        print("  Or enter custom value (e.g., 0.03)")
        res_input = input("\nResolution [1-4 or custom]: ").strip()
        
        # Default to 0.05 (approx 5km)
        buffer = 0.05
        if res_input:
            try:
                # Map 1-4 to buffer sizes
                res_mapping = {
                    "1": 0.01,
                    "2": 0.05,
                    "3": 0.1,
                    "4": 0.2
                }
                buffer = res_mapping.get(res_input, float(res_input))
            except ValueError:
                print("Invalid resolution. Using default (0.05).")
        
        print(f"Selected coordinates: ({lat}, {lon})")
        print(f"Selected resolution: {buffer}°")
        
        return lat, lon, buffer

    def _get_field_selection(self) -> Optional[Dict[str, Any]]:
        """Open the map window with initial bbox and return user selection."""
        # 1. Ask for input first
        lat, lon, buffer = self._get_gui_input()
        
        # 2. Calculate initial bbox
        initial_bbox = [
            lon - buffer, # min_lon
            lat - buffer, # min_lat
            lon + buffer, # max_lon
            lat + buffer  # max_lat
        ]
        
        # 3. Calculate appropriate zoom level
        # Heuristic: 0.05 deg -> zoom 12
        try:
            # Avoid log(0)
            safe_buffer = max(0.001, buffer)
            zoom_offset = math.log2(safe_buffer / 0.05)
            # Higher buffer -> lower zoom
            zoom_level = int(12 - zoom_offset)
            zoom_level = max(8, min(16, zoom_level)) # Clamp
        except ValueError:
            zoom_level = 10

        # 4. Open Map Window
        print("\nOpening Map Window...")
        try:
            window = MapWindow(
                center_lat=lat, 
                center_lon=lon, 
                zoom_level=zoom_level,
                initial_bbox=initial_bbox
            )
            window.create_window()
            window.setup_controls()
            window.show()
            
            return window.get_result()
        except Exception as e:
            print(f"Error opening map window: {e}")
            return None
