# Crop Monitoring App v3 – Roadmap

## Overview

Building on v2's foundation (Sentinel-2 NDVI, LST, Sentinel-1 radar, rainfall, crop mask), v3 adds **5 new analytical layers** for comprehensive agricultural monitoring.

**Current Status (Jan 24, 2026):** Phase 1 ✅ complete. Phase 2 ✅ complete. Phase 3 ✅ complete. Processing pipeline fully operational with 8 alert rules and refined 3×3 visualization grid.

---

## Layer Status

| Layer | Status | Collection | Notes |
|-------|--------|------------|-------|
| Sentinel-2 NDVI | ✅ Done | `s2_l2a` | Primary vegetation index |
| Crop Mask | ✅ Done | `esa_worldcover_2021` | ESA WorldCover class 40 |
| HLS NDVI Fallback | 🔜 v3 | `ls8_sr` / `ls9_sr` | When S2 is cloudy |
| 7-day & 30-day Rain | 🔜 v3 | `rainfall_chirps_daily` | Accumulated precipitation |
| LST Anomaly | 🔜 v3 | `ls9_st` | Temperature deviation from baseline |
| Sentinel-1 Flooding | 🔜 v3 | `s1_rtc` | VV threshold-based detection |
| Soil Moisture (WaPOR) | 🔜 v3 | `wapor_soil_moisture` | Root zone moisture |

---

## New Layers – Technical Specification

### 1. HLS NDVI Fallback

**Purpose:** Provide NDVI when Sentinel-2 has >50% cloud cover

**Data Source:**
- Collections: `ls8_sr`, `ls9_sr` (Landsat 8/9 Surface Reflectance)
- Resolution: 30m
- Assets: `SR_B4` (Red), `SR_B5` (NIR), `QA_PIXEL`

**Implementation:**
```python
# Check S2 cloud cover from SCL band
cloud_pct = np.mean(np.isin(scl, [3, 8, 9, 10])) * 100

if cloud_pct > 50:
    # Fetch Landsat SR
    items_ls = search_stac(collections=["ls9_sr"], ...)
    red = read_band(item, "SR_B4", bbox)
    nir = read_band(item, "SR_B5", bbox)
    ndvi_fallback = (nir - red) / (nir + red)
```

**Output:** `ndvi_fallback` layer + `ndvi_source` indicator ("S2" or "Landsat")

---

### 2. Rainfall Accumulation (7-day & 30-day)

**Purpose:** Track precipitation trends for irrigation planning

**Data Source:**
- Collection: `rainfall_chirps_daily`
- Resolution: ~5km (0.05°)
- Asset: `rainfall`
- Latency: ~5-10 days

**Implementation:**
```python
# Fetch last 30 days
items_rain = search_stac(
    collections=["rainfall_chirps_daily"],
    bbox=bbox,
    limit=30,
    sortby=[{"field": "datetime", "direction": "desc"}]
)

# Stack and sum
rain_stack = np.stack([read_band(item, "rainfall", bbox) for item in items_rain])
rain_7d = np.sum(rain_stack[:7], axis=0)
rain_30d = np.sum(rain_stack, axis=0)
```

**Output:** `rain_7d`, `rain_30d` layers (mm accumulated)

**Thresholds:**
- 🔴 Drought: 7-day < 5mm AND 30-day < 30mm
- 🟡 Dry spell: 7-day < 10mm
- 🟢 Adequate: 7-day >= 10mm

---

### 3. LST Anomaly Detection

**Purpose:** Identify thermal stress relative to historical baseline

**Data Source:**
- Collection: `ls9_st` (also `ls8_st` for longer history)
- Resolution: 30m (100m thermal resampled)
- Asset: `ST_B10`
- Scale: `Kelvin = DN * 0.00341802 + 149.0`

**Implementation:**
```python
from datetime import datetime, timedelta

# Get current month
current_month = datetime.now().month

# Fetch historical data for same month (last 3 years)
historical_items = []
for year in [2023, 2024, 2025]:
    start = f"{year}-{current_month:02d}-01"
    end = f"{year}-{current_month:02d}-28"
    items = search_stac(collections=["ls9_st"], datetime=f"{start}/{end}", ...)
    historical_items.extend(items)

# Compute baseline (mean of historical)
lst_stack = np.stack([read_band(item, "ST_B10", bbox) for item in historical_items])
lst_baseline = np.nanmean(lst_stack, axis=0)

# Current LST
lst_current = read_band(current_item, "ST_B10", bbox)

# Anomaly = Current - Baseline
lst_anomaly = lst_current - lst_baseline
```

**Output:** `lst_anomaly` layer (°C deviation)

**Thresholds:**
- 🔴 Heat stress: anomaly > +5°C
- 🟡 Warm: anomaly > +2°C
- 🟢 Normal: -2°C to +2°C
- 🔵 Cool: anomaly < -2°C

---

### 4. Sentinel-1 Flood Detection

**Purpose:** Detect standing water and flooded vegetation

**Data Source:**
- Collection: `s1_rtc` (Gamma0 normalized backscatter)
- Resolution: 20m
- Assets: `vv`, `vh`, `mask`

**Implementation:**
```python
# Convert to dB
vv_db = 10 * np.log10(np.clip(vv_linear, 1e-5, None))
vh_db = 10 * np.log10(np.clip(vh_linear, 1e-5, None))

# Simple threshold for open water
FLOOD_THRESHOLD_VV = -15  # dB (adjustable)
flood_mask = vv_db < FLOOD_THRESHOLD_VV

# Optional: Flooded vegetation (dual-pol ratio)
# High VH/VV ratio can indicate flooded crops
vv_vh_ratio = vh_db - vv_db
flooded_veg = (vv_vh_ratio > -3) & (vv_db < -12)

# Combined flood map
flood_combined = flood_mask | flooded_veg
```

