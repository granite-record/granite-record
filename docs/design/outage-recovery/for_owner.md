# Keeping the site current when the General Court's website drops out

**What it does.** When the General Court's website drops our connections, the nightly no longer waits for you. For up to 16 days it builds the site from their database, which their IT office said we may use. Meanwhile GitHub tests the website with one request for one small file: **once an hour for the first two days, then every six hours**, never during the night's own run (2:30 to 8:30 a.m. Eastern from 1 November; also Sunday 10:30 p.m. to 1:30 a.m., the weekly's). When the website answers, the refusal clears itself, and the next morning's night fetches as usual.

**Yours to change**: GitHub variables `KNOCK_HOURLY_HOURS` (48 if unset), `KNOCK_EVERY_HOURS` (6) and `KNOCK_DAYS` (16 at most). A nonsense value turns testing off and emails you.

**On 29 October**: two dropped connections at 4:27 a.m., nothing more asked, one email; then one request an hour from 9:47 a.m. Either way the 30 October site is current by about 5:30 a.m.: a normal fetch if the website answered (another machine's test suggests so; a guess), the database if not.

**What hourly testing buys.** After a drop the site is about a day behind either way: the full fetch happens only in the morning, after the night's own test. What changes is a longer outage: the site recovers the morning after the website does, not days later. Hourly tests matter most when GitHub starts the night late, as on six October nights. A morning-only test would cost at most 18 requests, not 96; your choice of hourly stands.

**What still comes to you.** A real block ("forbidden", "too many requests", the firewall's page, a redirect): everything stops at once, the database too. Sixteen days, or a fourth time the website answers a test and then drops the full fetch. Anything met on your laptop or by a test run or recorded before this change, a test whose answer was lost; as now, the new term and held nights.

**The cost, said plainly.** If it is really a block that looks like dropped connections, the blocked machine could get up to **96 single requests over 16 days with the default settings** (about 19 a day for two days, then 4 a day), against 6 under the daily schedule. The settings can raise it: hourly throughout would be about 300. Each is one small file, with our name on it, never retried.

**Your laptop and GitHub are kept from asking at once.**
- GitHub tests hourly only a refusal that reached the bucket before the night's hours ended; one from a late night waits for the next morning.
- **Before checking or clearing a refusal early yourself, set `NIGHT_KNOCK` to `off`** (or disable the "knock" workflow) and wait 15 minutes. netcheck refuses until you confirm it (`--knock-stopped`). Two machines asking at once is how the second block happened.
- The laptop needs nothing meanwhile; after GitHub clears a refusal, its next pull says to run `python3 refusal.py --clear`.

**How you would hear.**
- **A new Healthchecks check, "a refusal is yours,"** emails the moment something becomes yours, and says why.
- Your night check emails the morning it happens, when the site is built again, after seven database nights running, and once if hourly testing stops.
- The Actions tab shows about 25 short "knock" runs a day.

**Your decisions** (approved 29 October, with the hourly change).
1. Clear the refusal standing now: on the laptop, `python3 netcheck.py` (read the table, not the last line), then `python3 src/ops/cloud.py clear-refusal` and `python3 refusal.py --clear`.
2. The night clears a dropped-connection refusal itself.
3. The database while it tests, never during a block.
4. A "503" treated like a drop.
5. **Before it goes live:**
   1. Healthchecks: **Add Check** `a refusal is yours`, Simple, Period **1 day**, Grace **1 day**, your email on. In GitHub, its ping URL as the **repository** secret `HEALTHCHECKS_PERSON_URL`. The morning after going live it should say "up"; "new" means a wrong URL: set `NIGHT_KNOCK` to `off` until fixed.
   2. **New:** a Cloudflare R2 token with **Object Read only** on the kit's bucket, as repository secrets `R2_READ_ACCESS_KEY_ID` and `R2_READ_SECRET_ACCESS_KEY`. Then the hourly look, which runs all day, holds no key that can change the site's sources. Without it only the morning test runs.
6. The safety settings (now also: ask before re-running or cancelling a GitHub run) and the CLAUDE.md paragraph.

**Off switch:** the GitHub variable `NIGHT_KNOCK` set to `off` gives today's behaviour; a refusal being tested becomes yours, with one email. Disabling the "knock" workflow stops only hourly testing.

**When.** It follows the night clock, due in early November. Nothing goes live until you say so.
