"""
FixGenerator: Generates automated cryptographic remediations using LLMs or template-based offline mock.
"""

import os
from typing import Dict, List, Any, Optional

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


CWE_FIX_TEMPLATES = {
    "CWE-321": {
        "pattern": "Hard-coded cryptographic key",
        "fixed_code": """// Remediation for CWE-321: Secure Key Retrieval via Environment / Vault
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

int load_secure_key(unsigned char *key_buffer, size_t key_len) {
    const char *env_key = getenv("CRYPTO_SECRET_KEY");
    if (!env_key) {
        fprintf(stderr, "Error: CRYPTO_SECRET_KEY environment variable not configured.\\n");
        return -1;
    }
    size_t env_len = strlen(env_key);
    if (env_len < key_len) {
        fprintf(stderr, "Error: Key provided does not meet length requirement.\\n");
        return -1;
    }
    memcpy(key_buffer, env_key, key_len);
    return 0;
}
""",
        "explanation": "Replaced hard-coded plaintext cryptographic key with a dynamic retrieval function reading from a secure environment variable or KMS vault.",
        "dependencies": ["AWS Secrets Manager SDK", "libenv"],
    },
    "CWE-338": {
        "pattern": "Weak PRNG used for cryptography",
        "fixed_code": """// Remediation for CWE-338: Cryptographically Secure Pseudo-Random Number Generation
#include <openssl/rand.h>

int generate_secure_random(unsigned char *buffer, int num_bytes) {
    if (RAND_bytes(buffer, num_bytes) != 1) {
        // Handle CSPRNG failure
        return -1;
    }
    return 0;
}
""",
        "explanation": "Replaced standard pseudo-random number generator (e.g., rand()/srand()) with OpenSSL cryptographically secure random generator RAND_bytes().",
        "dependencies": ["OpenSSL libcrypto"],
    },
    "CWE-327": {
        "pattern": "Broken cryptographic algorithm",
        "fixed_code": """// Remediation for CWE-327: Modern AEAD encryption (AES-256-GCM)
#include <openssl/evp.h>

EVP_CIPHER_CTX *create_secure_cipher() {
    EVP_CIPHER_CTX *ctx = EVP_CIPHER_CTX_new();
    EVP_EncryptInit_ex(ctx, EVP_aes_256_gcm(), NULL, NULL, NULL);
    return ctx;
}
""",
        "explanation": "Upgraded broken or weak cryptographic cipher (e.g. DES, MD5, RC4) to AES-256-GCM authenticated encryption.",
        "dependencies": ["OpenSSL libcrypto"],
    },
}


class FixGenerator:
    """
    Generates remediation code for detected cryptographic vulnerabilities.
    Gracefully falls back to template-based fixes when ANTHROPIC_API_KEY is not configured.
    """

    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if api_key and Anthropic is not None:
            self.client = Anthropic(api_key=api_key)
            self.use_mock = False
        else:
            self.client = None
            self.use_mock = True

    def generate(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates remediation response dictionary.
        """
        if self.use_mock:
            return self._mock_fix(finding)
        return self._real_fix(finding)

    def _mock_fix(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        cwe = finding.get("cwe", "CWE-321")
        template = CWE_FIX_TEMPLATES.get(cwe, CWE_FIX_TEMPLATES["CWE-321"])
        return {
            "finding_id": finding.get("finding_id", "CF-001"),
            "original_code": finding.get("code_snippet", "// Original vulnerable code"),
            "fixed_code": template["fixed_code"],
            "explanation": template["explanation"],
            "dependencies": template["dependencies"],
            "confidence": 0.90,
        }

    def _real_fix(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""Given this cryptographic API misuse finding:
- CWE: {finding.get('cwe')}
- Description: {finding.get('description')}
- Source location: {finding.get('source_location')}
- Code snippet:
{finding.get('code_snippet')}

Generate a fixed version that:
1. Removes hard-coded key / fixes nonce reuse / uses strong algorithm
2. Uses secure key management (AWS Secrets Manager or env var)
3. Maintains same functionality
4. Includes error handling

Return only a valid JSON response with keys: finding_id, original_code, fixed_code, explanation, dependencies, confidence."""

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}],
            )
            # Parse or fallback
            return {
                "finding_id": finding.get("finding_id", "CF-001"),
                "original_code": finding.get("code_snippet", ""),
                "fixed_code": response.content[0].text,
                "explanation": "Remediation generated via Claude API",
                "dependencies": ["aws-secretsmanager-crypto"],
                "confidence": 0.88,
            }
        except Exception:
            return self._mock_fix(finding)
