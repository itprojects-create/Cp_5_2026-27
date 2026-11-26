"""
Regression tests for bugs fixed during the deep-refactor phase.

Covers: scan_external_code heuristics (B13/B14/B15), graph_builder magic
feature offsets & O(N) indexing (B17/B18), Rust param prefix stripping
(B20), chained Rust call extraction, case-insensitive weak-alg detection
(B23), non-pointer aliasing (B16) and wrapper detection in string literals.
"""

import pytest


# ---------------------------------------------------------------------- #
# scan_external_code (B13/B14/B15)
# ---------------------------------------------------------------------- #
def test_crypto_call_inside_comment_and_string_not_matched():
    from External_scanner.scan_external_code import find_crypto_call_arguments

    code = """
    void t() {
        // EVP_EncryptInit_ex(fake1, fake2);
        printf("AES_set_encrypt_key(hidden) not a call");
        EVP_EncryptInit_ex(ctx, cipher, NULL, key, iv);
    }
    """
    usages = find_crypto_call_arguments(code)
    assert len(usages) == 1
    assert usages[0]["api"] == "EVP_EncryptInit_ex"
    assert usages[0]["key_index"] == 3


def test_flow_matching_uses_per_api_key_index():
    from External_scanner.scan_external_code import (
        find_literal_variables,
        find_crypto_call_arguments,
        _usage_matches_variable,
    )

    code = """
        void setup(EVP_CIPHER_CTX *ctx, const EVP_CIPHER *cipher, EVP_CIPHER_CTX *schedule) {
            char *secret_key = "static";
            char *key_iv = "static";
            EVP_EncryptInit_ex(ctx, cipher, NULL, secret_key, key_iv);
            AES_set_encrypt_key(key_iv, 128, schedule);
        }
    """
    vars_ = find_literal_variables(code)
    assert set(vars_.keys()) == {"secret_key", "key_iv"}
    usages = find_crypto_call_arguments(code)
    by_api = {u["api"]: u for u in usages}

    # EVP key_index == 3: secret_key at index 3 must match, key_iv (idx 4) not.
    assert _usage_matches_variable(by_api["EVP_EncryptInit_ex"], "secret_key")
    assert not _usage_matches_variable(by_api["EVP_EncryptInit_ex"], "key_iv")

    # AES key_index == 0: key_iv at index 0 must match.
    assert _usage_matches_variable(by_api["AES_set_encrypt_key"], "key_iv")


def test_array_literal_with_nested_braces_parsed():
    from External_scanner.scan_external_code import find_literal_variables

    code = """
    unsigned char key_schedule[16] = {0x00, {0x01, 0x02}, 0x03};
    int plain = 42;
    """
    vars_ = find_literal_variables(code)
    assert "key_schedule" in vars_
    assert vars_["key_schedule"]["kind"] == "array_literal"
    assert "plain" not in vars_


# ---------------------------------------------------------------------- #
# graph_builder (B17/B18)
# ---------------------------------------------------------------------- #
def test_build_graph_handles_unknown_node_types_and_missing_endpoints():
    from External_scanner.graph_builder import GraphBuilder
    from External_scanner.graph_schema import NODE_FEATURE_DIM, EDGE_FEATURE_DIM

    result = {
        "nodes": [
            {"id": "a", "type": "made_up_type", "confidence": 0.9, "line_number": 3},
            {"id": "b", "type": "VARIABLE", "confidence": 1.0, "line_number": 4},
        ],
        "edges": [
            {"source": "a", "target": "b", "type": "FLOWS_TO", "confidence": 0.5},
            {"source": "b", "target": "missing_node", "type": "FLOWS_TO"},
        ],
        "label": 1,
    }
    data = GraphBuilder().build_graph(result)
    n = len(result["nodes"])
    assert data.x.shape == (n, NODE_FEATURE_DIM)
    assert data.edge_index.shape[1] == 1  # dangling edge skipped, not a crash
    assert data.edge_attr.shape == (1, EDGE_FEATURE_DIM)


def test_node_feature_uses_schema_encode():
    from External_scanner.graph_builder import GraphBuilder
    from External_scanner.graph_schema import NODE_FEATURE_DIM

    builder = GraphBuilder()
    feats = builder._encode_node_features(
        {"type": "KEY", "confidence": 0.77, "line_number": 42}
    )
    assert len(feats) == NODE_FEATURE_DIM
    # line number at index 30, confidence at index 31, boundary at 32, depth at 33
    assert feats[NODE_FEATURE_DIM - 4] == 42 / 1000.0
    assert abs(feats[NODE_FEATURE_DIM - 3] - 0.77) < 1e-6
    assert feats[NODE_FEATURE_DIM - 2] == 0.0
    assert feats[NODE_FEATURE_DIM - 1] == 0.0


