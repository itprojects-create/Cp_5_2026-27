import pytest
from External_scanner.rust_detector import RustDetector


def test_vulnerable_hardcoded_key_rust():
    code = """
const HARDCODED_KEY: &[u8; 32] = b"secret_key_12345678901234567890";

fn run_crypto() {
    let key = ring::aead::UnboundKey::new(&ring::aead::AES_256_GCM, HARDCODED_KEY).unwrap();
}
"""
    detector = RustDetector()
    findings = detector.scan_code(code, file_path="vuln_key.rs")
    assert len(findings) == 1
    assert findings[0].cwe == "CWE-321"
    assert "HARDCODED_KEY" in findings[0].description


def test_vulnerable_static_nonce_rust():
    code = """
fn encrypt() {
    let nonce = STATIC_NONCE_ZERO;
    let sealing_key = ring::aead::SealingKey::new(key, nonce);
}
"""
    detector = RustDetector()
    findings = detector.scan_code(code, file_path="vuln_nonce.rs")
    assert len(findings) == 1
    assert findings[0].cwe == "CWE-323"


def test_clean_csprng_rust():
    code = """
fn safe_crypto() {
    let mut key_bytes = [0u8; 32];
    getrandom::getrandom(&mut key_bytes).unwrap();
    let key = ring::aead::UnboundKey::new(&ring::aead::AES_256_GCM, &key_bytes).unwrap();
}
"""
    detector = RustDetector()
    findings = detector.scan_code(code, file_path="clean_rng.rs")
    assert len(findings) == 0


def test_clean_standard_rust():
    code = """
fn process_network_packet(data: &[u8]) -> usize {
    data.len()
}
"""
    detector = RustDetector()
    findings = detector.scan_code(code, file_path="clean_std.rs")
    assert len(findings) == 0
