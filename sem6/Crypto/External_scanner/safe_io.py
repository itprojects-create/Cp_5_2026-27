"""
safe_io.py: Safe on-disk serialization helpers.

Pytorch Geometric ``Data`` objects are pickled with torch.save. Loading them with
``torch.load(weights_only=False)`` is unsafe: an untrusted ``.pt`` file can execute
arbitrary code during unpickling. This module registers the bounded set of
classes required to reconstruct CryptoFlow graphs and always loads with
``weights_only=True``.
"""

from typing import Any

import torch
from torch_geometric.data import Data
from torch_geometric.data.data import DataEdgeAttr, DataTensorAttr
from torch_geometric.data.storage import GlobalStorage

_SAFE_GLOBALS_REGISTERED = False

#: Classes CryptoFlow graph pickles may legitimately reference.
SAFE_GRAPH_GLOBALS = [Data, DataEdgeAttr, DataTensorAttr, GlobalStorage]


def _register_safe_globals() -> None:
    global _SAFE_GLOBALS_REGISTERED
    if _SAFE_GLOBALS_REGISTERED:
        return
    torch.serialization.add_safe_globals(SAFE_GRAPH_GLOBALS)
    _SAFE_GLOBALS_REGISTERED = True


def safe_load_graph(path: str) -> Any:
    """Load a Pytorch Geometric ``Data`` graph without arbitrary code execution."""
    _register_safe_globals()
    return torch.load(path, weights_only=True)