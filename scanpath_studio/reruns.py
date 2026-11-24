"""`rerun` and `switch_page`: the app's `st.rerun` and `st.switch_page`, which
keep held widget writes.

A write held against a closed popover's echo (`controls.write_through`) ends
when the next run finds the written value in place, read as the browser having
taken it. A run the script starts itself brings no browser values, so it would
end every such hold early, and the echo the browser sends after it would win.
`tests/test_reruns.py` checks that the package calls neither Streamlit function
another way.
"""

from __future__ import annotations

from typing import Literal, NoReturn

import streamlit as st


def rerun(*, scope: Literal["app", "fragment"] = "app") -> NoReturn:
    """`st.rerun` after `controls.keep_holds_through_rerun`. A fragment's own
    rerun runs no `reassert_pending_writes`, so it has no holds to keep."""
    if scope == "app":
        from scanpath_studio.controls import keep_holds_through_rerun

        keep_holds_through_rerun()
    st.rerun(scope=scope)


def switch_page(page, **kwargs) -> NoReturn:
    """`st.switch_page` after `controls.keep_holds_through_rerun`: the run it
    starts brings no browser values either."""
    from scanpath_studio.controls import keep_holds_through_rerun

    keep_holds_through_rerun()
    st.switch_page(page, **kwargs)
