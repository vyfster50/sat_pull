# Crop Monitoring App v4 – Gap Analysis & Roadmap

## Overview
Building on the v3 foundation, v4 focuses on bridging the gap between basic monitoring and advanced agricultural intelligence for Soya farming.

**Target Features:**
1.  **Weather Intelligence:** 7-Day Forecast & Historical Graphs.
2.  **Radar Indices:** RVI (Vegetation) & RSM (Soil Moisture).
3.  **Advanced Crop Health:** EVI, SAVI (Biomass/Early growth).
4.  **Irrigation Management:** NDWI, NDMI, Evapotranspiration.
5.  **Accessibility:** Colorblind-safe visualizations.

---

## 1. New Features Checklist (v4)

### A. Weather Intelligence (Priority 1)
- [x] **7-Day Forecast:** Integrate Open-Meteo API.
- [x] **Historical Weather:** Fetch past 5 days temp/rain for context.
- [x] **Visualization:** Line graphs for temp/rain trends.

### B. Advanced Vegetation Indices (Priority 2)
- [x] **EVI (Enhanced Vegetation Index):** $2.5 \cdot \frac{NIR - Red}{NIR + 6 \cdot Red - 7.5 \cdot Blue + 1}$
- [x] **SAVI (Soil Adjusted Vegetation Index):** $\frac{NIR - Red}{NIR + Red + L} \cdot (1 + L)$
- [x] **RVI (Radar Vegetation Index):** $4 \cdot \frac{VH}{VV + VH}$

### C. Water & Irrigation Management (Priority 3)
- [x] **NDMI (Moisture Index):** $\frac{NIR - SWIR}{NIR + SWIR}$ (Requires Sentinel-2 B11).
- [x] **NDWI (Water Index):** $\frac{Green - NIR}{Green + NIR}$
- [x] **Evapotranspiration (ET):** Fetch `iwmi_green_et_monthly` (Replacement for deprecated WaPOR v2).

### D. Accessibility
- [ ] **Colorblind-Safe Visualization:** Replace Red-Green colormaps.

---

## 2. Technical Implementation Plan

### Phase 1: Data Source Expansion (COMPLETE)
1.  **Open-Meteo Integration:** Add weather API client.
2.  **Sentinel-2 Upgrade:** Add `B11` (SWIR) to fetch list.
3.  **WaPOR Expansion:** Add Evapotranspiration (ET) collection (Using IWMI Monthly).

### Phase 2: Processing Logic
1.  **Indices Calculation:** Implement EVI, SAVI, NDMI, NDWI, RVI.
2.  **Weather Processing:** Parse API JSON into graph-ready format.

### Phase 3: Visualization
1.  **Expand Grid:** Move to 4x3 grid or tabbed interface.
2.  **Add Graphs:** Plot weather trends using matplotlib.
3.  **Update Colors:** Use accessible cmaps (`viridis`, `cividis`, `Blues`).

---

## 3. Execution Order

1.  **Weather Forecast:** High value, independent of satellite passes.
2.  **Advanced Indices:** EVI/SAVI/RVI (Math only).
3.  **Water Management:** NDMI/ET (Requires new band fetch).
4.  **Visualization:** Final polish.
