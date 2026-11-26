"""
Explainer: Developer-friendly vulnerability explainer agent with risk assessment and attack scenarios.
"""

import os
from typing import Dict, Any, Optional

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


CWE_EXPLANATIONS = {
    "CWE-321": {
        "explanation": "A cryptographic key is directly embedded into the source code as a static string literal. Anyone with read access to the codebase or compiled binary can extract this key and decrypt sensitive data or forge signatures. To fix this, store keys outside source code in environment variables or a dedicated Secrets Manager.",
        "risk_level": "high",
        "attack_scenario": "An attacker decompiles the distributed application binary or reads a public repository commit, locates the plaintext key string, and impersonates legitimate servers or decrypts captured customer traffic.",
    },
    "CWE-338": {
        "explanation": "The code uses a standard pseudo-random number generator (such as rand()) for security-sensitive cryptographic operations. Standard PRNGs are deterministic and predictable, allowing adversaries to guess nonces or session tokens. Upgrade to a cryptographically secure random generator such as RAND_bytes() or getrandom().",
        "risk_level": "high",
        "attack_scenario": "An attacker observes a small sequence of generated nonces, recovers the internal seed state of the PRNG, and predicts all past and future keys and session identifiers.",
    },
    "CWE-327": {
        "explanation": "The application relies on a broken or deprecated cryptographic algorithm that no longer meets modern security standards. Known cryptanalytic attacks can compromise the confidentiality or integrity of protected data. Transition to modern primitives such as AES-GCM, ChaCha20-Poly1305, or SHA-256.",
        "risk_level": "critical",
        "attack_scenario": "An attacker leverages collision attacks or differential cryptanalysis on weak ciphers (e.g. MD5 or single DES) to decrypt stored passwords or forge authentication tokens in real time.",
    },
    "CWE-326": {
        "explanation": "The cryptographic key length is insufficient to resist modern brute-force attacks (e.g., RSA with <2048 bits or symmetric keys <128 bits). Increase key size to at least 256 bits for symmetric ciphers and 3072+ bits for asymmetric algorithms.",
        "risk_level": "high",
        "attack_scenario": "An adversary harnesses cloud compute or specialized ASIC hardware to factor small RSA moduli or exhaust the symmetric key space, obtaining full plaintext access.",
    },
    "CWE-329": {
        "explanation": "The Initialization Vector (IV) or nonce is hard-coded or statically initialized across cryptographic operations. Reusing nonces across encryptions destroys confidentiality under modes like CBC and GCM, exposing plaintext XOR diffs.",
        "risk_level": "critical",
        "attack_scenario": "An attacker captures two ciphertexts encrypted with the same key and IV, performs a two-time pad XOR cancellation, and recovers plaintext messages directly.",
    },
}


class Explainer:
    """
    Produces developer-oriented explanations of cryptographic flaws with risk ratings and attack scenarios.
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
        if self.use_mock:
            return self._mock_explanation(finding)
        return self._real_explanation(finding)

    def _mock_explanation(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        cwe = finding.get("cwe", "CWE-321")
        entry = CWE_EXPLANATIONS.get(cwe, CWE_EXPLANATIONS["CWE-321"])
        return {
            "finding_id": finding.get("finding_id", "CF-001"),
            "explanation": entry["explanation"],
            "risk_level": entry["risk_level"],
            "attack_scenario": entry["attack_scenario"],
        }

    def _real_explanation(self, finding: Dict[str, Any]) -> Dict[str, Any]:
        prompt = f"""You are explaining a cryptographic vulnerability to a developer.

Vulnerability:
- Type: {finding.get('cwe')}
- Location: {finding.get('source_location')}
- Issue: {finding.get('description')}

Explain in 3-4 sentences:
1. What the vulnerability is (simple terms)
2. Why it's dangerous (what could attacker do?)
3. How to fix it (concrete steps)
4. Reference to OWASP/CWE guidelines

Return a concise explanation, risk level (critical/high/medium/low), and attack scenario."""

        try:
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )
            return {
                "finding_id": finding.get("finding_id", "CF-001"),
                "explanation": response.content[0].text,
                "risk_level": "high",
                "attack_scenario": "Attacker extracts hardcoded key or predicts nonces to decrypt communications.",
            }
        except Exception:
            return self._mock_explanation(finding)
