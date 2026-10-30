"""Scratch: the State Budget mock, in the site's own Learn layout.

    python3 -I mock.py SITE FIGURES.json HISTORY.json OUT.html

Takes SITE/learn/county-government.html as the template (header, footer,
hub tabs, On this page, Cite this page, pager, all-topics list), replaces its
article with the budget sections, and writes OUT. Every figure comes from
FIGURES.json / HISTORY.json (themselves read from the bill texts); nothing
is typed except what the text quotes and the docket dates and votes, which
are copied from the docket lines named beside them.
"""
import html, json, re, sys
from pathlib import Path

site, figs, hist, out = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text()), \
    json.loads(Path(sys.argv[3]).read_text()), Path(sys.argv[4])
tpl = (site / "learn/county-government.html").read_text(encoding="utf-8")
READ = "October 30, 2026"

S25, S23 = figs["summary"]["2025"], figs["summary"]["2023"]
F25 = figs["funds"]["2025"]


def m(v, d=1):
    """$ millions, as a reader reads them."""
    return f"${v / 1e6:,.{d}f} million"


def bn(v):
    return f"${v / 1e9:,.2f} billion"


def nice(name):
    t = name.title().replace(" And ", " and ").replace("&", "and").replace("Fines and Fees", "Fines and Fees")
    return {"Transfer From Lottery": "Lottery Transfer",
            "Transfer From Liquor": "Liquor Commission Transfer",
            "Interest and Dividends Tax": "Interest and Dividends Tax",
            "Other Revenues": "Other Revenue",
            "Miscellaneous": "Miscellaneous (Highway Fund)",
            "Fines and Miscellaneous": "Fines and Miscellaneous (Fish and Game)"}.get(t, t)


# ---------------------------------------------------------------- charts

FUND_CLS = {"General Fund": "c-gf", "Education Fund": "c-ef",
            "Highway Fund": "c-hf", "Fish and Game Fund": "c-fg"}
FUND_SHOW = {}


def fund_bar():
    bf = S25["biennium_by_fund"]
    tot = S25["biennium_all"]
    segs, key = [], []
    for f, v in bf.items():
        segs.append(f'<i class="{FUND_CLS[f]}" style="flex:{v}" title="{FUND_SHOW.get(f, f)}: {m(v)}"></i>')
        key.append(f'<li><span class="l-sw {FUND_CLS[f]}" aria-hidden="true"></span><span><b>{m(v)}</b> '
                   f'{FUND_SHOW.get(f, f)} <span class="l-sub">({v / tot * 100:.1f}%)</span></span></li>')
    label = ("The four funds' estimated unrestricted revenue for fiscal 2026 and 2027 together: "
             + "; ".join(f"{FUND_SHOW.get(f, f)} {m(v)}" for f, v in bf.items()))
    return (f'<figure class="l-fig l-bar" role="group" aria-label="{label}">'
            f'<figcaption>Estimated Unrestricted Revenue, Fiscal 2026 and 2027: {bn(tot)}</figcaption>'
            f'<div class="l-barb" aria-hidden="true">{"".join(segs)}</div>'
            f'<ul class="l-barkey">{"".join(key)}</ul></figure>')


