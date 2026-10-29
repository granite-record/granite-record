# Keeping the site current when the General Court's website drops out

**What it does.** When the General Court's website drops our connections, the nightly no longer waits for you. For up to 16 days it builds the site from their database, which their IT office said we may use any time. It tests the website with one request for one small file: the next morning, then 2, 4 and 7 days later. When the website answers, everything goes back to normal by itself.

**What would have happened on 29 October.**
- **4:27 a.m.** Two dropped connections. As today, nothing more asked, nothing built. One email says what happened and when the test comes.
- **30 October, about 4:25 a.m.** One request for a file the night fetches anyway.
  - If it answers: a normal night, the site current by about 5:30 a.m.
  - If not: the site is built from the database. The website is tried again on 1, 5 and 12 November.
- **So:** the site is one day behind, not behind until you act. Whether the website would have answered is a guess.

**What still comes to you.**
- **A real block:** "forbidden", "too many requests", the firewall's block page, or a redirect, on any night or on the test. Everything stops at once, the database too.
- **A long outage:** four tests unanswered, or 16 days. The site then stops updating until you look, as some parts would be too old.
- **Anything met on your laptop or by a test run,** anything recorded before this change, and, as now, the new term (2 December) and nights held for approval.

If it was really a block, the blocked machine sends at most six single requests, over about two weeks.

**How you would hear.**
- **A new Healthchecks check, "a refusal is yours",** emails the moment something becomes yours, and says why.
- Your night check emails the morning it happens, when the site is built again, and after seven database nights running.
- **Your laptop:** if it pulled the refusal, its own fetching stays stopped until you run `python3 refusal.py --clear` there. Its next pull says so.

**Your idea: let the live updates say when to resume.** Half of it is in, and half can't work.
- **In: frequent light checks decide when the heavy job resumes.** That's the test request above. It's made by the machine that will fetch, just before it fetches, because only that proves anything.
- **In: the other door stays open.** The live updates read the General Court's database, not its website. That same database is what keeps the site current while the website is out.
- **In: on session days,** the live page and live votes keep the day current whatever the night's website does.
- **Can't work:**
  - The live updates never ask the website, so a healthy database doesn't show the website is back.
  - Having them ask it would add a third machine knocking beside the night. Two fetches at once caused the second block.
  - They also sleep outside the session, so on 29 October they would have seen nothing.

**Your decisions.**

1. **Clear the refusal standing now.** It predates this change, so nothing will lift it. *Recommended: yes, today.*
   - On the laptop, run `python3 netcheck.py`. Read the table, not the last line, which counts a "forbidden" as success.
   - Then run `python3 src/ops/cloud.py clear-refusal` and `python3 refusal.py --clear`.
2. **Let the night test and clear a dropped-connection refusal itself.** This changes "only a person clears a refusal", for this one kind. *Recommended: yes.*
3. **Build from the database while the night is testing, 16 days at most.** This changes "carrying on by another door is a person's decision". Never during a block. *Recommended: yes.* If no, it stays stale up to 16 days.
4. **"503 Service Unavailable"** (never yet seen from them): treat it like a dropped connection, but never test before the time the server names; over a week, and it is yours. *Recommended: yes.*
5. **Create the "a refusal is yours" check** in Healthchecks, and save its ping address in GitHub as the secret `HEALTHCHECKS_PERSON_URL`. Until it exists, none of this runs. *Recommended: yes, before it goes live.*
6. **Safety settings:** the assistant asks before clearing the night's refusal or running netcheck; netcheck's last line is fixed; CLAUDE.md gets a new paragraph. *Recommended: yes.*

**Off switch:** set the GitHub variable `NIGHT_KNOCK` to `off` to restore today's behaviour.

**When.** It follows the night clock, due in early November. Nothing goes live until you say so.
