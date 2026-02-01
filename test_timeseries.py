"""
Tests for Phase B: Historical Data Fetching (timeseries.py)

Run with: python -m pytest test_timeseries.py -v
Or: python test_timeseries.py
"""

import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from datetime import datetime

# Import the module under test
from src.sat_mon.data.timeseries import (
    fetch_timeseries,
    extract_field_values,
    compute_ndvi_for_scene,
    fetch_ndvi_timeseries,
    fetch_multi_index_timeseries,
    fetch_lst_timeseries,
    fetch_rainfall_timeseries,
    SceneResult,
    TimeseriesPoint,
    _search_stac_paginated,
    _compute_indices_for_scene
)
from src.sat_mon.config import setup_environment


class TestSceneResultNamedTuple(unittest.TestCase):
    """Test the SceneResult named tuple."""
    
    def test_scene_result_creation(self):
        """Test creating a SceneResult."""
        dt = datetime(2024, 1, 15, 10, 30, 0)
        item = {'id': 'test-scene', 'properties': {'datetime': '2024-01-15T10:30:00Z'}}
        
        result = SceneResult(date=dt, item=item)
        
        self.assertEqual(result.date, dt)
        self.assertEqual(result.item['id'], 'test-scene')
    
    def test_timeseries_point_creation(self):
        """Test creating a TimeseriesPoint."""
        dt = datetime(2024, 1, 15)
        
        point = TimeseriesPoint(
            date=dt,
            value=0.65,
            metadata={'std': 0.1, 'cloud_fraction': 0.2}
        )
        
        self.assertEqual(point.date, dt)
        self.assertAlmostEqual(point.value, 0.65)
        self.assertIn('std', point.metadata)


