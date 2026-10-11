// The reader's steps, as the Functions see them: sign up, confirm from the
// email, open the manage page. Each goes through the world's call(), so every
// answer is kept for the leak checks.

import { onRequest as signup } from "../../functions/api/follow/signup.js";
import { onRequest as confirm } from "../../functions/api/follow/confirm.js";
import { onRequest as manage } from "../../functions/api/follow/manage.js";
import { onRequest as unsubscribe } from "../../functions/api/follow/unsubscribe.js";
import { onRequest as count } from "../../functions/api/follow/count.js";
import { onRequest as bounce } from "../../functions/api/follow/bounce.js";
import { lastMailTo, postForm, postJson, tokensIn } from "./fakes.js";

export const handlers = { signup, confirm, manage, unsubscribe, count, bounce };

export const signUp = (w, address, kind = "bill", ref = "2026/HB9901", extra = {}) =>
  w.call(signup, postJson("/api/follow/signup",
    { email: address, kind, ref, turnstile: "pass", website: "", ...extra }));

export async function confirmLatest(w, address, opts = {}) {
  const t = tokensIn(lastMailTo(w, address)).confirm;
  return w.call(confirm, postForm("/api/follow/confirm", { t }, opts));
}

export const manageToken = res => (/manage#t=([A-Za-z0-9_-]{43})/.exec(res.headers.location || "") || [])[1];

// Sign up and confirm: a subscriber following one record. Returns the address
// and the manage token the confirmation handed back.
export async function join(w, name, kind = "bill", ref = "2026/HB9901") {
  const address = w.address(name);
  await signUp(w, address, kind, ref);
  const r = await confirmLatest(w, address);
  return { address, manage: manageToken(r), response: r };
}

export const view = (w, t, opts = {}) =>
  w.call(manage, postForm("/api/follow/manage", { t, action: "view" }, opts));

export const act = (w, t, action, fields = {}, opts = {}) =>
  w.call(manage, postForm("/api/follow/manage", { t, action, ...fields }, opts));

export const snapshot = w => Object.fromEntries(w.d1.tables().map(t => [t, w.d1.rows(t)]));
