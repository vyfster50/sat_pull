
import numpy as np
import unittest
from src.sat_mon.processing.indices import process_indices
from src.sat_mon.processing.radar import compute_rvi

class TestIndices(unittest.TestCase):
    def test_process_indices(self):
        # Mock data
        shape = (10, 10)
        s2_data = {
            "red": np.full(shape, 1000, dtype=np.uint16),      # 0.1
            "green": np.full(shape, 2000, dtype=np.uint16),    # 0.2
            "blue": np.full(shape, 500, dtype=np.uint16),      # 0.05
            "nir": np.full(shape, 4000, dtype=np.uint16),      # 0.4
            "swir": np.full(shape, 1500, dtype=np.uint16),     # 0.15
            "red_edge": np.full(shape, 3000, dtype=np.uint16), # 0.3
            "scl": np.full(shape, 4, dtype=np.uint8)           # Vegetation
        }
        
        s1_data = {
            "vv": np.full(shape, 0.1, dtype=np.float32),
            "vh": np.full(shape, 0.02, dtype=np.float32)
        }
        
        weather_data = {"temp": [20, 21]}
        
        data = {
            "s2": s2_data,
            "s1": s1_data,
            "weather": weather_data,
            "bbox": [0, 0, 1, 1]
        }
        
        # Run processing
        processed = process_indices(data)
        
        # Check indices
        # EVI
        # red=0.1, nir=0.4, blue=0.05
        # num = 2.5 * (0.4 - 0.1) = 0.75
        # den = 0.4 + 6*0.1 - 7.5*0.05 + 1 = 0.4 + 0.6 - 0.375 + 1 = 1.625
        # evi = 0.75 / 1.625 = 0.4615
        self.assertIn("evi", processed)
        self.assertTrue(np.allclose(processed["evi"], 0.75 / 1.625, atol=0.01))
        
        # SAVI
        # L=0.5
        # num = 0.4 - 0.1 = 0.3
        # den = 0.4 + 0.1 + 0.5 = 1.0
        # savi = (0.3 / 1.0) * 1.5 = 0.45
        self.assertIn("savi", processed)
        self.assertTrue(np.allclose(processed["savi"], 0.45, atol=0.01))
        
        # NDMI
        # (NIR - SWIR) / (NIR + SWIR) = (0.4 - 0.15) / (0.4 + 0.15) = 0.25 / 0.55 = 0.4545
        self.assertIn("ndmi", processed)
        self.assertTrue(np.allclose(processed["ndmi"], 0.25/0.55, atol=0.01))
        
        # NDWI
        # (Green - NIR) / (Green + NIR) = (0.2 - 0.4) / (0.2 + 0.4) = -0.2 / 0.6 = -0.333
        self.assertIn("ndwi", processed)
        self.assertTrue(np.allclose(processed["ndwi"], -1/3, atol=0.01))
        
        # RVI
        # 4 * VH / (VV + VH) = 4 * 0.02 / (0.1 + 0.02) = 0.08 / 0.12 = 0.666
        self.assertIn("rvi", processed)
        self.assertTrue(np.allclose(processed["rvi"], 2/3, atol=0.01))
        
        # Weather
        self.assertIn("weather", processed)
        self.assertEqual(processed["weather"], weather_data)

if __name__ == '__main__':
    unittest.main()
