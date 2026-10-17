"""The deep link / Share contract for every public corpus.

`url_state._SHAREABLE_SOURCES` gives a `?source=` token to the sources whose
*identity is the token* — demo, synthetic, authored, the local env bundle.
Every public corpus shares one generic token covering the whole of
`app.public_dataset_registry()`: `?source=corpus&corpus=<slug>`.
Without it they would fall through to "this data source can't be rebuilt from a
link".

The two things these tests exist to pin:

* **the slug is derived from the entry's stable identifier**, not from its
  display label (which carries em-dashes and is the thing most likely to be
  reworded — a link has to survive a rewording);
* **a slug two entries would claim resolves to neither** — a colliding slug
  that picked a winner would silently open the *wrong corpus*, which is the
  worst failure this feature can have.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from tests.conftest import APP_SCRIPT

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


def _hide_builtin_corpus_data(monkeypatch, tmp_path) -> None:
    """Point the built-in corpora's data directories at empty paths.

    A developer who has downloaded PoTeC or OneStop would otherwise load tens to
    hundreds of MB inside an AppTest — and the test would then depend on an
    untracked directory. The picker entry (which is what these tests are about)
    exists either way; the loader just falls back to the demo frames.
    """
    from scanpath_studio import app

    for const in (
        "POTEC_DEFAULT_DIR",
        "ONESTOP_PUBLIC_DEFAULT_DIR",
    ):
        monkeypatch.setattr(app, const, str(tmp_path / const.lower()))


@pytest.fixture
def public_corpora(tmp_path, monkeypatch):
    """The public corpora switched on, their data directories empty."""
    monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
    _hide_builtin_corpus_data(monkeypatch, tmp_path)


def _native_potec_label() -> str:
    """The built-in PoTeC entry."""
    from scanpath_studio import app

    return next(k for k in app.PUBLIC_DATASET_REGISTRY if k.startswith("PoTeC"))


def _add_builtin(monkeypatch, short: str) -> str:
    """Add a hypothetical built-in corpus whose `short` is ``short``; its label.

    `public_dataset_registry()` copies the static dict at call time, so adding
    an entry to it is enough.
    """
    from scanpath_studio import app

    label = f"{short} — a corpus that happens to be named this way"
    monkeypatch.setitem(
        app.PUBLIC_DATASET_REGISTRY,
        label,
        dict(loader=lambda *a, **k: None, short=short),
    )
    return label


class TestSlugs:
    """What the slug is derived from, and that no two entries share one."""

    def test_a_builtin_corpus_slugs_its_short_name_not_its_label(self, public_corpora):
        from scanpath_studio.url_state import registry_corpus_slugs

        label = _native_potec_label()
        # The registry *key* is "PoTeC — Potsdam Textbook Corpus"; the slug is
        # the entry's `short`, so the full title can be rewritten freely.
        assert registry_corpus_slugs()[label] == "potec"

    def test_every_corpus_in_the_catalogue_has_a_unique_slug(self, public_corpora):
        """No two slugs equal.

        The expectation is derived from `public_dataset_registry()` itself:
        `registry_corpus_slugs` drops every slug two entries would claim, so
        "each corpus still has a slug" **is** the uniqueness assertion, and it
        keeps meaning that as the catalogue grows.
        """
        from scanpath_studio import app
        from scanpath_studio.url_state import registry_corpus_slugs

        nameable = set(app.public_dataset_registry())
        assert set(registry_corpus_slugs()) == nameable, (
            "a corpus lost its slug — `registry_corpus_slugs` drops any slug two "
            "entries would answer to, so these are the colliding ones: "
            f"{sorted(nameable - set(registry_corpus_slugs()))}"
        )

    def test_an_unknown_slug_resolves_to_nothing(self, public_corpora):
        from scanpath_studio.url_state import corpus_choice_for_slug

        assert corpus_choice_for_slug("zuco1") is None
        assert corpus_choice_for_slug("not-a-corpus") is None
        assert corpus_choice_for_slug("") is None
        assert corpus_choice_for_slug(None) is None


class TestAmbiguousSlugsResolveToNeither:
    """A collision has to be detected, not merely avoided.

    The resolver iterates the registry in order, so an undetected collision
    would resolve to whichever entry comes first: silently, and to the wrong
    corpus. Refusing to answer costs the recipient one link; answering wrongly
    opens the wrong data.

    Each test below asserts the pair resolves to **neither** entry, not merely
    that something was reported.
    """

    def test_names_differing_only_in_punctuation_collide(
        self, public_corpora, monkeypatch
    ):
        """`_slugify_corpus` is not injective."""
        from scanpath_studio import app
        from scanpath_studio.url_state import corpus_choice_for_slug, corpus_slug

        both = {_add_builtin(monkeypatch, short) for short in ("ZuCo-1", "ZuCo 1")}

        registry = app.public_dataset_registry()
        assert both <= set(registry), "premise: both corpora are registry entries"
        assert {corpus_slug(label, registry[label]) for label in both} == {"zuco-1"}, (
            "premise: the two names slug alike"
        )
        # The load-bearing pin: the slug BOTH corpora claim resolves to neither
        # of them.
        assert corpus_choice_for_slug("zuco-1") is None

    def test_a_name_with_nothing_sluggable_in_it_is_not_shareable(
        self, public_corpora, monkeypatch
    ):
        """A non-Latin name slugifies to nothing.

        Not shareable is the honest answer — the entry still works everywhere
        else, and the link falls back to the "can't be rebuilt" caveat.
        """
        from scanpath_studio import app
        from scanpath_studio.url_state import corpus_slug

        labels = [
            _add_builtin(monkeypatch, short) for short in ("日本語コーパス", "Корпус")
        ]

        registry = app.public_dataset_registry()
        assert set(labels) <= set(registry), "premise: both are registry entries"
        for label in labels:
            assert corpus_slug(label, registry[label]) == ""

        # And the writer refuses too, rather than emitting a slug that names two
        # corpora and resolves to neither.
        parsed, caveats = _share(labels[0])
        assert "corpus" not in parsed
        assert "source" not in parsed
        assert len(caveats) == 1, caveats


def _share_app():
    """Build the Share query for whatever corpus the test selected."""
    import streamlit as st

    from scanpath_studio.constants import PUBLIC_DATASETS_CHOICE
    from scanpath_studio.url_state import _build_share_query

    st.session_state["_share_selection"] = {"participant_id": "p1", "trial_id": "t1"}
    # The three public-OneStop options are set for *every* corpus this
    # helper shares, not just OneStop: they are what proves the block that emits
    # them is reached — and, for the other corpora, that it is not.
    st.session_state["onestop_variant"] = "public"
    st.session_state["onestop_regime"] = "repeated"
    st.session_state["onestop_parts"] = ["Paragraph", "Title"]
    query, caveats = _build_share_query(PUBLIC_DATASETS_CHOICE)
    st.session_state["_query"] = query
    st.session_state["_caveats"] = caveats


def _share(corpus_label: str):
    """``(parsed query, caveats)`` for a share of ``corpus_label``.

    Passes ``PUBLIC_DATASETS_CHOICE`` + ``public_dataset_choice`` because that
    is exactly what the app hands the Share panel: the picker collapses every
    registry label to the constant and stashes the label beside it.
    """
    at = AppTest.from_function(_share_app)
    at.session_state["public_dataset_choice"] = corpus_label
    at.run(timeout=30)
    assert not at.exception, at.exception
    return parse_qs(at.session_state["_query"]), at.session_state["_caveats"]


class TestShareEmitsTheCorpus:
    def test_a_builtin_corpus_is_shared_without_a_cannot_rebuild_caveat(
        self, public_corpora
    ):
        parsed, caveats = _share(_native_potec_label())
        assert parsed["source"] == ["corpus"]
        assert parsed["corpus"] == ["potec"]
        assert caveats == []

    @pytest.mark.parametrize(
        "regime",
        ["ordinary", "information_seeking", "repeated", "information_seeking_repeated"],
    )
    def test_each_onestop_regime_keeps_a_token_of_its_own(self, public_corpora, regime):
        """A corpus reachable by both tokens emits its own. Each OneStop
        regime is its own dataset, so it is its own `onestop_<regime>`
        — on the path the **app** takes, where `data_choice` is
        `PUBLIC_DATASETS_CHOICE` and only `public_dataset_choice` names it. The
        helper sets `onestop_regime="repeated"` for every share, so a link that
        carried the session's regime instead of the dataset's would fail here.
        """
        from scanpath_studio.constants import ONESTOP_REGIME_CHOICES

        parsed, _ = _share(ONESTOP_REGIME_CHOICES[regime])
        assert parsed["source"] == [f"onestop_{regime}"]
        assert "corpus" not in parsed
        for gone in ("onestop_variant", "onestop_regime", "onestop_parts"):
            assert gone not in parsed

    def test_the_onestop_options_ride_only_with_that_corpus(self, public_corpora):
        """The same three keys are set for every corpus this helper shares, so
        the assertion above would pass on a block that fired unconditionally."""
        parsed, _ = _share(_native_potec_label())
        assert "onestop_variant" not in parsed
        assert "onestop_regime" not in parsed
        assert "onestop_parts" not in parsed


def _share_panel_app():
    """Render the Share subtab's body for whatever corpus is selected."""
    from scanpath_studio.constants import PUBLIC_DATASETS_CHOICE
    from scanpath_studio.url_state import _render_share_body

    _render_share_body(PUBLIC_DATASETS_CHOICE)


