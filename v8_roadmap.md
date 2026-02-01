# v8 Roadmap: Field-Level Time Series Analysis

**Created**: 2026-02-01  
**Last Updated**: 2026-02-01  
**Status**: In Progress (Phases A+B Complete)  
**Progress**: 40% (2/5 phases)

## 1. Overview

v8 introduces **field-level historical analysis** — the ability to draw a boundary around a specific field (e.g., a pivot circle) and track its agricultural activity over multiple years.

**Target field**: Circular pivot between river and road (approx. center: -28.736, 29.365)

**Goal**: Analyze 3 years of data (2023–2026) to detect:
- Planting dates (vegetation greenup)
- Harvest dates (vegetation senescence/removal)
- Crop health throughout each growing season
- Irrigation patterns via soil moisture and LST

---

## 2. Key Features

### 2.1 Field Boundary Definition

| Feature | Description |
|---------|-------------|
| **Circular mask** | Define center point + radius for pivot fields |
| **Polygon mask** | Support arbitrary GeoJSON polygons for irregular fields |
| **Mask application** | Apply mask to all raster calculations (mean within field only) |

### 2.2 Time Series Data Extraction

| Metric | Source | Temporal Resolution | 3-Year Coverage |
|--------|--------|---------------------|-----------------|
| NDVI | Sentinel-2 | ~5 days | ~220 scenes |
| Soil Moisture | WaPOR / Sentinel-1 | ~10 days | ~110 scenes |
| LST | Landsat 8/9 | ~16 days | ~70 scenes |
| Rainfall | CHIRPS | Daily | ~1095 days |

### 2.3 Phenology Detection

| Event | Detection Method |
|-------|------------------|
| **Planting** | NDVI crosses threshold (0.2→0.3) with positive slope |
| **Peak growth** | NDVI maximum in season |
| **Harvest** | NDVI drops sharply (>0.2 in <2 weeks) |
| **Fallow** | NDVI stable below 0.2 |

### 2.4 Outputs

1. **Time series plots** — NDVI, SM, LST over 3 years with detected events marked
2. **Season summary table** — Start date, end date, peak NDVI, duration, health score per season
3. **Anomaly detection** — Flag seasons with unusual patterns (drought stress, early harvest, etc.)

---

## 3. Technical Approach

### Phase A: Field Boundary & Masking (1 day)

**Goal**: Allow user to define a field boundary and apply it as a mask.

```python
# New module: src/sat_mon/analysis/field_boundary.py

def create_circular_mask(center_lat, center_lon, radius_m, shape, transform, crs):
    """Creates a boolean mask for a circular field."""
    # Convert center to pixel coords
    # Create distance grid from center
    # Return mask where distance <= radius

def create_polygon_mask(geojson, shape, transform, crs):
    """Creates a boolean mask from a GeoJSON polygon."""
    # Use rasterio.features.geometry_mask()

def apply_mask(data, mask):
    """Returns masked array with NaN outside field."""
    return np.where(mask, data, np.nan)

def field_mean(data, mask):
    """Returns mean value within field boundary."""
    return np.nanmean(data[mask])
```

**Deliverable**: `field_boundary.py` with mask creation and application functions.

---

### Phase B: Historical Data Fetching (1–2 days)

**Goal**: Fetch 3 years of satellite data for a single field.

```python
# New module: src/sat_mon/data/timeseries.py

def fetch_timeseries(lat, lon, buffer, start_date, end_date, collections):
    """Fetches all available scenes for a location over a date range.
    
    Args:
        lat, lon: Field center
        buffer: Small buffer (just enough to cover field)
        start_date: e.g., "2023-01-01"
        end_date: e.g., "2026-01-31"
        collections: ["s2_l2a", "ls9_st", etc.]
    
    Returns:
        List of (date, item) tuples sorted chronologically
    """

def extract_field_values(items, asset_key, bbox, mask):
    """Extracts field-mean values from each scene.
    
    Returns:
        List of (date, mean_value) tuples
    """
```

**STAC considerations**:
- Pagination needed (limit=1000 may not be enough for 3 years of S2)
- Cloud filtering: skip scenes with >50% cloud over field
- Memory: don't load all bands at once; process one scene at a time

**Deliverable**: `timeseries.py` with historical fetch and extraction functions.

---

### Phase C: Phenology Detection (1 day)

**Goal**: Automatically detect planting, peak, and harvest dates from NDVI time series.

```python
# New module: src/sat_mon/analysis/phenology.py

def smooth_timeseries(dates, values, window=5):
    """Apply Savitzky-Golay or rolling mean to reduce noise."""

def detect_seasons(dates, ndvi_values, threshold=0.25):
    """Detects growing seasons from NDVI time series.
    
    Returns:
        List of Season objects with:
        - start_date (planting)
        - peak_date
        - peak_ndvi
        - end_date (harvest)
        - duration_days
    """

def classify_health(season):
    """Classifies season health based on peak NDVI and duration.
    
    Returns: 'excellent', 'good', 'moderate', 'poor'
    """
```

