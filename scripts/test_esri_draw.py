import sys
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from sat_mon.config import setup_environment
from sat_mon.visualization.plots import CropMonitorVisualizer
from sat_mon.data.stac import get_bbox

def test_esri_draw():
    print("Testing ESRI Basemap Drawing...")
    setup_environment()

    # Default coordinates from app.py
    lat = -28.736214289538538
    lon = 29.365144005056933
    buffer = 0.05
    
    print(f"Location: {lat}, {lon}")
    
    # Calculate bbox
    bbox = get_bbox(lat, lon, buffer)
    print(f"BBox: {bbox}")
    
    # Mock raw_data
    # We need 'bbox' and 's2' with 'epsg' for get_extent() to work
    # 29E is in UTM Zone 35S -> EPSG:32735
    raw_data = {
        "bbox": bbox,
        "s2": {
            "epsg": 32735,
            "metadata": {
                "properties": {
                    "datetime": "2026-01-25T10:00:00Z"
                }
            }
        },
        "ndvi_source": "S2"
    }
    
    # Empty processed data
    processed_data = {}
    
    print("Initializing Visualizer...")
    viz = CropMonitorVisualizer(processed_data, raw_data)
    
    # Setup figure
    viz.setup_figure()
    
    # Set to Overlay mode and ESRI base layer
    viz.view_mode = 'overlay'
    viz.base_layer = 'esri'
    
    print("Rendering...")
    
    # Check extent before render
    extent, crs = viz.get_extent()
    print(f"Calculated Extent: {extent}")
    print(f"Target CRS: {crs}")
    
    try:
        viz.render()
        
        output_file = "esri_draw_test.png"
        viz.fig.savefig(output_file)
        print(f"✓ Render successful. Saved to {output_file}")
        print("Please check the output image to verify the map is visible.")
        
    except Exception as e:
        print(f"✗ Render failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_esri_draw()
