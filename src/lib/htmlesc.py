#!/usr/bin/env python3
# GRANITE_VERSION: 2026-11-11.1
"""
The two escapes that mirror components.js's esc() byte for byte: the
ampersand, the angles and the double quote, and nothing else.

NOT html.escape (shell.E), which also turns an apostrophe into &#x27;: the
two render the same on a page and differ in a diff, and a check that holds a
Python chip to its JavaScript twin compares bytes.

They differ in one thing, and the difference is kept because output depends
on it:

  esc(s)        None is "" and everything else is str(s): 0 is "0".
                components.py's, the chips and the cards.
  esc_blank(x)  anything falsy is "": 0 is "". build_pages' home page and
                calendar.

Other escapes on purpose (not copies): shell.E (html.escape), key_dates._esc
(an apostrophe becomes &rsquo;), nightly.py's workflow-command escape.
"""


def esc(s):
    return (str("" if s is None else s).replace("&", "&amp;")
            .replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


def esc_blank(x):
    return (str(x or "").replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))
