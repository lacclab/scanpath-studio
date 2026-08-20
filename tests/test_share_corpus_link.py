"""DATA-27 (Task 12): the deep link / Share contract for every public corpus.

Before this, `url_state._SHAREABLE_SOURCES` gave a `?source=` token to the
sources whose *identity is the token* — demo, synthetic, authored, the two local
env bundles — and every public corpus fell through to "this data source can't be
rebuilt from a link". PoTeC and MultiplEYE were unshareable, and each prepared
(harmonised) corpus was born unshareable for the same reason.

One generic token now covers the whole of `app.public_dataset_registry()` —
built-in corpora and prepared ones alike (R42): `?source=corpus&corpus=<slug>`.

The two things these tests exist to pin:

* **the slug is derived from the entry's stable identifier**, not from its
  display label (which carries em-dashes and "(harmonised benchmark)", and is
  the thing most likely to be reworded — a link has to survive a rewording);
* **the overlapping pair.** PoTeC and OneStop each ship *both* natively and
  harmonised, and both entries are kept on purpose. Their identifiers are the
  same string, so bare slugs would collide — and a colliding slug silently opens
  the *wrong corpus*, which is the worst failure this feature can have.

Fixture values come from the real bundle manifest (`data/EyeGenBench/
manifest.json`), not from tidy documentation values: `language` is an ISO code
(`'de'`), `monitor_source` a provenance word, the counts plain integers.
"""

from __future__ import annotations

from urllib.parse import parse_qs

import pytest

from scanpath_studio.constants import BENCHMARK_SETUP_CHOICE
from tests.conftest import (
    APP_SCRIPT,
    _write_benchmark_corpus,
    _write_benchmark_manifest,
)

streamlit_testing = pytest.importorskip("streamlit.testing.v1")
AppTest = streamlit_testing.AppTest


# Two real manifest rows, verbatim from data/EyeGenBench/manifest.json.
_POTEC_ROW = {
    "name": "PoTeC",
    "language": "de",
    "monitor": [1680, 1050],
    "monitor_source": "published",
    "n_readers": 75,
    "n_texts": 12,
    "n_fixations": 404420,
    "license": "CC-BY-4.0",
    "citation": "Jakobi et al. 2024",
    "repeated_readings": 0,
    "geometry_source": "real",
    "interpolated_fraction": 0.0016,
    "display_source": "eyegenbench:texts",
    "paragraphs_without_real_boxes": 0,
}
_PROVO_ROW = {
    "name": "Provo",
    "language": "en",
    "monitor": [1600, 900],
    "monitor_source": "published",
    "n_readers": 84,
    "n_texts": 55,
    "n_fixations": 219556,
    "license": "CC-BY-4.0",
    "citation": "Luke & Christianson 2018",
    "repeated_readings": 0,
    "geometry_source": "reconstructed",
    "interpolated_fraction": 0.0,
    "display_source": "paper:LukeChristianson2018",
    "paragraphs_without_real_boxes": 55,
    "monospaced": True,
}

#: Every corpus the real bundle carries, as ``(name, language)`` — the actual
#: 30 names and ISO codes (MECO's multi-language rows included, comma-separated
#: exactly as the manifest writes them). Used by the uniqueness test, which is
#: about the *catalogue*, so an invented three-corpus stand-in would not answer
#: the question it asks.
_REAL_MANIFEST_CORPORA = (
    ("ADEGBTS", "zh"),
    ("BSC", "zh"),
    ("BSCII", "zh"),
    ("ChineseReading", "zh"),
    ("CoLAGaze", "en"),
    ("CopCo", "da"),
    ("Cuentos", "es"),
    ("EMTeC", "en"),
    ("EyeVoiceSpan", "de"),
    ("GGTG", "en"),
    ("Gaze4Hate", "de"),
    ("IITBHGC", "en"),
    ("InteRead", "en"),
    ("MECOL1W1", "de, el, en, es, fi, he, it, ko, nl, no, ru, tr"),
    ("MECOL1W2", "da, de, en, es, eu, hi, is, no, pt, ru, sr, tr"),
    ("MECOL2W1", "en"),
    ("MECOL2W2", "en"),
    ("OASSTETC", "en"),
    ("OneStop", "en"),
    ("PSC2", "de"),
    ("PSR", "fa"),
    ("PoTeC", "de"),
    ("Provo", "en"),
    ("RSC", "ru"),
    ("RaCCooNS", "nl"),
    ("ReadingBrain", "en"),
    ("ReadingBrainL2", "en"),
    ("SBSAT", "en"),
    ("ZuCo1", "en"),
    ("ZuCo2", "en"),
)