class TestTheCurrentLinkFollowsTheView:
    def test_panel_always_shares_the_full_view_without_an_identity_picker(
        self, public_corpora
    ):
        at = AppTest.from_function(_share_panel_app)
        at.session_state["public_dataset_choice"] = _native_potec_label()
        at.session_state["_share_selection"] = {
            "participant_id": "p2",
            "trial_id": "t3",
        }
        at.run(timeout=30)
        assert not at.exception, at.exception
        query, _ = at.session_state["_share_query_current"]
        parsed = parse_qs(query)
        assert parsed["participant"] == ["p2"]
        assert parsed["trial_id"] == ["t3"]
        assert not [radio for radio in at.radio if radio.key == "share_identity_mode"]
        copy = " ".join(
            element.value
            for element in [*at.markdown, *at.caption]
            if getattr(element, "value", None)
        )
        assert "different address or port" in copy
        assert "Refresh & Copy uses" not in copy

    def test_switching_corpus_updates_the_share_link(self, public_corpora):
        from scanpath_studio.constants import ONESTOP_REGIME_CHOICES

        at = AppTest.from_function(_share_panel_app)
        at.session_state["public_dataset_choice"] = _native_potec_label()
        at.run(timeout=30)
        assert not at.exception, at.exception
        query, _ = at.session_state["_share_query_current"]
        assert parse_qs(query)["corpus"] == ["potec"]

        # The single Refresh & Copy action must receive the corpus now on screen.
        at.session_state["public_dataset_choice"] = ONESTOP_REGIME_CHOICES["ordinary"]
        at.run(timeout=30)
        assert not at.exception, at.exception
        query, _ = at.session_state["_share_query_current"]
        parsed = parse_qs(query)
        assert parsed["source"] == ["onestop_ordinary"], (
            "the panel handed out a link naming the previously selected corpus"
        )
        assert "corpus" not in parsed

    def test_a_setting_change_updates_the_share_link(self, public_corpora):
        at = AppTest.from_function(_share_panel_app)
        at.session_state["public_dataset_choice"] = _native_potec_label()
        at.run(timeout=30)
        assert not at.exception, at.exception
        before, _ = at.session_state["_share_query_current"]

        at.session_state["global_show_words"] = not st_value_of(at, "global_show_words")
        at.run(timeout=30)
        assert not at.exception, at.exception
        after, _ = at.session_state["_share_query_current"]
        assert after != before, "Refresh & Copy received stale settings"


