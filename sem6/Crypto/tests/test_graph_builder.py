import os
import tempfile
import torch
import pytest
from External_scanner.graph_builder import GraphBuilder
from External_scanner.graph_schema import NODE_FEATURE_DIM, EDGE_FEATURE_DIM


def test_simple_hardcoded_key_graph():
    code = """
#define API_KEY "fixed_secret_key_123"
void process() {
    char *key = API_KEY;
    AES_set_encrypt_key(key, 128, NULL);
}
"""
    builder = GraphBuilder()
    data = builder.build_from_source(code, file_path="crypto_test.c", label=1)

    assert data.x is not None
    assert data.x.shape[1] == NODE_FEATURE_DIM
    assert data.edge_index is not None
    assert data.edge_index.shape[0] == 2
    assert data.y.item() == 1
    assert len(data.node_ids) == data.x.shape[0]


def test_wrapper_function_case():
    code = """
void low_wrapper(char *k) {
    EVP_EncryptInit_ex(ctx, cipher, NULL, k, iv);
}

void high_wrapper(char *user_k) {
    low_wrapper(user_k);
}
"""
    builder = GraphBuilder()
    data = builder.build_from_source(code, file_path="wrapper_test.c", label=1)

    assert data.x.shape[0] > 3
    # Check that wrapper nodes exist in node_ids
    wrapper_nodes = [nid for nid in data.node_ids if "wrapper" in nid.lower()]
    assert len(wrapper_nodes) >= 2


def test_multi_file_batch_processing():
    builder = GraphBuilder()
    file1 = ('char *k = "pass"; AES_set_encrypt_key(k, 128, NULL);', "file1.c", 1)
    file2 = ('void clean_func() { int a = 10; }', "file2.c", 0)

    batch = builder.build_batch([file1, file2])
    assert batch.num_graphs == 2
    assert batch.y.tolist() == [1, 0]


def test_graph_serialization():
    code = 'char *k = "key123";'
    builder = GraphBuilder()
    data = builder.build_from_source(code, file_path="save_test.c", label=0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        pt_path = os.path.join(tmp_dir, "test_graph.pt")
        builder.save_graph(data, pt_path)
        assert os.path.exists(pt_path)

        loaded = builder.load_graph(pt_path)
        assert loaded.x.shape == data.x.shape
        assert loaded.y.item() == data.y.item()
