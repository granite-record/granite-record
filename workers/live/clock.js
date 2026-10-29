/*
 * When the live Worker asks YouTube, on New Hampshire's clock.
 *
 * The cron runs every 2 minutes, all day, every day, and decides nothing: each
 * run asks youtubeDue() what is due now, from the times state.json keeps of the
 * last look, and does that and nothing else. A run with nothing due writes
 * nothing (index.js).
 *
 *   In the window, weekdays 07:00 to 20:00 New Hampshire time: every run reads
 *   both uploads playlists and asks after what is new, live or due today
 *   (discovery); the search backstop every 30 minutes; and the first run of
 *   the day re-asks every upcoming id kept (refresh). Every stream start on
 *   record, 2020 to 2026, fell inside the window.
 *   Outside it, weekends included: discovery every 30 minutes, and ids still
 *   live every 10 minutes (nothing when none is), so an evening or weekend
 *   stream is followed until it ends.
 *
 * Each interval is counted from the last look, not from the clock face, so a
 * run that was missed or held is made up at the next one, and a day of 23 or
 * 25 hours (the changes of 14 March and 7 November 2027) neither skips nor
 * doubles a look. SLACK lets a cron run a few seconds early count as on time.
 *
 * NEW HAMPSHIRE'S CLOCK is workers/follow/common.js's nhClock, imported rather
 * than copied: the IANA zone carries the daylight-saving rule.
 */
import { addDays, nhClock } from "../follow/common.js";
import { NIGHT_WINDOWS } from "./live.gen.js";

export const MINUTE = 60_000;
export const HOUR = 60 * MINUTE;
export const DAY = 24 * HOUR;

// Weekdays, New Hampshire hours [from, to).
export const WINDOW = { from: 7, to: 20 };
export const EVERY = {
  window: 2 * MINUTE,     // discovery, in the window: every run
  outside: 30 * MINUTE,   // discovery, outside it and at weekends
  live: 10 * MINUTE,      // ids still live, outside the window
  search: 30 * MINUTE,    // the search backstop, in the window only
};
export const SLACK = MINUTE;
// The cron's period: */2 in wrangler.toml's [env.production.triggers].
export const STEP = 2 * MINUTE;

export const NEW_YORK = "America/New_York";
// YouTube's quota resets at midnight Pacific.
export const PACIFIC = "America/Los_Angeles";

const WEEKEND = new Set(["Sat", "Sun"]);

// New Hampshire's date, hour, minute and weekday, and whether it is a weekend.
export function nh(now) {
  const c = nhClock(new Date(+now));
  return { ...c, weekend: WEEKEND.has(c.weekday) };
}

export const iso = t => new Date(+t).toISOString().replace(/\.\d{3}Z$/, "Z");

// Milliseconds from an ISO time to now; Infinity when there is none.
export function since(when, now) {
  const t = when ? Date.parse(when) : NaN;
  return Number.isFinite(t) ? +now - t : Infinity;
}

export function inWindow(now) {
  const c = nh(now);
  return !c.weekend && c.hour >= WINDOW.from && c.hour < WINDOW.to;
}

// What the YouTube half is due to do now, from state.json's `yt`:
//   discover  read both uploads playlists, and ask after the new, the live and
//             the upcoming due from two hours ago to the end of today
//   live      ask after the ids still live (outside the window)
//   search    the search backstop on both channels (in the window)
//   refresh   widen discovery to every upcoming id kept (once a day)
// and nothing at all while a hold stands (quota, or a refused key).
export function youtubeDue(now, yt = {}) {
  const t = +now;
  if (yt.held && Date.parse(yt.held.until) > t) {
    return { any: false, discover: false, live: false, search: false, refresh: false, held: yt.held };
  }
  const win = inWindow(now);
  const discover = since(yt.discovery, t) >= (win ? EVERY.window : EVERY.outside) - SLACK;
  const live = !discover && (yt.live || []).length > 0 && since(yt.looked, t) >= EVERY.live - SLACK;
  const searchHeld = Boolean(yt.search_held) && Date.parse(yt.search_held) > t;
  const search = win && !searchHeld && since(yt.search, t) >= EVERY.search - SLACK;
  const refresh = win && discover && yt.refreshed !== nh(now).date;
  return { any: discover || live || search, discover, live, search, refresh, held: null };
}

// When the Worker will next look at YouTube, as youtubeDue() itself would
// answer at each run of the cron from here: the streams file's next_check, by
// which the page tells a fresh file from a stale one.
export function nextLook(now, yt) {
  for (let t = +now + STEP; t <= +now + DAY; t += STEP) {
    if (youtubeDue(new Date(t), yt).any) return new Date(t);
  }
  return new Date(+now + DAY);
}

const ZONED = new Map();
function zoned(tz, t) {
  if (tz === NEW_YORK) return nhClock(new Date(t));
  if (!ZONED.has(tz)) {
    ZONED.set(tz, new Intl.DateTimeFormat("en-US", {
      timeZone: tz, hourCycle: "h23", year: "numeric", month: "2-digit", day: "2-digit",
      hour: "2-digit", minute: "2-digit" }));
  }
  const p = Object.fromEntries(ZONED.get(tz).formatToParts(new Date(t)).map(x => [x.type, x.value]));
  return { date: `${p.year}-${p.month}-${p.day}`, hour: Number(p.hour) % 24, minute: Number(p.minute) };
}

// The first midnight in `tz` after `now`: where a hold ends (midnight Pacific
// for YouTube's quota, New Hampshire's for the rest of the day).
export function midnightAfter(now, tz) {
  const next = addDays(zoned(tz, +now).date, 1);
  const [y, m, d] = next.split("-").map(Number);
  for (let h = 0; h < 24; h++) {
    const t = Date.UTC(y, m - 1, d, h);
    const z = zoned(tz, t);
    if (z.date === next && z.hour === 0 && z.minute === 0) return new Date(t);
  }
  throw new Error(`no midnight found in ${tz} on ${next}`);
}

// The night's window (refusal.NIGHT_WINDOWS, through live.gen.js) that `now`
// falls in, as {start, end}, or null. The YouTube half asks YouTube only and
// keeps no window; the database half (a later branch) keeps out of these.
export function nightWindow(now) {
  const t = +now;
  const midnight = Date.UTC(new Date(t).getUTCFullYear(), new Date(t).getUTCMonth(),
                            new Date(t).getUTCDate());
  for (let k = -1; k <= 1; k++) {
    const day = midnight + k * DAY;
    const weekday = (new Date(day).getUTCDay() + 6) % 7;    // refusal.py's: 0 is Monday
    for (const [wd, [sh, sm], [eh, em]] of NIGHT_WINDOWS) {
      if (wd !== null && wd !== weekday) continue;
      const start = day + (sh * 60 + sm) * MINUTE;
      let end = day + (eh * 60 + em) * MINUTE;
      if (end <= start) end += DAY;
      if (start <= t && t < end) return { start: new Date(start), end: new Date(end) };
    }
  }
  return null;
}