# ---------------------------------------------------------------------- #
# rust_parser (B20) / rust_detector (B23)
# ---------------------------------------------------------------------- #
def test_rust_param_prefix_stripping_not_char_stripping():
    from External_scanner.rust_parser import RustParser

    code = """
    fn enc(mut key: &[u8]) {}
    fn mangle(&mut thumb: &[u8]) {}
    fn refs(&data: &[u8]) {}
    """
    parser = RustParser()
    result = parser.parse_code(code)
    names = {f.name: f.parameters for f in result["functions"]}
    assert names["enc"] == ["key"]
    assert names["mangle"] == ["thumb"]  # B20: 'thumb' must survive
    assert names["refs"] == ["data"]


def test_rust_chained_crypto_call():
    from External_scanner.rust_parser import RustParser

    code = """
    fn enc() {
        let key = ring::aead::UnboundKey::new(&ring::aead::AES_256_GCM, STATIC_KEY).unwrap();
    }
    """
    result = RustParser().parse_code(code)
    callees = [c.callee_path for c in result["crypto_calls"]]
    assert "ring::aead::UnboundKey::new" in callees
    new_call = next(c for c in result["crypto_calls"] if c.callee_path == "ring::aead::UnboundKey::new")
    assert len(new_call.arguments) == 2
    assert new_call.arguments[0] == "&ring::aead::AES_256_GCM"
    assert new_call.arguments[1] == "STATIC_KEY"


def test_rust_des_detection_is_case_insensitive():
    from External_scanner.rust_detector import RustDetector

    code = """
    fn weak() {
        let _ = ring::DesDES_CBC::new();
    }
    """
    findings = RustDetector().scan_code(code, file_path="weak.rs")
    assert any(f.cwe == "CWE-327" for f in findings)


# ---------------------------------------------------------------------- #
# Alias analysis (B16)
# ---------------------------------------------------------------------- #
def test_non_pointer_copy_not_aliased():
    from External_scanner.alias_analyzer import AliasAnalyzer

    code = """
    int x = 5;
    int y = x;
    char *p = &y;
    """
    analyzer = AliasAnalyzer()
    analyzer.find_pointer_assignments(code)
    analyzer.build_alias_sets()
    assert not analyzer.may_alias("x", "y")
    assert analyzer.may_alias("p", "y")


# ---------------------------------------------------------------------- #
# Wrapper / semantic engine (B5/B8)
# ---------------------------------------------------------------------- #
def test_crypto_api_inside_string_not_treated_as_wrapper_call():
    from External_scanner.wrapper_resolver import WrapperResolver

    code = '''
    void safe_log() {
        printf("AES_set_encrypt_key(not, a, call)");
    }
    '''
    resolver = WrapperResolver()
    functions = resolver.parse_functions(code)
    assert len(functions) == 1
    calls = {c.callee_name for c in functions[0].calls}
    assert calls == {"printf"}


def test_wrapper_arg_index_maps_to_key_position():
    from External_scanner.wrapper_resolver import WrapperResolver

    code = """
    void low(const unsigned char *k) {
        AES_set_encrypt_key(k, 128, ctx);
    }
    void high(const unsigned char *user_key) {
        low(user_key);
    }
    """
    resolver = WrapperResolver(crypto_apis={"AES_set_encrypt_key"})
    functions = resolver.parse_functions(code)
    wrappers = resolver.find_wrappers(functions)
    w = next(w for w in wrappers if w.name == "high")
    # high passes its first param to low; low's key flows to crypto arg 0.
    assert w.param_to_crypto_arg.get(0) == 0


def test_semantic_engine_hardcoded_key_through_wrapper():
    from External_scanner.semantic_engine import SemanticEngine

    code = '''
    void low(const unsigned char *key) {
        AES_set_encrypt_key(key, 128, ctx);
    }
    void high() {
        low("00 11 22 static key");
    }
    '''
    engine = SemanticEngine()
    result = engine.analyze(code, file_path="wrapped.c")
    hardcoded = [f for f in result.findings if f.vulnerability_type == "Hard-coded Cryptographic Key"]
    assert any("00 11 22 static key" in str(h.evidence_path) for h in hardcoded)