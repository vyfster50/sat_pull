import sys
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from sat_mon.config import setup_environment
from sat_mon.data.composite import get_satellite_data
from sat_mon.processing.indices import process_indices
from sat_mon.visualization.plots import CropMonitorVisualizer

def run_test():
    setup_environment()
    # Johannesburg
    lat, lon = -26.2041, 28.0473
    buffer = 0.01 # Small buffer for speed (~1km radius)
    
    print(f"Fetching REAL satellite data for {lat}, {lon} (buffer={buffer})...")
    
    try:
        raw_data = get_satellite_data(lat, lon, buffer=buffer)
    except Exception as e:
        print(f"Failed to fetch data: {e}")
        return

    if not raw_data.get('s2'):
        print("No Sentinel-2 data found. Cannot proceed with alignment test.")
        return

    print("Processing indices (generating RGB)...")
    try:
        processed_data = process_indices(raw_data)
    except Exception as e:
        print(f"Failed to process indices: {e}")
        return
    
    print("Initializing Visualizer...")
    viz = CropMonitorVisualizer(processed_data, raw_data)
    
    # Create figure
    viz.setup_figure()
    
    # Test ESRI fetch via render()
    print("Testing fetch_basemap_tiles(source='esri')...")
    
    # Set mode to overlay and base to esri
    viz.view_mode = 'overlay'
    viz.base_layer = 'esri' 
    
    # Important: Set an overlay so we can see alignment (e.g., RGB overlay with alpha)
    # We want to see the ESRI basemap AND the Sentinel-2 RGB on top
    viz.active_overlay_key = 'rgb'
    viz.layer_alphas['rgb'] = 0.5 # 50% opacity to see both
    
    try:
        viz.render()
        print("Render successful.")
    except Exception as e:
        print(f"Render failed: {e}")
        import traceback
        traceback.print_exc()
        raise e
        
    output_file = "v6_alignment_test_real.png"
    viz.fig.savefig(output_file)
    print(f"Saved output to {output_file}")
    
    # Programmatic check of extent
    extent, crs = viz.get_extent()
    print(f"Calculated Extent: {extent} in {crs}")
    
    epsg = raw_data['s2'].get('epsg')
    if str(epsg) not in str(crs):
         print(f"WARNING: CRS mismatch? Expected {epsg}, got {crs}")
    else:
         print("CRS matches expected native EPSG.")
    
    print("\nAlignment Validation:")
    print(f"1. Check {output_file}")
    print("2. Verify that features (roads, fields) in the translucent S2 RGB layer")
    print("   align with the high-res ESRI background.")

if __name__ == "__main__":
    run_test()