def _pin_bundle(monkeypatch, root) -> None:
    """Make ``root`` the only prepared bundle this process can see.

    Every module binds ``EYEGENBENCH_DEFAULT_DIR`` separately (see the session
    fixture in `tests/conftest.py`, which pins them all at an empty directory),
    so all three have to be repointed or discovery answers differently depending
    on which one asked.
    """
    from scanpath_studio import app, compare_source, constants

    for module in (constants, app, compare_source):
        monkeypatch.setattr(module, "EYEGENBENCH_DEFAULT_DIR", str(root))


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
        "MULTIPLEYE_DEFAULT_DIR",
    ):
        monkeypatch.setattr(app, const, str(tmp_path / const.lower()))


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    """A prepared bundle holding harmonised PoTeC + Provo, pinned as the one
    this app can see. PoTeC is the overlapping half: it also ships natively."""
    monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
    root = tmp_path / "EyeGenBench"
    _write_benchmark_corpus(root, "PoTeC", paragraphs=("PoTeC_a", "PoTeC_b"))
    _write_benchmark_corpus(root, "Provo", paragraphs=("Provo_a", "Provo_b"))
    _write_benchmark_manifest(root, [_POTEC_ROW, _PROVO_ROW])
    _pin_bundle(monkeypatch, root)
    _hide_builtin_corpus_data(monkeypatch, tmp_path)
    return root


def _native_potec_label() -> str:
    """The built-in PoTeC entry — the *other* half of the overlapping pair."""
    from scanpath_studio import app

    return next(k for k in app.PUBLIC_DATASET_REGISTRY if k.startswith("PoTeC"))


