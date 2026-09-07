"""Remembering which entries the helpers put into the user's VS Code files.

Without this, updating a managed list means guessing which entries were ours.
The previous implementation guessed by prefix -- it dropped everything
starting with CONFIG_ -- which cannot work for include paths and quietly
clobbers hand-written entries that happen to match.

Instead each run records exactly what it wrote to `.vscode/.kdev-state.json`,
and the next run removes exactly that before adding the new values.  Anything
the user added by hand is left untouched.
"""

import json

STATE_FILENAME = ".kdev-state.json"
STATE_VERSION = 1


def load(vscode_dir):
    path = vscode_dir / STATE_FILENAME
    try:
        data = json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if data.get("version") != STATE_VERSION:
        return {}
    return data.get("managed", {})


def save(vscode_dir, managed, dry_run=False):
    if dry_run:
        return
    path = vscode_dir / STATE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"version": STATE_VERSION, "managed": managed}, indent=4) + "\n"
    )


def merge_list(existing, previously_managed, now_managed):
    """Replace our previous entries in `existing`, preserving the user's.

    Managed entries are appended in order after whatever the user kept, and
    duplicates are collapsed so repeated runs stay idempotent.
    """
    previous = set(previously_managed or ())
    preserved = [item for item in existing or () if item not in previous]

    merged = []
    for item in [*preserved, *now_managed]:
        if item not in merged:
            merged.append(item)
    return merged


def merge_dict(existing, previously_managed, now_managed):
    """Same as merge_list() for the key/bool maps VS Code uses for excludes."""
    previous = set(previously_managed or ())
    merged = {
        key: value
        for key, value in (existing or {}).items()
        if key not in previous
    }
    merged.update(now_managed)
    return merged
