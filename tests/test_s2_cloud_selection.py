import numpy as np
import types
import importlib

from sat_mon.data import composite as composite_mod


def test_select_s2_item_with_cloud_threshold_monkeypatched(monkeypatch):
    # Create fake items with ids indicating cloud levels
    # We'll encode cloud percentage in the id as 'cloudXX'
    def make_item(cloud_pct, dt_idx):
        return {
            'id': f'S2_item_cloud{cloud_pct:02d}_{dt_idx}',
            'properties': {
                'datetime': f'2024-01-{20-dt_idx:02d}T10:00:00Z',
            },
            'assets': {
                'SCL': {'href': f'http://example.com/scl_{cloud_pct}_{dt_idx}.tif'}
            }
        }

    items = [
        make_item(35, 0),  # newest, 35% cloud
        make_item(25, 1),
        make_item(9, 2),   # third newest, 9% cloud -> should be selected for threshold=10
        make_item(5, 3),   # older but lower cloud (should not be picked because we stop at first <= threshold)
    ]

    # Monkeypatch read_band to return SCL-like arrays with desired cloud fraction
    def fake_read_band(item, asset_key, bbox, dtype='uint8', out_shape=None, max_pixels=5_000_000, max_dim=4096):
        # Parse percent from id
        cid = item['id']
        try:
            pct = int(cid.split('cloud')[1].split('_')[0])
        except Exception:
            pct = 100
        # Create small array with pct% ones in cloud mask classes, represented by value 8
        size = 100
        arr = np.zeros((size, size), dtype=np.uint8)
        n_cloud = int(size * size * (pct / 100.0))
        if n_cloud > 0:
            arr.flat[:n_cloud] = 8  # 8 is a cloud class in our code
        return arr

    monkeypatch.setattr(composite_mod, 'read_band', fake_read_band)

    bbox = [0, 0, 1, 1]
    chosen_item, chosen_cloud, best_item, best_cloud = composite_mod._select_s2_item_with_cloud_threshold(
        items, bbox, threshold_pct=10.0
    )

    assert chosen_item is not None
    assert chosen_item['id'].startswith('S2_item_cloud09_')  # the third item should be chosen
    assert chosen_cloud is not None and abs(chosen_cloud - 9.0) < 0.5

    # If threshold is very low, fallback to best available (5%) even though it's older
    chosen_item2, chosen_cloud2, best_item2, best_cloud2 = composite_mod._select_s2_item_with_cloud_threshold(
        items, bbox, threshold_pct=4.0
    )
    assert chosen_item2 is not None
    assert chosen_item2['id'].startswith('S2_item_cloud05_')
    assert chosen_cloud2 is not None and abs(chosen_cloud2 - 5.0) < 0.5
