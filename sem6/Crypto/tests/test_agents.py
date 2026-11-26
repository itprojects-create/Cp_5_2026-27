import os
import tempfile
import torch
import pytest
from torch_geometric.data import Data
from agents.fix_generator import FixGenerator
from agents.explainer import Explainer
from agents.visualizer import Visualizer
from agents.repo_scanner_agent import RepoScannerAgent


def test_fix_generator_mock():
    generator = FixGenerator()
    finding = {
        "finding_id": "CF-101",
        "cwe": "CWE-321",
        "description": "Hard-coded key in static variable",
        "source_location": "crypto.c:12",
        "code_snippet": 'char *key = "hardcoded_secret";',
    }
    result = generator.generate(finding)
    assert result["finding_id"] == "CF-101"
    assert "fixed_code" in result
    assert "explanation" in result
    assert len(result["dependencies"]) > 0


def test_explainer_mock():
    explainer = Explainer()
    finding = {
        "finding_id": "CF-102",
        "cwe": "CWE-321",
        "source_location": "auth.c:45",
        "description": "Static API key found",
    }
    result = explainer.generate(finding)
    assert result["finding_id"] == "CF-102"
    assert "explanation" in result
    assert result["risk_level"] in {"critical", "high", "medium", "low"}
    assert "attack_scenario" in result


def test_visualizer():
    with tempfile.TemporaryDirectory() as tmp_dir:
        viz = Visualizer(output_dir=tmp_dir)
        # Create dummy graph
        x = torch.randn((5, 32))
        edge_index = torch.tensor([[0, 1, 2], [1, 2, 3]], dtype=torch.long)
        data = Data(x=x, edge_index=edge_index)
        data.node_ids = ["node_0", "var_key_1", "func_AES", "node_3", "node_4"]

        html_path = viz.generate(data, evidence_path=["var_key_1", "func_AES"], finding_id="TEST-001")
        assert os.path.exists(html_path)
        with open(html_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Plotly" in content or "plotly" in content


def test_repo_scanner_agent():
    scanner = RepoScannerAgent()
    with tempfile.TemporaryDirectory() as tmp_dir:
        test_file = os.path.join(tmp_dir, "sample_vuln.c")
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("""
void encrypt_sample() {
    char *secret_key = "1234567812345678";
    AES_set_encrypt_key(secret_key, 128, NULL);
}
""")
        out_prefix = os.path.join(tmp_dir, "test_findings")
        findings = scanner.scan_repository(tmp_dir, output_report_prefix=out_prefix)
        assert len(findings) >= 1
        assert os.path.exists(f"{out_prefix}.json")
        assert os.path.exists(f"{out_prefix}.csv")
        assert os.path.exists(f"{out_prefix}.html")
