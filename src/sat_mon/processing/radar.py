import numpy as np

def compute_flood_mask(s1_vv, s1_vh):
    """
    Detects flooding using Sentinel-1 radar thresholds.
    Returns flood_mask (binary) and flood_risk (probability 0-1).
    
    Phase 2: Flood Threshold Detection
    """
    print("  Computing flood detection from Sentinel-1...")
    
    # Convert linear to dB
    def to_db(x):
        return 10 * np.log10(np.clip(x, 1e-5, None))
    
    vv_db = to_db(s1_vv)
    vh_db = to_db(s1_vh)
    
    # Thresholds from v3 roadmap
    FLOOD_THRESHOLD_VV_DEFINITE = -18  # dB - Definite water
    FLOOD_THRESHOLD_VV_LIKELY = -15    # dB - Likely flooded
    FLOOD_THRESHOLD_VV_VEGI = -12      # dB - Flooded vegetation threshold
    VH_VV_RATIO_THRESHOLD = -3         # dB - Flooded vegetation indicator
    
    # Binary flood mask: VV < -15 dB (likely flooded or water)
    flood_mask = (vv_db < FLOOD_THRESHOLD_VV_LIKELY).astype(float)
    
    # Enhanced detection: flooded vegetation (high VH/VV ratio + moderate VV)
    vh_vv_ratio = vh_db - vv_db
    flooded_vegetation = ((vh_vv_ratio > VH_VV_RATIO_THRESHOLD) & 
                          (vv_db < FLOOD_THRESHOLD_VV_VEGI)).astype(float)
    
    # Combined: water OR flooded vegetation
    flood_mask_combined = np.maximum(flood_mask, flooded_vegetation)
    
    # Flood risk probability (0-1 scale)
    # VV < -18: high risk (1.0), VV = -15: medium risk (0.5), VV > -12: low risk (0.0)
    flood_risk = np.clip((FLOOD_THRESHOLD_VV_LIKELY - vv_db) / 6.0, 0, 1)
    
    # Reduce risk where VV is very high (unlikely to be flooded)
    flood_risk = np.where(vv_db > -8, 0, flood_risk)
    
    return flood_mask_combined, flood_risk

def compute_rvi(s1_vv, s1_vh):
    """
    Computes Radar Vegetation Index (RVI) from Sentinel-1 data.
    RVI = 4 * VH / (VV + VH)
    Range: 0 (bare soil) to 1 (dense vegetation)
    """
    print("  Computing RVI from Sentinel-1...")
    
    # Convert linear to dB for safe processing or work in linear?
    # RVI formula is usually applied to linear power (intensity), not dB.
    # The read_band function returns whatever the source is. 
    # Sentinel-1 RTC on Microsoft Planetary Computer is usually Gamma0 power (linear) or float32.
    # If the values are very small (e.g. 0.0something), they are linear.
    # If they are negative (e.g. -10), they are dB.
    
    # Assuming linear based on typical STAC RTC assets, but let's add a check/conversion just in case.
    # Actually, look at compute_flood_mask: it converts to_db(x) -> 10*log10.
    # This implies the input IS linear.
    
    # RVI formula relies on linear power values.
    # Ensure no division by zero.
    epsilon = 1e-10
    denominator = s1_vv + s1_vh + epsilon
    
    rvi = (4 * s1_vh) / denominator
    
    # RVI should be roughly 0 to 1.
    # Sometimes it can exceed 1 due to noise or double bounce, clip it.
    rvi = np.clip(rvi, 0, 1)
    
    return rvi
