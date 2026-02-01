import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt


def test_error_overlay_create_and_dismiss():
    from src.sat_mon.gui.map_window import MapWindow
    window = MapWindow()
    fig, ax = window.create_window()
    try:
        # Show error
        window._show_error('Test error')
        assert hasattr(window, '_error_ax')
        assert window._error_ax is not None

        # Dismiss
        window._dismiss_error(None)
        assert not hasattr(window, '_error_ax') or window._error_ax is None
    finally:
        plt.close(fig)

ess = ['_loading_text']
def test_loading_overlay_show_and_hide():
    from src.sat_mon.gui.map_window import MapWindow
    window = MapWindow()
    fig, ax = window.create_window()
    try:
        window._show_loading('Loading...')
        assert hasattr(window, '_loading_text')
        assert window._loading_text is not None

        window._hide_loading()
        # Attribute may be removed or set to None
        assert not hasattr(window, '_loading_text') or window._loading_text is None
    finally:
        plt.close(fig)
