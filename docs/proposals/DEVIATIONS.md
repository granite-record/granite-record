# Where the build departs from the approved design

The design is `design_final.md` with `design_addendum_hourly.md` taking
precedence (the owner's "defaults" to D1-D6 on 29 October 2026, knocking
hourly). Where it was wrong against the code, or silent, the build took the
simpler safe answer, and says so here, one entry per point, in the commit
that made it.

## Commit 1: the record says what it was

1. **`whose()` with no record on file returns `("none", why)`.** The design
   gives only `"night"` or `"person"`. A missing record is neither: a gate
   that asks `whose()[0] == "night"` stays shut, and a sentence that says "a
   refusal is yours" (`person_line`, later) is not written about nothing.
2. **A 503 whose `Retry-After` reads as neither seconds nor an HTTP date is
   not "unavailable".** The design says only "seconds or an HTTP date".
   `unavailable()` returns `None` for it, so the record's kind is
   `"refused"`: a person's, the worst reading of an answer that cannot be
   read. A date already passed is 0.
3. **`machine`, `ref`, `dry` and `run_id` are written on every record**,
   with a kind or without, as §2.1's "with these fields added" reads.
   `retry_after` is written only for `"unavailable"` and only when the
   server named a wait (non-zero).
4. **The committee pages fetch's kinds are held by the existing
   `_committees_fetch_stops`**, which the design does not name: it now
   asserts each record's kind (a 403 and the block page `"refused"`, two
   drops `"dropped"`, a bare 503 `"unavailable"` with its wait).
