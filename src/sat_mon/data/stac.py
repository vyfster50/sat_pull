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

def read_band(
    item,
    asset_key,
    bbox_wgs84,
    dtype="float32",
    out_shape=None,
    max_pixels=5_000_000,
    max_dim=4096,
):
    """Reads a specific band from a STAC item (dict) within a bounding box.

    Adds automatic downsampling for very large read windows to prevent OOM.

    Args:
        item: STAC item dict or pystac Item
        asset_key: asset key to read (e.g., "B04")
        bbox_wgs84: [min_lon, min_lat, max_lon, max_lat]
        dtype: numpy dtype for output array
        out_shape: optional (rows, cols) to resample to
        max_pixels: soft cap for total pixels when out_shape is None
        max_dim: soft cap for max(rows, cols) when out_shape is None
    """
    # Handle item as dict or pystac Item
    href = item['assets'][asset_key]['href'] if isinstance(item, dict) else item.assets[asset_key].href

    with rasterio.open(href) as src:
        bbox_native = transform_bounds("EPSG:4326", src.crs, *bbox_wgs84)
        window = from_bounds(*bbox_native, src.transform)

        target_shape = out_shape

        # If caller did not set out_shape, guard against massive windows
        if target_shape is None:
            try:
                w = int(round(window.width))
                h = int(round(window.height))
            except Exception:
                # Fallback if width/height not available
                w = h = None

            if w and h and w > 0 and h > 0:
                scale = 1.0
                # Cap by max_dim first
                if max_dim and max(w, h) > max_dim:
                    scale = min(max_dim / float(w), max_dim / float(h))

                # Cap by max_pixels as well
                if max_pixels and (w * h) > max_pixels:
                    scale = min(scale, (max_pixels / float(w * h)) ** 0.5)

                if scale < 1.0:
                    th = max(1, int(h * scale))
                    tw = max(1, int(w * scale))
                    target_shape = (th, tw)
                    print(f"[read_band] Large window {h}x{w}; downsampling to {th}x{tw} for memory safety.")

        if target_shape:
            data = src.read(
                1,
                window=window,
                out_shape=target_shape,
                resampling=Resampling.bilinear,
                boundless=True,
            )
        else:
            data = src.read(1, window=window, boundless=True)

        return data.astype(dtype)
