import numpy as np
import pytest
from src.sat_mon.analysis.field_boundary import (
    create_circular_boundary,
    create_polygon_boundary,
    create_field_mask,
    apply_field_mask,
    compute_field_statistics,
    mask_all_indices
)

def test_create_circular_boundary():
    """Test that circular boundary is created with correct properties."""
    boundary = create_circular_boundary(-26.5, 28.3, 400)
    
    assert boundary["type"] == "Polygon"
    assert len(boundary["coordinates"][0]) >= 32  # At least 32 vertices
    assert boundary["properties"]["radius_m"] == 400
    assert abs(boundary["properties"]["area_ha"] - 50.27) < 1.0  # ~50 ha for 400m radius

def test_create_polygon_boundary():
    """Test polygon creation from vertices."""
    vertices = [
        (-26.50, 28.30),
        (-26.51, 28.30),
        (-26.51, 28.31),
        (-26.50, 28.31)
    ]
    boundary = create_polygon_boundary(vertices)
    
    assert boundary["type"] == "Polygon"
    assert boundary["properties"]["num_vertices"] == 4
    assert boundary["properties"]["area_ha"] > 0

def test_create_polygon_boundary_too_few_vertices():
    """Test that ValueError is raised for < 3 vertices."""
    with pytest.raises(ValueError):
        create_polygon_boundary([(-26.5, 28.3), (-26.51, 28.3)])

def test_create_field_mask_shape():
    """Test that mask has correct shape."""
    boundary = create_circular_boundary(-26.5, 28.3, 400)
    bbox = [28.25, -26.55, 28.35, -26.45]  # ~11km x 11km area
    
    mask = create_field_mask(boundary, (500, 500), bbox, epsg=32735)
    
    assert mask.shape == (500, 500)
    assert mask.dtype == bool
    # Depending on resolution vs circle size, some pixels should be True
    # 400m radius in 11km box is small but visible
    assert mask.sum() > 0  # Some pixels should be inside
    assert mask.sum() < 500 * 500  # Not all pixels should be inside

def test_create_field_mask_no_epsg():
    """Test mask creation without EPSG (WGS84 fallback)."""
    boundary = create_circular_boundary(-26.5, 28.3, 400)
    bbox = [28.25, -26.55, 28.35, -26.45]
    
    mask = create_field_mask(boundary, (500, 500), bbox, epsg=None)
    
    assert mask.shape == (500, 500)

def test_apply_field_mask():
    """Test that mask correctly sets outside pixels to NaN."""
    data = np.ones((100, 100))
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:60, 40:60] = True  # 20x20 region is field
    
    result = apply_field_mask(data, mask)
    
    assert np.isnan(result[0, 0])  # Outside is NaN
    assert result[50, 50] == 1.0  # Inside is preserved
    assert np.sum(~np.isnan(result)) == 400  # 20*20 pixels preserved

def test_apply_field_mask_shape_mismatch():
    """Test that ValueError is raised for shape mismatch."""
    data = np.ones((100, 100))
    mask = np.zeros((50, 50), dtype=bool)
    
    with pytest.raises(ValueError):
        apply_field_mask(data, mask)

def test_compute_field_statistics():
    """Test statistics computation."""
    data = np.random.rand(100, 100)
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:60, 40:60] = True
    
    stats = compute_field_statistics(data, mask)
    
    assert "mean" in stats
    assert "std" in stats
    assert "percentiles" in stats
    assert stats["count"] == 400
    assert 0 <= stats["mean"] <= 1
    assert 50 in stats["percentiles"]

def test_compute_field_statistics_with_nan():
    """Test that NaN values are excluded from statistics."""
    data = np.ones((100, 100))
    data[45:55, 45:55] = np.nan  # Some NaN in field area
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:60, 40:60] = True
    
    stats = compute_field_statistics(data, mask)
    
    assert stats["count"] == 300  # 400 - 100 NaN pixels

def test_mask_all_indices():
    """Test batch masking of processed data."""
    processed = {
        "ndvi": np.random.rand(100, 100),
        "evi": np.random.rand(100, 100),
        "rgb": np.random.rand(100, 100, 3),  # Should not be masked
    }
    mask = np.zeros((100, 100), dtype=bool)
    mask[40:60, 40:60] = True
    
    result = mask_all_indices(processed, mask)
    
    # NDVI and EVI should be masked
    assert np.isnan(result["ndvi"][0, 0])
    assert np.isnan(result["evi"][0, 0])
    
    # RGB should be unchanged
    assert not np.isnan(result["rgb"][0, 0, 0])

def test_full_pipeline_integration():
    """Integration test with realistic data shapes."""
    # Simulate data structure from composite.py
    ref_shape = (512, 512)
    bbox = [28.25, -26.55, 28.35, -26.45]
    epsg = 32735
    
    # Create boundary
    boundary = create_circular_boundary(-26.5, 28.3, 500)
    
    # Create mask
    mask = create_field_mask(boundary, ref_shape, bbox, epsg)
    
    # Simulate processed data
    processed = {
        "ndvi": np.random.rand(*ref_shape) * 0.8 + 0.1,
        "lst": np.random.rand(*ref_shape) * 20 + 25,
    }
    
    # Mask all
    masked = mask_all_indices(processed, mask)
    
    # Compute stats
    ndvi_stats = compute_field_statistics(processed["ndvi"], mask)
    
    assert ndvi_stats["mean"] > 0
    assert ndvi_stats["count"] > 0
    assert mask.sum() == ndvi_stats["count"]

if __name__ == "__main__":
    # If run directly, run manual checks
    test_create_circular_boundary()
    print("test_create_circular_boundary passed")
    test_create_polygon_boundary()
    print("test_create_polygon_boundary passed")
    test_create_field_mask_shape()
    print("test_create_field_mask_shape passed")
    test_apply_field_mask()
    print("test_apply_field_mask passed")
    test_compute_field_statistics()
    print("test_compute_field_statistics passed")
    print("All tests passed!")
