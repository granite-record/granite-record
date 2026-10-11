// Rows written straight into the fake database, the way the Functions write
// them: a subscriber with its sealed address and its links' hashes, and
// follows sealed and hashed. For tests that start from a state rather than
// from a sign-up.

import { followHash, linksFor, lookupHash, sealAddress, sealFollow } from "../../workers/follow/address.js";

export async function insertSubscriber(db, env, address, { frequency = "daily",
    confirmedOn = "2026-09-30", lastSentOn = null, sentDate = null, sentBuilt = null,
    follows = [], since = "2026-09-30" } = {}) {
  const h = await lookupHash(env, address);
  const links = await linksFor(env, h, 0);
  const id = await db.prepare("INSERT INTO subscribers (email_hmac, email_enc, frequency, " +
    "confirmed_on, link_gen, manage_hash, unsub_hash, last_sent_on, sent_date, sent_built) " +
    "VALUES (?1, ?2, ?3, ?4, 0, ?5, ?6, ?7, ?8, ?9) RETURNING id")
    .bind(h, await sealAddress(env, address, h), frequency, confirmedOn,
          links.manageHash, links.unsubHash, lastSentOn, sentDate, sentBuilt).first("id");
  for (const key of follows) await insertFollow(db, env, id, h, key, since);
  return { id, h, links };
}

export async function insertFollow(db, env, id, h, key, since = "2026-09-30") {
  await db.prepare("INSERT INTO follows (subscriber_id, follow_hmac, follow_enc, since) " +
    "VALUES (?1, ?2, ?3, ?4)")
    .bind(id, await followHash(env, h, key), await sealFollow(env, key, h), since).run();
}

// Every follow in the database, opened: ["<subscriber id> <kind>:<ref>", ...],
// sorted. The tests' own eyes; nothing in the follow code lists them so.
export async function followKeys(db, env) {
  const { openFollow } = await import("../../workers/follow/address.js");
  const hmacs = new Map(db.rows("subscribers").map(s => [s.id, s.email_hmac]));
  const out = [];
  for (const f of db.rows("follows"))
    out.push(`${f.subscriber_id} ${await openFollow(env, f.follow_enc, hmacs.get(f.subscriber_id))}`);
  return out.sort();
}
