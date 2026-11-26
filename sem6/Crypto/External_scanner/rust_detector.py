"""
rust_detector.py: Minimal proof-of-concept cryptographic misuse detector for Rust.
Identifies hard-coded keys in const/static declarations, nonce reuse, and weak ciphers.
"""

import re
from typing import Dict, List, Optional, Any
from External_scanner.rust_parser import RustParser
from External_scanner.rust_crypto_apis import RUST_CRYPTO_APIS
from External_scanner.report_generator import Finding


class RustDetector:
    """
    Analyzes Rust source files for cryptographic API misuse patterns.
    """

    def __init__(self):
        self.parser = RustParser()

    @staticmethod
    def _strip_refs(arg: str) -> str:
        """Removes Rust reference/pointer prefixes without character-stripping bugs."""
        text = arg.strip()
        if text.startswith("&mut "):
            text = text[len("&mut "):]
        elif text.startswith("&"):
            text = text[1:].lstrip()
        elif text.startswith("*"):
            text = text[1:].lstrip()
        return text

    def scan_file(self, file_path: str) -> List[Finding]:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
            return self.scan_code(code, file_path=file_path)
        except Exception:
            return []

    def scan_code(self, code: str, file_path: str = "main.rs") -> List[Finding]:
        parsed = self.parser.parse_code(code, file_path=file_path)
        findings: List[Finding] = []
        counter = 1

        constants = parsed["constants"]
        crypto_calls = parsed["crypto_calls"]
        let_bindings = parsed.get("let_bindings", [])

        # Track known hard-coded key names
        hardcoded_key_names = set()
        for const_def in constants:
            val_lower = const_def.value.lower()
            name_lower = const_def.name.lower()
            # If value is a literal byte slice b"..." or string
            if val_lower.startswith('b"') or val_lower.startswith('"') or any(k in name_lower for k in ["key", "secret", "passwd"]):
                hardcoded_key_names.add(const_def.name)

        # Track local assignments: let var = val; (from AST when available)
        local_bindings = {p.name: p.value for p in let_bindings}
        for line in code.splitlines():
            m = re.search(r"let\s+(?:mut\s+)?(?P<var>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?P<val>[^;]+);", line)
            if m and m.group("var").strip() not in local_bindings:
                local_bindings[m.group("var").strip()] = m.group("val").strip()

        # Check crypto calls for misuse patterns
        for call in crypto_calls:
            api_info = RUST_CRYPTO_APIS.get(call.callee_path, {})
            api_type = api_info.get("type", "")

            # 1. Check for hard-coded key passing to key_init or encryption
            if api_type in {"key_init", "encryption"}:
                for arg in call.arguments:
                    arg_clean = self._strip_refs(arg)
                    resolved_val = local_bindings.get(arg_clean, arg_clean)
                    is_literal = (
                        arg_clean.startswith('b"')
                        or arg_clean.startswith('"')
                        or resolved_val.startswith('b"')
                        or resolved_val.startswith('"')
                        or (resolved_val.lower().startswith("b\"") or resolved_val.lower().startswith('"'))
                    )
                    if arg_clean in hardcoded_key_names or is_literal:
                        f = Finding(
                            finding_id=f"RS-{counter:03d}",
                            cwe="CWE-321",
                            severity="high",
                            confidence=0.95,
                            source_location=f"{file_path}:{call.line_number}",
                            description=f"Rust cryptographic key initialization with hard-coded byte key '{arg_clean}' in {call.callee_path}",
                            evidence_path=[
                                {"node": arg_clean, "type": "CONST_DECLARATION"},
                                {"node": call.callee_path, "type": "CRYPTO_API"},
                            ],
                            remediation="Retrieve key dynamically using getrandom or KMS environment secret",
                        )
                        findings.append(f)
                        counter += 1

            # 2. Check for weak algorithms
            if "des_cbc" in call.callee_path.lower() or "md5" in call.callee_path.lower():
                f = Finding(
                    finding_id=f"RS-{counter:03d}",
                    cwe="CWE-327",
                    severity="critical",
                    confidence=0.99,
                    source_location=f"{file_path}:{call.line_number}",
                    description=f"Rust crypto usage of broken cipher algorithm in {call.callee_path}",
                    evidence_path=[{"node": call.callee_path, "type": "BROKEN_ALGORITHM"}],
                    remediation="Upgrade to AES-256-GCM or ChaCha20-Poly1305 AEAD cipher",
                )
                findings.append(f)
                counter += 1

            # 3. Check for static nonce reuse
            if "SealingKey" in call.callee_path or "seal" in call.callee_path.lower():
                for arg in call.arguments:
                    arg_clean = self._strip_refs(arg)
                    resolved_val = local_bindings.get(arg_clean, arg_clean).upper()
                    if any(marker in resolved_val for marker in ("STATIC", "FIXED", "NONCE_ZERO", "ZERO_NONCE", "624")):
                        f = Finding(
                            finding_id=f"RS-{counter:03d}",
                            cwe="CWE-323",
                            severity="high",
                            confidence=0.92,
                            source_location=f"{file_path}:{call.line_number}",
                            description=f"Static nonce passed to AEAD SealingKey risking key compromise: {arg_clean}",
                            evidence_path=[{"node": arg_clean, "type": "STATIC_NONCE"}],
                            remediation="Generate fresh, unique nonces for each message using a cryptographically secure random counter or CSPRNG",
                        )
                        findings.append(f)
                        counter += 1

        return findings
