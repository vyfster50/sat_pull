"""
Historical Time Series Data Fetching for Satellite Crop Monitoring.

This module provides functions to fetch multi-year satellite data archives
and extract field-level statistics for trend analysis.

Phase B Implementation - Historical Data Fetching (2023-2026)
"""

import numpy as np
import requests
from datetime import datetime, date
from typing import List, Tuple, Optional, Dict, Any, Union, Callable
from collections import namedtuple

from .stac import search_stac, get_bbox, read_band
from ..config import STAC_URL
from ..analysis.field_boundary import (
    create_circular_boundary,
    create_field_mask,
    compute_field_statistics
)

# Named tuple for scene results
SceneResult = namedtuple('SceneResult', ['date', 'item'])
TimeseriesPoint = namedtuple('TimeseriesPoint', ['date', 'value', 'metadata'])


def fetch_timeseries(
    lat: float,
    lon: float,
    buffer: float = 0.05,
    start_date: str = "2023-01-01",
    end_date: str = "2026-01-31",
    collections: List[str] = None,
    max_cloud_cover: float = 50.0,
    progress_callback: Callable[[int, int, str], None] = None
) -> List[SceneResult]:
    """
    Query STAC API for all scenes in a date range with pagination support.
    
    Args:
        lat: Latitude of the area of interest (WGS84 decimal degrees).
        lon: Longitude of the area of interest (WGS84 decimal degrees).
        buffer: Buffer around point in degrees (default 0.05 ≈ 5km).
        start_date: Start date in ISO format (YYYY-MM-DD).
        end_date: End date in ISO format (YYYY-MM-DD).
        collections: List of collection IDs to query. Defaults to ["s2_l2a"].
        max_cloud_cover: Maximum cloud cover percentage (only for optical).
        progress_callback: Optional callback(page_num, total_items, message).
    
    Returns:
        List of SceneResult(date, item) tuples sorted chronologically.
        
    Example:
        >>> scenes = fetch_timeseries(-1.5, 35.2, buffer=0.03, 
        ...                           start_date="2023-01-01", end_date="2024-12-31")
        >>> print(f"Found {len(scenes)} scenes")
    """
    if collections is None:
        collections = ["s2_l2a"]
    
    bbox = get_bbox(lat, lon, buffer)
    datetime_range = f"{start_date}/{end_date}"
    
    all_items = []
    page = 1
    page_size = 100  # STAC API typically limits to 100 items per request
    
    while True:
        if progress_callback:
            progress_callback(page, len(all_items), f"Fetching page {page}...")
        
        # Build query with cloud cover filter for optical collections
        query = None
        if any(c in ["s2_l2a", "ls9_sr", "ls8_sr"] for c in collections):
            query = {
                "eo:cloud_cover": {"lte": max_cloud_cover}
            }
        
        try:
            items = _search_stac_paginated(
                collections=collections,
                bbox=bbox,
                datetime=datetime_range,
                limit=page_size,
                query=query,
                sortby=[{"field": "datetime", "direction": "asc"}]
            )
        except Exception as e:
            print(f"[fetch_timeseries] Error on page {page}: {e}")
            break
        
        if not items:
            break
            
        all_items.extend(items)
        
        # Check if we got fewer items than page_size (last page)
        if len(items) < page_size:
            break
            
        page += 1
        
        # Safety limit to prevent infinite loops
        if page > 100:
            print("[fetch_timeseries] Warning: Hit page limit (100 pages)")
            break
    
    # Convert to SceneResult tuples with parsed dates
    results = []
    for item in all_items:
        try:
            date_str = item['properties']['datetime']
            # Parse ISO datetime string
            if 'T' in date_str:
                scene_date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            else:
                scene_date = datetime.strptime(date_str, '%Y-%m-%d')
            results.append(SceneResult(date=scene_date, item=item))
        except (KeyError, ValueError) as e:
            print(f"[fetch_timeseries] Skipping item with invalid date: {e}")
            continue
    
    # Sort by date (should already be sorted, but ensure)
    results.sort(key=lambda x: x.date)
    
    if progress_callback:
        progress_callback(page, len(results), f"Complete: {len(results)} scenes found")
    
    print(f"[fetch_timeseries] Found {len(results)} scenes from {start_date} to {end_date}")
    return results


