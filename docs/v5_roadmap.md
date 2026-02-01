# v5 Roadmap: Advanced Visualization & Interactive Modes

## 1. Overview
The goal of v5 is to transition the visualization from a static grid of charts to an interactive, multi-mode interface. This will allow users to toggle between the traditional detailed grid view and a new "Single Image Overlay" mode. The overlay mode mimics a GIS/Photoshop workflow, allowing users to stack analysis layers (NDVI, Flood, etc.) over a base RGB image with individual opacity controls.

## 2. Feature Checklist

### View Modes
- [x] **Traditional Grid View**: Preserve the existing 5x3 grid layout as a selectable mode.
- [x] **Single Image Overlay Mode**:
    - [x] **Base Layer**: Sentinel-2 True Color (RGB).
    - [x] **Overlay Stack**: NDVI, Flood Mask, Crop Mask, LST.
    - [x] **Layer Controls**:
        - [x] Visibility Toggle (On/Off) per layer.
        - [x] Blend/Opacity Slider (0-100%) per layer.

### UI/UX
- [x] **Mode Toggle**: Switch between "Grid" and "Overlay" views.
- [x] **Rainfall Integration**: Keep rainfall trend charts persistent at the bottom of the screen in Overlay mode.
- [x] **Matplotlib Widgets**: Implement interactive controls using standard Matplotlib widgets (Sliders, CheckButtons, RadioButtons).

## 3. Technical Implementation Plan

### Phase 1: Refactoring Visualization Logic
- Convert the standalone `plot_grid` function in `src/sat_mon/visualization/plots.py` into a stateful `CropMonitorVisualizer` class.
- Separate data preparation (normalizing arrays) from rendering logic.

### Phase 2: Implementing the Overlay View
- Create a new rendering method `_draw_overlay_view()` within the class.
- Implement layer blending logic using Matplotlib's `alpha` channel and `zorder`.
- Stack: RGB (Base) -> Crop Mask -> LST -> NDVI -> Flood Mask (Top).

### Phase 3: Interactive Controls
- Add a sidebar or control area in the Matplotlib figure.
- **RadioButtons**: For selecting the View Mode.
- **CheckButtons**: For toggling layer visibility.
- **Sliders**: For adjusting layer opacity.
- connect widget events to a `update()` method that clears and redraws the main axes.

### Phase 4: Persistent Layouts
- Ensure the "Rainfall Trends" row remains visible at the bottom of the figure in Overlay mode, or effectively re-rendered in a dedicated subplot area.
- Optimization: Ensure redrawing doesn't re-fetch or re-process data, only re-renders the image arrays.

## 4. Execution Order
1.  **Refactor**: Create `CropMonitorVisualizer` class in `plots.py`.
2.  **Basic Overlay**: Implement the overlay rendering logic with hardcoded alpha.
3.  **Widgets**: Add the mode switcher and layer controls.
4.  **Refine**: Tune the layout to fit controls + map + rainfall charts.
