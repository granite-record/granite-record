#!/usr/bin/env python3
# GRANITE_VERSION: 2026-10-23.1
"""
The browser's scripts as the site publishes them: without their comments.

    import strip_js as SJ
    SJ.published("app.js", text)     # what site/app.js carries
    SJ.strip(text)                   # the same, or SJ.Refused

THE PUBLISHED SCRIPTS CARRY NO COMMENTS (23 October 2026). The comments are
the scripts' documentation and stay in src/pages/; the copy a reader's phone
downloads goes without them, as app.css has since the same day
(build_pages.strip_css). Measured on dry-run.graniterecord.pages.dev that
morning, as Cloudflare sends them to Chrome (brotli): app.js was 543 KB and
189 KB over the wire, of which the code was 255 KB and 82; find.js 31 KB over
the wire and 15; components.js 19 and 14. app.js is loaded by every bill,
legislator, committee, town and law page and by /bills, so a first visit on a
phone over 4G spent about a tenth of a second on its comments alone, before
the parser had read a word of them.

WHAT IS TAKEN OUT, AND NOTHING ELSE. Every comment, the lines they leave
blank, and the spaces at the end of a line. A line's own indent stays, so
what is published still reads; the names, the strings, the regular
expressions and every template literal are kept byte for byte, an HTML
comment inside a template among them, because that is text the page writes.
A block comment that held a line end leaves one, so automatic semicolon
insertion reads the code as it did; one that sat between two tokens on a line
leaves a space, so `a/**/b` stays two names and `+/**/+` two signs.

IT READS THE SCRIPT, IT DOES NOT GUESS. A comment can only be found by
knowing where strings, template literals and regular expressions are, and a
regular expression can only be told from a division by what stands before
it. tokens() decides that the way the language does for everything this
site writes, and where the language leaves it to the grammar -- a / after a
}, after `++`, after a word such as `of` or `await` that may be a name -- it
refuses rather than choosing. So does anything else it does not read: an
escape in a name, a #! line, an HTML comment marker in the code (which a
browser reads as a comment), a regular expression with the v flag (whose
classes nest), a string, comment or bracket left open.

AND IT CHECKS ITSELF. What strip() returns is read again, and its tokens --
each with whether a line ends before it -- must be the original's with the
comments taken out, or it refuses. A refused script is published as it is
(published() says so in the build's log): it costs bytes and nothing else,
and preflight's _published_scripts_stripped fails on it, so it is found before
it reaches a reader rather than shipped quietly. And
_published_scripts_run_the_same runs every node harness in preflight that
loads a page's script on the published copy too, and holds its result to the
result on the source.
"""

import re

# The line terminators and the white space of ECMAScript (LineTerminator,
# WhiteSpace: the Zs category, tab, vertical tab, form feed and the BOM).
_NL = "\n\r  "
_WS = (" \t\v\f ﻿        "
       "      　")
_SPACE = frozenset(_NL + _WS)
# A name or a keyword: ASCII letters, digits, _ and $, and any character past
# ASCII that is not white space or a line end.
_WORD = re.compile(r"(?:[A-Za-z0-9_$]|[^\x00-\x7f\s﻿])+")
_NUMBER = re.compile(r"0[xX][0-9a-fA-F_]+n?|0[oO][0-7_]+n?|0[bB][01_]+n?"
                     r"|(?:\d[\d_]*(?:\.[\d_]*)?|\.\d[\d_]*)(?:[eE][+-]?\d[\d_]*)?n?")
# After these a / begins a regular expression.
_REGEX_AFTER = frozenset(("return", "typeof", "instanceof", "in", "new", "delete", "void",
                          "throw", "case", "do", "else"))
# After these it may do either, depending on whether the word is a keyword
# where it stands: refused.
_UNSURE_AFTER = frozenset(("of", "yield", "await", "let", "async", "get", "set", "static"))
# A ) that closes the head of one of these is followed by a statement, where
# a / begins a regular expression.
_CONTROL = frozenset(("if", "while", "for", "with"))

# The scripts the site publishes without their comments.
SCRIPTS = ("components.js", "app.js", "find.js", "print.js", "billmatch.js", "map.js")