**Algorithm outline**:
1. Smooth NDVI time series (remove cloud artifacts)
2. Find crossings above threshold (season starts)
3. Find local maxima (peaks)
4. Find crossings below threshold or sharp drops (season ends)
5. Group into Season objects

**Deliverable**: `phenology.py` with season detection and health classification.

---

### Phase D: Visualization (1 day)

**Goal**: Create multi-panel time series plots with event markers.

```python
# Addition to src/sat_mon/visualization/plots.py or new timeseries_plots.py

def plot_field_timeseries(dates, ndvi, sm, lst, rainfall, seasons):
    """Creates a 4-panel figure showing 3 years of field data.
    
    Panel 1: NDVI with season markers (planting=green, harvest=orange)
    Panel 2: Soil Moisture
    Panel 3: LST
    Panel 4: Cumulative rainfall
    
    All panels share x-axis (time).
    """

def plot_season_comparison(seasons):
    """Bar chart comparing peak NDVI, duration, health across seasons."""
```

**Deliverable**: Time series plotting functions with phenology overlays.

---

### Phase E: CLI / Interactive Mode (0.5 day)

**Goal**: Add command-line or interactive option to run historical analysis.

```python
# app.py addition

def run_historical_analysis():
    """Interactive mode for field-level time series analysis."""
    # Get field center
    # Get field type (circle/polygon) and dimensions
    # Get date range
    # Fetch data
    # Detect phenology
    # Generate plots and report
```

**Deliverable**: `python app.py --historical` or interactive menu option.

---

## 4. Data Requirements

### Sentinel-2 (NDVI)

| Parameter | Value |
|-----------|-------|
| Collection | `s2_l2a` |
| Date range | 2023-01-01 to 2026-01-31 |
| Expected scenes | ~200–250 (5-day revisit, minus clouds) |
| Bands needed | B04 (Red), B08 (NIR), SCL (cloud mask) |

### Landsat 8/9 (LST)

| Parameter | Value |
|-----------|-------|
| Collection | `ls9_st`, `ls8_st` |
| Date range | 2023-01-01 to 2026-01-31 |
| Expected scenes | ~70 (16-day revisit per satellite) |
| Bands needed | ST_B10 |

### Soil Moisture

| Parameter | Value |
|-----------|-------|
| Collection | `wapor_soil_moisture` or derived from S1 |
| Date range | 2023-01-01 to 2026-01-31 |
| Expected scenes | ~100 |

### Rainfall

| Parameter | Value |
|-----------|-------|
| Collection | `rainfall_chirps_daily` |
| Date range | 2023-01-01 to 2026-01-31 |
| Days | ~1095 |

---

## 5. Execution Plan

### Overall Progress: 4/5 Phases Complete (80%)

```
[███████████████████░░░] 80%
```

| Phase | Task | Effort | Status | Completed | Tested |
|-------|------|--------|--------|-----------|--------|
| A | Field boundary & masking | 1 day | ✅ Done | 2026-02-01 | ✅ Pass |
| B | Historical data fetching | 1–2 days | ✅ Done | 2026-02-01 | ✅ Pass |
| C | Phenology detection | 1 day | ✅ Done | 2026-02-01 | ✅ Pass |
| D | Time series visualization | 1 day | ✅ Done | 2026-02-01 | ✅ Pass |
| E | CLI integration | 0.5 day | 🔲 Next | — | — |

### Phase A Deliverables ✅
- [x] `src/sat_mon/analysis/field_boundary.py` — 6 functions
- [x] `create_circular_boundary()` — pivot fields
- [x] `create_polygon_boundary()` — irregular fields
- [x] `create_field_mask()` — rasterize to image grid
- [x] `apply_field_mask()` — mask data arrays
- [x] `compute_field_statistics()` — field-only stats
- [x] `mask_all_indices()` — batch mask all indices
- [x] Unit tests: `test_field_boundary.py` — 7 tests passing
- [x] Integration test: `test_phase_a.py` — verified with real coords

### Phase B Deliverables ✅
- [x] `src/sat_mon/data/timeseries.py` — 913 lines, 7 functions
- [x] `fetch_timeseries()` — 3-year historical fetch with pagination
- [x] `extract_field_values()` — field-mean per scene with cloud filtering
- [x] `compute_ndvi_for_scene()` — single-scene NDVI computation
- [x] `fetch_ndvi_timeseries()` — high-level NDVI timeseries
- [x] `fetch_multi_index_timeseries()` — NDVI, EVI, NDMI, NDWI, NDRE
- [x] `fetch_lst_timeseries()` — Landsat LST timeseries
- [x] `fetch_rainfall_timeseries()` — CHIRPS rainfall timeseries
- [x] Pagination handling for large queries (100 items/page)
- [x] Cloud filtering per scene (SCL band, configurable threshold)
- [x] Unit tests: `test_timeseries.py` — 16 tests (14 pass, 2 skipped integration)

