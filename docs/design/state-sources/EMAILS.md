# Two emails for the owner to send

Drafts, 30 October 2026. They are written for the owner to send from their own
address as a state representative, and to change as they see fit. Text in
[brackets] is for the owner to fill in. No address for any office is given
here, because none is on hand that could be cited; each office's contact page
will have one.

---

## 1. To the Legislative Budget Assistant and the DAS budget office

**To:** the Office of Legislative Budget Assistant; the Department of
Administrative Services, budget office (two separate emails, or one to both)

**Subject:** Could I be sent new budget and revenue documents when they are posted?

> Hello,
>
> I'm [name], state representative for [district]. I also help with Granite
> Record (graniterecord.org), a free public record of the General Court that
> is adding a plain-language page on the state budget.
>
> Could you add me to any list that sends new budget documents and revenue
> reports when they are published? The page cites them directly, and we would
> rather read the documents as you issue them than find out later that one
> has changed.
>
> The ones we use now, or would like to:
>
> - the General and Education Trust Fund revenue collection reports
> - the operating budget as enacted for fiscal 2026-2027, with its department
>   totals
> - the FY28-29 agency budget submissions, the Statewide Agency Budget Book,
>   and the capital budget presentations
> - the Annual Comprehensive Financial Report for fiscal 2025
>
> If there is no list, the name of the person to ask when something new
> comes out would help just as much.
>
> Thank you,
> [name]
> [district, phone]

---

## 2. To the state's web team

**To:** the Department of Information Technology (whoever looks after the
nh.gov agency websites)

**Subject:** A small, identified reader for public nh.gov pages: can it be let through?

> Hello,
>
> I'm [name], state representative for [district]. I help with Granite
> Record (graniterecord.org), a free public record of the General Court. It
> also has plain-language guides to state services: registering to vote,
> vital records, the DMV and others. Every guide links to the agency's own
> page and states only what that page says.
>
> To keep the guides current we would like to check those pages
> automatically. That means about 125 public pages and documents on sos.nh.gov,
> dmv.nh.gov, dhhs.nh.gov, das.nh.gov and the other agency sites, each read at
> most once a week.
>
> Our script identifies itself plainly, as
> "GraniteRecord/1.0 (graniterecord.org; checking a guide against its official
> page)". It asks for one page at a time, a few seconds apart, and never
> retries. The sites refuse it with "Access Denied", which I understand is
> the protection doing its job. We won't disguise the script as a browser to
> get past it. So today I save each page by hand.
>
> Would you be willing to let that reader through, from one address we would
> give you? Or is there a way you would prefer we did this, such as a feed or
> a list of recent changes?
>
> Thank you,
> [name]
> [district, phone]

---

**Notes for the owner**

- The reader's name in email 2 is the one the project's script really sends
  (`src/fetch/other/guide_sources.py`, `AGENT`). So are the spacing, one at a
  time and no retries (the same file's docstring). "About 125" is the
  registry's count of documents a browser reads.
- "From one address" in email 2: the laptop's home address can change.
  Whether to offer it, or a fixed address, is for the web team's answer to
  settle.
