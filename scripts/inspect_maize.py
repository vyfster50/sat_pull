import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from sat_mon.config import setup_environment
from sat_mon.data.stac import get_bbox, search_stac, read_band
import json
import numpy as np

def inspect_maize_collection():
    print("Inspecting esa_worldcereal_maize_main...")
    setup_environment()
    
    # Use Johannesburg coordinates again as it's in a covered region
    lat = -26.2041
    lon = 28.0473
    buffer = 0.05
    bbox = get_bbox(lat, lon, buffer)
    
    items = search_stac(
        collections=["esa_worldcereal_maize_main"],
        bbox=bbox,
        limit=1
    )
    
    if items:
        item = items[0]
        print(f"Found Item: {item['id']}")
        print(f"Date: {item['properties'].get('datetime')}")
        
        # Read classification band
        data = read_band(item, "classification", bbox, dtype="uint8")
        print(f"Unique values in classification: {np.unique(data)}")
    else:
        print("No maize items found in this region.")

if __name__ == "__main__":
    inspect_maize_collection()
