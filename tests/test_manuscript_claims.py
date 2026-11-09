from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MANUSCRIPT_SOURCES = [
    ROOT / "manuscript.tex",
    ROOT / "manuscript_bioinspiration.tex",
    ROOT / "analysis" / "generate_iop_latex_manuscript.py",
    ROOT / "results" / "publication" / "manuscript.tex",
    ROOT / "results" / "publication" / "manuscript_bioinspiration.tex",
]

FORBIDDEN_UNSUPPORTED_CLAIMS = [
    "significantly outperforming all baselines",
    "superiority over all 5 baselines",
    r"T_{\text{adapt}} = 2.8",
    r"86.4\%",
    "Cortex-M4",
    "prevents permanent motor burnout",
    r"tab:adaptation_latency",
    "fastest dynamic engagement across all fault types",
    r"119.7\%",
    r"maintains $\eta_{\text{rec}} \ge 58\%$",
    "outperforming fixed CPG baselines",
    "Actuator Thermal Dissipation Stress",
    "electrical coil burnout risk",
]


@pytest.mark.parametrize("source_path", MANUSCRIPT_SOURCES, ids=lambda path: path.name)
def test_p0_manuscript_sources_exclude_unsupported_claims(source_path):
    text = source_path.read_text(encoding="utf-8")

    found = [claim for claim in FORBIDDEN_UNSUPPORTED_CLAIMS if claim in text]

    assert found == []