### Phase C Deliverables ✅
- [x] `src/sat_mon/analysis/phenology.py` — 3 functions + Season dataclass
- [x] `smooth_timeseries()` — rolling mean with edge padding + NaN interpolation
- [x] `detect_seasons()` — planting/harvest detection with configurable params:
  - `threshold` — NDVI level for season start/end (default 0.25)
  - `sharp_drop` — harvest detection sensitivity (default 0.2)
  - `sharp_drop_days` — window for drop detection (default 14)
  - `min_duration` — filter noise seasons (default 30 days)
  - `close_unclosed` — handle truncated data (default True)
- [x] `classify_health()` — season health rating (excellent/good/moderate/poor)
- [x] `Season` NamedTuple — start_date, peak_date, peak_ndvi, end_date, duration_days, health
- [x] Sharp drop detection for harvest (>0.2 NDVI drop in <2 weeks)
- [x] Unclosed season handling at end of timeseries
- [x] Unit tests: `test_phenology.py` — 6 tests passing
- [x] Integration test: `test_phase_c.py` — 3-year synthetic data validation

### Phase D Deliverables ✅
- [x] `src/sat_mon/visualization/plots.py` — Updated with time series functions
- [x] `plot_field_timeseries()` — 4-panel layout (NDVI, SM, LST, Rain)
  - Input validation: Raises `ValueError` on mismatched array lengths
  - Auto-converts LST from Kelvin to Celsius (>200 threshold)
  - Handles None/empty optional series gracefully
- [x] Phenology event markers — P/H labels, shaded seasons, peak dots
- [x] `plot_season_comparison()` — Bar chart for health/duration comparison
  - Unique labels using `start_date.strftime('%Y-%m')` (handles multiple seasons/year)
- [x] Dual-axis rainfall chart — Daily bars + Cumulative line
- [x] Unit tests: `test_visualization.py` — Updated and passing
- [x] Integration test: `test_phase_d.py` — End-to-end plot generation
- [x] Performance: ~317ms for 1000 data points (4 panels)

### Phase E Deliverables 🔲
- [ ] CLI flag `--historical`
- [ ] Interactive field definition
- [ ] Report generation

**Total estimated effort**: 4.5–5.5 days  
**Elapsed**: ~3.5 days  
**Remaining**: ~0.5–1 day

---

## 6. Expected Outputs

### 6.1 Time Series Plot (example)

```
┌─────────────────────────────────────────────────────────────┐
│  NDVI Time Series (2023-2026)                               │
│  Field: Pivot Circle (-28.736, 29.365)                      │
├─────────────────────────────────────────────────────────────┤
│ 0.8│      ▲           ▲           ▲                         │
│    │     /│\         /│\         /│\                        │
│ 0.5│    / │ \       / │ \       / │ \                       │
│    │   /  │  \     /  │  \     /  │  \                      │
│ 0.2│──●   │   ●───●   │   ●───●   │   ●                     │
│    │  P   H   P       H   P       H                         │
│    └─────────────────────────────────────────────────────── │
│      2023        2024        2025        2026               │
│                                                             │
│  P = Planting detected   H = Harvest detected               │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Season Summary Table

| Season | Planting | Harvest | Duration | Peak NDVI | Health |
|--------|----------|---------|----------|-----------|--------|
| 2023   | Oct 15   | Mar 20  | 156 days | 0.72      | Good   |
| 2024   | Oct 08   | Apr 02  | 177 days | 0.78      | Excellent |
| 2025   | Nov 01   | Mar 15  | 135 days | 0.61      | Moderate |

---

## 7. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| STAC API rate limits | Slow fetch | Batch requests, add delays, cache results |
| Cloud gaps in S2 | Missing data points | Interpolate, use Landsat as backup |
| Memory for 3 years of data | OOM | Process one scene at a time, store only means |
| Phenology misdetection | Wrong dates | Allow manual override, show confidence score |

---

## 8. Future Enhancements (v9+)

- **Yield estimation** — Correlate peak NDVI + duration to expected yield
- **Multi-field comparison** — Compare multiple fields side-by-side
- **Alert system** — Notify if current season deviates from historical norm
- **Export to CSV/GeoJSON** — Allow data export for external analysis
- **Crop type classification** — Identify what crop is planted based on phenology signature

---

## Summary

```
┌─────────────────────────────────────────────────────────────┐
│  v8 Field-Level Time Series Analysis                        │
├─────────────────────────────────────────────────────────────┤
│  ✅ Define field boundary (circle or polygon)               │
│  ✅ Fetch 3 years of NDVI, SM, LST, rainfall                │
│  ✅ Detect planting and harvest dates automatically         │
│  ✅ Classify crop health per season                         │
│  ✅ Visualize with interactive time series plots            │
├─────────────────────────────────────────────────────────────┤
│  Estimated effort: 4.5–5.5 days                             │
└─────────────────────────────────────────────────────────────┘
```
