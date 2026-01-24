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
