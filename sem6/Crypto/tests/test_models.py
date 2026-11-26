import torch
import pytest
from torch_geometric.data import Data, Batch
from External_scanner.graph_schema import NODE_FEATURE_DIM
from models.gnns.generic_gnn import GenericGNN
from models.gnns.crypto_gnn import CryptoGNN
from models.gnns.generic_hgnn import GenericHGNN
from models.gnns.crypto_hgnn import CryptoHGNN


@pytest.fixture
def sample_graph():
    # 4 nodes, 4 edges
    x = torch.randn((4, NODE_FEATURE_DIM))
    edge_index = torch.tensor([[0, 1, 2, 3], [1, 2, 3, 0]], dtype=torch.long)
    y = torch.tensor([1], dtype=torch.long)
    return Data(x=x, edge_index=edge_index, y=y)


def test_generic_gnn(sample_graph):
    model = GenericGNN()
    model.eval()
    with torch.no_grad():
        out = model(sample_graph)
    assert out.shape == (1, 5)

    binary_model = GenericGNN(num_classes=2)
    binary_model.eval()
    with torch.no_grad():
        out_bin = binary_model(sample_graph)
    assert out_bin.shape == (1, 2)


def test_crypto_gnn(sample_graph):
    model = CryptoGNN()
    model.eval()
    with torch.no_grad():
        out = model(sample_graph)
    assert out.shape == (1, 5)

    binary_model = CryptoGNN(num_classes=2)
    binary_model.eval()
    with torch.no_grad():
        out_bin = binary_model(sample_graph)
    assert out_bin.shape == (1, 2)


def test_generic_hgnn(sample_graph):
    model = GenericHGNN()
    model.eval()
    with torch.no_grad():
        out = model(sample_graph)
    assert out.shape == (1, 5)

    binary_model = GenericHGNN(num_classes=2)
    binary_model.eval()
    with torch.no_grad():
        out_bin = binary_model(sample_graph)
    assert out_bin.shape == (1, 2)


def test_crypto_hgnn(sample_graph):
    model = CryptoHGNN()
    model.eval()
    with torch.no_grad():
        out = model(sample_graph)
    assert out.shape == (1, 5)

    binary_model = CryptoHGNN(num_classes=2)
    binary_model.eval()
    with torch.no_grad():
        out_bin = binary_model(sample_graph)
    assert out_bin.shape == (1, 2)


def test_batched_forward(sample_graph):
    batch = Batch.from_data_list([sample_graph, sample_graph])
    model = CryptoHGNN()
    out = model(batch)
    assert out.shape == (2, 5)
