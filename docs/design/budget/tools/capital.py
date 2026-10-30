"""Scratch: HB 25 of 2025 (chapter 159), section 159:1, capital appropriations
by department. Checks projects -> paragraph totals -> section total."""
import json, re, sys

t = open(sys.argv[1]).read()
a = t.index("159:1 Capital Appropriations")
b = t.index("Total state appropriation section 1", a)
sec = t[a:b + 80]
print(sec[b - a:b - a + 80])
paras = list(re.finditer(r"(?:(?<=\s)|^)([IVX]{1,5})\. ([A-Z][A-Za-z,.&' \-]+?) 1\. ", sec))
out, problems = [], []
for k, m in enumerate(paras):
    body = sec[m.end() - 3: paras[k + 1].start() if k + 1 < len(paras) else len(sec)]
    tot = re.search(r"Total state appropriation paragraph ([IVX]+) \$([\d,]+)", body)
    lines = re.findall(r"(?:^|\s)\d{1,2}\. (.+?) (\d{1,3}(?:,\d{3})+|\d+)(?=\s)", body[: tot.start()] if tot else body)
    s = sum(int(v.replace(",", "")) for _, v in lines)
    T = int(tot.group(2).replace(",", "")) if tot else None
    out.append({"para": m.group(1), "who": m.group(2).strip(), "projects": len(lines), "sum": s, "total": T,
                "total_para": tot.group(1) if tot else None})
    if T != s or (tot and tot.group(1) != m.group(1)):
        problems.append(out[-1])
sec_total = int(re.search(r"Total state appropriation section 1 \$([\d,]+)", sec).group(1).replace(",", ""))
psum = sum(o["total"] or 0 for o in out)
for o in out:
    print(f"{o['para']:>5} {o['who'][:60]:60s} {o['projects']:3d} projects  sum {o['sum']:>12,}  printed {o['total'] or 0:>12,}")
print("paragraphs", len(out), "sum of paragraph totals", f"{psum:,}", "section total", f"{sec_total:,}")
print("PROBLEMS", problems)
json.dump({"paragraphs": out, "section_total": sec_total}, open(sys.argv[2], "w"), indent=1)
