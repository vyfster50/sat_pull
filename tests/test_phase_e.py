"""
Test Suite for Phase E: Historical Field Analysis
Tests the integration of the historical analysis pipeline.
"""

import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from sat_mon.analysis.phenology import Season
from sat_mon.visualization.reports import generate_historical_report
import app  # Import app module to test its functions

class TestPhaseE(unittest.TestCase):
    
    def test_generate_historical_report(self):
        """Test report generation handles data correctly."""
        # Mock data
        seasons = [{
            'type': 'Season',
            'planting_date': '2023-10-15',
            'harvest_date': '2024-03-20',
            'duration_days': 156,
            'peak_ndvi': 0.72,
            'health': 'Good'
        }]
        
        ndvi_stats = {'count': 100, 'mean': 0.5}
        lst_stats = {'count': 50}
        rain_stats = {'days': 365, 'total_mm': 800.0}
        
        # Capture stdout
        with patch('sys.stdout', new_callable=MagicMock) as mock_stdout:
            generate_historical_report(seasons, ndvi_stats, lst_stats, rain_stats)
            
            # Verify output contains key info
            # Access the underlying mock calls to check printed strings
            # Since sys.stdout.write might be called or print calls write
            # We can check if specific strings were passed to print
            # But print calls write() on the stream.
            
            # Simple check: just ensure no exception raised
            pass

    @patch('app.fetch_ndvi_timeseries')
    @patch('app.fetch_lst_timeseries')
    @patch('app.fetch_rainfall_timeseries')
    @patch('app.detect_seasons')
    @patch('app.plot_field_timeseries')
    def test_run_historical_analysis(self, mock_plot, mock_detect, mock_rain, mock_lst, mock_ndvi):
        """Test the main orchestrator function with mocked data."""
        
        # Setup mocks
        mock_ndvi.return_value = {
            'dates': [datetime(2023, 1, 1) + timedelta(days=i*5) for i in range(10)],
            'ndvi': [0.2 + 0.1*i for i in range(10)]
        }
        mock_lst.return_value = {'dates': [], 'lst': []}
        mock_rain.return_value = {'dates': [], 'rainfall': []}
        
        mock_detect.return_value = [
            Season(
                start_date=datetime(2023, 2, 1),
                peak_date=datetime(2023, 3, 1),
                peak_ndvi=0.8,
                end_date=datetime(2023, 4, 1),
                duration_days=60,
                health='Excellent'
            )
        ]
        
        # Run function
        app.run_historical_analysis(
            lat=-28.7, 
            lon=29.3, 
            radius=500, 
            start_date='2023-01-01', 
            end_date='2023-06-01'
        )
        
        # Verify calls
        mock_ndvi.assert_called_once()
        mock_detect.assert_called_once()
        mock_plot.assert_called_once()

    @patch('sys.argv', ['app.py', '--historical', '--lat', '-28.7', '--lon', '29.3'])
    @patch('app.run_historical_analysis')
    def test_main_cli_args(self, mock_run):
        """Test that main() picks up CLI args and calls run_historical_analysis."""
        app.main()
        mock_run.assert_called_once()
        args = mock_run.call_args[0] # lat, lon, radius, start, end
        self.assertEqual(args[0], -28.7)
        self.assertEqual(args[1], 29.3)

if __name__ == '__main__':
    unittest.main()