class TestSlugs:
    """What the slug is derived from, and that no two entries share one."""

    def test_a_prepared_corpus_slugs_its_manifest_name_not_its_label(self, bundle):
        from scanpath_studio import app
        from scanpath_studio.url_state import corpus_slug, registry_corpus_slugs

        label = app.benchmark_corpus_label("PoTeC")
        registry = app.public_dataset_registry()
        assert registry_corpus_slugs()[label] == "harmonised-potec"
        # The label is copy. Reword it and the slug — hence every link already
        # written — is unchanged, because it is built from `benchmark_dataset`
        # (the manifest name) alone.
        assert (
            corpus_slug("PoTeC — some entirely reworded label", registry[label])
            == "harmonised-potec"
        )

    def test_a_builtin_corpus_slugs_its_short_name_not_its_label(self, bundle):
        from scanpath_studio.url_state import registry_corpus_slugs

        label = _native_potec_label()
        # The registry *key* is "PoTeC — Potsdam Textbook Corpus"; the slug is
        # the entry's `short`, so the full title can be rewritten freely.
        assert registry_corpus_slugs()[label] == "potec"

    def test_the_two_potec_entries_have_distinct_slugs_each_resolving_to_itself(
        self, bundle
    ):
        """The whole test of the slug scheme (R42's warning made concrete).

        Native PoTeC and harmonised PoTeC are two distinct entries whose stable
        identifiers are the *same string*. The disambiguator is the namespace
        prefix a prepared corpus carries — a constant in code, not label text —
        and without it one slug would name two entries.
        """
        from scanpath_studio import app
        from scanpath_studio.url_state import (
            corpus_choice_for_slug,
            registry_corpus_slugs,
        )

        native = _native_potec_label()
        harmonised = app.benchmark_corpus_label("PoTeC")
        slugs = {
            label: slug
            for label, slug in registry_corpus_slugs().items()
            if label in (native, harmonised)
        }
        assert slugs[native] != slugs[harmonised], (
            "the two PoTeC entries share one slug — a link would silently open "
            f"the wrong corpus: {slugs}"
        )
        # …and each slug resolves back to its own entry, not to the other one.
        assert corpus_choice_for_slug(slugs[native]) == native
        assert corpus_choice_for_slug(slugs[harmonised]) == harmonised

    def test_every_corpus_in_the_real_catalogue_has_a_unique_slug(
        self, tmp_path, monkeypatch
    ):
        """All 30 prepared corpora + the built-ins, no two slugs equal.

        Discovery reads the manifest, so the corpus directories need not exist
        for the registry to list them — which is what makes the *whole real
        catalogue* affordable as a fixture. (The suite pins discovery at an
        empty directory, so the bundle a test wants must be written by the test.)

        The expectation is derived from `public_dataset_registry()` itself rather
        than from a count of the snapshot above: `registry_corpus_slugs` drops
        every slug two entries would claim, so "each corpus that isn't the setup
        placeholder still has a slug" **is** the uniqueness assertion, and it
        keeps meaning that as the catalogue grows.
        """
        from scanpath_studio import app
        from scanpath_studio.url_state import registry_corpus_slugs

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "EyeGenBench"
        root.mkdir()
        _write_benchmark_manifest(
            root,
            [
                {"name": name, "language": language}
                for name, language in _REAL_MANIFEST_CORPORA
            ],
        )
        _pin_bundle(monkeypatch, root)

        registry = app.public_dataset_registry()
        nameable = {
            label for label, spec in registry.items() if not spec.get("setup_only")
        }
        # Premise: the catalogue under test really is the whole real one.
        assert len(nameable) >= len(_REAL_MANIFEST_CORPORA)
        assert set(registry_corpus_slugs()) == nameable, (
            "a corpus lost its slug — `registry_corpus_slugs` drops any slug two "
            "entries would answer to, so these are the colliding ones: "
            f"{sorted(nameable - set(registry_corpus_slugs()))}"
        )

    def test_the_bootstrap_placeholder_is_not_a_corpus(self, tmp_path, monkeypatch):
        """With zero corpora discovered the registry offers one placeholder that
        carries the bundle-directory input. It is not a corpus, so it gets no
        slug — there is nothing for a link to reopen."""
        from scanpath_studio import app
        from scanpath_studio.constants import BENCHMARK_SETUP_CHOICE
        from scanpath_studio.url_state import corpus_slug, registry_corpus_slugs

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        _pin_bundle(monkeypatch, tmp_path / "absent")

        registry = app.public_dataset_registry()
        assert BENCHMARK_SETUP_CHOICE in registry  # premise: it is offered
        assert (
            corpus_slug(BENCHMARK_SETUP_CHOICE, registry[BENCHMARK_SETUP_CHOICE]) == ""
        )
        assert BENCHMARK_SETUP_CHOICE not in registry_corpus_slugs()

    def test_an_unknown_slug_resolves_to_nothing(self, bundle):
        from scanpath_studio.url_state import corpus_choice_for_slug

        assert corpus_choice_for_slug("harmonised-zuco1") is None
        assert corpus_choice_for_slug("not-a-corpus") is None
        assert corpus_choice_for_slug("") is None
        assert corpus_choice_for_slug(None) is None


