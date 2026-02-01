# v7 Roadmap: Optimization & Consolidation

## 1. Overview
Following the successful integration of ESRI basemaps (v6), v7 focuses on refining the analysis toolkit. The goal is to reduce visual clutter and computational overhead by auditing the existing 13+ overlays and retiring those that are redundant or provide low unique value to the user.

## 2. Key Objectives

1.  **Overlay Audit & Consolidation**: Review all existing indices and layers for relevance.
2.  **TBA**: Second major objective to be determined.

## 3. Detailed Tasks

### Phase A: Overlay Audit (Efficiency/Relevance)

**Current Layer Inventory:**

| Layer | Type | Relevance / Usage Note | Action |
| :--- | :--- | :--- | :--- |
| `rgb` | Base | Essential reference. | **Keep** |
| `esri_satellite` | Base | High-res ground truth. | **Keep** |
| `ndvi` | Vegetation | Standard vegetation health index. | **Keep** |
| `evi` | Vegetation | Enhanced sensitivity (high biomass). Do we need both NDVI and EVI? | *Review* |
| `savi` | Vegetation | Soil-adjusted. Useful for early season? | *Review* |
| `ndmi` | Water/Veg | Vegetation water content. | *Review* |
| `ndwi` | Water | Surface water detection. Redundant with Flood Mask? | *Review* |
| `rvi` | Radar | Vegetation structure (cloud-penetrating). Unique value. | **Keep** |
| `crop_mask_plot` | Context | Essential for masking non-ag areas. | **Keep** |
| `lst` | Thermal | Absolute temperature. | *Review* |
| `lst_anomaly` | Thermal | Deviation from baseline. More actionable than raw LST? | **Keep** |
| `soil_moisture` | Moisture | WaPOR data. Essential agronomic variable. | **Keep** |
| `flood_mask` | Radar | Disaster monitoring. | **Keep** |

**Audit Questions:**
1.  **Redundancy**: Do `ndwi` and `flood_mask` serve sufficiently distinct purposes?
2.  **Cognitive Load**: Is `evi` or `savi` providing actionable insight that `ndvi` misses for the general user?
3.  **Performance**: Are any layers computationally expensive to generate relative to their value?

### Phase B: TBA

*(Space reserved for future requirements)*

## 4. Execution Plan

1.  **Analyze**: Evaluate visual correlation between similar indices (e.g., NDVI vs EVI vs SAVI) on sample scenes.
2.  **Decide**: Mark low-value layers for deprecation.
3.  **Refactor**: Remove deprecated layers from `plots.py` and processing pipelines to save compute/bandwidth.
