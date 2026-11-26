"""
Tests for SemanticEngine master pipeline.
"""

import pytest
from External_scanner.semantic_engine import SemanticEngine


def test_full_pipeline_macro_and_wrapper():
    code = """
    #define SECRET_KEY "hardcoded_master_key_123"
    
    void low_level_encrypt(char *k, char *data) {
        AES_set_encrypt_key(k, 128, data);
    }
    
    void high_level_wrapper() {
        char *my_key = SECRET_KEY;
        low_level_encrypt(my_key, buffer);
    }
    """
    engine = SemanticEngine()
    result = engine.analyze(code, "test_wrapper.c")

    # Verify macros were expanded
    assert "SECRET_KEY" not in result.expanded_code
    assert '"hardcoded_master_key_123"' in result.expanded_code

    # Verify wrappers were detected
    wrapper_names = [w.name for w in result.wrappers]
    assert "low_level_encrypt" in wrapper_names

    # Verify findings detected the hardcoded key
    assert len(result.findings) >= 1
    assert result.findings[0].cwe == "CWE-321"
    assert result.label == 1


def test_alias_aware_flow_tracking():
    code = """
    void run_crypto() {
        char *secret = "super_secret_pw";
        char *alias_ptr = secret;
        AES_set_encrypt_key(alias_ptr, 128, buf);
    }
    """
    engine = SemanticEngine(use_aliases=True)
    result = engine.analyze(code, "test_alias.c")

    # Check alias groups
    assert any("alias_ptr" in grp and "secret" in grp for grp in result.alias_groups)
    assert result.label == 1
    assert len(result.findings) >= 1


def test_ablation_disabled_macros():
    code = """
    #define SECRET_KEY "pass123"
    void run() {
        AES_set_encrypt_key(SECRET_KEY, 128, buf);
    }
    """
    # Without macro expansion, SECRET_KEY is not recognized as a string literal
    engine = SemanticEngine(use_macros=False)
    result = engine.analyze(code, "test_no_macro.c")
    assert "SECRET_KEY" in result.expanded_code


def test_graph_serialization_for_graph_builder():
    code = """
    void crypto_func() {
        char *key = "fixed_key";
        AES_set_encrypt_key(key, 128, NULL);
    }
    """
    engine = SemanticEngine()
    result = engine.analyze(code, "test_serialize.c")

    assert len(result.nodes) > 0
    assert any(n["type"] == "FILE" for n in result.nodes)
    assert any(n["type"] in ("FUNCTION", "WRAPPER") for n in result.nodes)
    assert len(result.edges) > 0
