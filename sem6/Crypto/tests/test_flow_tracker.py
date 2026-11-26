import pytest
from External_scanner.flow_tracker import FlowTracker, FlowNode, FlowGraph


def test_argument_passing_dataflow():
    tracker = FlowTracker()
    graph = tracker.track_function_call(
        callee_name="AES_encrypt",
        caller_args=['"hardcoded_password"', "data_in"],
        callee_params=["key", "data"],
        line_number=10,
    )
    assert "arg_\"hardcoded_password\"_10" in graph.nodes
    assert "AES_encrypt_param_key" in graph.nodes
    assert graph.nodes["arg_\"hardcoded_password\"_10"].node_type == "LITERAL"
    assert graph.nodes["AES_encrypt_param_key"].node_type == "PARAMETER"
    assert len(graph.edges) == 2
    assert graph.edges[0].edge_type == "ARGUMENT_TO_PARAMETER"


def test_return_value_dataflow():
    tracker = FlowTracker()
    graph = tracker.track_return(
        caller_var="local_key",
        func_name="generate_key",
        return_expr="secret_buf",
        line_number=25,
    )
    assert "generate_key_ret_25" in graph.nodes
    assert "var_local_key_25" in graph.nodes
    assert graph.edges[0].edge_type == "RETURNS_TO"


def test_struct_field_dataflow():
    tracker = FlowTracker()
    graph = tracker.track_assignment(
        lhs="crypto_key",
        rhs="config.auth_secret",
        line_number=40,
    )
    assert "var_crypto_key_40" in graph.nodes
    assert "expr_config.auth_secret_40" in graph.nodes
    assert "var_config_40" in graph.nodes
    # Connected from base object to field and field to lhs
    edge_types = [e.edge_type for e in graph.edges]
    assert "ASSIGNED_FROM" in edge_types
    assert "FLOWS_TO" in edge_types


def test_pointer_dereference_bounded_depth():
    tracker = FlowTracker(max_deref_depth=3)
    graph = tracker.track_pointer_deref(
        ptr_var="ptr_key",
        dest_var="real_key",
        depth=5,  # Bound to 3
        line_number=50,
    )
    # Check that maximum 3 levels of dereferencing were created
    deref_nodes = [n for n in graph.nodes.values() if n.node_type == "DEREF"]
    assert len(deref_nodes) == 3
    assert "deref_***ptr_key_50" in graph.nodes
    assert "var_real_key_50" in graph.nodes


def test_array_index_dataflow():
    tracker = FlowTracker()
    graph = tracker.track_assignment(
        lhs="active_key",
        rhs="keys[0]",
        line_number=60,
    )
    assert "var_keys_60" in graph.nodes
    assert "expr_keys[0]_60" in graph.nodes
    assert "var_active_key_60" in graph.nodes


def test_evidence_path_construction():
    tracker = FlowTracker()
    # Step 1: Assignment "secret" -> raw_key
    tracker.track_assignment("raw_key", '"secret"', line_number=1)
    # Step 2: raw_key -> param key
    tracker.track_function_call("encrypt", ["raw_key"], ["key"], line_number=2)
    
    # Path from "secret" to encrypt_param_key
    source_id = 'expr_"secret"_1'
    # Connect var_raw_key_1 to arg_raw_key_2
    tracker.global_graph.add_edge('var_raw_key_1', 'arg_raw_key_2', 'FLOWS_TO')
    sink_id = 'encrypt_param_key'

    path = tracker.build_evidence_path(source_id, sink_id)
    assert len(path) >= 3
    node_ids = [n.id for n in path]
    assert source_id in node_ids
    assert sink_id in node_ids


class TestFlowTracker:
    def test_track_assignment(self):
        """Test variable assignment tracking."""
        tracker = FlowTracker()
        graph = tracker.track_assignment("key", '"hardcoded-key"', "test.c", 15)
        assert "key" in graph.nodes
        assert '"hardcoded-key"' in graph.nodes
        assert len(graph.edges) == 1
        assert graph.edges[0].edge_type == 'assignment'

    def test_track_function_call(self):
        """Test function call argument tracking."""
        tracker = FlowTracker()
        graph = tracker.track_function_call("encrypt", ["data", "key"], "test.c", 20)
        assert "encrypt" in graph.nodes
        assert "data" in graph.nodes
        assert "key" in graph.nodes
        assert len(graph.edges) == 2

    def test_track_return_value(self):
        """Test return value tracking."""
        tracker = FlowTracker()
        graph = tracker.track_return_value("get_key", "secret_key", "test.c", 10)
        assert "get_key" in graph.nodes
        assert "secret_key" in graph.nodes
        assert len(graph.edges) == 1
        assert graph.edges[0].edge_type == 'return_value'

    def test_track_struct_field(self):
        """Test struct field access tracking."""
        tracker = FlowTracker()
        graph = tracker.track_struct_field("config", "key", "test.c", 5)
        assert "config" in graph.nodes
        assert "config.key" in graph.nodes
        assert len(graph.edges) == 1

    def test_build_evidence_path(self):
        """Test evidence path construction."""
        tracker = FlowTracker()
        tracker.track_assignment("key", '"secret"', "test.c", 15)
        tracker.track_function_call("encrypt", ["key"], "test.c", 20)

        # Add edge from key to encrypt_arg0
        from External_scanner.flow_tracker import FlowEdge
        tracker.flow_graph.edges.append(FlowEdge("key", "encrypt_arg0", "flow"))

        path = tracker.build_evidence_path('"secret"', "encrypt_arg0")
        assert len(path) > 0
        assert '"secret"' in path

