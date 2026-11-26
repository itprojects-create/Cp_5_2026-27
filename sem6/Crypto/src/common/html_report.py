"""
html_report.py — shared HTML chart rendering for all three compared methods.

Matches CryptoFlow's existing dark visual identity (see agents/visualizer.py
NODE_TYPE_COLORS / EDGE_TYPE_COLORS: dark slate background, cyan/magenta/
orange accents) so FusionHGNN's and CoCa's result pages look like the same
family of report as CryptoHGNN's. Charts are standalone, self-contained
Plotly HTML files (JS inlined) so they open offline with no errors.

Chart types mirror what CryptoHGNN's own scan reports show: class
distribution, prediction results (confusion-matrix-derived breakdown),
confusion matrix heatmap, and per-CWE performance. No flowcharts and no
"representation graph in a lattice spectrum" visuals are produced here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Sequence

import plotly.graph_objects as go

# --- Shared CryptoFlow dark palette (consistent with agents/visualizer.py) ---
BG_COLOR = "#0f172a"        # slate-900
PANEL_COLOR = "#1e293b"     # slate-800
TEXT_COLOR = "#e2e8f0"      # slate-200
GRID_COLOR = "#334155"      # slate-700
ACCENT_CYAN = "#06b6d4"
ACCENT_MAGENTA = "#ec4899"
ACCENT_ORANGE = "#f97316"
ACCENT_LIME = "#84cc16"
ACCENT_ROSE = "#f43f5e"

FONT = dict(family="Inter, 'Segoe UI', Helvetica, Arial, sans-serif", color=TEXT_COLOR, size=13)

_PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
  body {{
    margin: 0; padding: 24px 32px 48px 32px;
    background: {bg}; color: {text};
    font-family: 'Inter','Segoe UI',Helvetica,Arial,sans-serif;
  }}
  h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 4px; }}
  .subtitle {{ color: #94a3b8; font-size: 14px; margin-bottom: 24px; }}
  .chart-card {{
    background: {panel}; border: 1px solid {grid};
    border-radius: 10px; padding: 12px; margin-bottom: 24px;
  }}
</style>
</head>
<body>
<h1>{heading}</h1>
<div class="subtitle">{subtitle}</div>
{body}
</body>
</html>
"""


def _layout(title: str, xaxis_title: str = "", yaxis_title: str = "") -> go.Layout:
    return go.Layout(
        title=dict(text=title, font=dict(size=16, color=TEXT_COLOR)),
        paper_bgcolor=PANEL_COLOR,
        plot_bgcolor=PANEL_COLOR,
        font=FONT,
        xaxis=dict(title=xaxis_title, gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        yaxis=dict(title=yaxis_title, gridcolor=GRID_COLOR, zerolinecolor=GRID_COLOR),
        margin=dict(l=60, r=30, t=60, b=50),
    )


def class_distribution_figure(label_counts: Dict[str, int], split_name: str) -> go.Figure:
    labels = list(label_counts.keys())
    values = list(label_counts.values())
    fig = go.Figure(
        data=[go.Bar(x=labels, y=values, marker_color=[ACCENT_CYAN, ACCENT_ROSE][: len(labels)])],
        layout=_layout(f"Class Distribution — {split_name}", "Class", "Count"),
    )
    return fig


def confusion_matrix_figure(tp: int, tn: int, fp: int, fn: int) -> go.Figure:
    z = [[tn, fp], [fn, tp]]
    fig = go.Figure(
        data=go.Heatmap(
            z=z,
            x=["Pred: Not Vulnerable", "Pred: Vulnerable"],
            y=["True: Not Vulnerable", "True: Vulnerable"],
            colorscale=[[0, PANEL_COLOR], [1, ACCENT_CYAN]],
            text=z,
            texttemplate="%{text}",
            textfont=dict(color=TEXT_COLOR, size=16),
            showscale=False,
        ),
        layout=_layout("Confusion Matrix (Test Split)"),
    )
    return fig


def prediction_results_figure(main_metrics: Dict[str, float]) -> go.Figure:
    keys = ["accuracy", "precision", "recall", "f1_score", "fp_rate", "fn_rate"]
    values = [main_metrics.get(k, 0.0) for k in keys]
    colors = [ACCENT_CYAN, ACCENT_LIME, ACCENT_LIME, ACCENT_CYAN, ACCENT_ROSE, ACCENT_ORANGE]
    fig = go.Figure(
        data=[go.Bar(x=keys, y=values, marker_color=colors, text=[f"{v:.3f}" for v in values], textposition="outside")],
        layout=_layout("Prediction Results — Main Metrics", "Metric", "Score"),
    )
    fig.update_yaxes(range=[0, 1.1])
    return fig


def per_cwe_figure(per_cwe: Dict[str, Dict[str, float]]) -> go.Figure:
    cwes = sorted(per_cwe.keys())
    f1s = [per_cwe[c].get("f1_score", 0.0) for c in cwes]
    accs = [per_cwe[c].get("accuracy", 0.0) for c in cwes]
    fig = go.Figure(
        data=[
            go.Bar(name="F1", x=cwes, y=f1s, marker_color=ACCENT_CYAN),
            go.Bar(name="Accuracy", x=cwes, y=accs, marker_color=ACCENT_MAGENTA),
        ],
        layout=_layout("Per-CWE Performance (Test Split)", "CWE", "Score"),
    )
    fig.update_layout(barmode="group", legend=dict(font=FONT))
    fig.update_yaxes(range=[0, 1.1])
    return fig


def resource_usage_figure(resources: Dict[str, float]) -> go.Figure:
    keys = ["train_time_s", "inference_time_s", "total_time_s"]
    values = [resources.get(k, 0.0) for k in keys]
    fig = go.Figure(
        data=[go.Bar(x=keys, y=values, marker_color=ACCENT_ORANGE, text=[f"{v:.2f}s" for v in values], textposition="outside")],
        layout=_layout("Execution Time", "Stage", "Seconds"),
    )
    return fig


def render_report(
    out_path: Path,
    title: str,
    heading: str,
    subtitle: str,
    figures: Sequence[go.Figure],
) -> Path:
    """Render a list of Plotly figures into one standalone offline HTML file."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    chunks: List[str] = []
    for i, fig in enumerate(figures):
        include_js = "inline" if i == 0 else False
        chunks.append(
            f'<div class="chart-card">'
            + fig.to_html(full_html=False, include_plotlyjs=include_js, config={"displaylogo": False})
            + "</div>"
        )
    html = _PAGE_TEMPLATE.format(
        title=title,
        heading=heading,
        subtitle=subtitle,
        body="\n".join(chunks),
        bg=BG_COLOR,
        panel=PANEL_COLOR,
        text=TEXT_COLOR,
        grid=GRID_COLOR,
    )
    out_path.write_text(html, encoding="utf-8")
    return out_path
