"""Conservative read-only guard for ad-hoc Cypher queries."""
from __future__ import annotations

import re

_WRITE = re.compile(
    r"\b(create|merge|delete|set|remove|detach|drop|load\s+csv|foreach|call|apoc\.|dbms\.)\b",
    re.I,
)
_READ_START = re.compile(r"^\s*(match|optional\s+match|return|with|unwind)\b", re.I)


def _mask_literals_and_comments(text: str) -> tuple[str, str | None]:
    """Mask strings, backtick identifiers, and Cypher comments."""
    out = list(text)
    i = 0
    state = "normal"
    quote = ""
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if state == "normal":
            if ch in {"'", '"', "`"}:
                quote = ch
                out[i] = " "
                state = "quoted"
            elif ch == "/" and nxt == "/":
                out[i] = out[i + 1] = " "
                i += 1
                state = "line_comment"
            elif ch == "/" and nxt == "*":
                out[i] = out[i + 1] = " "
                i += 1
                state = "block_comment"
        elif state == "quoted":
            if ch == "\\" and quote in {"'", '"'} and nxt:
                out[i] = out[i + 1] = " "
                i += 1
            elif ch == quote and nxt == quote:
                out[i] = out[i + 1] = " "
                i += 1
            elif ch == quote:
                out[i] = " "
                state = "normal"
                quote = ""
            elif ch != "\n":
                out[i] = " "
        elif state == "line_comment":
            if ch == "\n":
                state = "normal"
            else:
                out[i] = " "
        elif state == "block_comment":
            if ch == "*" and nxt == "/":
                out[i] = out[i + 1] = " "
                i += 1
                state = "normal"
            elif ch != "\n":
                out[i] = " "
        i += 1

    if state in {"quoted", "block_comment"}:
        return "".join(out), "unclosed quote or comment"
    return "".join(out), None


def validate_readonly_cypher(cypher: str) -> tuple[str, str | None, str]:
    """Return (clean, error, masked) for one conservative read-only statement."""
    if not isinstance(cypher, str):
        return "", "query must be a string", ""
    clean = cypher.strip()
    if not clean:
        return clean, "empty query", ""
    if clean.endswith(";"):
        clean = clean[:-1].rstrip()

    masked, mask_error = _mask_literals_and_comments(clean)
    if mask_error:
        return clean, mask_error, masked
    if ";" in masked:
        return clean, "only one Cypher statement is allowed", masked
    if not _READ_START.match(masked):
        return clean, "query must start with MATCH, OPTIONAL MATCH, RETURN, WITH, or UNWIND", masked
    if _WRITE.search(masked):
        return clean, "write, procedure, and administration clauses are not allowed", masked
    return clean, None, masked