class TestFetchTimeseriesMocked(unittest.TestCase):
    """Test fetch_timeseries with mocked API calls."""
    
    @patch('src.sat_mon.data.timeseries._search_stac_paginated')
    def test_fetch_timeseries_single_page(self, mock_search):
        """Test fetching scenes that fit in a single page."""
        mock_search.return_value = [
            {'id': 'scene1', 'properties': {'datetime': '2024-01-10T10:00:00Z'}},
            {'id': 'scene2', 'properties': {'datetime': '2024-01-15T10:00:00Z'}},
        ]
        
        results = fetch_timeseries(
            lat=-1.5, lon=35.2,
            start_date="2024-01-01",
            end_date="2024-01-31",
            collections=["s2_l2a"]
        )
        
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].item['id'], 'scene1')
        self.assertEqual(results[1].item['id'], 'scene2')
        # Verify chronological order
        self.assertLess(results[0].date, results[1].date)
    
    @patch('src.sat_mon.data.timeseries._search_stac_paginated')
    def test_fetch_timeseries_empty_results(self, mock_search):
        """Test handling when no scenes are found."""
        mock_search.return_value = []
        
        results = fetch_timeseries(
            lat=-1.5, lon=35.2,
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        
        self.assertEqual(len(results), 0)
    
    @patch('src.sat_mon.data.timeseries._search_stac_paginated')
    def test_fetch_timeseries_pagination(self, mock_search):
        """Test pagination handling."""
        # First call returns full page (100 items), second returns partial (50 items)
        # Use different months to avoid invalid day-of-month issues
        page1 = []
        for i in range(100):
            # Spread across multiple months to avoid invalid dates
            month = (i // 28) + 1  # 1, 1, ... 2, 2, ... 3, 3, ... 4
            day = (i % 28) + 1     # 1-28
            page1.append({
                'id': f'scene{i}', 
                'properties': {'datetime': f'2024-{month:02d}-{day:02d}T10:00:00Z'}
            })
        
        page2 = []
        for i in range(50):
            month = 6 + (i // 28)  # Start from June
            day = (i % 28) + 1
            page2.append({
                'id': f'scene{100+i}', 
                'properties': {'datetime': f'2024-{month:02d}-{day:02d}T10:00:00Z'}
            })
        
        mock_search.side_effect = [page1, page2]
        
        results = fetch_timeseries(
            lat=-1.5, lon=35.2,
            start_date="2024-01-01",
            end_date="2024-12-31"
        )
        
        self.assertEqual(len(results), 150)
        self.assertEqual(mock_search.call_count, 2)
    
    @patch('src.sat_mon.data.timeseries._search_stac_paginated')
    def test_fetch_timeseries_skips_invalid_dates(self, mock_search):
        """Test that scenes with invalid dates are skipped."""
        mock_search.return_value = [
            {'id': 'scene1', 'properties': {'datetime': '2024-01-10T10:00:00Z'}},
            {'id': 'scene2', 'properties': {}},  # Missing datetime
            {'id': 'scene3', 'properties': {'datetime': 'invalid-date'}},
        ]
        
        results = fetch_timeseries(
            lat=-1.5, lon=35.2,
            start_date="2024-01-01",
            end_date="2024-01-31"
        )
        
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item['id'], 'scene1')


class TestExtractFieldValuesMocked(unittest.TestCase):
    """Test extract_field_values with mocked band reading."""
    
    @patch('src.sat_mon.data.timeseries.read_band')
    @patch('src.sat_mon.data.timeseries.compute_field_statistics')
    def test_extract_field_values_basic(self, mock_stats, mock_read):
        """Test basic field value extraction."""
        # Setup mocks
        mock_read.return_value = np.random.rand(64, 64)
        mock_stats.return_value = {
            'mean': 0.65, 'std': 0.1, 'min': 0.3, 'max': 0.9, 'count': 1000
        }
        
        scenes = [
            SceneResult(datetime(2024, 1, 10), {'id': 's1', 'assets': {'B08': {'href': 'url1'}}}),
            SceneResult(datetime(2024, 1, 15), {'id': 's2', 'assets': {'B08': {'href': 'url2'}}}),
        ]
        
        field_mask = np.ones((64, 64), dtype=bool)
        field_mask[:32, :32] = True  # Only top-left quadrant is field
        
        results = extract_field_values(
            scenes=scenes,
            asset_key='B08',
            bbox=[35.0, -2.0, 35.1, -1.9],
            field_mask=field_mask,
            out_shape=(64, 64)
        )
        
        self.assertEqual(len(results), 2)
        self.assertAlmostEqual(results[0].value, 0.65)
    
    @patch('src.sat_mon.data.timeseries.read_band')
    def test_extract_field_values_missing_asset(self, mock_read):
        """Test handling of missing asset key."""
        mock_read.side_effect = KeyError("B08")
        
        scenes = [
            SceneResult(datetime(2024, 1, 10), {'id': 's1', 'assets': {}}),
        ]
        
        results = extract_field_values(
            scenes=scenes,
            asset_key='B08',
            bbox=[35.0, -2.0, 35.1, -1.9],
            field_mask=np.ones((64, 64), dtype=bool)
        )
        
        self.assertEqual(len(results), 0)


class TestComputeNDVIForSceneMocked(unittest.TestCase):
    """Test NDVI computation for individual scenes."""
    
    @patch('src.sat_mon.data.timeseries.read_band')
    @patch('src.sat_mon.data.timeseries.compute_field_statistics')
    def test_compute_ndvi_for_scene_success(self, mock_stats, mock_read):
        """Test successful NDVI computation."""
        # Mock band reads - B04 (red) and B08 (nir)
        mock_read.side_effect = [
            np.full((64, 64), 0.1),  # RED
            np.full((64, 64), 0.5),  # NIR
        ]
        mock_stats.return_value = {
            'mean': 0.67, 'std': 0.05, 'min': 0.5, 'max': 0.8, 'count': 500
        }
        
        scene = SceneResult(
            datetime(2024, 1, 15),
            {'id': 'test', 'assets': {'B04': {}, 'B08': {}}}
        )
        field_mask = np.ones((64, 64), dtype=bool)
        
        result = compute_ndvi_for_scene(
            scene=scene,
            bbox=[35.0, -2.0, 35.1, -1.9],
            field_mask=field_mask,
            out_shape=(64, 64)
        )
        
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.value, 0.67)
    
    @patch('src.sat_mon.data.timeseries.read_band')
    def test_compute_ndvi_for_scene_too_cloudy(self, mock_read):
        """Test that cloudy scenes return None."""
        # Mock: B04, B08, then SCL with lots of clouds
        mock_read.side_effect = [
            np.full((64, 64), 0.1),  # RED
            np.full((64, 64), 0.5),  # NIR
            np.full((64, 64), 9, dtype=np.uint8),  # SCL - all high cloud
        ]
        
        scene = SceneResult(
            datetime(2024, 1, 15),
            {'id': 'test', 'assets': {'B04': {}, 'B08': {}, 'SCL': {}}}
        )
        field_mask = np.ones((64, 64), dtype=bool)
        
        result = compute_ndvi_for_scene(
            scene=scene,
            bbox=[35.0, -2.0, 35.1, -1.9],
            field_mask=field_mask,
            out_shape=(64, 64)
        )
        
        self.assertIsNone(result)


class TestFetchNDVITimeseriesMocked(unittest.TestCase):
    """Test the high-level NDVI timeseries function."""
    
    @patch('src.sat_mon.data.timeseries.fetch_timeseries')
    @patch('src.sat_mon.data.timeseries.read_band')
    @patch('src.sat_mon.data.timeseries.create_circular_boundary')
    @patch('src.sat_mon.data.timeseries.create_field_mask')
    @patch('src.sat_mon.data.timeseries.compute_ndvi_for_scene')
    def test_fetch_ndvi_timeseries_success(self, mock_ndvi, mock_mask, mock_boundary, 
                                            mock_read, mock_fetch):
        """Test successful NDVI timeseries fetch."""
        # Setup mocks
        mock_boundary.return_value = {
            'type': 'Polygon',
            'coordinates': [[(35.0, -2.0), (35.1, -2.0), (35.1, -1.9), (35.0, -1.9), (35.0, -2.0)]],
            'properties': {'area_ha': 78.5}
        }
        mock_mask.return_value = np.ones((64, 64), dtype=bool)
        mock_read.return_value = np.random.rand(64, 64)
        
        mock_fetch.return_value = [
            SceneResult(datetime(2024, 1, 10), {'id': 's1', 'properties': {'proj:epsg': 32736}}),
            SceneResult(datetime(2024, 1, 25), {'id': 's2', 'properties': {'proj:epsg': 32736}}),
        ]
        
        mock_ndvi.side_effect = [
            TimeseriesPoint(datetime(2024, 1, 10), 0.65, {'std': 0.1}),
            TimeseriesPoint(datetime(2024, 1, 25), 0.70, {'std': 0.08}),
        ]
        
        result = fetch_ndvi_timeseries(
            lat=-1.5, lon=35.2, radius_m=500,
            start_date="2024-01-01", end_date="2024-01-31"
        )
        
        self.assertEqual(len(result['dates']), 2)
        self.assertEqual(len(result['ndvi']), 2)
        self.assertAlmostEqual(result['ndvi'][0], 0.65)
        self.assertIn('summary', result)
        self.assertEqual(result['summary']['count'], 2)
    
    @patch('src.sat_mon.data.timeseries.fetch_timeseries')
    def test_fetch_ndvi_timeseries_no_scenes(self, mock_fetch):
        """Test handling when no scenes are found."""
        mock_fetch.return_value = []
        
        result = fetch_ndvi_timeseries(
            lat=-1.5, lon=35.2, radius_m=500,
            start_date="2024-01-01", end_date="2024-01-31"
        )
        
        self.assertEqual(len(result['dates']), 0)
        self.assertEqual(result['summary']['count'], 0)


class TestComputeIndicesForSceneMocked(unittest.TestCase):
    """Test multi-index computation."""
    
    @patch('src.sat_mon.data.timeseries.read_band')
    @patch('src.sat_mon.data.timeseries.compute_field_statistics')
    def test_compute_multiple_indices(self, mock_stats, mock_read):
        """Test computing multiple indices at once."""
        # Mock band reads for NDVI and EVI (need B02, B04, B08)
        mock_read.side_effect = [
            np.full((64, 64), 0.05),  # B02 (blue)
            np.full((64, 64), 0.1),   # B04 (red)
            np.full((64, 64), 0.5),   # B08 (nir)
        ]
        mock_stats.return_value = {
            'mean': 0.6, 'std': 0.1, 'min': 0.3, 'max': 0.8, 'count': 500
        }
        
        scene = SceneResult(
            datetime(2024, 1, 15),
            {'id': 'test', 'assets': {'B02': {}, 'B04': {}, 'B08': {}}}
        )
        field_mask = np.ones((64, 64), dtype=bool)
        
        values, meta = _compute_indices_for_scene(
            scene=scene,
            bbox=[35.0, -2.0, 35.1, -1.9],
            field_mask=field_mask,
            out_shape=(64, 64),
            indices=['ndvi', 'evi']
        )
        
        self.assertIn('ndvi', values)
        self.assertIn('evi', values)
        self.assertIn('scene_id', meta)


class TestProgressCallback(unittest.TestCase):
    """Test progress callback functionality."""
    
    @patch('src.sat_mon.data.timeseries._search_stac_paginated')
    def test_progress_callback_called(self, mock_search):
        """Test that progress callback is called during fetch."""
        mock_search.return_value = [
            {'id': 'scene1', 'properties': {'datetime': '2024-01-10T10:00:00Z'}},
        ]
        
        callback_calls = []
        def track_progress(current, total, message):
            callback_calls.append((current, total, message))
        
        fetch_timeseries(
            lat=-1.5, lon=35.2,
            start_date="2024-01-01",
            end_date="2024-01-31",
            progress_callback=track_progress
        )
        
        self.assertGreater(len(callback_calls), 0)


class TestIntegration(unittest.TestCase):
    """Integration tests that hit the real STAC API (skip in CI)."""
    
    @unittest.skip("Integration test - requires network access")
    def test_real_stac_search(self):
        """Test real STAC search (run manually)."""
        setup_environment()
        
        results = fetch_timeseries(
            lat=-1.5, lon=35.2,
            buffer=0.02,
            start_date="2024-01-01",
            end_date="2024-01-31",
            collections=["s2_l2a"],
            max_cloud_cover=30.0
        )
        
        print(f"Found {len(results)} scenes")
        for r in results[:5]:
            print(f"  {r.date.date()}: {r.item['id']}")
    
    @unittest.skip("Integration test - requires network access")
    def test_real_ndvi_timeseries(self):
        """Test real NDVI timeseries fetch (run manually)."""
        setup_environment()
        
        result = fetch_ndvi_timeseries(
            lat=-1.5, lon=35.2,
            radius_m=500,
            start_date="2024-01-01",
            end_date="2024-03-31",
            max_cloud_cover=30.0
        )
        
        print(f"NDVI timeseries: {result['summary']}")
        for d, v in zip(result['dates'][:10], result['ndvi'][:10]):
            print(f"  {d.date()}: {v:.3f}")


def run_quick_validation():
    """Quick validation that imports work and basic structures are correct."""
    print("=" * 60)
    print("Phase B Timeseries Module - Quick Validation")
    print("=" * 60)
    
    # Test named tuples
    print("\n1. Testing named tuples...")
    scene = SceneResult(datetime.now(), {'id': 'test'})
    point = TimeseriesPoint(datetime.now(), 0.5, {})
    print(f"   SceneResult: {scene}")
    print(f"   TimeseriesPoint: {point}")
    print("   ✓ Named tuples OK")
    
    # Test imports
    print("\n2. Testing imports...")
    from src.sat_mon.data.timeseries import (
        fetch_timeseries, extract_field_values, fetch_ndvi_timeseries,
        fetch_multi_index_timeseries, fetch_lst_timeseries, fetch_rainfall_timeseries
    )
    print("   ✓ All main functions imported successfully")
    
    # Test boundary creation
    print("\n3. Testing boundary creation...")
    from src.sat_mon.analysis.field_boundary import create_circular_boundary
    boundary = create_circular_boundary(-1.5, 35.2, 500)
    print(f"   Created circular boundary: {boundary['properties']['area_ha']:.2f} ha")
    print("   ✓ Boundary creation OK")
    
    # Test mask creation
    print("\n4. Testing mask creation...")
    from src.sat_mon.analysis.field_boundary import create_field_mask
    from src.sat_mon.data.stac import get_bbox
    bbox = get_bbox(-1.5, 35.2, 0.01)
    mask = create_field_mask(boundary, (64, 64), bbox)
    print(f"   Mask shape: {mask.shape}, coverage: {np.mean(mask)*100:.1f}%")
    print("   ✓ Mask creation OK")
    
    print("\n" + "=" * 60)
    print("All quick validations passed!")
    print("=" * 60)
    print("\nTo run full tests: python -m pytest test_timeseries.py -v")
    print("To run integration tests: uncomment @unittest.skip decorators")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--quick":
        run_quick_validation()
    else:
        # Run unit tests
        unittest.main(verbosity=2)
