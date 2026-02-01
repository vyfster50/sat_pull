"""
GUI orchestrator - connects map interface to analysis pipeline.

Flow:
1) User draws field on map (rectangle or circle)
2) Orchestrator derives parameters (lat/lon, radius_m, dates)
3) Fetch NDVI / rainfall / LST
4) Print summary and display NDVI overlay
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from .map_window import MapWindow
from .raster_overlay import RasterOverlay
from ..data.timeseries import (
    fetch_ndvi_timeseries,
    fetch_rainfall_timeseries,
    fetch_lst_timeseries,
)


class GUIOrchestrator:
    """Orchestrates GUI selection → analysis → visualization."""

    def __init__(self):
        self.field_selection: Optional[Dict[str, Any]] = None
        self.analysis_results: Optional[Dict[str, Any]] = None

    def run(self) -> Optional[Dict[str, Any]]:
        """Run the complete GUI workflow."""
        self.field_selection = self._get_field_selection()
        if not self.field_selection:
            print("No field selected. Exiting GUI mode.")
            return None

        params = self._get_analysis_parameters(self.field_selection)
        self.analysis_results = self._run_analysis(params)
        self._display_results(self.field_selection, self.analysis_results)
        return self.analysis_results

    def _get_field_selection(self) -> Optional[Dict[str, Any]]:
        """Open the map window and return the selection after Analyze."""
        window = MapWindow(center_lat=-0.5, center_lon=37.5, zoom_level=8)
        window.create_window()
        window.setup_controls()
        window.show()
        return window.get_result()

    def _get_analysis_parameters(self, selection: Dict[str, Any]) -> Dict[str, Any]:
        """Derive lat/lon, radius_m, bbox and date range from selection."""
        center = selection['center']
        bbox = selection['bbox']

        # Determine radius in meters
        if selection['type'] == 'circle':
            radius_km = float(selection.get('radius_km', 1.0))
            radius_m = radius_km * 1000.0
        else:
            # Approximate radius from bbox max span
            lat_diff = abs(bbox[3] - bbox[1])
            lon_diff = abs(bbox[2] - bbox[0])
            # Convert degrees to meters at current latitude
            lat_m = lat_diff * 111_000.0
            lon_m = lon_diff * 111_000.0 * max(0.1, abs(math.cos(math.radians(center['lat']))))
            radius_m = max(lat_m, lon_m) / 2.0

        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=30)

        return {
            'lat': center['lat'],
            'lon': center['lon'],
            'radius_m': radius_m,
            'bbox': bbox,
            'start_date': start_dt.strftime('%Y-%m-%d'),
            'end_date': end_dt.strftime('%Y-%m-%d'),
        }

    def _run_analysis(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Fetch NDVI, rainfall, and LST using existing pipeline."""
        lat = params['lat']
        lon = params['lon']
        radius_m = params['radius_m']
        start_date = params['start_date']
        end_date = params['end_date']

        results: Dict[str, Any] = {'params': params}

        # NDVI
        try:
            ndvi = fetch_ndvi_timeseries(lat, lon, radius_m=radius_m, start_date=start_date, end_date=end_date)
            results['ndvi'] = ndvi.get('ndvi', [])
            results['ndvi_dates'] = ndvi.get('dates', [])
        except Exception as e:
            print(f"NDVI fetch failed: {e}")
            results['ndvi'] = []
            results['ndvi_dates'] = []

        # Rainfall
        try:
            rain = fetch_rainfall_timeseries(lat, lon, radius_m=radius_m, start_date=start_date, end_date=end_date)
            results['rainfall'] = rain.get('rainfall', [])
            results['rainfall_dates'] = rain.get('dates', [])
        except Exception as e:
            print(f"Rainfall fetch failed: {e}")
            results['rainfall'] = []
            results['rainfall_dates'] = []

        # LST
        try:
            lst = fetch_lst_timeseries(lat, lon, radius_m=radius_m, start_date=start_date, end_date=end_date)
            results['lst'] = lst.get('lst', [])
            results['lst_dates'] = lst.get('dates', [])
        except Exception as e:
            print(f"LST fetch failed: {e}")
            results['lst'] = []
            results['lst_dates'] = []

        return results

    def _display_results(self, selection: Dict[str, Any], results: Dict[str, Any]) -> None:
        """Print summary and show NDVI overlay if available."""
        # Text summary
        print("\n=== Analysis Summary ===")
        print(f"Location: {results['params']['lat']:.4f}, {results['params']['lon']:.4f}")
        print(f"Period: {results['params']['start_date']} → {results['params']['end_date']}")
        if results.get('ndvi'):
            vals = [v for v in results['ndvi'] if v is not None]
            if vals:
                print(f"NDVI: n={len(vals)} mean={sum(vals)/len(vals):.3f} min={min(vals):.3f} max={max(vals):.3f}")
        if results.get('rainfall'):
            rain_vals = [v for v in results['rainfall'] if v is not None]
            if rain_vals:
                print(f"Rainfall: n={len(rain_vals)} total={sum(rain_vals):.1f}mm mean={sum(rain_vals)/len(rain_vals):.1f}mm")
        if results.get('lst'):
            lst_vals = [v for v in results['lst'] if v is not None]
            if lst_vals:
                print(f"LST: n={len(lst_vals)} mean={sum(lst_vals)/len(lst_vals):.1f}")

        # Graphical NDVI overlay (summary-only for now)
        if results.get('ndvi'):
            overlay = RasterOverlay(selection)
            overlay.display_ndvi({'ndvi': results['ndvi']}, title="NDVI Analysis Results")
            overlay.show()


def run_gui_mode() -> Optional[Dict[str, Any]]:
    orchestrator = GUIOrchestrator()
    return orchestrator.run()
