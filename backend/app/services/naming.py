from __future__ import annotations

import re

_INVALID_CHARS = re.compile(r"[^a-z0-9_]")
_LEADING_DIGIT = re.compile(r"^[0-9]")
MAX_IDENTIFIER_LENGTH = 63  # Postgres' hard limit on identifier length


def sanitize_identifier(raw: str, fallback: str = "col") -> str:
    """Turn an arbitrary string (a CSV header, a filename) into a safe,
    lowercase snake_case SQL identifier. Never trust the input directly.
    """
    name = raw.strip().lower()
    name = re.sub(r"\s+", "_", name)
    name = _INVALID_CHARS.sub("_", name)
    name = re.sub(r"_+", "_", name).strip("_")

    if not name:
        name = fallback
    if _LEADING_DIGIT.match(name):
        name = f"{fallback}_{name}"

    return name[:MAX_IDENTIFIER_LENGTH]


def dedupe_identifiers(names: list[str]) -> list[str]:
    """Given a list of already-sanitized names, make sure no two are identical
    by appending _2, _3, ... to later duplicates.
    """
    seen: dict[str, int] = {}
    result = []
    for name in names:
        if name not in seen:
            seen[name] = 1
            result.append(name)
        else:
            seen[name] += 1
            suffixed = f"{name}_{seen[name]}"
            while suffixed in seen:
                seen[name] += 1
                suffixed = f"{name}_{seen[name]}"
            seen[suffixed] = 1
            result.append(suffixed)
    return result
