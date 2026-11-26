"""
rust_crypto_apis.py: Catalog of known Rust cryptographic APIs, signatures,
and common misuse patterns across ring, rustls, openssl, and getrandom crates.
"""

from typing import Dict, List, Any


RUST_CRYPTO_APIS: Dict[str, Dict[str, Any]] = {
    "ring::aead::UnboundKey::new": {
        "crate": "ring",
        "type": "key_init",
        "parameters": ["algorithm", "key_bytes"],
        "misuse_patterns": ["hardcoded_key_bytes", "short_key"],
    },
    "ring::aead::SealingKey::new": {
        "crate": "ring",
        "type": "encryption",
        "parameters": ["key", "nonce"],
        "misuse_patterns": ["nonce_reuse", "weak_nonce", "static_nonce"],
    },
    "ring::aead::OpeningKey::new": {
        "crate": "ring",
        "type": "decryption",
        "parameters": ["key", "nonce"],
        "misuse_patterns": ["nonce_reuse"],
    },
    "ring::rand::SystemRandom::new": {
        "crate": "ring",
        "type": "csprng",
        "parameters": [],
        "misuse_patterns": [],  # Secure CSPRNG
    },
    "ring::digest::digest": {
        "crate": "ring",
        "type": "hash",
        "parameters": ["algorithm", "data"],
        "misuse_patterns": ["weak_hash_algorithm"],
    },
    "rustls::ClientConfig::new": {
        "crate": "rustls",
        "type": "tls_config",
        "parameters": [],
        "misuse_patterns": ["weak_cipher_suites", "certificate_validation_disabled"],
    },
    "rustls::ClientConfig::builder": {
        "crate": "rustls",
        "type": "tls_config",
        "parameters": [],
        "misuse_patterns": ["insecure_verifier"],
    },
    "rustls::ServerConfig::new": {
        "crate": "rustls",
        "type": "tls_config",
        "parameters": [],
        "misuse_patterns": ["deprecated_tls_version"],
    },
    "getrandom::getrandom": {
        "crate": "getrandom",
        "type": "csprng",
        "parameters": ["buffer"],
        "misuse_patterns": [],  # Secure OS-level CSPRNG
    },
    "openssl::symm::Cipher::aes_256_gcm": {
        "crate": "openssl",
        "type": "cipher_selection",
        "parameters": [],
        "misuse_patterns": [],
    },
    "openssl::symm::Cipher::des_cbc": {
        "crate": "openssl",
        "type": "cipher_selection",
        "parameters": [],
        "misuse_patterns": ["broken_cipher_des"],
    },
    "openssl::symm::encrypt": {
        "crate": "openssl",
        "type": "encryption",
        "parameters": ["cipher", "key", "iv", "data"],
        "misuse_patterns": ["hardcoded_key", "null_iv"],
    },
}