class TestAmbiguousSlugsResolveToNeither:
    """Avoiding the known collision is not the same as detecting an unknown one.

    The namespace prefix keeps native PoTeC and harmonised PoTeC apart, and that
    is the only collision today's catalogue has. It gives the scheme no way to
    *notice* another one — and the resolver iterates the registry with the
    built-ins first, so an undetected collision would resolve to whichever entry
    came first: silently, and to the wrong corpus. Refusing to answer costs the
    recipient one link; answering wrongly opens the wrong data.

    Each test below asserts the pair resolves to **neither** entry, not merely
    that something was reported.
    """

    def test_a_builtin_short_beginning_with_the_namespace_collides(
        self, tmp_path, monkeypatch
    ):
        """The `harmonised-` prefix is a convention, not a reserved word.

        A built-in corpus whose `short` is "Harmonised Foo" slugs exactly like a
        prepared corpus named "Foo" — the brief named this vector explicitly.
        """
        from scanpath_studio import app
        from scanpath_studio.url_state import corpus_choice_for_slug, corpus_slug

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "EyeGenBench"
        _write_benchmark_corpus(root, "Foo")
        _write_benchmark_manifest(root, [{"name": "Foo", "language": "en"}])
        _pin_bundle(monkeypatch, root)
        # A hypothetical future built-in. `public_dataset_registry()` copies the
        # static dict at call time, so adding an entry to it is enough.
        monkeypatch.setitem(
            app.PUBLIC_DATASET_REGISTRY,
            "Harmonised Foo — a native corpus that happens to be named this way",
            dict(loader=lambda *a, **k: None, short="Harmonised Foo"),
        )

        registry = app.public_dataset_registry()
        clashing = [
            label
            for label, spec in registry.items()
            if corpus_slug(label, spec) == "harmonised-foo"
        ]
        assert len(clashing) == 2, f"premise: two entries slug alike, got {clashing}"
        assert corpus_choice_for_slug("harmonised-foo") is None, (
            "an ambiguous slug resolved to one of the two corpora that claim it"
        )

    def test_names_differing_only_in_punctuation_collide(self, tmp_path, monkeypatch):
        """`_slugify_corpus` is not injective, and near-identical corpus names
        are the norm in this catalogue (MECOL1W1/…/MECOL2W2, ZuCo1/ZuCo2)."""
        from scanpath_studio import app
        from scanpath_studio.url_state import corpus_choice_for_slug, corpus_slug

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "EyeGenBench"
        for name in ("ZuCo-1", "ZuCo 1"):
            _write_benchmark_corpus(root, name)
        _write_benchmark_manifest(
            root,
            [
                {"name": "ZuCo-1", "language": "en"},
                {"name": "ZuCo 1", "language": "en"},
            ],
        )
        _pin_bundle(monkeypatch, root)

        registry = app.public_dataset_registry()
        both = {app.benchmark_corpus_label(n) for n in ("ZuCo-1", "ZuCo 1")}
        assert both <= set(registry), "premise: both corpora are registry entries"
        assert {corpus_slug(label, registry[label]) for label in both} == {
            "harmonised-zuco-1"
        }, "premise: the two names slug alike"
        # The load-bearing pin: the slug BOTH corpora claim resolves to neither
        # of them. Asserting a raw display name resolves to `None` would look
        # like a second vector but prove nothing — `"ZuCo 1"` slugifies to
        # `"zuco-1"`, which never matches the registered `"harmonised-zuco-1"`
        # with or without this guard, so it would pass on unfixed code too.
        assert corpus_choice_for_slug("harmonised-zuco-1") is None

    def test_a_name_with_nothing_sluggable_in_it_is_not_shareable(
        self, tmp_path, monkeypatch
    ):
        """A non-Latin manifest name slugifies to nothing.

        Emitting the bare namespace prefix for it would be doubly wrong: every
        such corpus would share the one slug, and none of them could ever
        round-trip, because the reader re-slugifies its input and the trailing
        hyphen is stripped. Not shareable is the honest answer — the entry still
        works everywhere else, and the link falls back to the "can't be rebuilt"
        caveat.
        """
        from scanpath_studio import app
        from scanpath_studio.url_state import corpus_choice_for_slug, corpus_slug

        monkeypatch.setenv("SCANPATH_PUBLIC_DATASETS", "1")
        root = tmp_path / "EyeGenBench"
        for name in ("日本語コーパス", "Корпус"):
            _write_benchmark_corpus(root, name)
        _write_benchmark_manifest(
            root,
            [
                {"name": "日本語コーパス", "language": "ja"},
                {"name": "Корпус", "language": "ru"},
            ],
        )
        _pin_bundle(monkeypatch, root)

        registry = app.public_dataset_registry()
        labels = [app.benchmark_corpus_label(n) for n in ("日本語コーパス", "Корпус")]
        assert set(labels) <= set(registry), "premise: both are registry entries"
        for label in labels:
            assert corpus_slug(label, registry[label]) == ""
        assert corpus_choice_for_slug("harmonised-") is None
        assert corpus_choice_for_slug("harmonised") is None

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
    # DATA-3's three public-OneStop options are set for *every* corpus this
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
    def test_a_prepared_corpus_is_shared_with_a_caveat_naming_it(self, bundle):
        from scanpath_studio import app

        parsed, caveats = _share(app.benchmark_corpus_label("Provo"))
        assert parsed["source"] == ["corpus"]
        assert parsed["corpus"] == ["harmonised-provo"]
        # Sharing "you'd need this corpus" beats sharing nothing (today's
        # behaviour), so the link is emitted *and* the caveat says which corpus
        # the recipient has to have prepared.
        assert any("Provo" in note for note in caveats), caveats

    def test_a_builtin_corpus_is_shared_without_a_cannot_rebuild_caveat(self, bundle):
        parsed, caveats = _share(_native_potec_label())
        assert parsed["source"] == ["corpus"]
        assert parsed["corpus"] == ["potec"]
        assert caveats == []

    def test_public_onestop_keeps_its_own_older_token_and_its_three_options(
        self, bundle
    ):
        """R42: a corpus reachable by both tokens still emits the older one —
        **with** the variant / regime / parts that make that token worth keeping.

        `?source=onestop_public` (+ its three options) has been in links since
        DATA-3. The generic token is additive; it must not retire that branch, or
        every link already written stops carrying the corpus slice.

        The three options are the point of this test, and they are asserted on
        the path the **app** takes: `data_choice` is `PUBLIC_DATASETS_CHOICE` and
        only `public_dataset_choice` says which corpus it is. The picker collapses
        every registry label before the Share panel sees it, so
        `data_choice == ONESTOP_PUBLIC_CHOICE` is never true in the running app —
        which is why the emitting block matches the *resolved* corpus too, and
        why a test that passes the label in directly proves nothing about it.
        """
        from scanpath_studio.constants import ONESTOP_PUBLIC_CHOICE

        parsed, _ = _share(ONESTOP_PUBLIC_CHOICE)
        assert parsed["source"] == ["onestop_public"]
        assert "corpus" not in parsed
        assert parsed["onestop_variant"] == ["public"]
        assert parsed["onestop_regime"] == ["repeated"]
        assert parsed["onestop_parts"] == ["Paragraph,Title"]

    def test_the_onestop_options_ride_only_with_that_corpus(self, bundle):
        """The same three keys are set for every corpus this helper shares, so
        the assertion above would pass on a block that fired unconditionally."""
        from scanpath_studio import app

        parsed, _ = _share(app.benchmark_corpus_label("Provo"))
        assert "onestop_variant" not in parsed
        assert "onestop_regime" not in parsed
        assert "onestop_parts" not in parsed


