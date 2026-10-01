"""The format's mechanical ids: statement hashes of anonymous declarations, passage and label ids.

The reference implementation of docs/annotations.md section 5.

* A **named** declaration's id is its fully qualified name; a **private**
  one's is ``private:<module>:<declared full name>`` (:func:`private_id`).
* An ``example`` or an anonymous ``instance`` gets
  ``<keyword>:<first 12 hex digits of statement_sha256>`` (:func:`anonymous_id`),
  with ``~k`` for the k-th duplicate, unless the companion declares an id
  (``<keyword>:<slug>``, :data:`DECLARED_ID`).  Its ``signature`` is in display
  form (:func:`normalize_statement`: comments replaced by a space, whitespace
  collapsed) and ``statement_sha256`` is the sha256 of its hash form
  (:func:`hash_form`: the tokens re-joined, so that the placement of
  whitespace, line breaks and comments, and the spellings ``fun``/``λ`` and
  ``=>``/``↦``, do not matter).
* A passage's id is ``passage-<8 hex>`` of its normalised quote
  (:func:`passage_quote_id`) or ``passage-p<printed page>-<8 hex>`` of its
  normalised title (:func:`passage_page_id`); a numbered item's is
  ``<kind>-<number>[-<sub>]`` (:func:`item_label_id`).

How a producer finds declarations and declared ids in Lean source is not part
of the format, and not here.  Every rule here is frozen with the format:
changing one re-keys ids.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata

from . import vocab

#: The stable public API of this module: exactly these names.  Anything else,
#: underscored or not, is internal and may change in any release.
__all__ = [
    "DECLARED_ID", "HASH_ID", "anonymous_id", "hash_form", "item_label_id", "normalize_statement",
    "normalize_text", "passage_page_id", "passage_quote_id", "private_id", "statement_sha256",
]

#: The anonymous-id grammars (vocab's), anchored at both ends: use ``fullmatch``
#: (``match`` gives the same answer, since ``\A``/``\Z`` are string ends).
HASH_ID = re.compile(r"\A(?:" + vocab.HASH_ID_PATTERN + r")\Z")
DECLARED_ID = re.compile(r"\A(?:" + vocab.DECLARED_ID_PATTERN + r")\Z")

# ---------------------------------------------------------------------------
# character sets (docs/annotations.md section 5.3)
# ---------------------------------------------------------------------------

#: Whitespace in the display and hash forms: exactly these four.
_WS = " \t\r\n"
#: The word characters (a Lean identifier character): ASCII letters and digits,
#: ``_``, ``'``, ``!``, ``?``, ``.``, Greek except λ Π Σ, Greek Extended,
#: letter-like symbols, mathematical alphanumerics, and the subscripts.
_WORD_CLASS = (r"A-Za-z0-9_'!?."
               r"Ͱ-ΟΡ-΢Τ-κμ-Ͽ"
               r"ἀ-῾℀-⅏\U0001d49c-\U0001d59f"
               r"₀-₉ₐ-ₜᵢ-ᵪⱼ")
_WORD_RE = re.compile(rf"[{_WORD_CLASS}]+")
_IS_WORD = re.compile(rf"[{_WORD_CLASS}]").fullmatch
#: The 25 code points with the Unicode ``White_Space`` property (passage ids).
_UNICODE_WHITE_SPACE = ("\u0009\u000a\u000b\u000c\u000d \u0085  "
                        "           "
                        "    　")
_WHITE_SPACE_RUN = re.compile("[" + _UNICODE_WHITE_SPACE + "]+")
_COMMENT_KINDS = frozenset({"doc", "moddoc", "block", "line"})


# ---------------------------------------------------------------------------
# id forms (docs/annotations.md sections 5.1 and 5.3)
# ---------------------------------------------------------------------------

def _utf8(text: str) -> bytes:
    """``text`` as UTF-8.  A lone surrogate is refused: no UTF-8 text holds one,
    so such text is outside the rules (it comes from decoding with ``surrogateescape``)."""
    try:
        return text.encode("utf-8")
    except UnicodeEncodeError:
        raise ValueError("the text is not valid Unicode: it holds a lone surrogate") from None


def statement_sha256(signature: str) -> str:
    """sha256 of the hash form of ``signature``, as 64 lowercase hex digits.

    Raises ``ValueError`` when ``signature`` holds a lone surrogate.
    """
    return hashlib.sha256(_utf8(hash_form(signature))).hexdigest()


def anonymous_id(keyword: str, digest: str, ordinal: int = 1) -> str:
    """``example:<12 hex>`` or ``instance:<12 hex>``, with ``~k`` for k >= 2."""
    if keyword not in vocab.ANONYMOUS_KEYWORDS:
        raise ValueError(f"not an anonymous keyword: {keyword!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("digest must be 64 lowercase hex digits")
    if ordinal < 1:
        raise ValueError("ordinal starts at 1")
    return f"{keyword}:{digest[:12]}" + (f"~{ordinal}" if ordinal > 1 else "")


def private_id(module: str, full_name: str) -> str:
    """``private:<module>:<declared full name>``."""
    if not module or not full_name:
        raise ValueError("a private id needs a module and a name")
    return f"private:{module}:{full_name}"


# ---------------------------------------------------------------------------
# passages and numbered items (docs/annotations.md section 5.5)
# ---------------------------------------------------------------------------

def normalize_text(text: str) -> str:
    """NFKC, then each run of ``White_Space`` code points to one space, ends stripped.

    The passage-id normaliser.  NFKC comes first because it can turn a
    character into whitespace (U+00A0) and it folds ligatures and the micro
    sign, which differ between PDF text extractors.  Case is kept.  Whitespace
    is the 25 code points with the Unicode ``White_Space`` property, written
    out in ``_UNICODE_WHITE_SPACE``: not Python's ``\\s``, which also matches
    U+001C..U+001F.
    """
    return _WHITE_SPACE_RUN.sub(" ", unicodedata.normalize("NFKC", text)).strip(_UNICODE_WHITE_SPACE)


def _h8(text: str) -> str:
    return hashlib.sha256(_utf8(normalize_text(text))).hexdigest()[:8]


def passage_quote_id(quote: str) -> str:
    """``passage-<8 hex>``: the id of a passage whose anchor quote is ``quote``."""
    if not normalize_text(quote):
        raise ValueError("an empty quote cannot identify a passage")
    return f"passage-{_h8(quote)}"


def passage_page_id(printed_page: int, title: str) -> str:
    """``passage-p<printed page>-<8 hex of the title>``, for a passage with no quote."""
    if not isinstance(printed_page, int) or isinstance(printed_page, bool) or printed_page < 1:
        raise ValueError("the printed page is a positive integer")
    if not normalize_text(title):
        raise ValueError("an empty title cannot identify a passage")
    return f"passage-p{printed_page}-{_h8(title)}"


def item_label_id(kind: str, number: str, sub: str | None = None) -> str:
    """``<kind>-<number>[-<sub>]``, the kind lower-cased with each run of other characters as ``-``."""
    slug = re.sub(r"[^a-z0-9]+", "-", kind.lower()).strip("-")
    if not slug or not number:
        raise ValueError("a label id needs a kind and a number")
    return f"{slug}-{number}" + (f"-{sub}" if sub else "")


# ---------------------------------------------------------------------------
# lexing: comments and literals (docs/annotations.md section 5.2)
# ---------------------------------------------------------------------------

_LEX = re.compile(r"/-|--|\"|'|«")
_HOLE = re.compile(r"/-|--|\"|'|«|[{}]")
_COMMENT_DELIM = re.compile(r"/-|-/")
_CHAR_ESCAPE = re.compile(r"'\\(?:x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)'", re.S)
_RAW_START = re.compile(r'r#*"')


def _word_before(text: str, i: int) -> bool:
    """Is the code point before offset ``i`` a word character?"""
    return i > 0 and _IS_WORD(text[i - 1]) is not None


def _comment_end(text: str, i: int) -> tuple[int, str]:
    """The end of the block comment opening at ``i`` (``/-``) and its kind."""
    if text.startswith("/--", i):
        kind, k = "doc", i + 3
    elif text.startswith("/-!", i):
        kind, k = "moddoc", i + 3
    else:
        kind, k = "block", i + 2
    depth = 1
    while depth:
        m = _COMMENT_DELIM.search(text, k)
        if m is None:
            return len(text), kind
        depth += 1 if m.group() == "/-" else -1
        k = m.end()
    return k, kind


def _char_end(text: str, i: int) -> int | None:
    """The end of the character literal at ``i`` (a ``'``), or None when it is a prime or a symbol."""
    if _word_before(text, i):
        return None
    n = len(text)
    if i + 2 < n and text[i + 1] not in "\\'" and text[i + 2] == "'":
        return i + 3
    m = _CHAR_ESCAPE.match(text, i)
    return m.end() if m else None


def _raw_string_span(text: str, i: int) -> tuple[int, int] | None:
    """The span of the raw string ``r#..."..."#...`` whose opening ``"`` is at ``i``, or None."""
    j = i
    while j > 0 and text[j - 1] == "#":
        j -= 1
    if j > 0 and text[j - 1] == "r" and not _word_before(text, j - 1):
        close = '"' + "#" * (i - j)
        k = text.find(close, i + 1)
        return j - 1, (len(text) if k < 0 else k + len(close))
    return None


def _interpolated_at(text: str, i: int) -> bool:
    """Does the string whose ``"`` is at ``i`` open with ``s!``, ``m!`` or ``f!``?"""
    return text[i - 2:i] in ("s!", "m!", "f!") and not _word_before(text, i - 2)


def _string_at(text: str, i: int) -> tuple[int, int]:
    """The span of the string literal whose ``"`` is at ``i``: plain, raw or interpolated.

    A hole ``{...}`` of an interpolated string may hold a string with holes of
    its own.  The open constructs are kept on an explicit stack,
    so the depth of that nesting never limits the lexer.
    """
    raw = _raw_string_span(text, i)
    if raw is not None:
        return raw
    n = len(text)
    # One frame per open construct, innermost last: ["string", interpolated?]
    # or ["hole", brace depth].
    frames: list[list] = [["string", _interpolated_at(text, i)]]
    k = i + 1
    while k < n:
        kind, state = frames[-1]
        if kind == "string":
            c = text[k]
            if c == '"':
                frames.pop()
                k += 1
                if not frames:
                    return i, k
            elif c == "\\":
                k += 2
            elif state and c == "{":
                frames.append(["hole", 1])
                k += 1
            else:
                k += 1
            continue
        m = _HOLE.search(text, k)                   # inside a hole: braces balance, literals and comments skip
        if m is None:
            break
        k = m.start()
        c = text[k]
        if c == "{":
            frames[-1][1] = state + 1
            k += 1
        elif c == "}":
            if state == 1:
                frames.pop()
            else:
                frames[-1][1] = state - 1
            k += 1
        elif c == '"':
            raw = _raw_string_span(text, k)
            if raw is None:
                frames.append(["string", _interpolated_at(text, k)])
                k += 1
            else:
                k = raw[1]
        else:
            end = _skip_literal_or_comment(text, k)
            k = k + 1 if end is None else end
    return i, n


def _skip_literal_or_comment(text: str, i: int) -> int | None:
    """The end of the comment, char literal or ``«»`` starting at ``i``, or None.

    A string is not handled here: :func:`_string_at` reads one, holes included.
    """
    c = text[i]
    if c == "/" and text.startswith("/-", i):
        return _comment_end(text, i)[0]
    if c == "-" and text.startswith("--", i):
        k = text.find("\n", i)
        return len(text) if k < 0 else k
    if c == "'":
        return _char_end(text, i)
    if c == "«":
        k = text.find("»", i + 1)
        return None if k < 0 else k + 1
    return None


def _lex(text: str) -> list[tuple[int, int, str]]:
    """The comment and literal spans of ``text``, in order: ``(start, end, kind)``.

    Kinds: ``doc`` (``/--``), ``moddoc`` (``/-!``), ``block``, ``line``
    (comments); ``string``, ``char``, ``guil`` (``«…»``) (literals).
    """
    spans: list[tuple[int, int, str]] = []
    i, n = 0, len(text)
    while i < n:
        m = _LEX.search(text, i)
        if m is None:
            break
        j = m.start()
        c = text[j]
        if c == "/":
            end, kind = _comment_end(text, j)
            spans.append((j, end, kind))
            i = end
        elif c == "-":
            end = text.find("\n", j)
            end = n if end < 0 else end
            spans.append((j, end, "line"))
            i = end
        elif c == '"':
            start, end = _string_at(text, j)
            spans.append((start, end, "string"))
            i = end
        elif c == "'":
            end = _char_end(text, j)
            if end is None:
                i = j + 1
            else:
                spans.append((j, end, "char"))
                i = end
        else:
            k = text.find("»", j + 1)
            if k < 0:
                i = j + 1
            else:
                spans.append((j, k + 1, "guil"))
                i = k + 1
    return spans


# ---------------------------------------------------------------------------
# display form and hash form (docs/annotations.md sections 5.2 and 5.3)
# ---------------------------------------------------------------------------

def _tokens(text: str) -> list[tuple[str, bool]]:
    """The tokens of ``text``: ``(token, wordlike)``, comments and whitespace dropped.

    A word token is a maximal run of word characters and ``«…»`` groups; a
    literal token is a whole string or char literal; every other non-whitespace
    code point is a symbol token on its own.  Word and literal tokens are
    wordlike.  The alias table is applied: ``↦`` gives ``=>``, ``λ`` gives the
    word ``fun``.
    """
    out: list[tuple[str, bool]] = []
    i, n = 0, len(text)
    word: list[str] = []

    def flush() -> None:
        if word:
            out.append(("".join(word), True))
            word.clear()

    while i < n:
        c = text[i]
        if c == "'":
            end = _char_end(text, i)
            if end is not None:
                flush()
                out.append((text[i:end], True))
                i = end
                continue
        if c == "r" and not _word_before(text, i) and _RAW_START.match(text, i):
            _start, end = _string_at(text, text.index('"', i))
            flush()
            out.append((text[i:end], True))
            i = end
            continue
        if _IS_WORD(c):
            m = _WORD_RE.match(text, i)
            word.append(m.group())
            i = m.end()
            continue
        if c == "«":
            k = text.find("»", i + 1)
            if k >= 0:
                word.append(text[i:k + 1])
                i = k + 1
                continue
        flush()
        if c in _WS:
            i += 1
        elif c == '"':
            out.append((text[i:_string_at(text, i)[1]], True))
            i = len(out[-1][0]) + i
        elif c == "/" and text.startswith("/-", i):
            i = _comment_end(text, i)[0]
        elif c == "-" and text.startswith("--", i):
            k = text.find("\n", i)
            i = n if k < 0 else k
        elif c == "↦":
            out.append(("=>", False))
            i += 1
        elif c == "λ":
            out.append(("fun", True))
            i += 1
        else:
            out.append((c, False))
            i += 1
    flush()
    return out



def hash_form(signature: str) -> str:
    """``H``: the tokens of ``signature`` joined, a space only between two wordlike tokens.

    Defined on a display-form signature; any comment in the input counts as
    whitespace, so for text whose literals are closed
    ``hash_form(text) == hash_form(normalize_statement(text))``
    (docs/annotations.md section 5.3).
    """
    parts: list[str] = []
    prev_wordlike = False
    for token, wordlike in _tokens(signature):
        if wordlike and prev_wordlike:
            parts.append(" ")
        parts.append(token)
        prev_wordlike = wordlike
    return "".join(parts)


def normalize_statement(text: str) -> str:
    """The display form: comments replaced by one space, each run of whitespace one space, ends stripped.

    Whitespace is U+0009, U+000A, U+000D, U+0020.  String, char and ``«…»``
    literals are kept verbatim, inner whitespace included.  Idempotent; the
    checker verifies a ``signature`` with ``normalize_statement(s) == s``.
    """
    parts: list[str] = []
    code: list[str] = []            # the code between two literals, comments already spaces
    last = 0
    for a, b, kind in _lex(text):
        code.append(text[last:a])
        if kind in _COMMENT_KINDS:
            code.append(" ")
        else:
            parts.append(_collapse("".join(code)))
            parts.append(text[a:b])
            code = []
        last = b
    code.append(text[last:])
    parts.append(_collapse("".join(code)))
    return "".join(parts).strip(_WS)


_WS_RUN = re.compile(f"[{_WS}]+")


def _collapse(text: str) -> str:
    return _WS_RUN.sub(" ", text)
