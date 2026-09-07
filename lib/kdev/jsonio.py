"""JSONC-tolerant reading and safe writing for VS Code configuration files.

VS Code's settings.json and c_cpp_properties.json are JSONC: they may contain
// and /* */ comments and trailing commas.  Feeding those to json.loads raises
"Expecting value", so every read goes through strip_jsonc() first.

Writes go through write_json(), which never truncates the destination in place:
it renders to a sibling temporary file and renames over the target, so a crash
mid-write cannot leave a half-written config behind.
"""

import difflib
import json
import os
import shutil
import tempfile

BACKUP_SUFFIX = ".kdev.bak"


def strip_jsonc(text):
    """Return `text` with // and /* */ comments and trailing commas removed."""
    return _strip_trailing_commas(_strip_comments(text))


def _strip_comments(text):
    """Remove // and /* */ comments, leaving markers inside strings alone.

    The stripped characters are dropped rather than blanked out, so positions
    in parse errors may shift slightly.  Callers report the file path rather
    than a position, so this is acceptable.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        if ch == '"':
            # Copy the string literal verbatim, honouring backslash escapes.
            out.append(ch)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\":
                    if i + 1 < n:
                        out.append(text[i + 1])
                        i += 2
                        continue
                elif text[i] == '"':
                    i += 1
                    break
                i += 1
            continue

        if ch == "/" and i + 1 < n:
            if text[i + 1] == "/":
                while i < n and text[i] != "\n":
                    i += 1
                continue
            if text[i + 1] == "*":
                end = text.find("*/", i + 2)
                i = n if end == -1 else end + 2
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def _strip_trailing_commas(text):
    """Drop commas that directly precede a closing brace or bracket."""
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]

        if ch == '"':
            out.append(ch)
            i += 1
            while i < n:
                out.append(text[i])
                if text[i] == "\\":
                    if i + 1 < n:
                        out.append(text[i + 1])
                        i += 2
                        continue
                elif text[i] == '"':
                    i += 1
                    break
                i += 1
            continue

        if ch == ",":
            j = i + 1
            while j < n and text[j] in " \t\r\n":
                j += 1
            if j < n and text[j] in "}]":
                i += 1
                continue

        out.append(ch)
        i += 1

    return "".join(out)


def has_comments(text):
    """True if `text` contains JSONC comments outside of string literals."""
    return _strip_comments(text) != text


def read_json(path, default=None):
    """Parse a JSONC file.  Returns `default` when the file does not exist."""
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {} if default is None else default

    if not raw.strip():
        return {} if default is None else default

    try:
        return json.loads(strip_jsonc(raw))
    except json.JSONDecodeError as exc:
        raise SystemExit(
            f"error: {path} is not valid JSON/JSONC: {exc}\n"
            f"hint: fix the syntax, or move the file aside and let the helper "
            f"regenerate it."
        )


def render(data):
    """Serialise `data` the way VS Code itself formats these files."""
    return json.dumps(data, indent=4, ensure_ascii=False) + "\n"


def diff(path, new_text):
    """Unified diff between the file's current contents and `new_text`."""
    try:
        old_text = path.read_text()
    except FileNotFoundError:
        old_text = ""
    return "".join(
        difflib.unified_diff(
            old_text.splitlines(keepends=True),
            new_text.splitlines(keepends=True),
            fromfile=f"a/{path.name}",
            tofile=f"b/{path.name}",
        )
    )


def write_json(path, data, dry_run=False, check=False, backup=True):
    """Write `data` to `path` atomically.

    Returns True when the file changed (or would change under --dry-run/--check).

    dry_run -- print a unified diff instead of writing
    check   -- report whether a write is needed, without writing
    backup  -- keep the previous contents as <path><BACKUP_SUFFIX>
    """
    new_text = render(data)

    try:
        current = path.read_text()
    except FileNotFoundError:
        current = None

    if current == new_text:
        return False

    if check:
        return True

    if dry_run:
        patch = diff(path, new_text)
        if patch:
            print(patch, end="")
        return True

    path.parent.mkdir(parents=True, exist_ok=True)

    if backup and current is not None:
        shutil.copy2(path, path.with_name(path.name + BACKUP_SUFFIX))

    # Same directory as the target so os.replace() stays on one filesystem.
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write(new_text)
        if current is not None:
            shutil.copymode(path, tmp_name)
        os.replace(tmp_name, path)
    except BaseException:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
        raise

    return True
