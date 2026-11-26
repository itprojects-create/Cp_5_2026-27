import pytest
from External_scanner.call_graph import CallGraphBuilder, FunctionDef, CallSite


def test_direct_function_call():
    code = """
void helper() {
    printf("Helper\\n");
}

void caller() {
    helper();
}
"""
    builder = CallGraphBuilder()
    builder.extract_functions_from_code(code, file_path="direct.c")
    builder.extract_calls()
    resolved = builder.resolve_calls()

    caller_calls = [r for r in resolved if r.call_site.caller_name == "caller"]
    assert len(caller_calls) == 1
    assert caller_calls[0].target_def is not None
    assert caller_calls[0].target_def.name == "helper"


def test_indirect_call_through_function_pointer():
    code = """
void target_crypto_impl() {
    // Crypto logic
}

void dispatcher() {
    void (*fp)() = &target_crypto_impl;
    fp();
}
"""
    builder = CallGraphBuilder()
    builder.extract_functions_from_code(code, file_path="indirect.c")
    builder.extract_calls()
    resolved = builder.resolve_calls()

    indirect_calls = [r for r in resolved if r.call_site.caller_name == "dispatcher"]
    assert len(indirect_calls) >= 1
    assert any(r.target_def and r.target_def.name == "target_crypto_impl" for r in indirect_calls)


def test_cross_file_call_resolution():
    code_a = """
void service_entry() {
    crypto_module();
}
"""
    code_b = """
void crypto_module() {
    init_crypto();
}
"""
    builder = CallGraphBuilder()
    builder.extract_functions_from_code(code_a, file_path="service.c")
    builder.extract_functions_from_code(code_b, file_path="crypto.c")
    builder.extract_calls()
    resolved = builder.resolve_calls()

    adj = builder.get_adjacency_list()
    assert "crypto_module" in adj["service_entry"]
    assert "init_crypto" in adj["crypto_module"]
