"""The stimulus / questions panel is data-driven, not OneStop-hardcoded.

It detects span columns (any per-word boolean whose name reads as a span) and
question/answer columns (any trial-level column whose name reads as
question/answer/correct), so it works on arbitrary corpora while keeping the
OneStop columns' friendly labels + span colours.
"""

from __future__ import annotations

import pandas as pd
import pytest

from scanpath_studio.tabs import (
    _detect_question_columns,
    _detect_span_columns,
    _humanize_field,
    _is_boolish,
)

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _comprehension_app():
    import json

    import pandas as pd

    from scanpath_studio.tabs import _render_comprehension_questions

    df = pd.DataFrame(
        {
            "comprehension_questions": [
                json.dumps(
                    [
                        {
                            "question": "Why more books?",
                            "target": "Better pillows",
                            "distractors": ["Cheaper", "Lighter"],
                            "condition": "local",
                            "question_no": 1,
                        }
                    ]
                )
            ]
        }
    )
    _render_comprehension_questions(df)


def _comprehension_malformed_app():
    import pandas as pd

    from scanpath_studio.tabs import _render_comprehension_questions

    _render_comprehension_questions(
        pd.DataFrame({"comprehension_questions": ["not json"]})
    )


class TestComprehensionQuestions:
    def test_excluded_from_generic_qa_detection(self):
        # The JSON column must NOT be caught by the generic question detector
        # (which would render the raw JSON blob).
        df = pd.DataFrame(
            {"text": ["a"], "comprehension_questions": ['[{"question": "Q"}]']}
        )
        assert "comprehension_questions" not in _detect_question_columns(df)

    def test_renders_questions_target_and_distractors(self):
        at = AppTest.from_function(_comprehension_app)
        at.run()
        assert not at.exception, at.exception
        md = " ".join(m.value for m in at.markdown)
        assert "Comprehension questions" in md
        assert "Why more books?" in md
        assert "✓ Better pillows" in md  # target marked
        assert "Cheaper" in md  # distractor

    def test_malformed_json_is_silent(self):
        at = AppTest.from_function(_comprehension_malformed_app)
        at.run()
        assert not at.exception
        assert " ".join(m.value for m in at.markdown).strip() == ""


class TestDetection:
    def test_onestop_spans_and_qa(self):
        w = pd.DataFrame(
            {
                "word_id": [0, 1, 2, 3],
                "text": ["the", "quick", "brown", "fox"],
                "is_in_aspan": [False, True, True, False],
                "is_in_dspan": [False, False, False, True],
                "question": ["What?"] * 4,
                "selected_answer": ["A"] * 4,
                "is_correct": [True] * 4,
                "question_preview": ["preview?"] * 4,
            }
        )
        # Known OneStop spans detected, in their canonical order.
        assert _detect_span_columns(w) == ["is_in_aspan", "is_in_dspan"]
        qa = _detect_question_columns(w)
        assert "question" in qa and "selected_answer" in qa and "is_correct" in qa
        # Span flags are NOT treated as Q&A text fields.
        assert "is_in_aspan" not in qa and "is_in_dspan" not in qa
        assert _humanize_field("is_in_aspan") == "Answer (critical) span"
        assert _humanize_field("question") == "Question"

    def test_generic_non_onestop_columns(self):
        w = pd.DataFrame(
            {
                "word_id": [0, 1, 2],
                "text": ["a", "b", "c"],
                "is_target_span": [True, False, True],
                "q_prompt": ["Pick one"] * 3,
                "response": ["yes"] * 3,
            }
        )
        assert _detect_span_columns(w) == ["is_target_span"]
        qa = _detect_question_columns(w)
        assert "q_prompt" in qa and "response" in qa
        assert _humanize_field("is_target_span") == "Is target span"

    def test_titles_and_reading_instructions_are_context(self):
        w = pd.DataFrame(
            {
                "word_id": [0, 1],
                "text": ["read", "this"],
                "passage_title": ["Practice"] * 2,
                "reading_instructions": ["Read naturally."] * 2,
            }
        )
        context = _detect_question_columns(w)
        assert "passage_title" in context
        assert "reading_instructions" in context

    def test_no_spans_or_qa(self):
        w = pd.DataFrame({"word_id": [0, 1], "text": ["a", "b"]})
        assert _detect_span_columns(w) == []
        assert _detect_question_columns(w) == []

    def test_per_word_varying_boolean_not_treated_as_qa(self):
        # A per-word *varying* boolean named like Q&A (e.g. "response") is
        # span-like data, not a trial-level field — it must NOT render as
        # "Response: True". A *constant* boolean (is_correct) stays Q&A.
        w = pd.DataFrame(
            {
                "word_id": [0, 1, 2],
                "text": ["a", "b", "c"],
                "response": [True, False, True],  # varies per word
                "is_correct": [True, True, True],  # constant per trial
            }
        )
        qa = _detect_question_columns(w)
        assert "response" not in qa
        assert "is_correct" in qa

    def test_string_id_column_not_boolish(self):
        # A string id column of "0"/"1" must not be mistaken for a boolean span.
        assert not _is_boolish(pd.Series(["0", "1", "0"]))
        assert _is_boolish(pd.Series([True, False, True]))

    def test_numeric_column_matching_a_qa_hint_is_not_treated_as_qa(self):
        # UX-32: a generic upload's unrelated numeric column (a timing/count/id
        # field) can still match a QA name hint by coincidence — e.g. a
        # `response_time_ms` column matches "response". It must not render as
        # bogus question/answer text ("Response time ms: 120").
        w = pd.DataFrame(
            {
                "word_id": [0, 1, 2],
                "text": ["a", "b", "c"],
                "response_time_ms": [120, 340, 210],
                "is_correct": [True, True, True],
            }
        )
        qa = _detect_question_columns(w)
        assert "response_time_ms" not in qa
        assert "is_correct" in qa


