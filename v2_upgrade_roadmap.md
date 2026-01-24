# V2 Upgrade Roadmap: "Sat Pull" Implementation

## Phase 1: Architecture & Foundation
Transition from a linear script to a modular pipeline structure.

- [x] **Refactor `extru_map.py`**: Break into functions:
    - `get_satellite_data(lat, lon, buffer)`
    - `process_indices(data)`
    - `analyze_thresholds(metrics)`
    - `generate_response(results)`
- [x] **Standardize Inputs**: Accept JSON-like inputs (Lat, Lon, Buffer_meters) instead of hardcoded variables.

## Phase 2: Data Acquisition (Expanding Sources)
The V2 diagram requires sources beyond Sentinel-2. We will map these to STAC/Open sources.

### 1. Sentinel-2 (Existing)
- [x] **Current**: Fetches RGB.
- [x] **Upgrade**:
    - [x] Fetch NIR band (B08) and Red Edge (B05/B06/B07) for NDVI/NDRE.
    - [x] **Cloud Masking**: Use the Scene Classification Layer (SCL) band provided in Sentinel-2 L2A to mask clouds/shadows (replaces `s2cloudless`).
    - [x] **Verification**: Confirmed band names (B02, B03, B04, B08, SCL) align with standard L2A definitions.

### 2. Landsat 8/9 (New - for LST)
- [x] **Source**: Digital Earth Africa STAC (`ls8_c2_l2`, `ls9_c2_l2`).
- [x] **Task**: Fetch Band 10 (Thermal) and Emissivity bands.
- [x] **Processing**: Convert Digital Numbers (DN) to Kelvin, then Celsius (LST).

### 3. Sentinel-1 (New - for Radar/Structure)
- [x] **Source**: Digital Earth Africa STAC (`s1_rtc`).
- [x] **Task**: Fetch VV and VH polarization.
- [x] **Processing**: Apply speckle filtering (basic log transform applied).

### 4. Rainfall (CHIRPS)
- [x] **Source**: Digital Earth Africa STAC (`rainfall_chirps_daily`).
- [x] **Task**: Fetch last 10 days of data.
- [x] **Processing**: Sum values to get `10-Day Rainfall Accumulation`.

### 5. iSDAsoil (New - Static Asset)
- **Source**: iSDAsoil is hosted on S3 (COG format) or via their API.
- **Task**: Fetch `pH`, `organic_carbon`, etc., for the coordinate.
- **Fallback**: If iSDA is hard to access via STAC, use alternative soil grids or an explicit S3 COG reader.

## Phase 3: Processing & Logic Layer
Implement the "Python Decision Engine".

- [x] **NDVI Calculation**: `(NIR - RED) / (NIR + RED)`
- [x] **NDRE Calculation**: `(NIR - RED_EDGE) / (NIR + RED_EDGE)`
- [x] **Data Fusion**: Reproject all rasters to a common 10m grid (using `rasterio.warp`).
- [x] **Threshold Analysis**:
    - `IF LST > 35°C AND NDVI < 0.3` -> **Water Stress**.
    - `IF pH < 5.5` -> **Lime Needed** (Pending iSDA).
    - `IF Rain_10day < 10mm` -> **Irrigation Alert**.

## Phase 4: Output Generation
- [x] **JSON Payload**: Create a structured dictionary output (Implemented in `analyze_thresholds`).
- [ ] **PostgreSQL Interface**: (Optional) Add a connector to save results if a DB is available.

---

## Technical Stack Mapping

| Component | V2 Diagram (GEE) | Python Implementation (Your Stack) |
|-----------|------------------|------------------------------------|
| **Collection** | `ee.ImageCollection` | `pystac_client` search |
| **Masking** | `s2cloudless` | Sentinel-2 `SCL` Band masking |
| **Compute** | Server-side GEE | Client-side `numpy` / `xarray` |
| **Reproject** | `reproject()` | `rasterio.warp.reproject` |
| **Database** | PostGIS | `psycopg2` (Python DB adapter) |