def _search_stac_paginated(
    collections: List[str],
    bbox: List[float],
    datetime: str = None,
    limit: int = 100,
    query: dict = None,
    sortby: List[dict] = None
) -> List[dict]:
    """
    Internal helper for paginated STAC search with query support.
    
    This extends the basic search_stac with proper query parameter handling.
    """
    payload = {
        "collections": collections,
        "bbox": bbox,
        "limit": limit
    }
    if datetime:
        payload["datetime"] = datetime
    if sortby:
        payload["sortby"] = sortby
    if query:
        payload["query"] = query
        
    try:
        response = requests.post(STAC_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("features", [])
    except requests.exceptions.Timeout:
        print("[_search_stac_paginated] Request timed out")
        return []
    except requests.exceptions.RequestException as e:
        print(f"[_search_stac_paginated] Request error: {e}")
        return []
    except Exception as e:
        print(f"[_search_stac_paginated] Unexpected error: {e}")
        return []


def extract_field_values(
    scenes: List[SceneResult],
    asset_key: str,
    bbox: List[float],
    field_mask: np.ndarray,
    out_shape: Tuple[int, int] = None,
    scl_cloud_classes: List[int] = None,
    max_cloud_fraction: float = 0.5,
    progress_callback: Callable[[int, int, str], None] = None
) -> List[TimeseriesPoint]:
    """
    Extract field-mean values from a list of scenes for a specific band.
    
    Processes one scene at a time to minimize memory usage.
    
    Args:
        scenes: List of SceneResult tuples from fetch_timeseries().
        asset_key: Asset key to read (e.g., "B04", "B08", "ST_B10").
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat].
        field_mask: Boolean mask array (True = inside field).
        out_shape: Optional (rows, cols) to resample to (matches field_mask shape).
        scl_cloud_classes: SCL classes considered as cloud for S2 (default: [3, 8, 9, 10]).
        max_cloud_fraction: Max fraction of field covered by clouds (0-1).
        progress_callback: Optional callback(current, total, message).
    
    Returns:
        List of TimeseriesPoint(date, value, metadata) tuples.
        
    Example:
        >>> points = extract_field_values(scenes, "B08", bbox, mask, out_shape=(512, 512))
    """
    if scl_cloud_classes is None:
        scl_cloud_classes = [3, 8, 9, 10]  # Shadow, Medium cloud, High cloud, Cirrus
    
    if out_shape is None:
        out_shape = field_mask.shape
    
    results = []
    total = len(scenes)
    
    for i, scene in enumerate(scenes):
        if progress_callback:
            progress_callback(i + 1, total, f"Processing scene {i + 1}/{total}")
        
        try:
            # Read the requested band
            data = read_band(scene.item, asset_key, bbox, out_shape=out_shape)
            
            # Check for cloud cover if S2 and SCL available
            cloud_fraction = 0.0
            if 'SCL' in scene.item.get('assets', {}):
                try:
                    scl = read_band(scene.item, 'SCL', bbox, dtype='uint8', out_shape=out_shape)
                    # Calculate cloud fraction within field
                    field_scl = scl[field_mask]
                    cloud_pixels = np.isin(field_scl, scl_cloud_classes)
                    cloud_fraction = np.mean(cloud_pixels)
                except Exception as e:
                    print(f"[extract_field_values] Could not read SCL for cloud check: {e}")
            
            # Skip if too cloudy
            if cloud_fraction > max_cloud_fraction:
                print(f"[extract_field_values] Skipping {scene.date.date()}: "
                      f"{cloud_fraction*100:.1f}% cloud over field")
                continue
            
            # Compute field statistics
            stats = compute_field_statistics(data, field_mask)
            
            if stats and stats['mean'] is not None:
                results.append(TimeseriesPoint(
                    date=scene.date,
                    value=stats['mean'],
                    metadata={
                        'std': stats['std'],
                        'min': stats['min'],
                        'max': stats['max'],
                        'count': stats['count'],
                        'cloud_fraction': cloud_fraction,
                        'scene_id': scene.item.get('id', 'unknown')
                    }
                ))
            else:
                print(f"[extract_field_values] No valid pixels for {scene.date.date()}")
                
        except KeyError as e:
            print(f"[extract_field_values] Asset '{asset_key}' not found in scene {scene.date.date()}: {e}")
            continue
        except Exception as e:
            print(f"[extract_field_values] Error processing scene {scene.date.date()}: {e}")
            continue
    
    print(f"[extract_field_values] Extracted {len(results)} valid observations from {total} scenes")
    return results


def compute_ndvi_for_scene(
    scene: SceneResult,
    bbox: List[float],
    field_mask: np.ndarray,
    out_shape: Tuple[int, int]
) -> Optional[TimeseriesPoint]:
    """
    Compute NDVI for a single scene with cloud filtering.
    
    Args:
        scene: SceneResult with date and STAC item.
        bbox: Bounding box [min_lon, min_lat, max_lon, max_lat].
        field_mask: Boolean mask array (True = inside field).
        out_shape: (rows, cols) to resample to.
    
    Returns:
        TimeseriesPoint if successful, None if failed or too cloudy.
    """
    try:
        # Read RED and NIR bands
        red = read_band(scene.item, 'B04', bbox, out_shape=out_shape)
        nir = read_band(scene.item, 'B08', bbox, out_shape=out_shape)
        
        # Check cloud cover using SCL
        cloud_fraction = 0.0
        if 'SCL' in scene.item.get('assets', {}):
            scl = read_band(scene.item, 'SCL', bbox, dtype='uint8', out_shape=out_shape)
            field_scl = scl[field_mask]
            cloud_pixels = np.isin(field_scl, [3, 8, 9, 10])
            cloud_fraction = np.mean(cloud_pixels)
            
            if cloud_fraction > 0.5:
                return None
        
        # Compute NDVI with safe division
        with np.errstate(divide='ignore', invalid='ignore'):
            ndvi = np.where(
                (nir + red) != 0,
                (nir - red) / (nir + red),
                np.nan
            )
        
        # Compute field statistics
        stats = compute_field_statistics(ndvi, field_mask)
        
        if stats and stats['mean'] is not None:
            return TimeseriesPoint(
                date=scene.date,
                value=stats['mean'],
                metadata={
                    'std': stats['std'],
                    'min': stats['min'],
                    'max': stats['max'],
                    'count': stats['count'],
                    'cloud_fraction': cloud_fraction,
                    'scene_id': scene.item.get('id', 'unknown')
                }
            )
        return None
        
    except Exception as e:
        print(f"[compute_ndvi_for_scene] Error: {e}")
        return None


def fetch_ndvi_timeseries(
    lat: float,
    lon: float,
    radius_m: float = 500.0,
    start_date: str = "2023-01-01",
    end_date: str = "2026-01-31",
    max_cloud_cover: float = 50.0,
    buffer_degrees: float = None,
    progress_callback: Callable[[int, int, str], None] = None
) -> Dict[str, Any]:
    """
    High-level function to fetch NDVI timeseries for a circular field.
    
    This is the main entry point for Phase B historical data analysis.
    Creates a circular boundary, fetches S2 scenes, computes NDVI per scene,
    and returns a structured result with dates and NDVI values.
    
    Args:
        lat: Latitude of field center (WGS84 decimal degrees).
        lon: Longitude of field center (WGS84 decimal degrees).
        radius_m: Radius of circular field in meters (default 500m).
        start_date: Start date in ISO format (YYYY-MM-DD).
        end_date: End date in ISO format (YYYY-MM-DD).
        max_cloud_cover: Maximum scene cloud cover percentage (default 50%).
        buffer_degrees: Bounding box buffer in degrees. If None, computed from radius.
        progress_callback: Optional callback(current, total, message).
    
    Returns:
        dict with keys:
            - 'dates': List of datetime objects
            - 'ndvi': List of mean NDVI values
            - 'metadata': List of per-scene metadata dicts
            - 'boundary': The circular boundary GeoJSON
            - 'bbox': Bounding box used for queries
            - 'summary': Dict with min, max, mean, std, count
    
    Example:
        >>> result = fetch_ndvi_timeseries(-1.5, 35.2, radius_m=400,
        ...                                start_date="2023-01-01", 
        ...                                end_date="2024-12-31")
        >>> print(f"NDVI range: {result['summary']['min']:.2f} to {result['summary']['max']:.2f}")
        >>> for d, v in zip(result['dates'][:5], result['ndvi'][:5]):
        ...     print(f"  {d.date()}: {v:.3f}")
    """
    print(f"[fetch_ndvi_timeseries] Starting for ({lat}, {lon}), radius={radius_m}m")
    print(f"[fetch_ndvi_timeseries] Date range: {start_date} to {end_date}")
    
    # 1. Create circular boundary
    boundary = create_circular_boundary(lat, lon, radius_m)
    print(f"[fetch_ndvi_timeseries] Field area: {boundary['properties']['area_ha']:.2f} ha")
    
    # 2. Compute bounding box
    # Convert radius to approximate degrees if buffer not specified
    if buffer_degrees is None:
        # Rough approximation: 1 degree ≈ 111km at equator
        buffer_degrees = (radius_m / 111000.0) * 1.5  # Add 50% padding
    
    bbox = get_bbox(lat, lon, buffer_degrees)
    print(f"[fetch_ndvi_timeseries] Bbox: {bbox}")
    
    # 3. Fetch S2 scenes
    if progress_callback:
        progress_callback(0, 0, "Fetching scene catalog...")
    
    scenes = fetch_timeseries(
        lat=lat,
        lon=lon,
        buffer=buffer_degrees,
        start_date=start_date,
        end_date=end_date,
        collections=["s2_l2a"],
        max_cloud_cover=max_cloud_cover
    )
    
    if not scenes:
        print("[fetch_ndvi_timeseries] No scenes found!")
        return {
            'dates': [],
            'ndvi': [],
            'metadata': [],
            'boundary': boundary,
            'bbox': bbox,
            'summary': {'min': None, 'max': None, 'mean': None, 'std': None, 'count': 0}
        }
    
    # 4. Create field mask using first scene to establish grid
    # Read a band to get the reference shape
    ref_item = scenes[0].item
    try:
        ref_band = read_band(ref_item, 'B04', bbox)
        ref_shape = ref_band.shape
        print(f"[fetch_ndvi_timeseries] Reference shape: {ref_shape}")
    except Exception as e:
        print(f"[fetch_ndvi_timeseries] Error reading reference band: {e}")
        # Use a default shape
        ref_shape = (512, 512)
    
    # Get EPSG from first scene if available
    epsg = ref_item.get('properties', {}).get('proj:epsg')
    
    # Create field mask
    field_mask = create_field_mask(boundary, ref_shape, bbox, epsg=epsg)
    mask_coverage = np.mean(field_mask) * 100
    print(f"[fetch_ndvi_timeseries] Field mask coverage: {mask_coverage:.1f}%")
    
    # 5. Process each scene and compute NDVI
    dates = []
    ndvi_values = []
    metadata_list = []
    
    total = len(scenes)
    for i, scene in enumerate(scenes):
        if progress_callback:
            progress_callback(i + 1, total, f"Computing NDVI for scene {i + 1}/{total}")
        
        result = compute_ndvi_for_scene(scene, bbox, field_mask, ref_shape)
        
        if result:
            dates.append(result.date)
            ndvi_values.append(result.value)
            metadata_list.append(result.metadata)
    
    print(f"[fetch_ndvi_timeseries] Extracted {len(dates)} valid NDVI observations")
    
    # 6. Compute summary statistics
    if ndvi_values:
        ndvi_array = np.array(ndvi_values)
        summary = {
            'min': float(np.min(ndvi_array)),
            'max': float(np.max(ndvi_array)),
            'mean': float(np.mean(ndvi_array)),
            'std': float(np.std(ndvi_array)),
            'count': len(ndvi_values)
        }
    else:
        summary = {'min': None, 'max': None, 'mean': None, 'std': None, 'count': 0}
    
    return {
        'dates': dates,
        'ndvi': ndvi_values,
        'metadata': metadata_list,
        'boundary': boundary,
        'bbox': bbox,
        'summary': summary
    }


def fetch_multi_index_timeseries(
    lat: float,
    lon: float,
    radius_m: float = 500.0,
    start_date: str = "2023-01-01",
    end_date: str = "2026-01-31",
    indices: List[str] = None,
    max_cloud_cover: float = 50.0,
    progress_callback: Callable[[int, int, str], None] = None
) -> Dict[str, Any]:
    """
    Fetch timeseries for multiple vegetation indices simultaneously.
    
    Supported indices: 'ndvi', 'evi', 'ndmi', 'ndwi', 'ndre'
    
    Args:
        lat: Latitude of field center.
        lon: Longitude of field center.
        radius_m: Radius of circular field in meters.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        indices: List of index names to compute. Defaults to ['ndvi', 'evi'].
        max_cloud_cover: Maximum scene cloud cover percentage.
        progress_callback: Optional callback(current, total, message).
    
    Returns:
        dict with keys:
            - 'dates': List of datetime objects
            - '<index_name>': List of values for each index
            - 'metadata': Per-scene metadata
            - 'boundary': Field boundary GeoJSON
            - 'bbox': Bounding box used
            - 'summary': Per-index summary statistics
    """
    if indices is None:
        indices = ['ndvi', 'evi']
    
    print(f"[fetch_multi_index_timeseries] Computing indices: {indices}")
    
    # Create boundary and bbox
    boundary = create_circular_boundary(lat, lon, radius_m)
    buffer_degrees = (radius_m / 111000.0) * 1.5
    bbox = get_bbox(lat, lon, buffer_degrees)
    
    # Fetch scenes
    scenes = fetch_timeseries(
        lat=lat,
        lon=lon,
        buffer=buffer_degrees,
        start_date=start_date,
        end_date=end_date,
        collections=["s2_l2a"],
        max_cloud_cover=max_cloud_cover
    )
    
    if not scenes:
        return {
            'dates': [],
            **{idx: [] for idx in indices},
            'metadata': [],
            'boundary': boundary,
            'bbox': bbox,
            'summary': {idx: {'count': 0} for idx in indices}
        }
    
    # Setup reference shape and mask
    ref_item = scenes[0].item
    try:
        ref_band = read_band(ref_item, 'B04', bbox)
        ref_shape = ref_band.shape
    except Exception:
        ref_shape = (512, 512)
    
    epsg = ref_item.get('properties', {}).get('proj:epsg')
    field_mask = create_field_mask(boundary, ref_shape, bbox, epsg=epsg)
    
    # Process scenes
    dates = []
    index_values = {idx: [] for idx in indices}
    metadata_list = []
    
    total = len(scenes)
    for i, scene in enumerate(scenes):
        if progress_callback:
            progress_callback(i + 1, total, f"Processing scene {i + 1}/{total}")
        
        try:
            values, meta = _compute_indices_for_scene(
                scene, bbox, field_mask, ref_shape, indices
            )
            
            if values:
                dates.append(scene.date)
                for idx in indices:
                    index_values[idx].append(values.get(idx))
                metadata_list.append(meta)
                
        except Exception as e:
            print(f"[fetch_multi_index_timeseries] Error on scene {scene.date.date()}: {e}")
            continue
    
    # Compute summary statistics
    summary = {}
    for idx in indices:
        vals = [v for v in index_values[idx] if v is not None]
        if vals:
            arr = np.array(vals)
            summary[idx] = {
                'min': float(np.min(arr)),
                'max': float(np.max(arr)),
                'mean': float(np.mean(arr)),
                'std': float(np.std(arr)),
                'count': len(vals)
            }
        else:
            summary[idx] = {'count': 0}
    
    return {
        'dates': dates,
        **index_values,
        'metadata': metadata_list,
        'boundary': boundary,
        'bbox': bbox,
        'summary': summary
    }


def _compute_indices_for_scene(
    scene: SceneResult,
    bbox: List[float],
    field_mask: np.ndarray,
    out_shape: Tuple[int, int],
    indices: List[str]
) -> Tuple[Optional[Dict[str, float]], Dict[str, Any]]:
    """
    Compute multiple vegetation indices for a single scene.
    
    Returns:
        Tuple of (values_dict, metadata_dict) or (None, {}) if failed.
    """
    item = scene.item
    
    # Read all potentially needed bands
    bands = {}
    band_map = {
        'B02': 'blue',
        'B03': 'green', 
        'B04': 'red',
        'B05': 'red_edge',
        'B08': 'nir',
        'B11': 'swir'
    }
    
    # Determine which bands we need
    needed = set()
    for idx in indices:
        if idx == 'ndvi':
            needed.update(['B04', 'B08'])
        elif idx == 'evi':
            needed.update(['B02', 'B04', 'B08'])
        elif idx == 'ndmi':
            needed.update(['B08', 'B11'])
        elif idx == 'ndwi':
            needed.update(['B03', 'B08'])
        elif idx == 'ndre':
            needed.update(['B05', 'B08'])
    
    # Read needed bands
    for band_key in needed:
        try:
            bands[band_map[band_key]] = read_band(item, band_key, bbox, out_shape=out_shape)
        except Exception as e:
            print(f"[_compute_indices_for_scene] Failed to read {band_key}: {e}")
            return None, {}
    
    # Check cloud cover
    cloud_fraction = 0.0
    if 'SCL' in item.get('assets', {}):
        try:
            scl = read_band(item, 'SCL', bbox, dtype='uint8', out_shape=out_shape)
            field_scl = scl[field_mask]
            cloud_pixels = np.isin(field_scl, [3, 8, 9, 10])
            cloud_fraction = np.mean(cloud_pixels)
            
            if cloud_fraction > 0.5:
                return None, {}
        except Exception:
            pass
    
    # Compute indices
    values = {}
    
    with np.errstate(divide='ignore', invalid='ignore'):
        if 'ndvi' in indices and 'red' in bands and 'nir' in bands:
            red, nir = bands['red'], bands['nir']
            ndvi = np.where((nir + red) != 0, (nir - red) / (nir + red), np.nan)
            stats = compute_field_statistics(ndvi, field_mask)
            values['ndvi'] = stats['mean'] if stats else None
        
        if 'evi' in indices and all(k in bands for k in ['red', 'nir', 'blue']):
            red, nir, blue = bands['red'], bands['nir'], bands['blue']
            # EVI = 2.5 * (NIR - RED) / (NIR + 6*RED - 7.5*BLUE + 1)
            denom = nir + 6 * red - 7.5 * blue + 1
            evi = np.where(denom != 0, 2.5 * (nir - red) / denom, np.nan)
            evi = np.clip(evi, -1, 1)
            stats = compute_field_statistics(evi, field_mask)
            values['evi'] = stats['mean'] if stats else None
        
        if 'ndmi' in indices and 'nir' in bands and 'swir' in bands:
            nir, swir = bands['nir'], bands['swir']
            ndmi = np.where((nir + swir) != 0, (nir - swir) / (nir + swir), np.nan)
            stats = compute_field_statistics(ndmi, field_mask)
            values['ndmi'] = stats['mean'] if stats else None
        
        if 'ndwi' in indices and 'green' in bands and 'nir' in bands:
            green, nir = bands['green'], bands['nir']
            ndwi = np.where((green + nir) != 0, (green - nir) / (green + nir), np.nan)
            stats = compute_field_statistics(ndwi, field_mask)
            values['ndwi'] = stats['mean'] if stats else None
        
        if 'ndre' in indices and 'red_edge' in bands and 'nir' in bands:
            red_edge, nir = bands['red_edge'], bands['nir']
            ndre = np.where((nir + red_edge) != 0, (nir - red_edge) / (nir + red_edge), np.nan)
            stats = compute_field_statistics(ndre, field_mask)
            values['ndre'] = stats['mean'] if stats else None
    
    metadata = {
        'cloud_fraction': cloud_fraction,
        'scene_id': item.get('id', 'unknown')
    }
    
    return values, metadata


def fetch_lst_timeseries(
    lat: float,
    lon: float,
    radius_m: float = 500.0,
    start_date: str = "2023-01-01",
    end_date: str = "2026-01-31",
    max_cloud_cover: float = 30.0,
    progress_callback: Callable[[int, int, str], None] = None
) -> Dict[str, Any]:
    """
    Fetch Land Surface Temperature timeseries from Landsat.
    
    Args:
        lat: Latitude of field center.
        lon: Longitude of field center.
        radius_m: Radius of circular field in meters.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        max_cloud_cover: Maximum scene cloud cover percentage (stricter for LST).
        progress_callback: Optional callback.
    
    Returns:
        dict with 'dates', 'lst' (in Kelvin), 'metadata', 'boundary', 'bbox', 'summary'
    """
    print(f"[fetch_lst_timeseries] Starting for ({lat}, {lon})")
    
    boundary = create_circular_boundary(lat, lon, radius_m)
    buffer_degrees = (radius_m / 111000.0) * 2.0  # Larger buffer for Landsat 30m resolution
    bbox = get_bbox(lat, lon, buffer_degrees)
    
    # Fetch Landsat thermal scenes
    scenes = fetch_timeseries(
        lat=lat,
        lon=lon,
        buffer=buffer_degrees,
        start_date=start_date,
        end_date=end_date,
        collections=["ls9_st"],
        max_cloud_cover=max_cloud_cover
    )
    
    if not scenes:
        return {
            'dates': [],
            'lst': [],
            'metadata': [],
            'boundary': boundary,
            'bbox': bbox,
            'summary': {'count': 0}
        }
    
    # Setup mask
    ref_item = scenes[0].item
    try:
        ref_band = read_band(ref_item, 'ST_B10', bbox)
        ref_shape = ref_band.shape
    except Exception:
        ref_shape = (256, 256)
    
    epsg = ref_item.get('properties', {}).get('proj:epsg')
    field_mask = create_field_mask(boundary, ref_shape, bbox, epsg=epsg)
    
    # Extract LST values
    points = extract_field_values(
        scenes=scenes,
        asset_key='ST_B10',
        bbox=bbox,
        field_mask=field_mask,
        out_shape=ref_shape,
        max_cloud_fraction=0.3,  # Stricter for thermal
        progress_callback=progress_callback
    )
    
    dates = [p.date for p in points]
    lst_values = [p.value for p in points]
    metadata_list = [p.metadata for p in points]
    
    # Summary
    if lst_values:
        arr = np.array(lst_values)
        summary = {
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'mean': float(np.mean(arr)),
            'std': float(np.std(arr)),
            'count': len(lst_values)
        }
    else:
        summary = {'count': 0}
    
    return {
        'dates': dates,
        'lst': lst_values,
        'metadata': metadata_list,
        'boundary': boundary,
        'bbox': bbox,
        'summary': summary
    }


def fetch_rainfall_timeseries(
    lat: float,
    lon: float,
    radius_m: float = 500.0,
    start_date: str = "2023-01-01",
    end_date: str = "2026-01-31",
    progress_callback: Callable[[int, int, str], None] = None
) -> Dict[str, Any]:
    """
    Fetch daily rainfall timeseries from CHIRPS.
    
    Args:
        lat: Latitude of field center.
        lon: Longitude of field center.
        radius_m: Radius of circular field in meters.
        start_date: Start date (YYYY-MM-DD).
        end_date: End date (YYYY-MM-DD).
        progress_callback: Optional callback.
    
    Returns:
        dict with 'dates', 'rainfall' (mm/day), 'metadata', 'boundary', 'bbox', 'summary'
    """
    print(f"[fetch_rainfall_timeseries] Starting for ({lat}, {lon})")
    
    boundary = create_circular_boundary(lat, lon, radius_m)
    buffer_degrees = (radius_m / 111000.0) * 3.0  # Larger buffer for CHIRPS ~5km resolution
    bbox = get_bbox(lat, lon, buffer_degrees)
    
    # Fetch CHIRPS scenes (no cloud filter needed)
    scenes = fetch_timeseries(
        lat=lat,
        lon=lon,
        buffer=buffer_degrees,
        start_date=start_date,
        end_date=end_date,
        collections=["rainfall_chirps_daily"],
        max_cloud_cover=100.0  # No cloud filter for rainfall
    )
    
    if not scenes:
        return {
            'dates': [],
            'rainfall': [],
            'metadata': [],
            'boundary': boundary,
            'bbox': bbox,
            'summary': {'count': 0}
        }
    
    # Setup mask
    ref_item = scenes[0].item
    try:
        ref_band = read_band(ref_item, 'rainfall', bbox)
        ref_shape = ref_band.shape
    except Exception:
        ref_shape = (64, 64)  # CHIRPS is lower resolution
    
    field_mask = create_field_mask(boundary, ref_shape, bbox, epsg=4326)
    
    # Extract rainfall values
    points = extract_field_values(
        scenes=scenes,
        asset_key='rainfall',
        bbox=bbox,
        field_mask=field_mask,
        out_shape=ref_shape,
        max_cloud_fraction=1.0,  # No cloud filtering for rainfall
        progress_callback=progress_callback
    )
    
    dates = [p.date for p in points]
    rainfall_values = [p.value for p in points]
    metadata_list = [p.metadata for p in points]
    
    # Summary
    if rainfall_values:
        arr = np.array(rainfall_values)
        summary = {
            'min': float(np.min(arr)),
            'max': float(np.max(arr)),
            'mean': float(np.mean(arr)),
            'std': float(np.std(arr)),
            'total': float(np.sum(arr)),
            'count': len(rainfall_values)
        }
    else:
        summary = {'count': 0}
    
    return {
        'dates': dates,
        'rainfall': rainfall_values,
        'metadata': metadata_list,
        'boundary': boundary,
        'bbox': bbox,
        'summary': summary
    }
