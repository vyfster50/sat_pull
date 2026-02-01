# v6 Roadmap: ESRI Satellite Imagery Integration — Current Status

**Last validated**: 2026-02-01

## 1. Overview

v6's goal remains to provide a high-resolution ESRI World Imagery basemap as a ground-truth reference so users can compare 10m/20m Sentinel-2 layers against commercial imagery.

This document has been updated to reflect work completed in the codebase and to list remaining tasks.

## 2. Completed work ✅

### Dependencies

- [x] Added `contextily` to `requirements.txt`
- [x] Added `requests-cache` to `requirements.txt` and enabled a simple disk cache (`.cache/contextily_cache.sqlite`) for basemap requests to reduce repeated downloads during development

### Tile fetching & integration

- [x] Implemented `fetch_basemap_tiles(ax, bounds, crs, alpha, source)` in [plots.py](src/sat_mon/visualization/plots.py#L224-L258) using `contextily.add_basemap`
- [x] Implemented support for ESRI World Imagery and Google Satellite tile templates (selectable via the visualizer)
- [x] Added an `esri_satellite` entry to `CropMonitorVisualizer.layers_config` (line 33)
- [x] Exposed ESRI as selectable base layer in the UI (Base Layer radio includes "ESRI Satellite")

### UI

- [x] Base layer selector (Sentinel-2 RGB, Google, ESRI) implemented via RadioButtons
- [x] Overlay selection and opacity slider present (opacity applied to the active overlay)
- [x] Created alignment test script at [scripts/v6_esri_alignment_test.py](scripts/v6_esri_alignment_test.py)

## 3. Current behavior / implementation notes

| Function | Location | Notes |
|----------|----------|-------|
| `fetch_basemap_tiles()` | plots.py | Supports `source='esri'`, `'google'`, or custom URL; uses dynamic zoom via `_calculate_zoom()` |
| `get_extent()` | plots.py:207–222 | Derives extent from `raw_data['bbox']` and `raw_data['s2']['epsg']` |
| Request cache | plots.py:12–18 | `requests-cache` with 1-day expiry under `.cache/` |

**Key implementation details:**
- Zoom level is now dynamic in `fetch_basemap_tiles()` based on bbox width (see `_calculate_zoom()`)
- `get_extent()` returns `[left, right, bottom, top]` tuple and CRS string for coordinate transforms
- Opacity slider triggers full re-render on change (potential performance issue noted in code comments)

## 4. Gaps, risks and remaining tasks

### 🔴 Critical (must fix before release)

| Issue | Details | Effort |
|-------|---------|--------|
| **`get_extent()` lacks defensive coding** | No type checking for `epsg` (could be string/int from STAC), no try/except for CRS parsing, no fallback to EPSG:3857 | 1–2 hours | ✅ FIXED |
| **Alignment test uses mock data** | Current script at `scripts/v6_esri_alignment_test.py` uses `np.random.rand()` instead of real S2 data — doesn't actually validate alignment | 2–3 hours | ✅ FIXED |
| **🆕 ESRI map not rendering** | `fetch_basemap_tiles()` doesn't set axis limits before calling `cx.add_basemap()` — contextily needs limits to know what tiles to fetch | 15 min | ✅ FIXED |

**Root cause identified (2026-01-25):** Minimal test (`scripts/test_esri_minimal.py`) confirmed that `cx.add_basemap()` requires `ax.set_xlim()` and `ax.set_ylim()` to be called BEFORE fetching tiles.

**Fix:** Update `fetch_basemap_tiles()` to set axis limits from bounds:
```python
def fetch_basemap_tiles(self, ax, bounds=None, crs=None, alpha=1.0, source='esri'):
    if bounds is None or crs is None:
        return
    
    # CRITICAL: Set axis limits BEFORE calling add_basemap
    left, right, bottom, top = bounds
    ax.set_xlim(left, right)
    ax.set_ylim(bottom, top)
    
    # ... rest of function
```

### 🟡 Important (should fix)

| Issue | Details | Effort |
|-------|---------|--------|
| **No basemap tests** | `test_visualization.py` doesn't cover ESRI/Google basemap functionality | 2 hours |
| **Slider performance** | Full re-render on opacity change is heavy; could update artist alpha directly | 2–3 hours |

### 🟢 Nice to have (future consideration)

| Issue | Details | Effort |
|-------|---------|--------|
| **Per-layer visibility** | Current UI uses single RadioButton selection; CheckButtons would allow multi-layer compositing | 3–6 hours |
| **Production caching** | Replace dev `requests-cache` with dedicated tile cache/CDN | 4–8 hours |
| **Licensing documentation** | Document ESRI World Imagery terms for deployment scenarios | 1–2 hours |

## 5. Recommended next steps (prioritized)

### Immediate (before any release)

1. **Harden `get_extent()`** — Add type coercion for `epsg`, try/except wrapper, and EPSG:3857 fallback
2. **Fix alignment test** — Update `scripts/v6_esri_alignment_test.py` to use real S2 data (via `get_satellite_data`) instead of random arrays
3. —

### Short-term (next sprint)

4. **Add basemap unit tests** — Extend `test_visualization.py` with tests for `fetch_basemap_tiles()` and `get_extent()`
5. **Optimize opacity slider** — Update artist alpha directly instead of full re-render

### Later (backlog)

6. **Multi-layer visibility** — Replace RadioButtons with CheckButtons for overlay selection
7. **Production caching strategy** — Document and implement proper tile caching for deployment
8. **ESRI licensing docs** — Add section to README on usage terms

## 6. Execution order (revised)

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | Harden `get_extent()` with defensive coding | 1–2h | ✅ Complete |
| 2 | Update alignment test to use real data | 2–3h | ✅ Complete |
| 2.5 | Fix axis limits in `fetch_basemap_tiles()` | 15 min | ✅ Complete |
| 3 | Add dynamic zoom calculation | 1h | ✅ Complete |
| 4 | Add basemap unit tests | 2h | ⬜ Not started |
| 5 | Optimize slider performance | 2–3h | ⬜ Not started |

**Quick wins available:**
- (A) Harden `get_extent()` immediately (safest first step) - **DONE**
- (B) Fix the alignment test to produce meaningful validation - **DONE**
- (C) Add dynamic zoom calculation for better UX at different scales

## Implementation Phases (detailed)

### Phase A — Harden Core Functions (0.5 day) ✅ COMPLETED

**Goal:** Make `get_extent()` production-ready with proper error handling.

**Changes to `src/sat_mon/visualization/plots.py`:**
- Added `try/except` around EPSG parsing
- Implemented EPSG:3857 fallback for missing or invalid CRS
- Validated via `test_visualization.py`

**Deliverable:** Updated `get_extent()` + unit test in `test_visualization.py`

---

### Phase B — Fix Alignment Test (0.5 day) ✅ COMPLETED

**Goal:** Update `scripts/v6_esri_alignment_test.py` to use real satellite data.

**Key changes:**
- Updated script to use `get_satellite_data()` and `process_indices()`
- Configured visualizer to render S2 RGB at 50% opacity over ESRI basemap
- Added programmatic CRS verification

**Deliverable:** `scripts/v6_esri_alignment_test.py` (run to generate `v6_alignment_test_real.png`)

---

### Phase C — Dynamic Zoom (2–4 hours) ✅ COMPLETED

**Goal:** Calculate zoom level based on extent size instead of hardcoding `zoom=18`.

**Implementation:**
```python
def _calculate_zoom(self, bounds):
    """Estimate appropriate zoom level from extent width."""
    width = abs(bounds[1] - bounds[0])  # right - left in meters
    # Rough heuristic: smaller extent = higher zoom
    if width < 1000:
        return 18
    elif width < 5000:
        return 16
    elif width < 20000:
        return 14
    else:
        return 12
```

**Deliverable:** Updated `fetch_basemap_tiles()` with dynamic zoom

---

### Phase D — Unit Tests (0.5 day) — IN PROGRESS

**Goal:** Add test coverage for basemap functions.

**Added tests:**
- `test_get_extent_valid_epsg()` — normal case
- `test_get_extent_missing_epsg()` — fallback to 3857
- `test_get_extent_string_epsg()` — coercion from string

**Remaining to add:**
- `test_fetch_basemap_tiles_esri()` — mock tile fetch
- `test_fetch_basemap_tiles_google()` — mock tile fetch

**Deliverable:** Expanded test suite with 5+ new tests

---

### Phase E — UI Polish (optional, 1 day)

**Goal:** Optimize slider and consider multi-layer visibility.

**Slider optimization approach:**
```python
def on_slider_update(val):
    self.layer_alphas[self.active_overlay_key] = val
    # Update artist alpha directly instead of full render
    for artist in self.overlay_artists:
        artist.set_alpha(val)
    self.fig.canvas.draw_idle()
```

**Deliverable:** Smoother opacity control + optional CheckButtons for multi-layer

---

### Phase F — Documentation & Release (0.5 day)

**Goal:** Document ESRI licensing and caching for deployment.

**Deliverable:** Updated README with:
- ESRI World Imagery usage terms
- Caching configuration options
- Deployment considerations

---

## Summary: v6 Status at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│  v6 ESRI Integration Status                                 │
├─────────────────────────────────────────────────────────────┤
│  ✅ Core Implementation      COMPLETE                       │
│     - contextily integration                                │
│     - ESRI/Google tile fetching                             │
│     - Base layer selector UI                                │
│     - Overlay mode with opacity                             │
├─────────────────────────────────────────────────────────────┤
│  ✅ Phase A+B+C              COMPLETE                       │
│     - get_extent() defensive coding                         │
│     - Alignment test with real data                         │
│     - Axis limits fix (contextily rendering)                │
│     - Dynamic zoom calculation                              │
├─────────────────────────────────────────────────────────────┤
│  📋 Remaining Work           ~4 hours (optional polish)     │
│     - Basemap unit tests                                    │
│     - Slider performance optimization                       │
├─────────────────────────────────────────────────────────────┤
│  🎯 Ready for Production?    YES - ESRI maps now working    │
└─────────────────────────────────────────────────────────────┘
```

**v6 is now functional.** ESRI basemap rendering verified via `scripts/test_esri_draw.py`. Optional remaining work: unit tests and UI polish.