def _onestop_panel_app():
    import pandas as pd

    from scanpath_studio.tabs import _render_paragraph_panel

    w = pd.DataFrame(
        {
            "word_id": [0, 1, 2, 3],
            "text": ["the", "quick", "brown", "fox"],
            "is_in_aspan": [False, True, True, False],
            "is_in_dspan": [False, False, False, True],
            "question": ["Which colour?"] * 4,
            "selected_answer": ["A"] * 4,
            "is_correct": [True] * 4,
        }
    )
    _render_paragraph_panel(w)


def _generic_panel_app():
    import pandas as pd

    from scanpath_studio.tabs import _render_paragraph_panel

    w = pd.DataFrame(
        {
            "word_id": [0, 1, 2, 3],
            "text": ["alpha", "beta", "gamma", "delta"],
            "is_target_span": [False, True, True, False],
            "q_prompt": ["Pick the target"] * 4,
            "response": ["beta gamma"] * 4,
        }
    )
    _render_paragraph_panel(w)


class TestRender:
    def test_onestop_renders_question_and_spans(self):
        at = AppTest.from_function(_onestop_panel_app)
        at.run()
        assert not at.exception, at.exception
        md = " ".join(m.value for m in at.markdown)
        assert "Question" in md
        assert "Which colour?" in md
        assert "Answer (critical) span" in md
        assert "Distractor span" in md

    def test_generic_renders_detected_fields(self):
        at = AppTest.from_function(_generic_panel_app)
        at.run()
        assert not at.exception, at.exception
        md = " ".join(m.value for m in at.markdown)
        # Generic column names humanized + shown — no OneStop names required.
        assert "Q prompt" in md
        assert "Pick the target" in md
        assert "Response" in md
        assert "Is target span" in md


def _unhinted_panel_app():
    """A corpus whose columns match no name hint at all — the UX-32 case."""
    import pandas as pd

    from scanpath_studio.tabs import _render_paragraph_panel

    w = pd.DataFrame(
        {
            "word_id": [0, 1, 2, 3],
            "text": ["alpha", "beta", "gamma", "delta"],
            "focus_region": [False, True, True, False],
            "probe_text": ["Which one stands out?"] * 4,
        }
    )
    _render_paragraph_panel(w, bare=True)


