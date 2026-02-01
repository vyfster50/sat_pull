# V10 Roadmap: Animated Time-Series Overlay & Timeline Visualization

## Overview

Version 10 introduces **animated satellite imagery** as the primary visualization mode. Instead of static single-frame overlays, the farmer's plot will display a 5-second animation looping through the last 75 available scenes (filtered for cloud cover ≤30%), providing a dynamic view of crop progression over time.

**Target User Experience:**
```
User runs: python app.py --gui
→ Selects field on map
→ Clicks "Analyze"
→ Animation plays: 75 frames at 15 FPS (5 seconds loop)
→ Dotted field boundary persists throughout animation
→ Timeline graph below shows NDVI/EVI progression with playhead
→ User can pause, scrub, or export frames
```

---

## Architecture Decision

**Chosen Stack: Matplotlib Animation + FuncAnimation**

Why this over alternatives:
- **Matplotlib FuncAnimation**: Already integrated, works with existing overlay infrastructure, supports blit for performance
- **OpenCV/FFmpeg**: Better for export but overkill for interactive display
- **Plotly/Dash**: Would require rewriting visualization layer

**Data Source:**
- Sentinel-2 L2A (optical indices: NDVI, EVI, SAVI, etc.)
- Cloud filtering via SCL band (<30% in-field cloud)
- Up to 75 most recent scenes (or all available within lookback window)

---

## Phase A: Data Pipeline for Multi-Scene Fetching

**Goal:** Extend the data fetching layer to retrieve multiple historical scenes efficiently.

### A.1: Create Multi-Scene Fetcher

New function in `src/sat_mon/data/composite.py`:

```python
def get_timeseries_frames(
    lat: float,
    lon: float,
    buffer: float = 0.05,
    max_scenes: int = 75,
    max_cloud_cover: float = 30.0,
    lookback_days: int = 365,
) -> List[Dict[str, Any]]:
    """
    Fetch up to `max_scenes` recent S2 scenes with cloud cover ≤ max_cloud_cover.
    
    Returns:
        List of dicts, each containing:
        - 'date': datetime
        - 'bands': {'red': array, 'nir': array, 'scl': array, ...}
        - 'indices': {'ndvi': array, 'evi': array, ...}
        - 'cloud_pct': float
        - 'metadata': STAC item
    """
```

### A.2: Efficient Band Reading

- Use lazy loading: fetch metadata first, then load bands on-demand during animation
- Cache processed indices to avoid recomputation
- Consider downsampling for preview (e.g., 256x256) then full-res on pause

### A.3: Cloud Filtering Strategy

1. Query STAC for up to `max_scenes * 2` candidates (sorted by date desc)
2. For each candidate:
   - Read SCL band (small, fast)
   - Compute in-field cloud percentage
   - Accept if ≤ 30%
3. Stop when 75 accepted or candidates exhausted
4. Return accepted scenes in chronological order (oldest first for animation)

---

## Phase B: Animation Engine

**Goal:** Create an animation controller that renders frames smoothly.

### B.1: Animation Data Structure

```python
@dataclass
class AnimationFrame:
    date: datetime
    index_array: np.ndarray  # e.g., NDVI masked to field
    cloud_pct: float
    
@dataclass
class AnimationSeries:
    frames: List[AnimationFrame]
    fps: int = 15
    index_name: str = "NDVI"
    colormap: str = "RdYlGn"
    vmin: float = -0.2
    vmax: float = 0.8
```

### B.2: Matplotlib FuncAnimation Integration

In `src/sat_mon/visualization/animation.py`:

```python
class TimeSeriesAnimator:
    """Handles animated overlay rendering."""
    
    def __init__(self, series: AnimationSeries, field_selection: Dict, extent: List):
        self.series = series
        self.field_selection = field_selection
        self.extent = extent
        self.current_frame = 0
        self.is_playing = True
        
    def setup_figure(self) -> Tuple[Figure, Axes]:
        """Create figure with map area and timeline."""
        
    def animate(self, frame_idx: int):
        """Update function for FuncAnimation."""
        
    def play(self):
        """Start animation loop."""
        
    def pause(self):
        """Pause animation."""
        
    def seek(self, frame_idx: int):
        """Jump to specific frame."""
        
    def export_gif(self, path: str, dpi: int = 100):
        """Export animation as GIF."""
```

### B.3: Performance Optimizations

- Use `blit=True` for faster rendering
- Pre-compute all masked arrays before animation starts
- Use `np.memmap` for large datasets to reduce memory
- Downsample to 512x512 max for smooth playback, offer full-res export

---

## Phase C: Timeline Graph Integration

**Goal:** Display a synchronized timeline showing index values over time.

### C.1: Timeline Panel Layout

```
┌────────────────────────────────────────────┐
│                                            │
│          ANIMATED MAP OVERLAY              │
│     (Field boundary + index animation)     │
│                                            │
│  ┌─ Date: 2025-12-15  Cloud: 8% ─────────┐│
│  │                                       ││
│  └───────────────────────────────────────┘│
├────────────────────────────────────────────┤
│ NDVI ▲                                     │
│  0.8 │    ╱╲    ╱╲                         │
│  0.6 │   ╱  ╲  ╱  ╲   ●←playhead          │
│  0.4 │  ╱    ╲╱    ╲                       │
│  0.2 │ ╱              ╲                    │
│    0 └──────────────────────────────────→ │
│      Jan  Feb  Mar  Apr  May  Jun  Jul    │
├────────────────────────────────────────────┤
│  [◄◄] [▶/❚❚] [►►]  ───●───────── [Export] │
└────────────────────────────────────────────┘
```

