// THE NIGHT'S TIMER (the person, 23 October 2026: "I approve the outside
// timer"). GitHub starts the nightly from its cron line, "17 8 * * *", and
// until 18 October it started it within half an hour of 08:17 UTC. From
// 19 October it started it five to seven hours late -- 15:38, 13:34, 13:50,
// 13:49 -- with the cron line unchanged: GitHub's scheduler, not this
// project. A night that late publishes in the afternoon, and it asks the
// General Court outside refusal.NIGHT_WINDOWS, the hours the laptop keeps
// clear so that two machines never ask at once.
//
// So Cloudflare's cron, which keeps time, starts the night instead: at 08:17
// UTC it asks GitHub to run nightly.yml on main exactly as a scheduled night
// runs -- not a dry run, taking the day's data, deployed to the night's
// preview, no new term -- with the box `timer` ticked, which names the run
// "nightly (scheduled, by the timer)". GitHub's own cron stays as the
// fallback: a scheduled run first asks whether the timer has started
// tonight's night, and stands down if it has (nightly.yml, job "started").
// And this asks first whether GitHub has already started one today, on
// time, so the two never both run a night.
//
// It holds one secret, GITHUB_TOKEN: a fine-grained token for this one
// repository with Actions read and write and nothing else, which can start
// and list workflow runs and cannot read or change code. README.md says how
// it is made. Nothing else is stored, sent or kept.

export const REPO = "granite-record/granite-record";
export const WORKFLOW = "nightly.yml";
// The scheduled night's boxes (nightly.yml: FETCH, DRY_RUN, PREVIEW and
// NEW_TERM read them as a schedule's), and `timer`, which says who started it.
export const INPUTS = { dry_run: "false", fetch: "true", preview: "true", new_term: "false",
                        timer: "true" };
const API = "https://api.github.com";
// A dispatch GitHub does not take is asked again, twice, a little apart.
const TRIES = 3, GAP_MS = 20000;

function headers(token) {
  return { Authorization: `Bearer ${token}`, Accept: "application/vnd.github+json",
           "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "graniterecord-night-timer" };
}

// A run of tonight's night already on main today (UTC): a scheduled one GitHub
// started on time, or this timer's own, started by an earlier try.
export function startedToday(runs, day) {
  return (runs || []).find(r => String(r.created_at || "").slice(0, 10) >= day
    && r.head_branch === "main"
    && (r.event === "schedule" || /\(scheduled, by the timer\)/.test(String(r.display_title || ""))));
}

export async function startNight(env, { now = new Date(), fetchImpl = fetch,
                                        wait = ms => new Promise(f => setTimeout(f, ms)) } = {}) {
  if (!env.GITHUB_TOKEN) throw new Error("night-timer: no GITHUB_TOKEN secret, so no night was started");
  const day = now.toISOString().slice(0, 10);
  const runs = `${API}/repos/${REPO}/actions/workflows/${WORKFLOW}/runs?branch=main&per_page=30`
    + `&created=${encodeURIComponent(">=" + day)}`;
  try {
    const r = await fetchImpl(runs, { headers: headers(env.GITHUB_TOKEN) });
    if (r.ok) {
      const seen = startedToday((await r.json()).workflow_runs, day);
      if (seen) return `already started today: run ${seen.id} (${seen.event}), so none started`;
    }
    // A list that cannot be read is no reason to miss a night: the scheduled
    // fallback stands down only for a run it can see, so at worst two run,
    // one after the other (nightly.yml's gc-night).
  } catch (e) { /* as above */ }
  const body = JSON.stringify({ ref: "main", inputs: INPUTS });
  let last = "";
  for (let i = 1; i <= TRIES; i++) {
    try {
      const d = await fetchImpl(`${API}/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`, {
        method: "POST", headers: { ...headers(env.GITHUB_TOKEN), "Content-Type": "application/json" },
        body });
      if (d.status === 204) return `started tonight's night on main (try ${i})`;
      last = `HTTP ${d.status}: ${(await d.text()).slice(0, 300)}`;
      // A refused token or a missing workflow does not get better by asking.
      if (d.status === 401 || d.status === 403 || d.status === 404 || d.status === 422) break;
    } catch (e) { last = String(e && e.message || e); }
    if (i < TRIES) await wait(GAP_MS);
  }
  throw new Error(`night-timer: GitHub did not start the night (${last}). GitHub's own schedule `
    + "is the fallback, and Healthchecks says so if no night starts.");
}

export default {
  async scheduled(event, env, ctx) {
    ctx.waitUntil(startNight(env).then(m => console.log(m)));
  },
  // No address answers anything: the Worker is a timer, and workers_dev is off.
  async fetch() { return new Response("Not found", { status: 404 }); },
};