def _share_panel_app():
    """Render the Share subtab's body for whatever corpus is selected."""
    from scanpath_studio.constants import PUBLIC_DATASETS_CHOICE
    from scanpath_studio.url_state import _render_share_body

    _render_share_body(PUBLIC_DATASETS_CHOICE)


class TestTheCurrentLinkFollowsTheView:
    def test_panel_always_shares_the_full_view_without_an_identity_picker(self, bundle):
        from scanpath_studio import app

        at = AppTest.from_function(_share_panel_app)
        at.session_state["public_dataset_choice"] = app.benchmark_corpus_label("Provo")
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

    def test_switching_corpus_updates_the_share_link(self, bundle):
        from scanpath_studio import app

        potec = app.benchmark_corpus_label("PoTeC")
        provo = app.benchmark_corpus_label("Provo")

        at = AppTest.from_function(_share_panel_app)
        at.session_state["public_dataset_choice"] = potec
        at.run(timeout=30)
        assert not at.exception, at.exception
        query, caveats = at.session_state["_share_query_current"]
        assert parse_qs(query)["corpus"] == ["harmonised-potec"]
        assert any("PoTeC" in note for note in caveats), caveats

        # The single Refresh & Copy action must receive the corpus now on screen.
        at.session_state["public_dataset_choice"] = provo
        at.run(timeout=30)
        assert not at.exception, at.exception
        query, caveats = at.session_state["_share_query_current"]
        assert parse_qs(query)["corpus"] == ["harmonised-provo"], (
            "the panel handed out a link naming the previously selected corpus"
        )
        assert not any("PoTeC" in note for note in caveats), caveats

    def test_a_setting_change_updates_the_share_link(self, bundle):
        from scanpath_studio import app

        at = AppTest.from_function(_share_panel_app)
        at.session_state["public_dataset_choice"] = app.benchmark_corpus_label("Provo")
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

    def test_each_registry_corpus_round_trips_to_itself(self, bundle):
        """A built-in, a prepared corpus, and **both** members of the
        overlapping pair — each link reopens the entry it was copied from.

        Round trip, not "the param appears": the second app is driven by the
        emitted query alone, and what is asserted is which corpus the picker
        ends up on.
        """
        from scanpath_studio import app

        labels = [
            _native_potec_label(),
            app.benchmark_corpus_label("PoTeC"),
            app.benchmark_corpus_label("Provo"),
        ]
        slugs = {}
        for label in labels:
            sender = AppTest.from_file(APP_SCRIPT)
            sender.session_state["data_source_choice"] = label
            sender.run(timeout=60)
            assert not sender.exception, f"{label}: {sender.exception}"
            query, _caveats = sender.session_state["_share_query_current"]
            parsed = parse_qs(query)
            assert parsed["source"] == ["corpus"], (label, parsed.get("source"))
            slugs[label] = parsed["corpus"][0]

            recipient = AppTest.from_file(APP_SCRIPT)
            for key, values in parsed.items():
                recipient.query_params[key] = values[0]
            recipient.run(timeout=60)
            assert not recipient.exception, f"{label}: {recipient.exception}"
            opened = recipient.session_state["public_dataset_choice"]
            assert opened == label, (
                f"the link for {label!r} (?corpus={slugs[label]}) opened {opened!r}"
            )
            picker = [s for s in recipient.selectbox if s.key == "data_source_picker"]
            assert picker and picker[0].value == label

        assert len(set(slugs.values())) == len(labels), (
            f"two entries shared a slug, so one link opened the other's corpus: {slugs}"
        )

    def test_an_unresolvable_slug_leaves_the_picker_where_it_was(self, bundle):
        """The common case — the recipient has no bundle, or a different subset.

        Compared against a control app opened with no link at all, so this pins
        "the link did not move the picker" rather than "it landed on the demo".
        """
        control = AppTest.from_file(APP_SCRIPT)
        control.run(timeout=60)
        assert not control.exception, control.exception
        before = control.session_state["data_source_choice"]

        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["source"] = "corpus"
        at.query_params["corpus"] = "harmonised-zuco1"
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
        named = [w.value for w in at.warning if "harmonised-zuco1" in w.value]
        assert named, (
            "the recipient was not told which corpus the link named: "
            f"{[w.value for w in at.warning]}"
        )
        # …and the remedy names something the recipient can actually click. The
        # bundle-directory input renders *inside* a benchmark corpus entry, so
        # "point the data directory at it" is only reachable after picking one in
        # Data source — with no bundle at all, the setup placeholder.
        assert "Data source" in named[0], named
        assert BENCHMARK_SETUP_CHOICE in named[0], named

    def test_a_corpus_link_is_not_silent_when_public_datasets_are_off(
        self, bundle, monkeypatch
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
        at.query_params["corpus"] = "harmonised-provo"
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert at.session_state["data_source_choice"] == before
        assert any("harmonised-provo" in w.value for w in at.warning), (
            f"silent no-op: {[w.value for w in at.warning]}"
        )

    def test_an_old_public_onestop_link_still_resolves_with_its_variant(self, bundle):
        """Back-compat for the one corpus that had a token before this task."""
        from scanpath_studio.constants import ONESTOP_PUBLIC_CHOICE

        at = AppTest.from_file(APP_SCRIPT)
        at.query_params["source"] = "onestop_public"
        at.query_params["onestop_variant"] = "public"
        at.query_params["onestop_regime"] = "repeated"
        at.run(timeout=60)
        assert not at.exception, at.exception
        assert at.session_state["data_source_choice"] == ONESTOP_PUBLIC_CHOICE
        assert at.session_state["public_dataset_choice"] == ONESTOP_PUBLIC_CHOICE
        assert at.session_state["onestop_variant"] == "public"
        assert at.session_state["onestop_regime"] == "repeated"


def test_the_corpus_param_and_the_keys_it_writes_are_pinned_as_wire_format():
    """M9: the new param + the session keys a link writes are in `session_keys`.

    They outlive the process — a link sits in a bookmark or a paper — so a
    rename has to fail a test rather than a user's link. The bundle directory is
    deliberately *not* on the wire: it is a local filesystem path, and a link
    carrying it would leak the sender's directory layout.
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
    assert "eyegenbench_dir" not in {
        *sk.URL_SELECTION_PARAMS,
        *sk.URL_SEEDED_STATE_KEYS,
        *sk.URL_SOURCE_STATE_KEYS,
    }
