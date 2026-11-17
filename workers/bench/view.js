/*
 * What the page is told after each call (next, judge, undo): the link's role
 * and state, the queues it may judge, the items it holds -- each as the page
 * draws it and nothing more -- the progress of the group being worked on, and
 * how far along every queue is.
 *
 * AN ITEM REACHES THE PAGE AS { ref, queue, card }. Not its key, which says
 * of a tag how the rule attached it; not its kind; not whether it is a
 * calibration item. The page answers by `ref` (store.js readRef).
 */

import { farAlong, next, progress, queueLabels } from "./store.js";

export const forPage = it => ({ ref: it.ref, queue: it.queue, card: it.card });

// `chosen` is a queue's name, or "mix" (every queue the link may judge).
// `first`, an item undo gave back, is put before the rest.
export async function view(db, link, chosen, now, first = null) {
  const want = chosen && chosen !== "mix" ? [chosen] : link.queues;
  let items = link.state === "active" ? await next(db, link, want, now) : [];
  if (first) items = [first, ...items.filter(x => x.ref !== first.ref)];
  const lead = items.find(x => !x.calib && x.grp);
  const p = lead ? await progress(db, lead.grp) : null;
  return {
    role: link.role, state: link.state, queue: chosen && chosen !== "mix" ? chosen : "mix",
    queues: await queueLabels(db, link), items: items.map(forPage),
    progress: p ? { label: p.label, goal: p.goal, done: p.done } : null, far: await farAlong(db),
  };
}

// The queue a request names, or "mix": only one of QUEUES' names is taken.
export function chosenQueue(body, link) {
  const q = body && typeof body.queue === "string" ? body.queue : "mix";
  return link.queues.includes(q) ? q : "mix";
}
