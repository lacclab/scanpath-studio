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
