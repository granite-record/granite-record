// One world for a test of the live Worker: a clock the test moves, an R2
// bucket in memory, a YouTube that is a function, and Healthchecks as a list
// of what it was sent. run() is the Worker's own (index.js), given all four.
import "./no_network.js";
import { FakeR2 } from "./fake_r2.js";
import { FakeYouTube, KEY } from "./fake_youtube.js";
import { run } from "../../workers/live/index.js";

export const HC = "https://hc-ping.example/live-test-check";
export const MIN = 60_000;
export const HOUR = 60 * MIN;
export const DAY = 24 * HOUR;
export const T = s => (typeof s === "number" ? s : Date.parse(s));
export const iso = t => new Date(t).toISOString().replace(/\.\d{3}Z$/, "Z");

export function world({ start, key = KEY, healthcheck = HC, control } = {}) {
  const w = { now: T(start), n: 0, pings: [], logs: [] };
  w.clock = () => w.now;
  w.r2 = new FakeR2({ clock: w.clock });
  w.yt = new FakeYouTube({ clock: w.clock });
  w.env = { LIVE: w.r2 };
  if (key) w.env.YOUTUBE_API_KEY = key;
  if (healthcheck) w.env.HEALTHCHECK_URL = healthcheck;
  if (control !== undefined) w.r2.seed("control.json", control);
  w.fetch = async (url, init = {}) => {
    if (String(url).startsWith(HC)) {
      w.pings.push({ url: String(url), body: String(init.body || ""), at: w.now });
      return new Response("OK");
    }
    return w.yt.fetch(url, init);
  };
  // One run at `when` (or now).
  w.runAt = (when, opts = {}) => {
    if (when !== undefined && when !== null) w.now = T(when);
    return run(w.env, { now: w.now, fetchImpl: w.fetch, run: opts.run || `run-${String(++w.n).padStart(6, "0")}`,
                        log: line => w.logs.push(line), ...opts });
  };
  // A run every `step` from `from` up to `to`; each(out, t) after each.
  w.every = async (from, to, each, step = 2 * MIN) => {
    for (let t = T(from); t < T(to); t += step) {
      const out = await w.runAt(t);
      if (each) await each(out, t);
    }
  };
  w.streams = day => w.r2.read(`streams/${day}.json`);
  w.state = () => w.r2.read("state.json");
  w.fails = () => w.pings.filter(p => p.url.endsWith("/fail"));
  return w;
}
