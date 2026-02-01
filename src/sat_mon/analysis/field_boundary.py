import numpy as np
from shapely.geometry import Point, Polygon, mapping
from shapely.ops import transform as shapely_transform
from rasterio.crs import CRS
from rasterio.transform import from_bounds
from rasterio.warp import transform_bounds
from rasterio.features import geometry_mask
import pyproj
from functools import partial

def create_circular_boundary(center_lat: float, center_lon: float, radius_meters: float) -> dict:
    """
    Creates a circular field boundary (e.g., for pivot irrigation fields).
    
    Args:
        center_lat: Latitude of the circle center (WGS84, decimal degrees).
        center_lon: Longitude of the circle center (WGS84, decimal degrees).
        radius_meters: Radius of the circular field in meters.
    
    Returns:
        dict: A GeoJSON-like geometry dict with keys:
            - "type": "Polygon"
            - "coordinates": List of coordinate rings
            - "properties": {
                "center_lat": float,
                "center_lon": float,
                "radius_m": float,
                "area_ha": float (estimated area in hectares)
              }
    """
    # 1. Determine UTM zone for accurate metric buffering
    utm_zone = int((center_lon + 180) / 6) + 1
    hemisphere = 'north' if center_lat >= 0 else 'south'
    # Use Proj string for CRS creation
    utm_crs_str = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"
    
    # 2. Transform WGS84 point to UTM
    project_to_utm = pyproj.Transformer.from_crs(
        "EPSG:4326",
        utm_crs_str,
        always_xy=True
    ).transform
    
    point_wgs84 = Point(center_lon, center_lat) # Point takes (x, y) -> (lon, lat)
    point_utm = shapely_transform(project_to_utm, point_wgs84)
    
    # 3. Buffer in meters
    circle_utm = point_utm.buffer(radius_meters, resolution=16)
    
    # 4. Transform back to WGS84
    project_to_wgs84 = pyproj.Transformer.from_crs(
        utm_crs_str,
        "EPSG:4326",
        always_xy=True
    ).transform
    circle_wgs84 = shapely_transform(project_to_wgs84, circle_utm)
    
    # 5. Build Output
    area_ha = (np.pi * radius_meters**2) / 10000.0
    
    return {
        "type": "Polygon",
        "coordinates": [list(circle_wgs84.exterior.coords)],
        "properties": {
            "center_lat": center_lat,
            "center_lon": center_lon,
            "radius_m": radius_meters,
            "area_ha": area_ha
        }
    }

def create_polygon_boundary(vertices: list) -> dict:
    """
    Creates a polygon field boundary from a list of vertices.
    
    Args:
        vertices: List of (lat, lon) tuples defining the polygon vertices.
                  Must have at least 3 points.
    
    Returns:
        dict: GeoJSON-like geometry dict.
    """
    if len(vertices) < 3:
        raise ValueError("Polygon must have at least 3 vertices")
        
    # Convert (lat, lon) to (lon, lat) for GeoJSON/Shapely
    coords = [(lon, lat) for lat, lon in vertices]
    
    # Ensure closed ring
    if coords[0] != coords[-1]:
        coords.append(coords[0])
        
    poly = Polygon(coords)
    
    # Calculate approximate area using simplified UTM projection based on centroid
    centroid = poly.centroid
    utm_zone = int((centroid.x + 180) / 6) + 1
    hemisphere = 'north' if centroid.y >= 0 else 'south'
    utm_crs_str = f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84"
    
    project_to_utm = pyproj.Transformer.from_crs(
        "EPSG:4326",
        utm_crs_str,
        always_xy=True
    ).transform
    poly_utm = shapely_transform(project_to_utm, poly)
    area_ha = poly_utm.area / 10000.0
    
    return {
        "type": "Polygon",
        "coordinates": [list(poly.exterior.coords)],
        "properties": {
            "num_vertices": len(vertices),
            "area_ha": area_ha
        }
    }