**Output:** `flood_mask` (binary), `flood_risk` (probability 0-1)

**Thresholds:**
- VV < -18 dB: Definite water
- VV < -15 dB: Likely flooded
- VV < -12 dB + high VH/VV: Flooded vegetation

---

### 5. Soil Moisture (WaPOR)

**Purpose:** Monitor root zone water availability

**Data Source:**
- Collection: `wapor_soil_moisture`
- Resolution: ~100m
- Asset: `relative_soil_moisture`
- Temporal: Dekadal (10-day intervals)
- Range: 2018-01-01 to present (~7 days latency)

**Implementation:**
```python
items_sm = search_stac(
    collections=["wapor_soil_moisture"],
    bbox=bbox,
    limit=1,
    sortby=[{"field": "datetime", "direction": "desc"}]
)

if items_sm:
    soil_moisture = read_band(items_sm[0], "relative_soil_moisture", bbox)
```

**Output:** `soil_moisture` layer (relative %, 0-100)

**Thresholds:**
- 🔴 Very dry: < 20%
- 🟡 Dry: 20-40%
- 🟢 Adequate: 40-70%
- 🔵 Wet: > 70%

---

## Updated Visualization Grid (3×3)

```
┌─────────────────┬─────────────────┬─────────────────┐
│ RGB Composite   │ NDVI            │ Crop Mask       │
│ (S2)            │ (S2/Landsat)    │ (WorldCover)    │
├─────────────────┼─────────────────┼─────────────────┤
│ LST             │ LST Anomaly     │ Flood Mask      │
│ (Landsat)       │ (vs baseline)   │ (S1 VV)         │
├─────────────────┼─────────────────┼─────────────────┤
│ Rain 7-day      │ Rain 30-day     │ Soil Moisture   │
│ (CHIRPS)        │ (CHIRPS)        │ (WaPOR)         │
└─────────────────┴─────────────────┴─────────────────┘
```

---

## Updated Alert Rules

| Alert | Condition | Severity |
|-------|-----------|----------|
| Water Stress | LST > 35°C AND NDVI < 0.3 | 🔴 High |
| Heat Anomaly | LST anomaly > +5°C | 🔴 High |
| Drought Risk | rain_7d < 5mm AND rain_30d < 30mm | 🔴 High |
| Flooding | flood_mask coverage > 10% | 🔴 High |
| Dry Spell | rain_7d < 10mm | 🟡 Medium |
| Low Soil Moisture | soil_moisture < 20% | 🟡 Medium |
| Poor Crop Health | NDVI < 0.25 | 🟡 Medium |
| Cloudy S2 | Using Landsat fallback | ℹ️ Info |

---

## Implementation Phases

### Phase 1: Core Data Acquisition ✅ COMPLETE
- [x] Add `sortby` to all STAC queries ✅ (done in v2)
- [x] Fetch 30-day rainfall stack → `rain_7d`, `rain_30d` arrays
- [x] Fetch WaPOR soil moisture → `relative_soil_moisture` band
- [x] Add Landsat SR fallback query → triggered when S2 cloud > 50%
- [x] Track NDVI source indicator → "S2" or "Landsat"
- **Status:** All data layers fetching successfully. 30-day rainfall tested (30 items stacked). WaPOR soil moisture available (latest 2025-03-11). Landsat SR fallback logic ready.

### Phase 2: Processing Pipeline ✅ COMPLETE
- [x] Implement rainfall accumulation (7d, 30d sums) ✅ (process_rainfall_accumulation)
- [x] Implement LST baseline computation ✅ (compute_lst_baseline)
- [x] Implement flood threshold detection ✅ (compute_flood_mask)
- [x] Add NDVI source switching logic ✅ (already in get_satellite_data)
- **Status:** All processing functions integrated into pipeline. 3×3 visualization grid active. 8 alert rules deployed.

### Phase 3: Visualization
- [x] Expand grid to 3×3 ✅
- [x] Add new colormaps (anomaly: diverging RdBu) ✅
- [x] Add data source indicators to titles ✅
- [x] Update colorbar labels ✅

### Phase 4: Alert System
- [ ] Add new alert rules
- [ ] Implement severity ranking
- [ ] Add composite risk score

---

## Dependencies

No new dependencies required. Current stack:
- `rasterio` – COG reading
- `numpy` – array processing
- `matplotlib` – visualization
- `requests` – STAC API

---

## Performance Considerations

| Operation | Est. Time | Optimization |
|-----------|-----------|--------------|
| 30-day rainfall fetch | ~30s | Parallel requests |
| LST baseline (3 years) | ~60s | Cache baseline locally |
| Landsat fallback | +10s | Only when S2 cloudy |
| WaPOR fetch | ~5s | Single dekadal item |

**Total estimated runtime:** ~90s (first run), ~45s (with cached baseline)

---

## API Reference

### Digital Earth Africa STAC Endpoint
```
POST https://explorer.digitalearth.africa/stac/search
```

### Key Collections
| Collection | Description |
|------------|-------------|
| `s2_l2a` | Sentinel-2 L2A |
| `ls9_sr` | Landsat 9 Surface Reflectance |
| `ls9_st` | Landsat 9 Surface Temperature |
| `s1_rtc` | Sentinel-1 RTC |
| `rainfall_chirps_daily` | CHIRPS Daily Rainfall |
| `wapor_soil_moisture` | WaPOR Root Zone Soil Moisture |
| `esa_worldcover_2021` | ESA WorldCover 2021 |
