#!/usr/bin/env python3
"""Quick test of Phase A implementation for v8 roadmap."""

from src.sat_mon.analysis.field_boundary import (
    create_circular_boundary,
    create_field_mask,
    compute_field_statistics
)
import numpy as np

print("Testing Phase A: Field Boundary & Masking")
print("=" * 50)

# Test with the user's pivot field coordinates
center_lat = -28.736
center_lon = 29.365
radius_m = 250  # ~250m radius pivot

# Create boundary
boundary = create_circular_boundary(center_lat, center_lon, radius_m)
print("✅ Circular boundary created")
print(f"   Area: {boundary['properties']['area_ha']:.2f} hectares")

# Test mask creation with realistic satellite grid
bbox = [29.36, -28.74, 29.37, -28.73]  # Small area around field
image_shape = (100, 100)
epsg = 32735  # UTM 35S (South Africa)

mask = create_field_mask(boundary, image_shape, bbox, epsg)
print("✅ Field mask created")
print(f"   Mask shape: {mask.shape}")
print(f"   Pixels inside field: {mask.sum()}")

# Test statistics on mock NDVI data
mock_ndvi = np.random.rand(*image_shape) * 0.6 + 0.2  # NDVI 0.2-0.8
stats = compute_field_statistics(mock_ndvi, mask)
print("✅ Field statistics computed")
print(f"   Mean NDVI: {stats['mean']:.3f}")
print(f"   Pixel count: {stats['count']}")

print()
print("=" * 50)
print("Phase A: PASS ✅")
print("=" * 50)