def create_field_mask(
    boundary: dict,
    image_shape: tuple,
    bbox_wgs84: list,
    epsg: int = None
) -> np.ndarray:
    """
    Creates a boolean mask for a field boundary matching satellite image dimensions.
    
    Args:
        boundary: GeoJSON-like geometry dict.
        image_shape: (rows, cols) tuple.
        bbox_wgs84: [min_lon, min_lat, max_lon, max_lat].
        epsg: EPSG code for the satellite data's native CRS. Defaults to 4326 if None.
    
    Returns:
        np.ndarray: Boolean 2D array (True = inside field).
    """
    # 1. Setup Polygon
    # boundary['coordinates'] is list of rings, Polygon takes shell, holes
    # We assume simple polygon for now (first ring is shell)
    poly_wgs84 = Polygon(boundary["coordinates"][0])
    
    # 2. Transform Boundary to Native CRS if needed
    if epsg and epsg != 4326:
        try:
            project = pyproj.Transformer.from_crs(
                "EPSG:4326",
                f"EPSG:{epsg}",
                always_xy=True
            ).transform
            poly_native = shapely_transform(project, poly_wgs84)
            
            # Also transform the bbox to get correct bounds for Affine Transform
            # transform_bounds takes (left, bottom, right, top)
            # bbox_wgs84 is [min_lon, min_lat, max_lon, max_lat] -> matches
            left, bottom, right, top = transform_bounds(
                CRS.from_epsg(4326), 
                CRS.from_epsg(epsg), 
                *bbox_wgs84
            )
        except Exception as e:
            print(f"[create_field_mask] Projection error: {e}. Falling back to WGS84 calculation.")
            poly_native = poly_wgs84
            left, bottom, right, top = bbox_wgs84
    else:
        poly_native = poly_wgs84
        left, bottom, right, top = bbox_wgs84
        
    # 3. Create Affine Transform for Rasterization
    # Note: Images are top-down, so y resolution is negative (top > bottom)
    # transform = from_bounds(west, south, east, north, width, height)
    transform = from_bounds(left, bottom, right, top, image_shape[1], image_shape[0])
    
    # 4. Rasterize
    # rasterio.features.geometry_mask returns True for masked (OUTSIDE) pixels by default
    # unless invert=True. We want True = Inside.
    # geometry_mask expects list of geometries
    mask = geometry_mask(
        [mapping(poly_native)],
        out_shape=image_shape,
        transform=transform,
        invert=True, # True = pixels inside geometry are True
        all_touched=True # Include pixels touched by line, safer for small features
    )
    
    return mask

def apply_field_mask(
    data_array: np.ndarray,
    mask: np.ndarray,
    fill_value: float = np.nan
) -> np.ndarray:
    """
    Applies a field mask to a data array, setting outside-field pixels to fill_value.
    """
    if data_array.shape[:2] != mask.shape:
        # Try to handle broadcastable shapes (e.g. RGB image)
        if data_array.shape[0] != mask.shape[0] or data_array.shape[1] != mask.shape[1]:
             raise ValueError(f"Shape mismatch: Data {data_array.shape} vs Mask {mask.shape}")
    
    result = data_array.copy()
    
    if result.ndim == 3:
        # Broadcast mask to channels
        # mask is (H, W), data is (H, W, C)
        # We need mask (H, W, 1) or loop
        mask_3d = mask[:, :, np.newaxis]
        # Invert mask logic for numpy indexing: we want to set OUTSIDE pixels (where mask is False) to fill_value
        result[~mask] = fill_value # This assumes fill_value broadcasts or applies to all channels? 
        # Actually standard assignment `arr[bool_mask] = val` flattens or assigns.
        # For 3D: result[~mask] selects (N, C) pixels. 
        result[~mask] = fill_value
    else:
        result[~mask] = fill_value
        
    return result

def compute_field_statistics(
    data_array: np.ndarray,
    mask: np.ndarray,
    percentiles: list = [10, 25, 50, 75, 90]
) -> dict:
    """
    Computes statistics for field-only pixels in a data array.
    """
    if data_array.shape != mask.shape:
        # Ignore shape mismatch if data is just None
        if data_array is None: 
            return None
        # Should strict check?
        pass

    # Extract valid pixels (inside mask AND not NaN)
    field_pixels = data_array[mask]
    valid_pixels = field_pixels[~np.isnan(field_pixels)]
    
    if len(valid_pixels) == 0:
        return {
            "mean": None, "std": None, "min": None, "max": None, 
            "median": None, "count": 0, "percentiles": {}
        }
        
    stats = {
        "mean": float(np.mean(valid_pixels)),
        "std": float(np.std(valid_pixels)),
        "min": float(np.min(valid_pixels)),
        "max": float(np.max(valid_pixels)),
        "median": float(np.median(valid_pixels)),
        "count": int(len(valid_pixels)),
        "percentiles": {p: float(np.percentile(valid_pixels, p)) for p in percentiles}
    }
    return stats

def mask_all_indices(
    processed_data: dict,
    mask: np.ndarray,
    indices_to_mask: list = None
) -> dict:
    """
    Applies a field mask to all (or specified) indices in processed data.
    """
    if indices_to_mask is None:
        # Default 2D float indices
        indices_to_mask = [
            "ndvi", "evi", "savi", "ndmi", "ndwi", "ndre", 
            "lst", "lst_anomaly", "soil_moisture", "rvi", 
            "flood_mask", "flood_risk", "cloud_mask"
        ]
        
    output = processed_data.copy()
    
    for key in indices_to_mask:
        if key in output and output[key] is not None:
            arr = output[key]
            # Check compatibility
            if isinstance(arr, np.ndarray):
                if arr.shape == mask.shape:
                    output[key] = apply_field_mask(arr, mask)
                else:
                    # Could define logic for resizing if needed, but for now skip
                    pass
                    
    return output