class TestFieldPicker:
    """UX-32: name-hint detection supplies the defaults, the picker overrides it.

    The panel was "generic when the column *names* cooperate" — a corpus whose
    critical span is called `focus_region` and whose question is `probe_text` got
    nothing at all out of it. Exposing the fields is what makes it actually
    corpus-generic.
    """

    def _words(self):
        return pd.DataFrame(
            {
                "word_id": [0, 1, 2, 3],
                "text": ["alpha", "beta", "gamma", "delta"],
                "focus_region": [False, True, True, False],
                "is_in_aspan": [True, False, False, False],
                "probe_text": ["Which one stands out?"] * 4,
                "question": ["Which colour?"] * 4,
                "reading_time_ms": [1200] * 4,
                # Constant boolean: a trial-level fact, not a span.
                "is_correct": [True] * 4,
                # Per-word, non-boolean: neither a span nor a trial-level field.
                "surprisal": [1.0, 2.0, 3.0, 4.0],
            }
        )

    def test_candidates_are_wider_than_the_name_hints(self):
        from scanpath_studio.tabs import _stimulus_field_candidates

        spans, qa = _stimulus_field_candidates(self._words())
        # Every *varying* boolean column is offerable as a span, hint or no hint.
        assert set(spans) == {"focus_region", "is_in_aspan"}
        # Every trial-level column is offerable as a field — including a numeric
        # one (auto-detection deliberately refuses to guess at those) and a
        # constant boolean, which is a fact about the trial, not a span.
        assert set(qa) == {"probe_text", "question", "reading_time_ms", "is_correct"}
        # Per-word non-boolean data is neither.
        assert "surprisal" not in spans and "surprisal" not in qa
        assert "text" not in qa and "word_id" not in qa

    def test_a_dataset_the_hints_miss_can_still_be_shown(self):
        at = AppTest.from_function(_unhinted_panel_app)
        at.run()
        assert not at.exception, at.exception
        md = " ".join(m.value for m in at.markdown)
        # Nothing is detected by name here, so nothing shows by default…
        assert "Which one stands out?" not in md
        picker = [ms for ms in at.multiselect if ms.key == "stimulus_qa_fields"]
        assert picker, "the ⚙️ Fields picker should offer the Q&A columns"
        assert "probe_text" in picker[0].options
        # …until the user picks them, and then it does.
        at.session_state["stimulus_qa_fields"] = ["probe_text"]
        at.session_state["stimulus_span_fields"] = ["focus_region"]
        at.run()
        md = " ".join(m.value for m in at.markdown)
        assert "Which one stands out?" in md
        assert "Focus region" in md

    def test_switching_corpus_shape_re_seeds_from_detection(self):
        """A stored pick must not leave the panel blank on another dataset."""

        def _app():
            import pandas as pd
            import streamlit as st

            from scanpath_studio.tabs import _stimulus_fields

            first = pd.DataFrame(
                {
                    "text": ["a", "b"],
                    "focus_region": [True, False],
                    "probe_text": ["q?"] * 2,
                }
            )
            second = pd.DataFrame(
                {
                    "text": ["a", "b"],
                    "is_in_aspan": [True, False],
                    "question": ["q?"] * 2,
                }
            )
            _stimulus_fields(first)
            st.session_state["stimulus_qa_fields"] = []  # user clears it
            st.write(_stimulus_fields(second))  # different corpus shape

        at = AppTest.from_function(_app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["stimulus_qa_fields"] == ["question"]
        assert at.session_state["stimulus_span_fields"] == ["is_in_aspan"]


class TestFieldPickerSurvivesAViewSwitch:
    """The picker's keys must outlive a run that doesn't render the picker.

    Streamlit drops a widget's key at the end of any run in which the widget did
    not render, and this panel exists only in the Scanpath view — so without
    `persist_state="session"` one trip through Corpus Analysis silently and
    *permanently* stripped every span highlight and the whole Q&A block,
    including the defaults the user never touched. The signature guard couldn't
    recover it either: that key is a plain one and survives the pruning, so it
    saw "nothing changed" and never re-seeded. Same shape as
    `test_canvas_settings_survive_a_corpus_analysis_round_trip`.
    """

    def test_a_corpus_analysis_round_trip_keeps_the_selection(self):
        from tests.conftest import APP_SCRIPT

        at = AppTest.from_file(APP_SCRIPT, default_timeout=120)
        at.run()
        assert not at.exception, at.exception
        before_spans = list(at.session_state["stimulus_span_fields"])
        before_qa = list(at.session_state["stimulus_qa_fields"])
        assert before_spans and before_qa, "the demo should auto-detect both"

        at.session_state["main_nav"] = "Corpus Analysis"
        at.run()
        at.session_state["main_nav"] = "Scanpath Visualization"
        at.run()
        assert not at.exception, at.exception
        assert list(at.session_state["stimulus_span_fields"]) == before_spans
        assert list(at.session_state["stimulus_qa_fields"]) == before_qa


class TestFieldPickerKeepsChoicesAcrossTrials:
    """Stepping through trials must not silently undo a choice.

    The re-seed guard keys on the dataset's *column set*, not on the derived
    option pools: those are computed from one trial's slice, so a trial whose
    critical span happens to be empty classifies that column into the other
    bucket — and keying on them reset the user's picks on exactly that trial.
    """

    def _app():
        import pandas as pd
        import streamlit as st

        from scanpath_studio.tabs import _stimulus_fields

        common = {"text": ["a", "b"], "question": ["q?"] * 2}
        # Trial 1: the span column has a True, so it is a span candidate.
        _stimulus_fields(pd.DataFrame({**common, "is_in_aspan": [True, False]}))
        st.session_state["stimulus_qa_fields"] = []  # the user clears the Q&A list
        # Trial 2: same columns, but this trial's span is empty.
        _stimulus_fields(pd.DataFrame({**common, "is_in_aspan": [False, False]}))

    def test_a_trial_with_an_empty_span_does_not_reset_the_picks(self):
        at = AppTest.from_function(TestFieldPickerKeepsChoicesAcrossTrials._app)
        at.run()
        assert not at.exception, at.exception
        assert at.session_state["stimulus_qa_fields"] == []