def st_value_of(at, key: str, default=True):
    """A session value an AppTest may or may not have set yet."""
    return at.session_state[key] if key in at.session_state else default


@pytest.mark.timeout(180)
class TestRoundTripThroughTheApp:
    """Select a corpus → copy the link → open it in a fresh app."""

    def test_a_registry_corpus_round_trips_to_itself(self, public_corpora):
        """The link reopens the entry it was copied from.

        Round trip, not "the param appears": the second app is driven by the
        emitted query alone, and what is asserted is which corpus the picker
        ends up on.
        """
        label = _native_potec_label()
        sender = AppTest.from_file(APP_SCRIPT)
        sender.session_state["data_source_choice"] = label
        sender.run(timeout=60)
        assert not sender.exception, f"{label}: {sender.exception}"
        query, _caveats = sender.session_state["_share_query_current"]
        parsed = parse_qs(query)
        assert parsed["source"] == ["corpus"], (label, parsed.get("source"))
        slug = parsed["corpus"][0]

        recipient = AppTest.from_file(APP_SCRIPT)
        for key, values in parsed.items():
            recipient.query_params[key] = values[0]
        recipient.run(timeout=60)
        assert not recipient.exception, f"{label}: {recipient.exception}"
        opened = recipient.session_state["public_dataset_choice"]
        assert opened == label, (
            f"the link for {label!r} (?corpus={slug}) opened {opened!r}"
        )
        picker = [s for s in recipient.selectbox if s.key == "data_source_picker"]
        assert picker and picker[0].value == label

    def test_an_unresolvable_slug_leaves_the_picker_where_it_was(self, public_corpora):
        """A slug naming a corpus this app does not offer.

        Compared against a control app opened with no link at all, so this pins
        "the link did not move the picker" rather than "it landed on the demo".
        """
        control = AppTest.from_file(APP_SCRIPT)
        control.run(timeout=60)
        assert not control.exception, control.exception
        before = control.session_state["data_source_choice"]

        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["source"] = "corpus"
        at.query_params["corpus"] = "zuco1"
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert at.session_state["data_source_choice"] == before, (
            "an unresolvable corpus slug moved the picker"
        )
        selected_corpus = (
            at.session_state["public_dataset_choice"]
            if "public_dataset_choice" in at.session_state
            else ""
        )
        assert "ZuCo1" not in str(selected_corpus)
        named = [w.value for w in at.warning if "zuco1" in w.value]
        assert named, (
            "the recipient was not told which corpus the link named: "
            f"{[w.value for w in at.warning]}"
        )
        # …and names no remedy: there is nothing the app could tell the user
        # to click.
        assert "Data directory" not in named[0], named

    def test_a_corpus_link_is_not_silent_when_public_datasets_are_off(
        self, public_corpora, monkeypatch
    ):
        """A build with the corpora switched off can't open one either — but the
        recipient still has to be told the link named a corpus, rather than
        watching it do nothing at all."""
        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "0")

        control = AppTest.from_file(APP_SCRIPT)
        control.run(timeout=60)
        assert not control.exception, control.exception
        before = control.session_state["data_source_choice"]

        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["source"] = "corpus"
        at.query_params["corpus"] = "potec"
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert at.session_state["data_source_choice"] == before
        assert any("potec" in w.value for w in at.warning), (
            f"silent no-op: {[w.value for w in at.warning]}"
        )

    def test_an_old_public_onestop_link_opens_the_regime_it_names(self, public_corpora):
        """`onestop_public` + `onestop_regime` lands on that regime's dataset."""
        from scanpath_studio.constants import ONESTOP_REGIME_CHOICES

        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["source"] = "onestop_public"
        at.query_params["onestop_variant"] = "public"
        at.query_params["onestop_regime"] = "repeated"
        at.run(timeout=60)
        assert not at.exception, at.exception
        repeated = ONESTOP_REGIME_CHOICES["repeated"]
        assert at.session_state["data_source_choice"] == repeated
        assert at.session_state["public_dataset_choice"] == repeated

    def test_a_regime_link_opens_that_regime(self, public_corpora):
        from scanpath_studio.constants import ONESTOP_REGIME_CHOICES

        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["source"] = "onestop_information_seeking"
        at.run(timeout=60)
        assert not at.exception, at.exception
        seeking = ONESTOP_REGIME_CHOICES["information_seeking"]
        assert at.session_state["data_source_choice"] == seeking


def test_the_corpus_param_and_the_keys_it_writes_are_pinned_as_wire_format():
    """The corpus param + the session keys a link writes are in `session_keys`.

    They outlive the process — a link sits in a bookmark or a paper — so a
    rename has to fail a test rather than a user's link.
    """
    from scanpath_studio import session_keys as sk
    from scanpath_studio.url_state import CORPUS_SOURCE_TOKEN

    assert sk.PARAM_CORPUS == "corpus"
    assert sk.PARAM_CORPUS in sk.URL_SELECTION_PARAMS
    # Emitted only when there is a corpus to name, like `compare` / `setup_prov`.
    assert sk.PARAM_CORPUS in sk.URL_OPTIONAL_PARAMS
    assert CORPUS_SOURCE_TOKEN == "corpus"
    assert sk.URL_SOURCE_STATE_KEYS == {"data_source_choice", "public_dataset_choice"}
    assert not (sk.URL_SOURCE_STATE_KEYS & sk.URL_SEEDED_STATE_KEYS), (
        "these are written by main()'s ?source= dispatch, not by _apply_url_preset"
    )
