"""Local dataset ownership and portable references for uploads."""

from __future__ import annotations

from uuid import uuid4

from .constants import DATASET_ALIASES_KEY

DATASET_IDS_KEY = "_upload_dataset_ids"


def dataset_share_id(session, token: str) -> str | None:
    """Give an upload a persistent ID. Legacy stores keep their original local key."""
    if token not in (session.get("_datasets") or {}):
        return None
    ids = session.get(DATASET_IDS_KEY) or {}
    if token not in ids:
        ids = {**ids, token: uuid4().hex}
        session[DATASET_IDS_KEY] = ids
    return ids[token]


def resolve_dataset_reference(
    session, name: str, share_id: str | None = None
) -> str | None:
    """Prefer an exact local ID, then the portable name. Old files used store keys."""
    uploads = session.get("_datasets") or {}
    if share_id:
        matches = [
            token
            for token, identifier in (session.get(DATASET_IDS_KEY) or {}).items()
            if identifier == share_id
        ]
        if matches:
            return matches[0] if len(matches) == 1 and matches[0] in uploads else None
    elif name in uploads:
        return name
    return dataset_key_for_display_name(session, name)


def dataset_key_for_display_name(session, name: str) -> str | None:
    """Look up an upload by the name shown in the picker."""
    uploads = session.get("_datasets") or {}
    aliases = session.get(DATASET_ALIASES_KEY) or {}
    matches = [token for token in uploads if aliases.get(token, token) == name]
    return matches[0] if len(matches) == 1 else None


def forget_dataset_identity(session, token: str) -> None:
    """Release the display name and share ID after the last owner is removed."""
    for key in (DATASET_ALIASES_KEY, DATASET_IDS_KEY):
        values = session.get(key) or {}
        if token in values:
            session[key] = {k: v for k, v in values.items() if k != token}
