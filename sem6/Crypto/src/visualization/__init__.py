"""
visualization package: 2D & 3D plotting utilities.
"""

def __getattr__(name):
    if name == "Visualizer3D":
        from src.visualization.visualizer_3d import Visualizer3D
        return Visualizer3D
    if name == "ComparePlots":
        from src.visualization.compare_plots import ComparePlots
        return ComparePlots
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["Visualizer3D", "ComparePlots"]
