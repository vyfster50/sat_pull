#!/usr/bin/env python3
"""Minimal test to verify contextily ESRI tile fetching works."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import contextily as cx
from rasterio.crs import CRS
from rasterio.warp import transform_bounds

# Test location: South Africa
bbox_wgs84 = [29.315, -28.786, 29.415, -28.686]
epsg = 32735

# Transform to UTM
native_crs = CRS.from_epsg(epsg)
left, bottom, right, top = transform_bounds(CRS.from_epsg(4326), native_crs, *bbox_wgs84)
print(f'Extent in EPSG:{epsg}:')
print(f'  left={left:.2f}, right={right:.2f}')
print(f'  bottom={bottom:.2f}, top={top:.2f}')

fig, ax = plt.subplots(figsize=(10, 10))

# KEY: Set axis limits BEFORE calling add_basemap
ax.set_xlim(left, right)
ax.set_ylim(bottom, top)
print(f'Axis limits set: xlim=({left:.2f}, {right:.2f}), ylim=({bottom:.2f}, {top:.2f})')

print('Fetching ESRI tiles (zoom=14)...')
try:
    cx.add_basemap(
        ax,
        crs=f'EPSG:{epsg}',
        source='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        zoom=14
    )
    print('SUCCESS: Tiles fetched')
except Exception as e:
    print(f'FAILED: {e}')
    import traceback
    traceback.print_exc()

fig.savefig('esri_minimal_test.png', dpi=150)
print('Saved to esri_minimal_test.png')
