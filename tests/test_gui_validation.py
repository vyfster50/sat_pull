import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt


def make_selector():
    from src.sat_mon.gui.field_selector import FieldSelector
    fig, ax = plt.subplots()
    selector = FieldSelector(ax)
    return fig, selector


def test_validate_no_selection():
    fig, selector = make_selector()
    try:
        ok, msg = selector.validate_selection()
        assert not ok
        assert 'No field selected' in msg
    finally:
        plt.close(fig)


def test_validate_rectangle_too_small():
    fig, selector = make_selector()
    try:
        selector.selection = {
            'type': 'rectangle',
            'center': {'lat': 0.0, 'lon': 0.0},
            'bbox': [-0.00025, -0.00025, 0.00025, 0.00025],  # ~55m span
        }
        ok, msg = selector.validate_selection()
        assert not ok
        assert 'too small' in msg
    finally:
        plt.close(fig)


def test_validate_rectangle_too_large():
    fig, selector = make_selector()
    try:
        selector.selection = {
            'type': 'rectangle',
            'center': {'lat': 0.0, 'lon': 0.0},
            'bbox': [-2.0, -2.0, 2.0, 2.0],  # ~444km span
        }
        ok, msg = selector.validate_selection()
        assert not ok
        assert 'too large' in msg
    finally:
        plt.close(fig)


def test_validate_circle_too_small():
    fig, selector = make_selector()
    try:
        selector.selection = {
            'type': 'circle',
            'center': {'lat': 0.0, 'lon': 0.0},
            'radius_km': 0.03,  # 30m radius, 60m diameter
            'bbox': [-0.00025, -0.00025, 0.00025, 0.00025],
        }
        ok, msg = selector.validate_selection()
        assert not ok
        assert 'too small' in msg
    finally:
        plt.close(fig)


def test_validate_rectangle_valid():
    fig, selector = make_selector()
    try:
        selector.selection = {
            'type': 'rectangle',
            'center': {'lat': -1.0, 'lon': 37.0},
            'bbox': [36.99, -1.005, 37.01, -0.995],  # ~2.2km span
        }
        ok, msg = selector.validate_selection()
        assert ok
        assert msg is None
    finally:
        plt.close(fig)


def test_validate_invalid_coords():
    fig, selector = make_selector()
    try:
        selector.selection = {
            'type': 'rectangle',
            'center': {'lat': 120.0, 'lon': 37.0},
            'bbox': [36.99, -1.005, 37.01, -0.995],
        }
        ok, msg = selector.validate_selection()
        assert not ok
        assert 'Invalid latitude' in msg
    finally:
        plt.close(fig)
