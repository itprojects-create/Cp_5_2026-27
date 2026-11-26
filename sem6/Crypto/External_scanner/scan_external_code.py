import json
import os
import re
import sys
from typing import Dict, List

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from External_scanner.c_parser import CParser

SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hpp",
    ".hxx",
}

CRYPTO_CALLS = [
    "EVP_EncryptInit_ex",
    "EVP_DecryptInit_ex",
    "EVP_CipherInit_ex",
    "AES_set_encrypt_key",
    "AES_set_decrypt_key",
    "RSA_public_encrypt",
    "RSA_private_decrypt",
    "CryptHashData",
    "CryptDeriveKey",
    "CryptEncrypt",
]

KEY_WORDS = [
    "key",
    "secret",
    "password",
    "passwd",
    "credential",
    "token",
]

RUNTIME_SOURCE_CALLS = [
    "fread",
    "read",
    "fgets",
    "fgetws",
    "getenv",
    "load_key",
    "read_key",
]


def _load_catalog():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    for candidate in (
        os.path.join(base_dir, "crypto_catalog.json"),
        os.path.join(os.getcwd(), "crypto_catalog.json"),
    ):
        if os.path.isfile(candidate):
            try:
                with open(candidate, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError):
                continue
    return {}


CRYPTO_CATALOG = _load_catalog()


def remove_comments(code):
    code = re.sub(r"/\*.*?\*/", "", code, flags=re.DOTALL)
    code = re.sub(r"//.*", "", code)
    return code


def find_literal_variables(code):
    variables = {}

    parser = CParser()
    result = parser.parse(code)

    for a in result.assignments:
        if not a.lhs or not a.rhs:
            continue
        name = a.lhs.strip()
        value = a.rhs.strip()

        if not any(word in name.lower() for word in KEY_WORDS):
            continue

        if value.startswith('"') or value.startswith('L"'):
            variables[name] = {
                "kind": "string_literal",
                "value": value,
                "line": a.line_number,
            }
        elif value.startswith("{"):
            variables[name] = {
                "kind": "array_literal",
                "value": value,
                "line": a.line_number,
            }

    return variables


def find_crypto_call_arguments(code):
    usages = []

    parser = CParser()
    result = parser.parse(code)

    api_set = set(CRYPTO_CALLS)
    for call in result.calls:
        if call.callee_name not in api_set:
            continue

        key_index = 0
        entry = CRYPTO_CATALOG.get(call.callee_name)
        if entry:
            key_index = int(entry.get("key_index", 0))

        usages.append({
            "api": call.callee_name,
            "arguments": call.arguments,
            "key_index": key_index,
            "line": call.line_number,
        })

    return usages


def find_runtime_sources(code):
    found = []

    for api in RUNTIME_SOURCE_CALLS:
        if re.search(rf"\b{re.escape(api)}\s*\(", code, flags=re.IGNORECASE):
            found.append(api)

    return found


def line_number_at(code, position):
    return code[:position].count("\n") + 1


def _usage_matches_variable(usage, variable_name):
    args = usage["arguments"]
    if not args:
        return False
    key_index = usage.get("key_index")
    if key_index is not None and 0 <= key_index < len(args):
        return bool(re.search(rf"\b{re.escape(variable_name)}\b", args[key_index]))
    return bool(re.search(rf"\b{re.escape(variable_name)}\b", " ".join(args)))


def scan_file(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as file:
        original_code = file.read()

    from External_scanner.macro_expander import MacroExpander
    expanded_code = MacroExpander().expand(original_code)
    code = remove_comments(expanded_code)

    literal_variables = find_literal_variables(code)
    crypto_usages = find_crypto_call_arguments(code)
    runtime_sources = find_runtime_sources(code)

    confirmed_flows = []

    for variable_name, details in literal_variables.items():
        for usage in crypto_usages:
            if _usage_matches_variable(usage, variable_name):
                confirmed_flows.append({
                    "variable": variable_name,
                    "kind": details["kind"],
                    "api": usage["api"],
                    "declaration_line": details["line"],
                    "api_line": usage["line"],
                })

    print("\n" + "=" * 80)
    print(f"File: {path}")
    print("Literal key-like variables found: " f"{len(literal_variables)}")
    print("Cryptographic call sites found: " f"{len(crypto_usages)}")
    print("Runtime key-source calls found: " f"{len(runtime_sources)}")
    print("Confirmed literal-to-crypto flows: " f"{len(confirmed_flows)}")

    if confirmed_flows:
        print("\nVERDICT: POSSIBLE CWE-321 " "WITH CONFIRMED VARIABLE FLOW")

        print("\nConfirmed evidence:")

        for flow in confirmed_flows:
            print(f"- Variable '{flow['variable']}' " f"({flow['kind']})")
            print(f"  Declaration line: " f"{flow['declaration_line']}")
            print(f"  Used in crypto API: " f"{flow['api']}")
            print(f"  Crypto API line: " f"{flow['api_line']}")
    else:
        print("\nVERDICT: NO CONFIRMED CWE-321 " "VARIABLE FLOW")

    if literal_variables:
        print("\nLiteral key-like declarations:")
        for name, details in literal_variables.items():
            print(f"- {name}: {details['kind']} at line {details['line']}")

    if crypto_usages:
        print("\nCryptographic call sites:")
        for usage in crypto_usages:
            print(f"- {usage['api']} at line {usage['line']}")


def main():
    if len(sys.argv) != 2:
        print("Usage: python scan_external_code.py <source_file>")
        return

    path = sys.argv[1]

    if not os.path.exists(path):
        print(f"File not found: {path}")
        return

    if not os.path.isfile(path):
        print(f"Not a regular file: {path}")
        return

    if os.path.splitext(path)[1].lower() not in SOURCE_EXTENSIONS:
        print(f"Unsupported source extension: {path}")
        return

    scan_file(path)


if __name__ == "__main__":
    main()