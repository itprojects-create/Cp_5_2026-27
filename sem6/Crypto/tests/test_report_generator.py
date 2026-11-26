import json
import os
import tempfile
import pytest
from External_scanner.report_generator import ReportGenerator, Finding


def test_single_finding_report():
    finding = Finding(
        finding_id="CF-001",
        cwe="CWE-321",
        severity="high",
        confidence=0.95,
        source_location="src/crypto.c:15",
        description="Hard-coded cryptographic key",
        evidence_path=[{"node": "key_str", "type": "LITERAL"}, {"node": "AES_set_key", "type": "CRYPTO_API"}],
        remediation="Use AWS Secrets Manager",
    )
    generator = ReportGenerator()

    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = os.path.join(tmp_dir, "report.json")
        csv_path = os.path.join(tmp_dir, "report.csv")
        html_path = os.path.join(tmp_dir, "report.html")

        generator.generate_json([finding], json_path)
        generator.generate_csv([finding], csv_path)
        generator.generate_html([finding], html_path)

        assert os.path.exists(json_path)
        assert os.path.exists(csv_path)
        assert os.path.exists(html_path)

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["total_findings"] == 1
            assert data["findings"][0]["finding_id"] == "CF-001"


def test_multiple_findings_report():
    findings = [
        Finding(
            finding_id="CF-001",
            cwe="CWE-321",
            severity="high",
            confidence=0.92,
            source_location="auth.c:45",
            description="Hard-coded key in variable",
        ),
        Finding(
            finding_id="CF-002",
            cwe="CWE-338",
            severity="medium",
            confidence=0.88,
            source_location="session.c:80",
            description="Weak PRNG used for nonce",
        ),
    ]
    generator = ReportGenerator()

    with tempfile.TemporaryDirectory() as tmp_dir:
        json_path = os.path.join(tmp_dir, "multi_report.json")
        generator.generate_json(findings, json_path)
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["total_findings"] == 2
