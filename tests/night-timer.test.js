// The night's timer (workers/night-timer/index.js), against a GitHub that is
// a function: what it sends, when it sends nothing, and what it does with a
// refusal. preflight runs this file (_night_timer).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { INPUTS, REPO, WORKFLOW, startNight, startedToday } from "../workers/night-timer/index.js";

const NOW = new Date("2026-10-24T08:17:03Z");
const env = { GITHUB_TOKEN: "t" };

function github({ runs = [], listStatus = 200, dispatch = [204] } = {}) {
  const asked = [];
  const answers = [...dispatch];
  const fetchImpl = async (url, init = {}) => {
    asked.push({ url: String(url), init });
    if (String(url).includes("/runs?")) {
      return { ok: listStatus === 200, status: listStatus, json: async () => ({ workflow_runs: runs }) };
    }
    const status = answers.length > 1 ? answers.shift() : answers[0];
    return { status, text: async () => (status === 204 ? "" : "refused") };
  };
  return { asked, fetchImpl, wait: async () => {} };
}

test("it starts nightly.yml on main with the scheduled night's boxes and its own", async () => {
  const g = github();
  const said = await startNight(env, { now: NOW, ...g });
  assert.match(said, /started tonight's night/);
  const d = g.asked.find(a => a.url.endsWith("/dispatches"));
  assert.equal(d.url, `https://api.github.com/repos/${REPO}/actions/workflows/${WORKFLOW}/dispatches`);
  assert.equal(d.init.method, "POST");
  assert.equal(d.init.headers.Authorization, "Bearer t");
  const body = JSON.parse(d.init.body);
  assert.equal(body.ref, "main");
  assert.deepEqual(body.inputs, { dry_run: "false", fetch: "true", preview: "true",
                                  new_term: "false", timer: "true" });
  assert.deepEqual(INPUTS, body.inputs);
  // The list it asks first is today's, on main.
  const l = g.asked[0].url;
  assert.match(l, /branch=main/);
  assert.match(l, new RegExp("created=" + encodeURIComponent(">=2026-10-24")));
});

test("it starts nothing when GitHub has already started tonight's night, or it has", async () => {
  for (const run of [
    { id: 1, event: "schedule", head_branch: "main", created_at: "2026-10-24T08:20:00Z",
      display_title: "nightly (scheduled)" },
    { id: 2, event: "workflow_dispatch", head_branch: "main", created_at: "2026-10-24T08:17:01Z",
      display_title: "nightly (scheduled, by the timer)" },
  ]) {
    const g = github({ runs: [run] });
    const said = await startNight(env, { now: NOW, ...g });
    assert.match(said, /already started today/);
    assert.ok(!g.asked.some(a => a.url.endsWith("/dispatches")), "it dispatched a second night");
  }
});

test("a dry run, a run by hand, another branch or yesterday's night is not tonight's", () => {
  const day = "2026-10-24";
  const not = [
    { event: "workflow_dispatch", head_branch: "dev", created_at: "2026-10-24T07:00:00Z",
      display_title: "nightly (dry run)" },
    { event: "workflow_dispatch", head_branch: "main", created_at: "2026-10-24T02:00:00Z",
      display_title: "nightly (by hand, may publish)" },
    { event: "schedule", head_branch: "main", created_at: "2026-10-23T13:49:09Z",
      display_title: "nightly (scheduled)" },
  ];
  assert.equal(startedToday(not, day), undefined);
});

test("a list it cannot read does not cost the night", async () => {
  const g = github({ listStatus: 500 });
  assert.match(await startNight(env, { now: NOW, ...g }), /started tonight's night/);
});

test("a passing failure is asked again; a refused token is not", async () => {
  const flaky = github({ dispatch: [502, 204] });
  assert.match(await startNight(env, { now: NOW, ...flaky }), /try 2/);
  const refused = github({ dispatch: [403] });
  await assert.rejects(startNight(env, { now: NOW, ...refused }), /HTTP 403/);
  assert.equal(refused.asked.filter(a => a.url.endsWith("/dispatches")).length, 1);
});

test("without its secret it says so and starts nothing", async () => {
  const g = github();
  await assert.rejects(startNight({}, { now: NOW, ...g }), /no GITHUB_TOKEN/);
  assert.equal(g.asked.length, 0);
});

test("its cron is the workflow's, and it carries no token", () => {
  // Line endings as a checkout has them: Windows' runner gives CRLF, and a
  // pattern anchored at $ or spanning \n would find nothing there (the dry run
  // of 99b2891, 23 October 2026).
  const read = rel => readFileSync(new URL(rel, import.meta.url), "utf8").replace(/\r\n/g, "\n");
  const toml = read("../workers/night-timer/wrangler.toml");
  const wf = read("../.github/workflows/nightly.yml");
  const mine = toml.match(/^crons = \["([^"]+)"\]$/m)[1];
  const theirs = wf.match(/^\s+- cron: "([^"]+)"$/m)[1];
  assert.equal(mine, theirs, "the timer and the workflow's fallback keep different times");
  assert.doesNotMatch(toml, /token|secret\s*=|ghp_|github_pat_/i);
  // The workflow takes the box the timer ticks, names the run by it, and its
  // fallback stands down for it.
  assert.match(wf, /^      timer:\n        description:/m);
  assert.match(wf, /'\(scheduled, by the timer\)'/);
  assert.match(wf, /needs\.started\.outputs\.by_timer == '0'/);
});