def ticks(top, step):
    n = int(top // step)
    out_ = []
    for k in range(n + 1):
        v = k * step
        out_.append(f'<i class="t{k * 10}" style="left:{v / top * 100:.4f}%">'
                    f'{v:,.0f}</i>')
    return "".join(out_)


def bars_chart(title, sub, rows, top, step, label, aria):
    """rows: [(label, value_millions, title)] -> the site's l-chart/l-bars."""
    lis = "".join(
        f'<li class="is-lab" title="{html.escape(t)}"><span class="l-bl">{html.escape(l)}</span>'
        f'<span class="l-bt"><span class="l-bf" style="width:{v / top * 100:.2f}%"></span>'
        f'<span class="l-bv" style="left:{v / top * 100:.2f}%">{v:,.1f}</span></span></li>'
        for l, v, t in rows)
    return (f'<figure class="l-chart bud-fig" role="img" aria-label="{html.escape(aria)}">'
            f'<h3 aria-hidden="true">{title}</h3><p aria-hidden="true">{sub}</p>'
            f'<ol class="l-bars bud-bars" aria-hidden="true" style="--l-grid:{step / top * 100:.4f}%">{lis}</ol>'
            f'<div class="l-axis" aria-hidden="true"><span>{html.escape(label)}</span>'
            f'<span class="l-ticks">{ticks(top, step)}</span></div></figure>')


def by_source_chart():
    src = S25["by_source"]
    order = sorted(src, key=lambda n: -src[n]["total"])
    shown, rest = order[:11], order[11:]
    rows = [(nice(n), src[n]["total"] / 1e6,
             f"{nice(n)}: {m(src[n]['total'])} over the two years, "
             + ", ".join(f"{FUND_SHOW.get(f, f)} {m(v)}" for f, v in src[n]["by_fund"].items()))
            for n in shown]
    rest_v = sum(src[n]["total"] for n in rest)
    rows.append((f"{len(rest)} other sources", rest_v / 1e6,
                 f"{len(rest)} other sources together: {m(rest_v)} -- the table lists each"))
    longest = max(len(r[0]) for r in rows)
    aria = ("Bar chart of estimated unrestricted revenue by source, fiscal 2026 and 2027 together, all four funds: "
            + "; ".join(f"{l} {v:,.1f} million dollars" for l, v, _ in rows) + ". The table below lists every source.")
    chart = bars_chart("By Source, All Four Funds",
                       "Millions of dollars, the two years added together. The table below splits each between the funds.",
                       rows, 2400, 400, max((r[0] for r in rows), key=len), aria)
    # the table: every source, by fund
    funds = list(S25["biennium_by_fund"])
    head = "".join(f'<th class="l-num">{FUND_SHOW.get(f, f)}</th>' for f in funds)
    body = ""
    for n in order:
        cells = "".join(f'<td class="l-num">{src[n]["by_fund"].get(f, 0) / 1e6:,.1f}</td>'
                        if src[n]["by_fund"].get(f) else '<td class="l-num">&ndash;</td>' for f in funds)
        body += f'<tr><td>{nice(n)}</td>{cells}<td class="l-num"><b>{src[n]["total"] / 1e6:,.1f}</b></td></tr>'
    tots = "".join(f'<td class="l-num">{S25["biennium_by_fund"][f] / 1e6:,.1f}</td>' for f in funds)
    body += f'<tr class="bud-tot"><td>Total</td>{tots}<td class="l-num"><b>{S25["biennium_all"] / 1e6:,.1f}</b></td></tr>'
    table = ('<details class="l-fold"><summary>Every source, fund by fund (millions of dollars)</summary>'
             '<div class="l-tablewrap l-numwrap"><table class="l-table l-numtab numtab"><thead><tr><th>Source</th>'
             f'{head}<th class="l-num">Both years</th></tr></thead><tbody>{body}</tbody></table></div></details>')
    return chart + table


def compare_chart():
    a, b = S23["by_source"], S25["by_source"]
    names = sorted(set(a) | set(b), key=lambda n: -max(a.get(n, {"total": 0})["total"], b.get(n, {"total": 0})["total"]))[:12]
    top, step = 2800, 400
    lis = ""
    for n in names:
        x, y = a.get(n, {"total": 0})["total"] / 1e6, b.get(n, {"total": 0})["total"] / 1e6
        d = y - x
        sign = "+" if d > 0 else "&minus;" if d < 0 else "&plusmn;"
        lis += (f'<li class="is-lab" title="{nice(n)}: {x:,.1f} million estimated for 2024-2025, {y:,.1f} million for 2026-2027">'
                f'<span class="l-bl">{nice(n)}</span><span class="l-bt bud-pair">'
                f'<span class="l-bf is-was" style="width:{x / top * 100:.2f}%"></span>'
                f'<span class="l-bf is-now" style="width:{y / top * 100:.2f}%"></span>'
                f'<span class="l-bv" style="left:{max(x, y) / top * 100:.2f}%">{sign}{abs(d):,.1f}</span></span></li>')
    aria = ("Paired bars, estimated unrestricted revenue by source, 2024-2025 against 2026-2027, millions of dollars: "
            + "; ".join(f"{nice(n)} {a.get(n, {'total': 0})['total'] / 1e6:,.1f} then {b.get(n, {'total': 0})['total'] / 1e6:,.1f}" for n in names))
    key = ('<ul class="l-barkey bud-key"><li><span class="l-sw bud-was" aria-hidden="true"></span><span>2024&ndash;2025, as HB 1 of 2023 estimated</span></li>'
           '<li><span class="l-sw bud-now" aria-hidden="true"></span><span>2026&ndash;2027, as HB 1 of 2025 estimated</span></li></ul>')
    return (f'<figure class="l-chart bud-fig" role="img" aria-label="{html.escape(aria)}">'
            '<h3 aria-hidden="true">The Twelve Largest Sources, Two Budgets</h3>'
            '<p aria-hidden="true">The twelve sources largest in either budget, by the larger figure. Millions of dollars, both years of each budget added together; the figure at the end of each pair is the change, and the table below gives both amounts.</p>'
            f'{key}<ol class="l-bars bud-bars" aria-hidden="true" style="--l-grid:{step / top * 100:.4f}%">{lis}</ol>'
            f'<div class="l-axis" aria-hidden="true"><span>{nice(max(names, key=lambda n: len(nice(n))))}</span>'
            f'<span class="l-ticks">{ticks(top, step)}</span></div></figure>' + pair_table(a, b))


def pair_table(a, b):
    names = sorted(set(a) | set(b), key=lambda n: -b.get(n, {"total": 0})["total"])
    body = ""
    for n in names:
        x, y = a.get(n, {"total": 0})["total"] / 1e6, b.get(n, {"total": 0})["total"] / 1e6
        body += (f'<tr><td>{nice(n)}</td><td class="l-num">{x:,.1f}</td><td class="l-num">{y:,.1f}</td>'
                 f'<td class="l-num">{y - x:+,.1f}</td></tr>')
    body = body.replace(">-", ">&minus;")
    return ('<details class="l-fold"><summary>Every source, both budgets (millions of dollars)</summary>'
            '<div class="l-tablewrap l-numwrap"><table class="l-table l-numtab numtab bud-tight"><thead><tr><th>Source</th>'
            '<th class="l-num">2024&ndash;25</th><th class="l-num">2026&ndash;27</th><th class="l-num">Change</th>'
            f'</tr></thead><tbody>{body}</tbody></table></div></details>')


def fund_compare_table():
    rows = ""
    for f in S25["biennium_by_fund"]:
        x, y = S23["biennium_by_fund"][f], S25["biennium_by_fund"][f]
        rows += (f'<tr><td>{FUND_SHOW.get(f, f).replace(" Fund", "")}</td><td class="l-num">{x / 1e6:,.1f}</td>'
                 f'<td class="l-num">{y / 1e6:,.1f}</td><td class="l-num">{(y - x) / 1e6:+,.1f}</td></tr>')
    x, y = S23["biennium_all"], S25["biennium_all"]
    rows += (f'<tr class="bud-tot"><td>All four</td><td class="l-num"><b>{x / 1e6:,.1f}</b></td>'
             f'<td class="l-num"><b>{y / 1e6:,.1f}</b></td><td class="l-num"><b>{(y - x) / 1e6:+,.1f}</b></td></tr>')
    return ('<div class="l-tablewrap l-numwrap"><table class="l-table l-numtab numtab bud-tight"><thead><tr><th>Fund</th>'
            '<th class="l-num">2024&ndash;25</th><th class="l-num">2026&ndash;27</th><th class="l-num">Change</th>'
            f'</tr></thead><tbody>{rows}</tbody></table></div>').replace("+-", "&minus;").replace(">-", ">&minus;")


def history_chart():
    rows = [(r["label"], (r["gf"] + r["ef"]) / 1e6,
             f'{r["label"]}: General Fund {m(r["gf"])}, Education Fund {m(r["ef"])}, as HB 1 of {r["term"]} estimated')
            for r in hist]
    aria = ("Bar chart: the General Fund and Education Fund estimates each budget printed, both years added, from "
            + "; ".join(f"{l} {v:,.1f} million dollars" for l, v, _ in rows) + ". Not adjusted for inflation.")
    return bars_chart("Six Budgets' Estimates, General and Education Funds",
                      "Millions of dollars, both years added, as each budget's HB 1 printed them. Not adjusted for inflation.",
                      rows, 7000, 1000, "2026–2027", aria)


HERE = Path(sys.argv[2]).parent
ACT = json.loads((HERE / "actuals.json").read_text())        # LBA collections, $ millions, cash basis
REQ = json.loads((HERE / "requests.json").read_text())       # DAS summary of submissions, dollars
CAP = json.loads((HERE / "capital.json").read_text())        # HB 25 of 2025, 159:1
LBA_REV = ("https://gc.nh.gov/lba/Revenues/FY%2026-27/REVISED%20FY20-26%20GF%20ETF%20Revenue%20"
           "Collection%20(Thru%206-30-2026).pdf")
LBA_PAGE = "https://gc.nh.gov/lba/budget/fy2026_2027_budget.aspx"
DAS_BUDGET = "https://www.das.nh.gov/budget/"
DAS_CAP = ("https://www.das.nh.gov/budget/Budget2028-2029/capital-budget-presentations/"
           "Dept%20of%20Administrative%20Services%20Capital%20Budget%20Presentation.pdf")


def das_name(s):
    """A DAS agency name, as printed, in title case: nothing expanded or guessed."""
    out = s.title().replace("&", "and").replace("Hhs:", "HHS:")
    out = re.sub(r"\bNh\b", "NH", out).replace("Dltss", "DLTSS")
    return out.replace(" Of ", " of ").replace(" The ", " the ").replace(" And ", " and ")


def collected_chart():
    """Estimated (HB 1) against collected (LBA), General + Education funds, by fiscal year."""
    est = {"FY 2024": figs["funds"]["2023"], "FY 2025": figs["funds"]["2023"], "FY 2026": figs["funds"]["2025"]}
    idx = {"FY 2024": 0, "FY 2025": 1, "FY 2026": 0}
    rows = []
    for y in ("FY 2024", "FY 2025", "FY 2026"):
        e = (est[y]["General Fund"]["total"][idx[y]] + est[y]["Education Fund"]["total"][idx[y]]) / 1e6
        c = ACT["Grand Total"][y]
        rows.append((y.replace("FY ", ""), e, c))
    top, step = 4000, 1000
    lis = "".join(
        f'<li class="is-lab" title="{l}: {e:,.1f} million estimated, {c:,.1f} million collected">'
        f'<span class="l-bl">{l}</span><span class="l-bt bud-pair">'
        f'<span class="l-bf is-was" style="width:{e / top * 100:.2f}%"></span>'
        f'<span class="l-bf is-now" style="width:{c / top * 100:.2f}%"></span>'
        f'<span class="l-bv" style="left:{max(e, c) / top * 100:.2f}%">{c - e:+,.1f}</span></span></li>'
        for l, e, c in rows).replace(">-", ">&minus;")
    key = ('<ul class="l-barkey bud-key"><li><span class="l-sw bud-was" aria-hidden="true"></span><span>Estimated in HB 1</span></li>'
           '<li><span class="l-sw bud-now" aria-hidden="true"></span><span>Collected, as the LBA reports it</span></li></ul>')
    aria = ("Paired bars, General and Education funds together, millions of dollars: "
            + "; ".join(f"{l} estimated {e:,.1f}, collected {c:,.1f}" for l, e, c in rows))
    table = "".join(f'<tr><td>{l}</td><td class="l-num">{e:,.1f}</td><td class="l-num">{c:,.1f}</td>'
                    f'<td class="l-num">{c - e:+,.1f}</td></tr>' for l, e, c in rows).replace(">-", ">&minus;")
    return (f'<figure class="l-chart bud-fig" role="img" aria-label="{html.escape(aria)}">'
            '<h3 aria-hidden="true">Estimated and Collected, General and Education Funds</h3>'
            '<p aria-hidden="true">Millions of dollars, each fiscal year. The figure at the end of each pair is collected minus estimated.</p>'
            f'{key}<ol class="l-bars bud-bars" aria-hidden="true" style="--l-grid:{step / top * 100:.4f}%">{lis}</ol>'
            f'<div class="l-axis" aria-hidden="true"><span>2026</span><span class="l-ticks">{ticks(top, step)}</span></div></figure>'
            '<div class="l-tablewrap l-numwrap"><table class="l-table l-numtab numtab bud-tight"><thead><tr><th>FY</th>'
            '<th class="l-num">Estimated</th><th class="l-num">Collected</th><th class="l-num">Diff.</th></tr></thead>'
            f'<tbody>{table}</tbody></table></div>')


def collections_history():
    years = ["FY 2020", "FY 2021", "FY 2022", "FY 2023", "FY 2024", "FY 2025", "FY 2026"]
    rows = [(y.replace("FY ", "Fiscal "), ACT["Grand Total"][y], f"{y}: {ACT['Grand Total'][y]:,.1f} million collected") for y in years]
    aria = ("Bar chart: General and Education Trust Fund unrestricted revenue collected, cash basis, millions of dollars: "
            + "; ".join(f"{l} {v:,.1f}" for l, v, _ in rows))
    return bars_chart("Collected, Seven Fiscal Years",
                      "General and Education Trust Fund unrestricted revenue, millions of dollars, cash basis, as the LBA reports it.",
                      rows, 4000, 1000, "Fiscal 2026", aria)


def departments():
    """DAS rows grouped to departments by the crosswalk: the ten HHS divisions are department 095."""
    dep = {}
    for r in REQ["rows"]:
        key = ("095", "Health and Human Services (ten agencies)") if r["group"] == "DHHS" else (r["num"], das_name(r["name"]))
        d = dep.setdefault(key, {k: 0 for k in r if k not in ("num", "name", "group")})
        for k in d:
            d[k] += r[k]
    return dep


def where_chart():
    dep = departments()
    order = sorted(dep, key=lambda k: -dep[k]["FY26 Actuals"])
    shown, rest = order[:10], order[10:]
    rows = [(k[1], dep[k]["FY26 Actuals"] / 1e6, f"{k[1]}: {dep[k]['FY26 Actuals'] / 1e6:,.1f} million, fiscal 2026 actuals") for k in shown]
    rv = sum(dep[k]["FY26 Actuals"] for k in rest) / 1e6
    rows.append((f"{len(rest)} others", rv, f"{len(rest)} others together: {rv:,.1f} million -- the table lists each"))
    aria = ("Bar chart, fiscal 2026 actuals by department, total funds, millions of dollars: "
            + "; ".join(f"{l} {v:,.1f}" for l, v, _ in rows) + ". The table below lists every department.")
    chart = bars_chart("Fiscal 2026 Actuals, by Department, Total Funds",
                       "Millions of dollars. The table below lists every department, with fiscal 2027's adjusted authorized figure.",
                       rows, 4000, 1000, "Health and Human Services (ten agencies)", aria)
    body = "".join(f'<tr><td>{k[1]}</td><td class="l-num">{dep[k]["FY26 Actuals"] / 1e6:,.1f}</td>'
                   f'<td class="l-num">{dep[k]["FY27 Adj Auth"] / 1e6:,.1f}</td></tr>' for k in order)
    g = REQ["totals"]["GRAND TOTAL APPROPRIATIONS"]
    body += (f'<tr class="bud-tot"><td>All</td><td class="l-num">{g["FY26 Actuals"] / 1e6:,.1f}</td>'
             f'<td class="l-num">{g["FY27 Adj Auth"] / 1e6:,.1f}</td></tr>')
    table = ('<details class="l-fold"><summary>Every department (millions of dollars, total funds)</summary>'
             '<div class="l-tablewrap l-numwrap"><table class="l-table l-numtab numtab bud-tight"><thead><tr><th>Department</th>'
             '<th class="l-num">FY26 actuals</th><th class="l-num">FY27 adj. auth.</th></tr></thead>'
             f'<tbody>{body}</tbody></table></div></details>')
    return chart + table


def capital_chart():
    ps = sorted([p for p in CAP["paragraphs"] if p["total"]], key=lambda p: -p["total"])
    rows = [(p["who"].replace("Department of ", ""), (p["total"] or 0) / 1e6,
             f"{p['who']}: ${p['total'] or 0:,} state appropriation (159:1, paragraph {p['para']})") for p in ps]
    aria = ("Bar chart, HB 25 of 2025 section 1, total state appropriation by department, millions of dollars: "
            + "; ".join(f"{l} {v:,.1f}" for l, v, _ in rows))
    return bars_chart("Capital Appropriations by Department, HB 25 of 2025",
                      "Section 1's &ldquo;total state appropriation&rdquo; for each department, millions of dollars. Section 2's $10 million of highway funds for Transportation is not in this chart.",
                      rows, 40, 10, max((r[0] for r in rows), key=len), aria)


def request_chart():
    dep = departments()
    order = sorted(dep, key=lambda k: -dep[k]["FY28 Request"])[:10]
    top, step = 5000, 1000
    lis = ""
    for k in order:
        x, y = dep[k]["FY27 Adj Auth"] / 1e6, dep[k]["FY28 Request"] / 1e6
        lis += (f'<li class="is-lab" title="{k[1]}: fiscal 2027 adjusted authorized {x:,.1f} million; fiscal 2028 request {y:,.1f} million">'
                f'<span class="l-bl">{k[1]}</span><span class="l-bt bud-pair">'
                f'<span class="l-bf is-was" style="width:{x / top * 100:.2f}%"></span>'
                f'<span class="l-bf is-req" style="width:{y / top * 100:.2f}%"></span>'
                f'<span class="l-bv" style="left:{max(x, y) / top * 100:.2f}%">{y - x:+,.1f}</span></span></li>')
    lis = lis.replace(">-", ">&minus;")
    key = ('<ul class="l-barkey bud-key"><li><span class="l-sw bud-was" aria-hidden="true"></span><span>Fiscal 2027, adjusted authorized</span></li>'
           '<li><span class="l-sw bud-req" aria-hidden="true"></span><span>Fiscal 2028, as requested</span></li></ul>')
    aria = ("Paired bars, the ten largest fiscal 2028 requests by department, total funds, millions of dollars: "
            + "; ".join(f"{k[1]} fiscal 2027 adjusted authorized {dep[k]['FY27 Adj Auth'] / 1e6:,.1f}, fiscal 2028 requested {dep[k]['FY28 Request'] / 1e6:,.1f}" for k in order))
    dall = sorted(dep, key=lambda k: -dep[k]["FY28 Request"])
    body = "".join(f'<tr><td>{k[1]}</td><td class="l-num">{dep[k]["FY27 Adj Auth"] / 1e6:,.1f}</td>'
                   f'<td class="l-num">{dep[k]["FY28 Request"] / 1e6:,.1f}</td><td class="l-num">{dep[k]["FY29 Request"] / 1e6:,.1f}</td></tr>'
                   for k in dall)
    g = REQ["totals"]["GRAND TOTAL APPROPRIATIONS"]
    body += (f'<tr class="bud-tot"><td>All</td><td class="l-num">{g["FY27 Adj Auth"] / 1e6:,.1f}</td>'
             f'<td class="l-num">{g["FY28 Request"] / 1e6:,.1f}</td><td class="l-num">{g["FY29 Request"] / 1e6:,.1f}</td></tr>')
    return (f'<figure class="l-chart bud-fig" role="img" aria-label="{html.escape(aria)}">'
            '<h3 aria-hidden="true">Asked For: The Ten Largest Requests for Fiscal 2028</h3>'
            '<p aria-hidden="true">Total funds, millions of dollars. The figure at the end of each pair is the request minus fiscal 2027&rsquo;s adjusted authorized amount. These are requests, not appropriations.</p>'
            f'{key}<ol class="l-bars bud-bars" aria-hidden="true" style="--l-grid:{step / top * 100:.4f}%">{lis}</ol>'
            f'<div class="l-axis" aria-hidden="true"><span>Health and Human Services (ten agencies)</span>'
            f'<span class="l-ticks">{ticks(top, step)}</span></div></figure>'
            '<details class="l-fold"><summary>Every department&rsquo;s request (millions of dollars, total funds)</summary>'
            '<div class="l-tablewrap l-numwrap"><table class="l-table l-numtab numtab bud-tight"><thead><tr><th>Department</th>'
            '<th class="l-num">FY27 adj. auth.</th><th class="l-num">FY28 request</th><th class="l-num">FY29 request</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div></details>')


def reductions_table():
    R = [("Legislative branch", "General fund", "500,000", "500,000", "140:7"),
         ("Office of the governor", "General fund", "50,000", "50,000", "140:8"),
         ("Department of information technology", "All appropriations", "5,000,000", "5,000,000", "140:9"),
         ("Department of natural and cultural resources", "General fund", "300,000", "300,000", "140:10"),
         ("Department of environmental services", "General fund", "3,000,000", "3,000,000", "140:11"),
         ("Department of health and human services", "General fund", "25,500,000", "25,500,000", "140:12"),
         ("Department of state", "General fund", "225,000", "240,000", "140:13"),
         ("Human rights commission", "General fund", "254,000", "267,000", "140:14"),
         ("Liquor commission", "Liquor fund", "1,000,000 over the two years", "", "140:15"),
         ("Department of corrections", "General fund", "10,000,000 over the two years", "", "140:16")]
    body = ""
    for who, fund, a, b, sec in R:
        first = f'<td>{who}<span class="bud-sub">{fund} &middot; <span class="l-rsa">{sec}</span></span></td>'
        if not b:
            amt = f'${a.replace(" over the two years", "")}<span class="bud-sub">over the two years</span>'
        elif a == b:
            amt = f'${a}<span class="bud-sub">in each year</span>'
        else:
            amt = f'${a}<span class="bud-sub">in 2026, and ${b} in 2027</span>'
        body += f'<tr>{first}<td class="l-num bud-amt">{amt}</td></tr>'
    return ('<div class="l-tablewrap"><table class="l-table"><thead><tr><th>Who, and from which money</th>'
            '<th class="l-num">How much</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


def need(title, what):
    return (f'<div class="bud-need" role="note"><p class="l-lbl">Placeholder &middot; needs a source</p>'
            f'<p><b>{title}</b></p><p>{what}</p></div>')


# ---------------------------------------------------------------- the body

def mk(day):
    return f'<span class="l-mk is-need is-bare"><span class="l-mt">{day}</span></span>'


SECTIONS = []


def sec(title, body):
    SECTIONS.append((title, body))


hb1, hb2 = '<a href="bill/2025/hb1">HB 1</a>', '<a href="bill/2025/hb2">HB 2</a>'

sec("Two Bills, Two Years", f"""
<p>The state budget covers two fiscal years at once. The one in force now made
appropriations &ldquo;for the expenses of certain departments of the state for
fiscal years ending June 30, 2026 and June 30, 2027&rdquo;, in the words of its
title, and took effect on July 1, 2025. <span class="l-rsa">(HB 1 of 2025, title and 140:18)</span></p>

<p>It comes as two bills. The constitution limits a budget bill to the
operating and capital expenses of the executive, legislative and judicial
branches: no section or footnote of one may establish, amend or repeal any
other statutory law. <span class="l-rsa">(<a href="/laws#part2-art18-a">Part Second, Article 18-a</a>)</span>
The statutes then make the changes to the law a document of their own, the
trailer bill, separate from the budget and not a budget bill.
<span class="l-rsa">(<a href="/laws/9#s2-a">RSA 9:2-a</a>)</span> So {hb1} carries the
amounts, and {hb2} the changes to the law that go with them. Both were
introduced in the House. The constitution says all money bills shall
originate there, and that the Senate may propose or concur with amendments.
<span class="l-rsa">(<a href="/laws#part2-art18">Part Second, Article 18</a>)</span></p>
</div><div class="l-wide"><div class="l-who" style="--n:2" role="group" aria-label="The two budget bills of 2025">
<section class="l-body"><h3>HB 1</h3><p class="l-lbl">The operating budget</p><dl>
<div><dt>What it holds</dt><dd>The amounts each department may spend, the footnotes that govern them, and the estimates of revenue.</dd></div>
<div><dt>Became</dt><dd>Chapter 140, signed June 27, 2025; in force July 1, 2025</dd></div></dl></section>
<section class="l-body"><h3>HB 2</h3><p class="l-lbl">The trailer bill</p><dl>
<div><dt>What it holds</dt><dd>&ldquo;Relative to state fees, funds, revenues, and expenditures&rdquo;: the changes to the law. Its analysis lists 247.</dd></div>
<div><dt>Became</dt><dd>Chapter 141, signed June 27, 2025; most of it in force July 1, 2025, some sections on dates of their own</dd></div></dl></section>
</div></div><div class="l-secb">
<p>HB 1 and HB 2 have been the budget's two numbers in every term since 1993&ndash;1994.
<span class="l-rsa">(This site's bill notes)</span> Buildings and other capital
projects are in a third bill, HB 25, described below.</p>
""")

gf25 = F25["General Fund"]["total"]
sec("Where the Money Comes From", f"""
<p>HB 1 ends with the state's estimates of its unrestricted revenue for each of
the two years, fund by fund: what each tax and fee is expected to bring in.
<span class="l-rsa">(HB 1 of 2025, 140:17)</span> For fiscal 2026 and 2027 together
they come to {bn(S25['biennium_all'])}, in four funds.</p>
{fund_bar()}
<p>The General Fund is estimated at {m(gf25[0])} in fiscal 2026 and {m(gf25[1])}
in 2027. Business taxes are the largest line in both the General Fund and the
Education Fund.</p>
{by_source_chart()}
<p class="l-note">These are estimates, made when the budget passed, not what was
collected. Nor are they all the money the budget spends: HB 1's own footnotes
speak of revenue agencies take in themselves &mdash; transfers from other
agencies, revolving funds, agency income, private and local funds &mdash; and of
federal funds. <span class="l-rsa">(HB 1 of 2025, 140:1.08, footnote I)</span></p>
{need("Every source of money, federal funds included",
      "The total the budget appropriates from every source, and how much of it is federal. That is in section 1 "
      "of HB 1, the department tables, which the bill text on hand does not carry (it begins at section 1.08). "
      "Request 1 on the design's source list.")}
<p class="l-note">One line of the estimates is printed &ldquo;$127,7000,000&rdquo; (the gasoline road
toll, fiscal 2026). The Highway Fund's own printed total, $259,600,000, is
$127,700,000 plus the fund's other two lines, and that is the figure used here.</p>
""")

g_ = REQ["totals"]["GRAND TOTAL APPROPRIATIONS"]
sec("Where It Goes", f"""
<p>The Department of Administrative Services' summary of the agencies' budget
submissions, dated September 28, 2026, gives each agency's fiscal 2026
&ldquo;actuals&rdquo; and fiscal 2027 &ldquo;adjusted authorized&rdquo; figures, under the heading
&ldquo;Total Appropriations &ndash; Total Funds&rdquo;.
<span class="l-rsa">(<a href="{DAS_BUDGET}">DAS summary</a>)</span>
Fiscal 2026 actuals come to {m(g_["FY26 Actuals"])}; fiscal 2027&rsquo;s adjusted
authorized figure to {m(g_["FY27 Adj Auth"])}. Health and Human Services is listed as
ten agencies, from Medicaid Services to the New Hampshire Hospital, which the DAS
crosswalk puts under one department number, 095; they are added together here.</p>
{where_chart()}
<p class="l-note">The statutes define the adjusted authorized budget as &ldquo;the
level of funding for the second year of the current operating budget including
budget footnote adjustments, executive orders, and adjustments by law including
additional appropriations and any changes in laws that affect revenues and expenses
outside of the operating budget&rdquo; <span class="l-rsa">(<a href="/laws/9#s4">RSA 9:4, IV(a)</a>)</span>,
so it is not simply what HB 1 appropriated. The summary does not define
&ldquo;actuals&rdquo;. Nor does it split the money by fund, so it does not say how much is
general fund and how much federal.</p>
{need("What HB 1 appropriated, department by department and fund by fund",
      "Section 1 of HB 1 as enacted. The LBA's budget page lists it as &ldquo;HB 1 Chaptered Final Version (PDF)&rdquo; "
      "and &ldquo;(Excel)&rdquo;. Request 1.")}
""")

sec("Other Directions in HB 1", f"""
<p>Beside the amounts, the act gives directions of its own. Among them, it tells
these parts of government to reduce their appropriations, each section saying
how:</p>
{reductions_table()}
<p>It also abolishes positions it lists by number in eight agencies, from the
Developmental Disabilities Council to the Department of Corrections.
<span class="l-rsa">(HB 1 of 2025, 140:5)</span></p>
""")

cs = CAP["section_total"]
sec("The Capital Budget", f"""
<p>Buildings, equipment and other capital projects are in a third bill.
<a href="bill/2025/hb25">HB 25</a> has been titled &ldquo;making appropriations for capital
improvements&rdquo; in every budget year since 1999, and in 2025 it went to the House
<a href="committee/H20">Public Works and Highways</a> committee and the Senate
<a href="committee/S02">Capital Budget</a> committee. Governor Ayotte signed it on
July 15, 2025, as chapter 159.</p>
<p>Its section 1 appropriates {m(cs)} of state money to {sum(1 for p in CAP["paragraphs"] if p["total"])}
departments and agencies, and section 2 a further $10,000,000 from highway funds for
projects of the Department of Transportation. <span class="l-rsa">(HB 25 of 2025, 159:1 and 159:2)</span>
The Fish and Game Department's three projects, $2,379,000, are each printed
&ldquo;Less Other Funds (Fish and Game Fund)&rdquo;, &ldquo;Net State 0&rdquo;. <span class="l-rsa">(159:1, VI)</span></p>
{capital_chart()}
<p>The operating budget may not use bonded debt to fund operating
appropriations (RSA 9:8-b). The capital budget is funded by borrowing: &ldquo;to provide
funds for the total of the appropriations of state funds made in sections 1 and
2&rdquo;, the act authorizes the state treasurer to borrow up to $171,060,895, and gives
the source of funds as general fund $137,678,945, highway funds $10,000,000 and
other funds $23,381,950. <span class="l-rsa">(HB 25 of 2025, 159:7)</span> The other funds
are the amounts section 1 prints as &ldquo;Less Other Funds&rdquo;: $19,700,000 from a
revolving loan fund, $2,379,000 from the Fish and Game Fund and $1,302,950 from the
Plate Fund.</p>
<p>It has a calendar of its own. Departments send their capital requests to the
commissioner of administrative services by May 1 before the session; the
commissioner sends the Governor a summary by May 31; the Governor holds public
hearings on them by June 30. <span class="l-rsa">(<a href="/laws/9#s3-a">RSA 9:3-a</a>)</span>
For the next budget, the Department of Administrative Services presented its own
requests, {m(143.4e6)} in all, at the Governor's capital budget hearing on June 16, 2026. <span class="l-rsa">(<a href="{DAS_CAP}">DAS presentation</a>)</span>
Its slide of past capital appropriations gives $15,400,000 for 2025, the figure HB 25
printed for the department (paragraph I).</p>
""")

sec("How the Budget Is Made", f"""
<p>RSA 9 sets the calendar, and the docket of 2025 shows it happening.</p>
<ol class="l-time" aria-label="How the budget is made">
<li><p><b>Departments ask.</b> Every department sends the commissioner of
administrative services its request for each year of the coming biennium.
<span class="l-rsa">(<a href="/laws/9#s4">RSA 9:4</a>)</span></p>{mk("By October 1 of the year before")}</li>
<li><p><b>Income is estimated.</b> The commissioner estimates the state's total
income for each year of the biennium, source by source.
<span class="l-rsa">(<a href="/laws/9#s5">RSA 9:5</a>)</span></p>{mk("By October 1 of the year before")}</li>
<li><p><b>A tentative budget.</b> The commissioner puts the requests and the
estimates together, and the director of the budget submits them to the Governor.
<span class="l-rsa">(<a href="/laws/9#s6">RSA 9:6</a>)</span></p>{mk("By November 1")}</li>
<li><p><b>The Governor proposes.</b> The Governor sends the legislature a budget
and a trailer bill. The proposals are the Governor's own judgment.
<span class="l-rsa">(<a href="/laws/9#s2">RSA 9:2</a>, <a href="/laws/9#s2-a">9:2-a</a>,
<a href="/laws/9#s8">9:8</a>)</span> In 2025 HB 1 and HB 2 were introduced
on February 20 and referred to <a href="committee/H34">House Finance</a>.</p>{mk("By February 15")}</li>
<li><p><b>House Finance.</b> A public hearing on March 12, 2025; on April 3 the
committee recommended both bills, amended, by 14 votes to 11.</p>{mk("March and April 2025")}</li>
<li><p><b>The House.</b> On April 10 it passed HB 1 by 192 to 183 and HB 2 by 185
to 175. That was HB 2's 26th roll call of the day; most of the others were on amendments.</p>{mk("April 10, 2025")}</li>
<li><p><b>The Senate.</b> <a href="committee/S07">Senate Finance</a> held its
hearing on May 6 and recommended both, amended, by 6 to 2. On June 5 the Senate
passed HB 1 by 15 to 9 and HB 2 by 14 to 10.</p>{mk("May and June 2025")}</li>
<li><p><b>A committee of conference.</b> The House did not accept the Senate's
amendments and asked for a committee of conference; five representatives and
three senators met on six days from June 12 to June 19.</p>{mk("June 2025")}</li>
<li><p><b>Both chambers vote on its report.</b> On June 26 the House first rejected
the HB 1 report by 182 to 183, reconsidered, and adopted it by 185 to 180; it
adopted the HB 2 report by 184 to 183. The Senate adopted both by 16 to 8.</p>{mk("June 26, 2025")}</li>
<li><p><b>The Governor signs.</b> Governor Ayotte signed both on June 27, 2025, as
chapters 140 and 141, in force July 1.</p>{mk("June 27, 2025")}</li>
</ol>
<p>One rule binds the result. &ldquo;The general court shall not adopt an
operating budget for any fund, or any other legislation which provides for
appropriations, which exceed the state's total estimated revenues from
existing, increased, or new taxes, fees, operating income and other
sources.&rdquo; The operating budget may not use bonded debt to fund operating
appropriations, and projected lapses may be counted in judging whether the
rule is met. <span class="l-rsa">(<a href="/laws/9#s8-b">RSA 9:8-b</a>)</span></p>
{need("The Ways and Means committees' part",
      "The brief names House Ways and Means. Neither 2025 budget bill's docket shows it: both went to Finance in each chamber. "
      "A source that says what Ways and Means does with the revenue estimates is needed before the page says anything. Request 6.")}
""")

items = ["Adds new definitions to the endangered species conservation act.",
         "Requires the department of environmental services to adopt rules and review procedures such that actions of state agencies do not jeopardize the existence or habitats of species protected under the endangered species conservation act.",
         "Establishes an environmental scientist position within the department of environmental services to ensure that state agencies do not jeopardize the existence or habitats of species protected under the endangered species conservation act."]
lis = "".join(f"<li>{t}</li>" for t in items)
sec("What HB 2 Changed", f"""
<p>{hb2}'s analysis, printed with its final text, lists 247 changes to the law,
in the bill's own order. The first &ldquo;adds new definitions to the endangered species
conservation act&rdquo;; the last &ldquo;exempts ambulatory surgical centers, emergency medical
care centers, birthing centers&rdquo; and others from a notice and consent requirement.</p>
<details class="l-fold"><summary>All 247, as the analysis prints them</summary>
<ol class="bud-list">{lis}<li class="bud-more">&hellip; and 244 more, rendered from the analysis at build time</li></ol></details>
<p>On the House floor on April 10, 2025, members offered amendments to HB 2 one
after another: 26 roll calls on it that day, final passage included; in the Senate on June 5, 15, final passage included. Each
is on the bill's page, with how every member voted.</p>
""")

sec("Compared With the Last Budget", f"""
<p>The budget before this one, <a href="bill/2023/hb1">HB 1 of 2023</a>, printed
the same four funds' estimates for fiscal 2024 and 2025.
<span class="l-rsa">(HB 1 of 2023, 106:9)</span> Set side by side, both years of
each added together, in millions of dollars:</p>
{fund_compare_table()}
{compare_chart()}
<p>The largest change is the interest and dividends tax: {m(S23['by_source']['INTEREST AND DIVIDENDS TAX']['total'])}
estimated for 2024&ndash;2025, {m(S25['by_source']['INTEREST AND DIVIDENDS TAX']['total'])} for 2026&ndash;2027,
and nothing at all for fiscal 2027.
In 2023 business taxes were printed as two lines, the business profits tax and the
business enterprise tax, with a subtotal; the subtotal is the figure used here.</p>
<p class="l-note">Both columns are estimates, each made when its budget passed. Neither
is what the state collected, and the change between them is not a change in
spending.</p>
{history_chart()}
<h3>What Came In</h3>
<p>The Legislative Budget Assistant reports what the General and Education Trust
funds actually collected each year, source by source, from the Department of
Administrative Services' monthly revenue reports.
<span class="l-rsa">(<a href="{LBA_REV}">LBA collections</a>)</span>
Against HB 1's estimates for the same two funds:</p>
{collected_chart()}
<p class="l-note">The estimates are as each budget was enacted: fiscal 2024 and 2025
from HB 1 of 2023, fiscal 2026 from HB 1 of 2025. The LBA's figures are on a cash
basis, as its table says, from a revised edition dated through June 30, 2026; HB 1
does not say on what basis its estimates are made, so the two may not be counted
the same way. Fiscal 2026 is the first year of the present budget; 2027 is not
over.</p>
{collections_history()}
""")

sec("Now Under Way: The 2028–2029 Budget", f"""
<div class="bud-mock bud-now-note"><b>Requests, not a budget.</b> What follows is what
the agencies have asked for. The Governor's budget, and then the legislature, decide
what is appropriated.</div>
<p>The next budget, for fiscal 2028 and 2029, is being prepared now. The Department of
Administrative Services' summary of the agencies' submissions, dated September 28,
2026, totals {m(g_["FY28 Request"])} requested for fiscal 2028 and {m(g_["FY29 Request"])}
for fiscal 2029, in total funds, against {m(g_["FY27 Adj Auth"])} adjusted authorized for
fiscal 2027. <span class="l-rsa">(<a href="{DAS_BUDGET}">DAS summary</a>, version 2028B01)</span></p>
<p>The summary shows each request in two columns, &ldquo;efficiency&rdquo; and
&ldquo;prioritized needs&rdquo;, which add up to it. For fiscal 2028 they total
{m(g_["FY28 Efficiency"])} and {m(g_["FY28 Prioritized Needs"])}; for fiscal 2029,
{m(g_["FY29 Efficiency"])} and {m(g_["FY29 Prioritized Needs"])}. The statutes define the
efficiency expenditure request as &ldquo;the cost of providing the services authorized and
funded in the preceding biennium, considering and incorporating changes in the
population and other factors outside the control of the department&hellip;&rdquo;, and ask
it to identify &ldquo;special or problematic needs&rdquo;, which &ldquo;are expected to be few and
prioritized&rdquo;. <span class="l-rsa">(<a href="/laws/9#s4">RSA 9:4, II and IV(f)</a>)</span>
The summary does not say whether its &ldquo;prioritized needs&rdquo; column is those.</p>
<p>The totals include the Legislative Branch, which does not submit a formal budget
at this stage; its figures for fiscal 2028 and 2029 repeat its fiscal 2027 amount,
as the summary's own note says.</p>
{request_chart()}
{need("The detail behind the requests",
      "The FY28&ndash;29 Final Statewide Agency Budget Book, which the owner named and has not yet saved, and a source "
      "for what the summary's &ldquo;prioritized needs&rdquo; column holds.")}
""")

sec("In the Record", f"""
<p><b>The bills:</b> {hb1} and {hb2} of 2025, with every printing, hearing,
committee vote and roll call, and the recordings where there are any. The two before:
<a href="bill/2023/hb1">HB 1</a> and <a href="bill/2023/hb2">HB 2</a> of 2023.</p>
<p><b>The capital budget:</b> <a href="bill/2025/hb25">HB 25 of 2025</a>.</p>
<p><b>The committees:</b> <a href="committee/H34">House Finance</a>,
<a href="committee/S07">Senate Finance</a>, House
<a href="committee/H20">Public Works and Highways</a> and Senate
<a href="committee/S02">Capital Budget</a>, with their meetings.</p>
<p><b>The state's own budget documents:</b> the Legislative Budget Assistant's
<a href="{LBA_PAGE}">FY 2026&ndash;2027 operating budget page</a>, which lists the
Governor's recommended budget, each chamber's version, the committee of conference
documents and the chaptered final version, and the Department of Administrative
Services' <a href="{DAS_BUDGET}">budget pages</a>.</p>
<p><b>The law:</b> <a href="/laws/9">RSA 9, Budget and Appropriations</a>, and the
constitution's <a href="/laws#part2-art18">Article 18</a> and
<a href="/laws#part2-art18-a">Article 18-a</a>.</p>
""")


def slug(t):
    return "s-" + re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


SRC = [
    ("HB 1 of 2025 (chapter 140), the chaptered final version", "bill/2025/hb1",
     "The General Court's database, LegislationText; printing stamped June 30, 2025; read " + READ),
    ("HB 2 of 2025 (chapter 141), the chaptered final version, and its analysis", "bill/2025/hb2",
     "The same; printing stamped July 23, 2025; read " + READ),
    ("HB 1 of 2015, 2017, 2019, 2021 and 2023, final versions", "bill/2023/hb1",
     "This project's saved copies of gc.nh.gov/legislation/; read " + READ),
    ("The docket and roll calls of HB 1 and HB 2, 2025", "bill/2025/hb1",
     "The General Court's day files and the 2025 roll-call files on this site; read " + READ),
    ("RSA 9, Budget and Appropriations; Revolving Funds", "/laws/9",
     "This site's Laws pages, from the statutes as dumped on October 26, 2026"),
    ("The New Hampshire Constitution, Part Second, Articles 18 and 18-a", "/laws#part2-art18-a",
     "nh.gov, read October 17, 2026"),
    ("HB 25 of 2025 (chapter 159), the capital budget, chaptered final version", "bill/2025/hb25",
     "The General Court's database, LegislationText; read " + READ),
    ("LBA: General and Education Trust Fund unrestricted revenue collections, FY 2020&ndash;2026 (revised, as of June 30, 2026)", LBA_REV,
     "Legislative Budget Assistant, PDF; saved by the owner, read " + READ),
    ("LBA: FY 2026&ndash;2027 operating budget page", LBA_PAGE,
     "Legislative Budget Assistant; printed by the owner, read " + READ),
    ("DAS: Summary of Budget Submissions by Agency, total funds (September 28, 2026), and the department crosswalk", DAS_BUDGET,
     "Department of Administrative Services, PDFs; saved by the owner, read " + READ),
    ("DAS: Capital budget presentation, Governor's capital budget hearings, June 16, 2026", DAS_CAP,
     "Department of Administrative Services, PDF; saved by the owner, read " + READ),
]
srcs = "".join(f'<li class="l-doc"><a href="{u}">{t}</a><span class="l-dmeta">{d}</span></li>' for t, u, d in SRC)

art = '<div class="l-art">'
art += ('<div class="bud-mock" role="note"><b>Design mock.</b> Not on the site. Real figures where a source on '
        'hand gives them; <span class="bud-mockneed">dashed boxes</span> are placeholders for sources still needed.</div>')
for t, b in SECTIONS:
    art += f'<section class="l-sec" id="{slug(t)}"><h2 class="l-sech">{t}</h2><div class="l-secb">{b}</div></section>'
art += ('<section class="l-sec" id="sources"><h2 class="l-sech">Where This Comes From</h2><div class="l-secb">'
        f'<ul class="l-docs">{srcs}</ul></div></section>')
art += ('<nav class="l-pager" aria-label="Other topics"><a class="l-pgp" href="learn/governor-and-council">'
        '<span class="l-pgw">Previous Topic</span><span class="l-pgd">The Governor and the Executive Council</span></a>'
        '<a class="l-pgm" href="/resources#learn">All Topics</a><a class="l-pgn" href="learn/the-courts">'
        '<span class="l-pgw">Next Topic</span><span class="l-pgd">The Courts</span></a></nav>')

# ---------------------------------------------------------------- template surgery

page = tpl.replace("learn/county-government", "learn/state-budget")
# The template's version stamp is the County Government page's; a mock is no
# project file and carries none (preflight holds every stamp to versions.json).
page = re.sub(r"<!-- GRANITE_VERSION: [^>]*-->\n?", "", page)
TITLE = "The State Budget"
LEAD = ("Two bills every two years: HB 1 says how much the state may spend, and HB 2 changes the laws "
        "that go with it. Where the money comes from, how the budget is made, and what changed from the last one.")
page = page.replace("<title>County Government", f"<title>{TITLE}")
page = re.sub(r'(<meta (?:name|property)="(?:og:)?description" content=")[^"]*"', lambda mm: mm.group(1) + html.escape(LEAD) + '"', page)
page = page.replace('content="County Government"', f'content="{TITLE}"')
page = page.replace("<h1>County Government</h1>", f"<h1>{TITLE}</h1>")
page = re.sub(r'<p class="l-lead">.*?</p>', f'<p class="l-lead">{html.escape(LEAD)}</p>', page, count=1, flags=re.S)
page = page.replace("&ldquo;County Government.&rdquo;", f"&ldquo;{TITLE}.&rdquo;").replace("<i>County Government</i>", f"<i>{TITLE}</i>")
page = page.replace("title = {County Government}", "title = {" + TITLE + "}").replace("learn-county-government", "learn-state-budget")
toc = "".join(f'<li><a href="learn/state-budget#{slug(t)}">{t}</a></li>' for t, _ in SECTIONS)
toc += '<li><a href="learn/state-budget#sources">Where This Comes From</a></li><li><a href="learn/state-budget#all-topics">The Fourteen Pages</a></li>'
page = re.sub(r'(<nav class="l-otpb" aria-label="On this page"><ol>).*?(</ol>)', lambda mm: mm.group(1) + toc + mm.group(2), page, count=1, flags=re.S)
a, b = page.index('<div class="l-art">'), page.index('<section class="l-sec" id="all-topics">')
page = page[:a] + art + page[b:]
page = page.replace('<li><span aria-current="page">County Government</span></li>', '<li><a href="learn/county-government">County Government</a></li>')
page = page.replace('<li><a href="learn/governor-and-council">The Governor and the Executive Council</a></li>',
                    '<li><a href="learn/governor-and-council">The Governor and the Executive Council</a></li>'
                    f'<li><span aria-current="page">{TITLE}</span></li>')
page = page.replace("The Thirteen Pages", "The Fourteen Pages")
page = page.replace('<html lang="en" data-alt-es="/es/learn/county-government">', '<html lang="en">')
page = page.replace('data-alt-es="/es/learn/state-budget"', "")

CSS = (Path(__file__).parent / "mock.css").read_text()
page = page.replace("</head>", f"<style>\n{CSS}\n</style>\n</head>", 1)
out.write_text(page, encoding="utf-8")
print("wrote", out, len(page))
