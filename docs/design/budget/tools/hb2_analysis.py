"""Scratch: HB 2 of 2025's analysis, as printed with its chaptered text, split
into its numbered items. Checks the numbering runs 1..N unbroken (four items
are printed without the full stop after the number) and writes them as JSON.
Args: the chaptered text file, the output json."""
import json, re, sys

t = re.sub(r"\s+", " ", open(sys.argv[1], encoding="utf-8").read())
a = t.index("ANALYSIS This bill:") + len("ANALYSIS This bill:")
b = t.index("- - - - -", a)
body = t[a:b].strip()

items, pos, n = [], 0, 1
while True:
    m = re.compile(rf"(?:^|\s){n}\.? (?=[A-Z])").search(body, pos)
    if not m:
        break
    if items:
        items[-1]["end"] = m.start()
    items.append({"n": n, "start": m.end(), "dotted": body[m.start():m.end()].strip().endswith(".")})
    pos, n = m.end(), n + 1
items[-1]["end"] = len(body)
out = []
for it in items:
    text = body[it["start"]:it["end"]].strip()
    out.append({"n": it["n"], "text": text, "number_printed_with_full_stop": it["dotted"]})
print(len(out), "items; numbering 1 to", out[-1]["n"])
print("printed without a full stop after the number:", [o["n"] for o in out if not o["number_printed_with_full_stop"]])
print("shortest:", min(out, key=lambda o: len(o["text"]))["text"][:120])
print("last:", out[-1]["text"][:200])
json.dump(out, open(sys.argv[2], "w"), indent=1)
