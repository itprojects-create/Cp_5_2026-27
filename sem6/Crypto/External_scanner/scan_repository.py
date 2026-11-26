import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path


SOURCE_EXTENSIONS = {
    ".c",
    ".cc",
    ".cpp",
    ".cxx",
    ".h",
    ".hh",
    ".hpp",
    ".hxx",
}

EXCLUDED_DIRECTORIES = {
    ".git",
    ".venv",
    "venv",
    "datasets",
    "reports",
    "__pycache__",
}

SCAN_TIMEOUT_SECONDS = 60


def extract_number(pattern, text):
    match = re.search(pattern, text, re.IGNORECASE)
    return int(match.group(1)) if match else 0


def extract_verdict(text):
    match = re.search(r"VERDICT:\s*(.+)", text, re.IGNORECASE)

    if not match:
        return "UNKNOWN"

    verdict = match.group(1).strip().upper()

    if "NO CONFIRMED" in verdict:
        return "NO_CONFIRMED_FLOW"

    if "CONFIRMED" in verdict or "VULNERABLE" in verdict:
        return "CONFIRMED_FLOW"

    return verdict


def collect_source_files(root):
    files = []

    for path in root.rglob("*"):
        if not path.is_file():
            continue

        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue

        if any(
            directory in EXCLUDED_DIRECTORIES
            for directory in path.parts
        ):
            continue

        files.append(path)

    return sorted(files)


def scan_file(scanner, source_file, project_root):
    command = [
        sys.executable,
        str(scanner),
        str(source_file),
    ]

    try:
        result = subprocess.run(
            command,
            cwd=str(project_root),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=SCAN_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        output = (exc.stdout or "") + (exc.stderr or "")
        record = {
            "file": source_file.relative_to(project_root).as_posix(),
            "status": "error",
            "return_code": -1,
            "literal_key_like_variables": 0,
            "cryptographic_call_sites": 0,
            "runtime_key_source_calls": 0,
            "confirmed_literal_to_crypto_flows": 0,
            "verdict": "TIMEOUT",
            "error_message": f"Scan exceeded {SCAN_TIMEOUT_SECONDS}s timeout",
        }
        record["error_message"] = (output[-1000:] or record["error_message"])
        return record

    output = result.stdout + result.stderr

    record = {
        "file": source_file.relative_to(project_root).as_posix(),
        "status": "ok" if result.returncode == 0 else "error",
        "return_code": result.returncode,
        "literal_key_like_variables": extract_number(
            r"Literal key-like variables found:\s*(\d+)",
            output,
        ),
        "cryptographic_call_sites": extract_number(
            r"Cryptographic call sites found:\s*(\d+)",
            output,
        ),
        "runtime_key_source_calls": extract_number(
            r"Runtime key-source calls found:\s*(\d+)",
            output,
        ),
        "confirmed_literal_to_crypto_flows": extract_number(
            r"Confirmed literal-to-crypto flows:\s*(\d+)",
            output,
        ),
        "verdict": extract_verdict(output),
    }

    if result.returncode != 0:
        record["error_message"] = output[-1000:]

    return record


def main():
    parser = argparse.ArgumentParser(
        description="Recursively scan a source-code directory."
    )

    parser.add_argument(
        "--root",
        required=True,
        help="Directory containing source files.",
    )

    parser.add_argument(
        "--output",
        default="reports/day4_scan",
        help="Output path without extension.",
    )

    args = parser.parse_args()

    script_path = Path(__file__).resolve()
    project_root = script_path.parents[1]

    scan_root = Path(args.root)

    if not scan_root.is_absolute():
        scan_root = project_root / scan_root

    scan_root = scan_root.resolve()
    scanner = script_path.parent / "scan_external_code.py"

    if not scan_root.exists():
        raise SystemExit(f"Directory not found: {scan_root}")

    if not scan_root.is_dir():
        raise SystemExit(f"Expected a directory: {scan_root}")

    if not scanner.exists():
        raise SystemExit(f"Scanner not found: {scanner}")

    source_files = collect_source_files(scan_root)

    if not source_files:
        raise SystemExit(
            f"No C/C++ source files found in: {scan_root}"
        )

    records = [
        scan_file(scanner, source_file, project_root)
        for source_file in source_files
    ]

    output_prefix = Path(args.output)

    if not output_prefix.is_absolute():
        output_prefix = project_root / output_prefix

    output_prefix.parent.mkdir(parents=True, exist_ok=True)

    json_path = output_prefix.with_suffix(".json")
    csv_path = output_prefix.with_suffix(".csv")
    summary_path = output_prefix.with_name(
        output_prefix.name + "_summary.json"
    )

    summary = {
        "scan_root": str(scan_root),
        "total_files": len(records),
        "successful_files": sum(
            record["status"] == "ok"
            for record in records
        ),
        "error_files": sum(
            record["status"] == "error"
            for record in records
        ),
        "confirmed_flow_files": sum(
            record["verdict"] == "CONFIRMED_FLOW"
            for record in records
        ),
        "no_confirmed_flow_files": sum(
            record["verdict"] == "NO_CONFIRMED_FLOW"
            for record in records
        ),
        "total_literal_key_like_variables": sum(
            record["literal_key_like_variables"]
            for record in records
        ),
        "total_cryptographic_call_sites": sum(
            record["cryptographic_call_sites"]
            for record in records
        ),
        "total_runtime_key_source_calls": sum(
            record["runtime_key_source_calls"]
            for record in records
        ),
        "total_confirmed_literal_to_crypto_flows": sum(
            record["confirmed_literal_to_crypto_flows"]
            for record in records
        ),
    }

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(records, file, indent=2)

    fieldnames = [
        "file",
        "status",
        "return_code",
        "literal_key_like_variables",
        "cryptographic_call_sites",
        "runtime_key_source_calls",
        "confirmed_literal_to_crypto_flows",
        "verdict",
        "error_message",
    ]

    with csv_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(records)

    with summary_path.open("w", encoding="utf-8") as file:
        json.dump(summary, file, indent=2)

    print("Day 4 repository scan completed.")
    print(f"Files scanned: {summary['total_files']}")
    print(f"Confirmed-flow files: {summary['confirmed_flow_files']}")
    print(
        "Confirmed literal-to-crypto flows: "
        f"{summary['total_confirmed_literal_to_crypto_flows']}"
    )
    print(f"JSON report: {json_path}")
    print(f"CSV report: {csv_path}")
    print(f"Summary report: {summary_path}")


if __name__ == "__main__":
    main()