class Refused(ValueError):
    """The script holds something strip() does not read with certainty."""


def tokens(js):
    """Every token of `js` in order, as (kind, text): "ws" for white space
    and line ends, "com" a comment, "str" a string, "tpl" a template
    literal's text up to and including its `${` or its closing backtick,
    "re" a regular expression, "word" a name or keyword, "num" a number and
    "p" a punctuator. Raises Refused where it cannot say which."""
    out = []
    i, n = 0, len(js)
    # What a / here would follow: "re" where it begins a regular expression,
    # "div" where it divides, "unsure:<what>" where only the grammar knows.
    prev = "re"
    braces, parens = [], []

    def at(k):
        return f"line {js.count(chr(10), 0, k) + 1}"

    def template(k):
        # From just after a ` or a }, to just after the ` that ends the
        # literal or the ${ that opens an expression in it.
        while k < n:
            c = js[k]
            if c == "\\":
                k += 2
            elif c == "`":
                return k + 1, False
            elif c == "$" and js.startswith("${", k):
                return k + 2, True
            else:
                k += 1
        raise Refused(f"a template literal is never closed ({at(k)})")

    while i < n:
        c = js[i]
        if c in _SPACE:
            j = i + 1
            while j < n and js[j] in _SPACE:
                j += 1
            out.append(("ws", js[i:j]))
            i = j
            continue
        if js.startswith("//", i):
            j = i
            while j < n and js[j] not in _NL:
                j += 1
            out.append(("com", js[i:j]))
            i = j
            continue
        if js.startswith("/*", i):
            j = js.find("*/", i + 2)
            if j < 0:
                raise Refused(f"a comment is never closed ({at(i)})")
            out.append(("com", js[i:j + 2]))
            i = j + 2
            continue
        if c in "\"'":
            j = i + 1
            while True:
                if j >= n or js[j] in "\n\r":
                    raise Refused(f"a string is never closed ({at(i)})")
                if js[j] == "\\":
                    j += 3 if js.startswith("\r\n", j + 1) else 2
                elif js[j] == c:
                    j += 1
                    break
                else:
                    j += 1
            out.append(("str", js[i:j]))
            prev = "div"
            i = j
            continue
        if c == "`" or (c == "}" and braces and braces[-1] == "${"):
            if c == "}":
                braces.pop()
            j, opened = template(i + 1)
            out.append(("tpl", js[i:j]))
            if opened:
                braces.append("${")
            prev = "re" if opened else "div"
            i = j
            continue
        if c == "}":
            if not braces:
                raise Refused(f"a }} closes nothing ({at(i)})")
            braces.pop()
            out.append(("p", c))
            prev = "unsure:}"
            i += 1
            continue
        if c == "{":
            braces.append("{")
            out.append(("p", c))
            prev = "re"
            i += 1
            continue
        if c == "(":
            parens.append(prev == "control")
            out.append(("p", c))
            prev = "re"
            i += 1
            continue
        if c == ")":
            if not parens:
                raise Refused(f"a ) closes nothing ({at(i)})")
            out.append(("p", c))
            prev = "re" if parens.pop() else "div"
            i += 1
            continue
        if c.isdigit() and c.isascii() or (c == "." and js[i + 1:i + 2].isdigit()):
            m = _NUMBER.match(js, i)
            out.append(("num", m.group()))
            prev = "div"
            i = m.end()
            if _WORD.match(js, i):
                raise Refused(f"a number runs into a name ({at(i)})")
            continue
        if c == "#" or _WORD.match(js, i):
            m = _WORD.match(js, i + (c == "#"))
            if not m or (c == "#" and i == 0):
                raise Refused(f"a # that is not a private name ({at(i)})")
            if js[m.end():m.end() + 1] == "\\" or c == "\\":
                raise Refused(f"an escape in a name ({at(i)})")
            word = js[i:m.end()]
            out.append(("word", word))
            if prev == "dot":
                prev = "div"
            elif word in _REGEX_AFTER:
                prev = "re"
            elif word in _UNSURE_AFTER:
                prev = "unsure:" + word
            elif word in _CONTROL:
                prev = "control"
            else:
                prev = "div"
            i = m.end()
            continue
        if c == "/":
            if prev == "div":
                out.append(("p", c))
                prev = "re"
                i += 1
                continue
            if prev.startswith("unsure:"):
                raise Refused(f"a / after {prev[7:]} may begin a regular expression or divide "
                              f"({at(i)})")
            j, in_class = i + 1, False
            while True:
                if j >= n or js[j] in _NL:
                    raise Refused(f"a regular expression is never closed ({at(i)})")
                d = js[j]
                if d == "\\":
                    j += 2
                    continue
                if d == "[":
                    in_class = True
                elif d == "]":
                    in_class = False
                elif d == "/" and not in_class:
                    break
                j += 1
            m = _WORD.match(js, j + 1)
            end = m.end() if m else j + 1
            if "v" in js[j + 1:end]:
                raise Refused(f"a regular expression with the v flag ({at(i)})")
            out.append(("re", js[i:end]))
            prev = "div"
            i = end
            continue
        if js.startswith("<!--", i) or js.startswith("-->", i):
            raise Refused(f"an HTML comment marker in the code ({at(i)})")
        if js.startswith("++", i) or js.startswith("--", i):
            out.append(("p", js[i:i + 2]))
            prev = "unsure:" + js[i:i + 2]
            i += 2
            continue
        if js.startswith("?.", i) and not js[i + 2:i + 3].isdigit():
            out.append(("p", "?."))
            prev = "dot"
            i += 2
            continue
        if c == "." and not js.startswith("...", i):
            out.append(("p", c))
            prev = "dot"
            i += 1
            continue
        if c in "!%&*+,-.:;<=>?[]^|~":
            out.append(("p", c))
            prev = "div" if c == "]" else "re"
            i += 1
            continue
        raise Refused(f"{c!r} is not a character a script here is written with ({at(i)})")
    if braces or parens:
        raise Refused("a bracket is never closed")
    return out


