"""VAL-5 — integrity of the computation register.

These guard *catalogue drift*, not correctness: they prove the register still
describes the code that exists, that nothing user-visible has quietly appeared
without an entry, and that the generated documentation is current. None of them
claims a computation is right — that is what the per-entry ``status`` field is
for, and why it is conservative.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from scanpath_studio import computations as reg

REPO = Path(__file__).resolve().parents[1]


class TestSchema:
    def test_ids_are_unique_and_stable_shaped(self):
        ids = [entry.id for entry in reg.REGISTER]
        assert len(ids) == len(set(ids)), "duplicate register id"
        for entry_id in ids:
            assert "." in entry_id, f"{entry_id}: expected a `group.name` id"
            assert entry_id == entry_id.lower()
            assert " " not in entry_id

    def test_every_entry_is_completely_described(self):
        for entry in reg.REGISTER:
            assert entry.name, entry.id
            assert entry.summary.endswith("."), f"{entry.id}: summary is a sentence"
            assert entry.formula, f"{entry.id}: no formula"
            assert entry.category in reg.CATEGORIES, f"{entry.id}: {entry.category}"
            assert entry.status in reg.STATUSES, f"{entry.id}: {entry.status}"
            assert entry.consumers, f"{entry.id}: names no consumer"

    def test_a_verified_entry_names_the_test_that_verifies_it(self):
        """*Verified* is a claim about evidence, so it must point at some."""
        for entry in reg.REGISTER:
            if entry.status == reg.STATUS_VERIFIED:
                assert entry.tests, f"{entry.id} claims Verified with no tests"
                assert entry.tiers, f"{entry.id} claims Verified with no tier"

    @pytest.mark.parametrize("entry", reg.REGISTER, ids=lambda e: e.id)
    def test_the_code_link_resolves(self, entry):
        """Every entry points at a module and symbol that actually exist."""
        module_path = REPO / entry.module
        assert module_path.exists(), f"{entry.id}: no such file {entry.module}"
        if not entry.symbol:
            return
        module_name = entry.module.replace("/", ".").removesuffix(".py")
        module = importlib.import_module(module_name)
        assert hasattr(module, entry.symbol), (
            f"{entry.id}: {module_name} has no {entry.symbol}"
        )

    @pytest.mark.parametrize("entry", reg.REGISTER, ids=lambda e: e.id)
    def test_referenced_tests_exist(self, entry):
        for test_path in entry.tests:
            assert (REPO / test_path).exists(), f"{entry.id}: missing {test_path}"


class TestNothingUserVisibleIsMissing:
    """The catalogue must not fall behind the code it describes."""

    def test_every_canonical_measure_has_an_entry(self):
        from scanpath_studio.aggregation import MEASURES

        described = " ".join(
            f"{entry.output} {entry.formula} {entry.summary}" for entry in reg.REGISTER
        )
        for key, measure in MEASURES.items():
            assert measure.column in described, (
                f"aggregation.MEASURES['{key}'] → column "
                f"'{measure.column}' appears in no register entry"
            )

    def test_every_drift_correction_algorithm_is_covered(self):
        from scanpath_studio.alignment import ALGORITHMS

        entry = reg.BY_ID["align.algorithms"]
        for name in ALGORITHMS:
            assert name in entry.formula, f"algorithm '{name}' is not listed"

    def test_the_similarity_metric_is_covered(self):
        assert "sim.nld" in reg.BY_ID
        assert reg.BY_ID["sim.nld"].unit.startswith("dimensionless")

    def test_each_category_is_populated(self):
        """An empty category means the audit skipped a whole class of work."""
        for category in reg.CATEGORIES:
            if category == reg.CATEGORY_IMPORTED:
                continue  # covered by the `precedence` field on each measure
            assert reg.entries_in(category), f"no entries for {category}"


class TestGeneratedDocsAreCurrent:
    def test_the_docs_page_matches_the_register(self):
        """`python -m scanpath_studio.computations` regenerates it."""
        page = REPO / "docs" / "computations.md"
        assert page.exists(), "docs/computations.md has not been generated"
        assert page.read_text(encoding="utf-8") == reg.to_markdown(), (
            "docs/computations.md is stale — regenerate it with "
            "`python -m scanpath_studio.computations`"
        )

    def test_every_entry_reaches_the_page(self):
        rendered = reg.to_markdown()
        for entry in reg.REGISTER:
            assert f"`{entry.id}`" in rendered


class TestKnownInconsistenciesAreRecorded:
    """VAL-5 step 6: an audit records discrepancies, it does not silently fix
    them. Both findings from the recon pass were then fixed under their own BUG
    items, and the register carries what changed and why."""

    def test_the_saccade_amplitude_units_finding_is_recorded(self):
        entry = reg.BY_ID["fix.saccade_amplitude"]
        assert entry.unit == "px"
        assert "BUG-25" in entry.reference
        assert "_deg" in entry.precedence

    def test_the_two_within_word_scales_point_at_one_accessor(self):
        """#BUG-27. The audit found the letter measures deriving their own
        `width / len(text)` while the word *boundary* was BUG-11-corrected. Both
        now resolve through `word_char_advance`, and the two geometry entries
        have to say how they relate — a reader landing on either one must not
        conclude that the corrected AOI edge is where a word's letters start."""
        advance = reg.BY_ID["geom.word_char_advance"]
        assert "BUG-27" in advance.precedence
        for consumer in (
            "measure.landing_position",
            "agg.landing_curve",
        ):
            assert consumer in advance.precedence
            assert "word_char_advance" in reg.BY_ID[consumer].formula
        bounds = reg.BY_ID["geom.word_box_bounds"]
        assert "between" in bounds.precedence
        assert "word_char_advance" in bounds.precedence
