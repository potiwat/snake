from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
GENERATOR = ROOT / "analysis" / "generate_iop_latex_manuscript.py"


def test_p1_related_work_uses_bounded_literature_comparison_language():
    text = GENERATOR.read_text(encoding="utf-8")

    assert "Model-Based and Reactive Fault-Tolerant Locomotion" in text
    assert "within the references reviewed here" in text.lower()
    assert "no existing framework provides" not in text
    assert "diagnostic latency ($>1.5\\text{ s}$" not in text
    assert "fully decentralized, model-free mechanism" not in text
    assert "swarm swarming" not in text


def test_p3_abstract_uses_only_frozen_benchmark_evidence():
    text = GENERATOR.read_text(encoding="utf-8")

    assert "bootstrap 95\\% CI $[61.2,78.0]\\%$" in text
    assert "480 simulation episodes" in text
    assert "no aggregate difference from C6" in text
    assert "simulation-specific" in text
    abstract = text[text.index(r"\begin{abstract}"):text.index(r"\end{abstract}")]
    assert "disaster rubble" not in abstract
    assert "vertebrate spinal tissue" not in abstract


def test_p2_system_overview_generator_is_reproducible_and_uses_code_contract(tmp_path):
    from analysis.plot_publication import fig00_system_overview

    paths = fig00_system_overview(output_dir=tmp_path)
    assert {path.suffix for path in paths} == {".jpg", ".pdf"}
    assert all(path.exists() and path.stat().st_size > 0 for path in paths)


def test_p2_system_overview_uses_a_single_readable_signal_flow():
    plotter = ROOT / "analysis" / "plot_publication.py"
    text = plotter.read_text(encoding="utf-8")

    for label in (
        "Simulation interface",
        "Local deficit stimulus",
        "Spatial modulation",
        "Control branches",
        "SO(2) CPG",
        "Command synthesis",
    ):
        assert label in text
    assert "Discrete hormone update" not in text


def test_p2_manuscript_generation_preserves_a_user_selected_system_overview(tmp_path):
    from analysis.generate_iop_latex_manuscript import ensure_system_overview_figure

    selected = tmp_path / "fig00_system_overview.jpg"
    selected.write_bytes(b"user-selected-system-overview")

    assert ensure_system_overview_figure(tmp_path) == selected
    assert selected.read_bytes() == b"user-selected-system-overview"


def test_p2_robot_platform_figure_is_rendered_from_pybullet(tmp_path):
    from analysis.plot_publication import fig00_robot_platform

    paths = fig00_robot_platform(output_dir=tmp_path)

    assert {path.suffix for path in paths} == {".png", ".pdf"}
    assert all(path.exists() and path.stat().st_size > 10_000 for path in paths)


def test_p2_platform_description_is_prose_and_robot_caption_is_concise():
    text = GENERATOR.read_text(encoding="utf-8")

    assert "fig00_robot_platform.png" in text
    assert "Figure~\\ref{fig:fig00_robot} shows the PyBullet-rendered platform" in text
    assert "\\caption{PyBullet rendering of the simulated serial snake-robot platform.}" in text
    assert "\\includegraphics[width=0.72\\linewidth]{figures/fig00_robot_platform.png}" in text
    assert "\\includegraphics[width=0.98\\linewidth]{figures/fig00_system_overview.jpg}" in text


def test_p4_discussion_keeps_biological_and_hardware_claims_evidence_bounded():
    text = GENERATOR.read_text(encoding="utf-8")

    assert "$17.8\\%$ over its 10 simulated episodes" in text
    assert "do not maintain recovery under that tested friction transition" in text
    assert "do not imply recovery beyond a physical optimum" in text
    assert "does not include motor electrical or thermal dynamics" in text
    assert "No physiological measurements were performed" in text
    assert "preregister a parameter grid" in text
    assert r"\mathcal{S}_m" not in text
    assert "Resilient Homeostatic Operating Plateau" not in text
    assert "residual lateral yaw drift" not in text


def test_p6_manuscript_reports_paired_uncertainty_and_excludes_oracle_from_claims():
    text = GENERATOR.read_text(encoding="utf-8")

    assert "Favourable paired difference [95\\% CI]" in text
    assert "C4 is an oracle-informed reference" in text


def test_p7_captions_disclose_scope_censoring_and_selected_trajectory_limits():
    text = GENERATOR.read_text(encoding="utf-8")

    assert "eight scenarios into three fault-type groups with unequal cell sizes" in text
    assert "recovery ratios above $100\\%$" in text
    assert "selected trajectory; it is descriptive" in text
    assert "zero false alarms across all 480 episodes" not in text
    assert "confirming effective bypass phase bridging" not in text
    assert "verifying the analytical phase-locking stability proof" not in text