def _read(toks):
    """What an engine reads of `toks`: each token but white space and
    comments, with whether a line ends before it (which is what automatic
    semicolon insertion reads). The first token's is not asked."""
    seen, line = [], False
    for kind, text in toks:
        if kind in ("ws", "com"):
            line = line or any(ch in _NL for ch in text)
            continue
        seen.append((text, line and bool(seen)))
        line = False
    return seen


def strip(js):
    """`js` without its comments, the lines they leave blank and the spaces
    that end a line; raises Refused where tokens() does, or where the result
    does not read as the same tokens."""
    toks = tokens(js)
    eol = "\r\n" if "\r\n" in js else "\n"
    # Each piece, and whether it is white space between tokens.
    pieces = []
    for k, (kind, text) in enumerate(toks):
        if kind == "com":
            if any(ch in _NL for ch in text):
                pieces.append((True, eol))
            else:
                before = pieces[-1][1][-1:] if pieces else ""
                after = toks[k + 1][1][:1] if k + 1 < len(toks) else ""
                if before and after and before not in _SPACE and after not in _SPACE:
                    pieces.append((True, " "))
            continue
        pieces.append((kind == "ws", text))
    out, run = [], []
    for space, text in pieces + [(False, "")]:
        if space:
            run.append(text)
            continue
        if run:
            gap = "".join(run)
            run = []
            last = max(gap.rfind(ch) for ch in _NL)
            # A gap holding a line end becomes one line end and the indent of
            # the line it opens; a gap within a line is left as it is.
            out.append(gap if last < 0 else eol + gap[last + 1:])
        out.append(text)
    text = "".join(out).lstrip("".join(_SPACE))
    text = text.rstrip("".join(_SPACE)) + eol if text.strip("".join(_SPACE)) else ""
    if _read(tokens(text)) != _read(toks):
        raise Refused("without its comments it does not read as the same tokens")
    return text


def published(name, text):
    """`text`, the browser script `name`, as the site publishes it: strip(),
    or where that refuses, the script as it is and a line in the build's log
    saying so."""
    try:
        return strip(text)
    except Refused as e:
        print(f"WARNING: {name} is published WITH its comments, because the comment strip "
              f"refused it: {e}. It works as it is and costs only bytes; preflight's "
              f"_published_scripts_stripped says the same until it is put right.")
        return text