### C.2: Timeline Data

- X-axis: Date (from oldest to newest frame)
- Y-axis: Mean index value within field mask
- Highlight current frame with vertical line / marker
- Optional: Show cloud cover as secondary axis or point markers

### C.3: Interactive Scrubbing

- Click on timeline to jump to that frame
- Drag playhead for manual scrubbing
- Sync between timeline click and map animation

---

## Phase D: UI Controls & Interactivity

**Goal:** Provide intuitive controls for animation playback.

### D.1: Control Buttons

| Button | Action |
|--------|--------|
| ▶ / ❚❚ | Play / Pause toggle |
| ◄◄ | Previous frame |
| ►► | Next frame |
| ⟲ | Reset to start |
| 🔄 | Loop toggle (on by default) |

### D.2: Index Selector

- Dropdown or radio to switch between:
  - NDVI (default)
  - EVI
  - SAVI
  - NDMI
  - NDWI
- Changing index recomputes frames from cached bands

### D.3: Speed Control

- Slider: 5 FPS (slow) → 30 FPS (fast)
- Default: 15 FPS (5 sec for 75 frames)

### D.4: Export Options

- "Save GIF" → Export current animation as animated GIF
- "Save Frames" → Export all frames as numbered PNGs
- "Save Timeline" → Export timeline graph as static PNG

---

## Phase E: Integration with Existing GUI

**Goal:** Seamlessly integrate animation into current workflow.

### E.1: Mode Toggle

In the visualization window, add a mode switch:
- **Static Mode** (current): Single-frame overlay with layer selector
- **Animation Mode** (new): Time-series animation with timeline

### E.2: Data Flow

```
GUIOrchestrator.run()
  │
  ├─→ _get_field_selection()  # Existing
  │
  ├─→ get_timeseries_frames()  # NEW: Fetch 75 scenes
  │
  ├─→ process_indices_batch()  # NEW: Compute indices for all frames
  │
  └─→ TimeSeriesAnimator.play()  # NEW: Launch animation
        │
        ├─→ AnimatedOverlay (map)
        └─→ TimelineGraph (synced)
```

### E.3: Fallback Behavior

- If fewer than 10 scenes available: Show warning, fall back to static mode
- If animation fails: Gracefully degrade to static overlay of most recent frame

---

## Phase F: Testing & Validation

### F.1: Unit Tests

- `test_timeseries_fetch.py`: Verify multi-scene fetching with cloud filter
- `test_animation_frames.py`: Verify frame generation and masking
- `test_timeline_sync.py`: Verify timeline/animation synchronization

### F.2: Integration Tests

- End-to-end GUI test with mock STAC responses
- Performance benchmark: 75 frames should load in <30 seconds
- Memory test: Animation should stay under 2GB RAM

### F.3: Visual Validation

- Test at different latitudes (projection distortion)
- Test with sparse data (few scenes available)
- Test with high-cloud periods (many rejected scenes)

---

## Implementation Order

| Phase | Priority | Estimated Effort | Dependencies |
|-------|----------|------------------|--------------|
| A (Data Pipeline) | P0 | 2-3 days | None |
| B (Animation Engine) | P0 | 2-3 days | Phase A |
| C (Timeline Graph) | P1 | 1-2 days | Phase B |
| D (UI Controls) | P1 | 1-2 days | Phase B |
| E (Integration) | P0 | 1 day | Phase A, B |
| F (Testing) | P1 | 1-2 days | All |

**Total Estimated Effort: 8-13 days**

---

## Configuration Defaults

Add to `src/sat_mon/config.py`:

```python
# Animation settings
ANIMATION_MAX_SCENES = 75
ANIMATION_FPS = 15
ANIMATION_CLOUD_THRESHOLD = 30.0  # percent
ANIMATION_LOOKBACK_DAYS = 365
ANIMATION_PREVIEW_SIZE = (512, 512)  # Downsampled for smooth playback
ANIMATION_DEFAULT_INDEX = "ndvi"
```

---

## Success Criteria

1. **Performance**: 75-frame animation loads in <30 seconds, plays smoothly at 15 FPS
2. **Accuracy**: Cloud filtering correctly rejects scenes >30% in-field cloud
3. **Usability**: User can play, pause, scrub, and export without confusion
4. **Visual Quality**: Animation clearly shows crop progression; timeline matches map
5. **Reliability**: Graceful fallback when data is sparse or fetching fails

---

## Future Enhancements (v11+)

- **Comparison Mode**: Side-by-side animation of two fields
- **Anomaly Detection**: Highlight frames with unusual index drops
- **Predictive Overlay**: ML-based forecast of next 2-4 weeks
- **Video Export**: MP4 export with audio narration
- **Mobile-Friendly**: Web-based viewer for sharing animations

---

## Notes

- Animation will use the same field masking logic as v9 (circular/rectangular)
- Dotted boundary persists throughout animation (drawn once, not per-frame)
- Timeline playhead syncs with animation frame index
- Consider caching fetched scenes to disk for repeat views
