import pytest
from External_scanner.rust_parser import RustParser


def test_rust_parser_with_crypto_calls():
    code = """
const STATIC_KEY: &[u8; 32] = b"fixed_secret_key_bytes_12345678";

fn encrypt_payload() {
    let key = ring::aead::UnboundKey::new(&ring::aead::AES_256_GCM, STATIC_KEY).unwrap();
}
"""
    parser = RustParser()
    result = parser.parse_code(code, file_path="crypto_module.rs")

    assert len(result["constants"]) == 1
    assert result["constants"][0].name == "STATIC_KEY"
    assert len(result["functions"]) == 1
    assert result["functions"][0].name == "encrypt_payload"
    assert len(result["crypto_calls"]) >= 1
    assert result["crypto_calls"][0].callee_path == "ring::aead::UnboundKey::new"


def test_rust_parser_without_crypto_calls():
    code = """
fn calculate_fibonacci(n: u32) -> u32 {
    if n <= 1 {
        return n;
    }
    calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)
}
"""
    parser = RustParser()
    result = parser.parse_code(code, file_path="fib.rs")

    assert len(result["functions"]) == 1
    assert len(result["crypto_calls"]) == 0
