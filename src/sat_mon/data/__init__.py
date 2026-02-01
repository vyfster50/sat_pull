"""
Data fetching and management module for sat_mon.

This module provides functions for:
- STAC API queries (stac.py)
- Satellite data composites (composite.py)
- Weather data (weather.py)
- Historical timeseries (timeseries.py)
"""

from .stac import search_stac, get_bbox, read_band
from .composite import get_satellite_data
from .timeseries import (
    fetch_timeseries,
    extract_field_values,
    fetch_ndvi_timeseries,
    fetch_multi_index_timeseries,
    fetch_lst_timeseries,
    fetch_rainfall_timeseries,
    SceneResult,
    TimeseriesPoint
)

__all__ = [
    # stac
    'search_stac',
    'get_bbox', 
    'read_band',
    # composite
    'get_satellite_data',
    # timeseries
    'fetch_timeseries',
    'extract_field_values',
    'fetch_ndvi_timeseries',
    'fetch_multi_index_timeseries',
    'fetch_lst_timeseries',
    'fetch_rainfall_timeseries',
    'SceneResult',
    'TimeseriesPoint',
]
