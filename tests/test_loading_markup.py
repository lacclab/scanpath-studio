"""UX-165: the loading card's markup and the plot-size bookkeeping."""

from __future__ import annotations

from scanpath_studio import loading
from scanpath_studio.constants import SELECTOR_ROW_GRID
from scanpath_studio.progress import Snapshot


def _snap(**overrides) -> Snapshot:
    base = dict(
        title="Loading PoTeC",
        steps=("Reading files", "Normalizing", "Building the trial list"),
        step_seconds=(2.4, None, None),
        current=1,
        done=312,
        total=900,
        unit="files",
        detail=None,
        elapsed=4.2,
        finished=False,
    )
    base.update(overrides)
    return Snapshot(**base)


def test_elapsed_reads_naturally_at_every_scale():
    assert loading.format_elapsed(0.84) == "0.8 s"
    assert loading.format_elapsed(42.4) == "42 s"
    assert loading.format_elapsed(125) == "2 min 5 s"
    assert loading.format_elapsed(120) == "2 min"


def test_counts_name_their_unit_and_bytes_read_as_megabytes():
    assert loading.format_count(312, 900, "files") == "312 of 900 files"
    assert loading.format_count(1200, None, "rows") == "1,200 rows"
    assert loading.format_count(120_000_000, 450_000_000, "bytes") == "120 of 450 MB"
    assert loading.format_count(3_200_000, None, "bytes") == "3.2 MB so far"
    assert loading.format_count(None, None, "files") == ""


def test_the_head_carries_title_time_and_last_load_and_escapes_the_title():
    html = loading.head_html(_snap(title="Load <b>x</b>"), last=6.0)
    assert "Load &lt;b&gt;x&lt;/b&gt;" in html
    assert "4.2 s · last load 6.0 s" in html
    assert 'role="status"' in html


def test_the_detail_line_joins_step_detail_and_count():
    html = loading.detail_html(_snap(detail="archive"))
    assert "Normalizing · archive · 312 of 900 files" in html


def test_the_step_list_marks_done_current_and_todo():
    html = loading.steps_html(_snap())
    assert html.count("sps-step-done") == 1
    assert html.count("sps-step-now") == 1
    assert html.count("sps-step-todo") == 1
    assert "2.4 s" in html and "312 of 900 files" in html
    assert "check_circle" in html  # icon_html("step_done") ligature


def test_the_bar_is_determinate_only_with_a_total():
    assert 'aria-valuenow="35"' in loading.bar_html(_snap())
    assert "sps-bar-indeterminate" in loading.bar_html(_snap(total=None))


def test_a_finished_task_shows_a_full_bar_not_a_sliding_one():
    """The page card stays up, every step ticked, until the view draws — a
    bar still sliding there would say the load is still working."""
    html = loading.bar_html(_snap(finished=True, done=None, total=None))
    assert 'aria-valuenow="100"' in html
    assert "sps-bar-indeterminate" not in html


def test_the_size_box_holds_the_exact_iframe_height():
    html = loading.size_box_html(960, 702)
    assert "height:702px" in html


def test_the_size_box_has_the_figures_own_width_capped_by_its_column():
    """A definite width — not a percentage — so the card's grid track can size
    to the figure, and the card centre over the figure, not the whole stage."""
    html = loading.size_box_html(960, 702)
    assert "width:960px;max-width:100%" in html


def test_the_scanpath_skeleton_follows_the_selector_grid_and_plot_height():
    html = loading.skeleton_html("scanpath", plot_height=640)
    tracks = " ".join(f"{w}fr" for w in SELECTOR_ROW_GRID)
    assert f"grid-template-columns:{tracks}" in html
    assert "height:640px" in html
    assert "sps-sk-scanpath" in html
    assert "sps-sk-corpus" in loading.skeleton_html("corpus")
    assert "sps-sk-table" in loading.skeleton_html("data")


def test_an_animation_estimate_is_taller_than_the_static_one():
    static_w, static_h = loading.estimate_plot_size(1680, 1050)
    anim_w, anim_h = loading.estimate_plot_size(1680, 1050, animation=True)
    assert static_w == anim_w
    assert anim_h > static_h > 0


def test_plot_size_prefers_the_recorded_size(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(loading, "_session", lambda: store)
    assert loading.plot_size("single", 1680, 1050) == loading.estimate_plot_size(
        1680, 1050
    )
    loading.record_plot_size("single", 900, 612)
    assert loading.plot_size("single", 1680, 1050) == (900, 612)
    assert loading.recorded_plot_height("single", 480) == 612
    assert loading.recorded_plot_height("compare", 480) == 480
