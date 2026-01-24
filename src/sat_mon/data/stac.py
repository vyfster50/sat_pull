import requests
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.enums import Resampling
from ..config import STAC_URL

def search_stac(collections, bbox, datetime=None, limit=1, query=None, sortby=None):
    """Helper to search STAC API using requests."""
    payload = {
        "collections": collections,
        "bbox": bbox,
        "limit": limit
    }
    if datetime:
        payload["datetime"] = datetime
    if sortby:
        payload["sortby"] = sortby
        
    try:
        response = requests.post(STAC_URL, json=payload, timeout=30)
        response.raise_for_status()
        return response.json().get("features", [])
    except Exception as e:
        print(f"STAC Search Error: {e}")
        return []

def get_bbox(lat, lon, buffer=0.05):
    """Creates a bounding box around a point."""
    return [
        lon - buffer,
        lat - buffer,
        lon + buffer,
        lat + buffer,
    ]

def read_band(item, asset_key, bbox_wgs84, dtype="float32", out_shape=None):
    """Reads a specific band from a STAC item (dict) within a bounding box."""
    # Handle item as dict or pystac Item
    href = item['assets'][asset_key]['href'] if isinstance(item, dict) else item.assets[asset_key].href
    
    with rasterio.open(href) as src:
        bbox_native = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84)
        window = from_bounds(*bbox_native, src.transform)
        
        if out_shape:
            data = src.read(
                1, 
                window=window, 
                out_shape=out_shape, 
                resampling=Resampling.bilinear,
                boundless=True
            )
        else:
            data = src.read(1, window=window, boundless=True)
            
        return data.astype(dtype)
