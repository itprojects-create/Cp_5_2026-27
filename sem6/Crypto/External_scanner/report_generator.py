"""
ReportGenerator: Multi-format vulnerability reporting engine.
Exports finding reports to JSON, CSV, and HTML formats with evidence paths.
"""

import csv
import html
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any


@dataclass
class Finding:
    finding_id: str
    cwe: str
    severity: str  # "critical", "high", "medium", "low"
    confidence: float
    source_location: str  # e.g., "src/crypto.c:15"
    description: str
    evidence_path: List[Dict[str, Any]] = field(default_factory=list)
    remediation: str = "Use AWS Secrets Manager or secure runtime configuration"
    fixed_code: Optional[str] = None
    explanation: Optional[str] = None
    visualization_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ReportGenerator:
    """
    Generates JSON, CSV, and HTML vulnerability reports from Finding instances.
    """

    def generate_json(self, findings: List[Finding], path: str):
        """
        Outputs machine-readable JSON report.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        data = {
            "total_findings": len(findings),
            "findings": [f.to_dict() for f in findings],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def generate_csv(self, findings: List[Finding], path: str):
        """
        Outputs spreadsheet-compatible CSV report.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        fieldnames = [
            "finding_id",
            "cwe",
            "severity",
            "confidence",
            "source_location",
            "description",
            "evidence_steps",
            "remediation",
        ]
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for finding in findings:
                writer.writerow(
                    {
                        "finding_id": finding.finding_id,
                        "cwe": finding.cwe,
                        "severity": finding.severity,
                        "confidence": f"{finding.confidence:.2f}",
                        "source_location": finding.source_location,
                        "description": finding.description,
                        "evidence_steps": len(finding.evidence_path),
                        "remediation": finding.remediation,
                    }
                )

    def generate_html(self, findings: List[Finding], path: str):
        """
        Outputs modern, styled HTML report with evidence path inspection and remediation.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        rows_html = []
        for f in findings:
            sev_badge_color = {
                "critical": "red",
                "high": "red",
                "medium": "orange",
                "low": "yellow",
            }.get(f.severity.lower(), "gray")


            esc = html.escape
            escaped_severity = esc(f.severity)
            evidence_items = "".join(
                f"<li><code>{esc(str(step.get('node', step)))}</code> ({esc(str(step.get('type', '')))})</li>"
                for step in f.evidence_path
            )
            evidence_block = f"<ul style='margin: 4px 0 0 16px;'>{evidence_items}</ul>" if evidence_items else "<em>None</em>"

            viz_link = "N/A"
            if f.visualization_path:
                try:
                    rel_viz = os.path.relpath(f.visualization_path, os.path.dirname(os.path.abspath(path)))
                    rel_viz = rel_viz.replace("\\", "/")
                    viz_link = f"<a href='{esc(rel_viz, quote=True)}' target='_blank'>View 3D Graph</a>"
                except ValueError:
                    viz_link = f"<a href='{esc(str(f.visualization_path), quote=True)}' target='_blank'>View 3D Graph</a>"

            row = f"""
            <tr style="border-bottom: 1px solid #ccc; background: white; color: black;">
                <td style="padding: 12px; font-weight: bold; color: black;">{esc(f.finding_id)}</td>
                <td style="padding: 12px;">{esc(f.cwe)}</td>
                <td style="padding: 12px;"><span style="background: {esc(sev_badge_color)}; color: black; padding: 3px 8px; border-radius: 4px; font-size: 0.85em; text-transform: uppercase;">{escaped_severity}</span></td>
                <td style="padding: 12px;">{f.confidence:.2f}</td>
                <td style="padding: 12px; font-family: monospace;">{esc(f.source_location)}</td>
                <td style="padding: 12px;">{esc(f.description)}</td>
                <td style="padding: 12px;">{evidence_block}</td>
                <td style="padding: 12px;">{esc(f.remediation)}</td>
                <td style="padding: 12px;">{viz_link}</td>
            </tr>
            """
            rows_html.append(row)

        html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>CryptoFlow Security Report</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: white;
            color: black;
            margin: 0;
            padding: 32px;
        }}
        .header {{
            margin-bottom: 24px;
        }}
        h1 {{
            color: black;
            margin: 0 0 8px 0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: white;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5);
            color: black;
        }}
        th {{
            background: yellow;
            color: black;
            padding: 12px;
            text-align: left;
            font-size: 0.9em;
            text-transform: uppercase;
            border-bottom: 2px solid #ccc;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>CryptoFlow Misuse Detection Report</h1>
        <p>Total Findings: <strong>{len(findings)}</strong></p>
    </div>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>CWE</th>
                <th>Severity</th>
                <th>Confidence</th>
                <th>Location</th>
                <th>Description</th>
                <th>Evidence Path</th>
                <th>Remediation</th>
                <th>Viz</th>
            </tr>
        </thead>
        <tbody>
            {"".join(rows_html)}
        </tbody>
    </table>
</body>
</html>
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(html_content)
