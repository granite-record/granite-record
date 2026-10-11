/*
 * A reader's address, what they follow, and the private links that stand in
 * for a login.
 *
 * WHAT IS KEPT. An address is stored only sealed: AES-GCM under
 * FOLLOW_ADDRESS_KEY, with a fresh nonce each time and the address's lookup
 * hash bound in as additional data, so a sealed address copied onto another
 * row will not open. Beside it is the lookup hash: HMAC-SHA-256 under
 * FOLLOW_LOOKUP_KEY of the address in lower case, which finds a second
 * sign-up of the same address without opening anything. Neither key is in
 * this repository; both are secrets set on Cloudflare (README.md).
 *
 * WHAT IS FOLLOWED IS SEALED TOO. A followed record's key ("bill:2026/HB1442")
 * is kept sealed under the same key, bound to the reader's lookup hash, beside
 * a keyed hash of the pair that finds a duplicate or a removal without
 * opening anything. So the database read without the keys -- in the
 * dashboard, or by anyone holding the account's login -- shows no follow
 * list, and one record followed by two readers shows two unrelated hashes.
 *
 * A LINK IS A TOKEN, AND ONLY ITS HASH IS KEPT. A confirmation link is 32
 * random bytes. The manage and unsubscribe links are an HMAC of the reader's
 * lookup hash and a generation number, under a key derived from
 * FOLLOW_ADDRESS_KEY, so every email can carry the same links without the
 * links being stored: the database holds only each one's SHA-256, and "send
 * me a new link" moves the generation on, which changes both and leaves every
 * earlier one matching nothing. All are 43 characters of base64url, travel
 * after a "#" in an email's links (a browser never sends that part to a
 * server), and are read and posted by the page's own script.
 *
 * Standard library only: Web Crypto, which Workers, Pages Functions and
 * node 24 all have.
 */

const enc = new TextEncoder();
const dec = new TextDecoder();

export class ConfigError extends Error {
  constructor() { super("follow configuration"); this.name = "ConfigError"; }
}

// ---- encodings ----------------------------------------------------------------
export function b64urlEncode(bytes) {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64urlDecode(s) {
  const t = String(s).replace(/-/g, "+").replace(/_/g, "/");
  const bin = atob(t + "=".repeat((4 - (t.length % 4)) % 4));
  return Uint8Array.from(bin, c => c.charCodeAt(0));
}

// A key as a person pastes it: standard base64, perhaps with a newline after.
export function b64Decode(s) {
  const bin = atob(String(s ?? "").replace(/\s+/g, ""));
  return Uint8Array.from(bin, c => c.charCodeAt(0));
}

const hex = buf => [...new Uint8Array(buf)].map(b => b.toString(16).padStart(2, "0")).join("");

// ---- comparing secrets ------------------------------------------------------------
// Constant time over the length of the inputs: every byte is looked at whether
// or not an earlier one differed. Lengths are not secret here (a signature's
// length is fixed by its hash).
export function sameBytes(a, b) {
  if (!(a instanceof Uint8Array) || !(b instanceof Uint8Array)) return false;
  let diff = a.length ^ b.length;
  const n = Math.max(a.length, b.length);
  for (let i = 0; i < n; i++) diff |= (a[i] ?? 0) ^ (b[i] ?? 0);
  return diff === 0;
}

export const sameText = (a, b) => sameBytes(enc.encode(String(a)), enc.encode(String(b)));

// ---- keys -----------------------------------------------------------------------
// Imported once per key string. A key that is missing or is not 32 bytes is a
// ConfigError, which says nothing about the key.
const imported = new Map();

// What keeps the link key apart from every other use of the address key.
// Changing it changes every reader's links at once.
const LINK_INFO = enc.encode("granite-record follow links v1");

async function importKey(b64, usage) {
  const cacheKey = usage + ":" + b64;
  if (imported.has(cacheKey)) return imported.get(cacheKey);
  let raw;
  try { raw = b64Decode(b64); } catch { throw new ConfigError(); }
  if (raw.length !== 32) throw new ConfigError();
  let key;
  if (usage === "aes") {
    key = await crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
  } else if (usage === "hmac") {
    key = await crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  } else {
    // HKDF-SHA-256 (RFC 5869) from the address key's bytes: the sender and
    // the Pages project both hold that key, so the links need no third secret.
    const base = await crypto.subtle.importKey("raw", raw, "HKDF", false, ["deriveKey"]);
    key = await crypto.subtle.deriveKey(
      { name: "HKDF", hash: "SHA-256", salt: new Uint8Array(32), info: LINK_INFO },
      base, { name: "HMAC", hash: "SHA-256", length: 256 }, false, ["sign"]);
  }
  imported.set(cacheKey, key);
  return key;
}

const addressKey = env => {
  if (!env.FOLLOW_ADDRESS_KEY) throw new ConfigError();
  return importKey(String(env.FOLLOW_ADDRESS_KEY).trim(), "aes");
};
const lookupKey = env => {
  if (!env.FOLLOW_LOOKUP_KEY) throw new ConfigError();
  return importKey(String(env.FOLLOW_LOOKUP_KEY).trim(), "hmac");
};
const linkKey = env => {
  if (!env.FOLLOW_ADDRESS_KEY) throw new ConfigError();
  return importKey(String(env.FOLLOW_ADDRESS_KEY).trim(), "link");
};

// Every key this deployment needs present and well formed, or a ConfigError:
// asked before an answer is given, so a missing secret is a 503 and not a
// request that quietly sends nothing.
export async function keysReady(env, { lookup = true } = {}) {
  await addressKey(env);
  await linkKey(env);
  if (lookup) await lookupKey(env);
}

const sign = async (key, text) =>
  new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(text)));

// ---- the address -----------------------------------------------------------------
// What is accepted: an ordinary address of printable ASCII, at most 254
// characters, with a domain of dotted labels and nothing that could end a
// header line. A domain in another script has to be given in its xn-- form.
const LOCAL = /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$/;
const DOMAIN = /^(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z][A-Za-z0-9-]{0,61}[A-Za-z0-9]$/;

export function cleanAddress(raw) {
  if (typeof raw !== "string") return null;
  const s = raw.normalize("NFC").trim();
  if (s.length < 6 || s.length > 254) return null;
  const at = s.indexOf("@");
  if (at < 1 || at !== s.lastIndexOf("@")) return null;
  const local = s.slice(0, at), domain = s.slice(at + 1);
  if (local.length > 64 || domain.length > 253) return null;
  return LOCAL.test(local) && DOMAIN.test(domain) ? s : null;
}

// The lookup hash: one address in any capitalisation is one subscriber.
export async function lookupHash(env, address) {
  return hex(await sign(await lookupKey(env), address.toLowerCase()));
}

// THE MAILBOX, for counting requests and nothing else. One inbox has many
// spellings: "pat+1@" and "pat+2@" reach "pat@" at most providers, and Gmail
// ignores dots and answers to googlemail.com as well. A limit on requests
// keyed on the spelling would let one person send a stranger's inbox as many
// confirmations as they cared to type spellings, so the limit is keyed on
// this instead. It never finds a subscriber: two spellings stay two
// addresses, as their owner typed them.
export function mailboxOf(address) {
  const s = String(address).toLowerCase();
  const at = s.lastIndexOf("@");
  let local = s.slice(0, at), domain = s.slice(at + 1);
  const plus = local.indexOf("+");
  if (plus > 0) local = local.slice(0, plus);
  if (domain === "googlemail.com") domain = "gmail.com";
  if (domain === "gmail.com") local = local.replace(/\./g, "");
  return `${local}@${domain}`;
}

// Each hash under the lookup key but the address's own starts with a label
// and a NUL, which no address can hold, so no two uses can make one hash.
export async function mailboxHash(env, address) {
  return hex(await sign(await lookupKey(env), `mailbox\u0000${mailboxOf(address)}`));
}

// A followed record as one reader follows it: finds a duplicate or a removal
// without opening anything, and differs from reader to reader.
export async function followHash(env, emailHmac, key) {
  return hex(await sign(await lookupKey(env), `follow\u0000${emailHmac}\u0000${key}`));
}

// ---- sealing ---------------------------------------------------------------------
// AES-GCM, a fresh nonce each time, and additional data that binds the sealed
// text to its row and its use: an address under its own lookup hash, a
// followed record under "follow:" and the same hash. A sealed value moved to
// another row, or from one use to the other, will not open.
async function sealText(env, text, ad) {
  const key = await addressKey(env);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: enc.encode(ad) }, key, enc.encode(text));
  return `v1.${b64urlEncode(iv)}.${b64urlEncode(new Uint8Array(ct))}`;
}

async function openText(env, sealed, ad) {
  const [v, iv, ct] = String(sealed).split(".");
  if (v !== "v1" || !iv || !ct) throw new ConfigError();
  const key = await addressKey(env);
  const pt = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: b64urlDecode(iv), additionalData: enc.encode(ad) },
    key, b64urlDecode(ct));
  return dec.decode(pt);
}

export const sealAddress = (env, address, hmac) => sealText(env, address, hmac);
export const openAddress = (env, sealed, hmac) => openText(env, sealed, hmac);
export const sealFollow = (env, key, hmac) => sealText(env, key, `follow:${hmac}`);
export const openFollow = (env, sealed, hmac) => openText(env, sealed, `follow:${hmac}`);

// ---- tokens ------------------------------------------------------------------------
export const TOKEN = /^[A-Za-z0-9_-]{43}$/;

// A confirmation link's token: random, used once.
export function newToken() {
  return b64urlEncode(crypto.getRandomValues(new Uint8Array(32)));
}

export async function hashToken(token) {
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(String(token))));
}

// A reader's manage and unsubscribe links for one generation, and the hashes
// the database keeps of them. One reader and one generation give the same
// links every time, which is how every email carries the same ones.
export async function linksFor(env, emailHmac, gen) {
  const key = await linkKey(env);
  const make = async purpose =>
    b64urlEncode(await sign(key, `${purpose}\u0000${Number(gen)}\u0000${emailHmac}`));
  const manage = await make("manage"), unsub = await make("unsubscribe");
  return { manage, unsub, manageHash: await hashToken(manage), unsubHash: await hashToken(unsub) };
}

// HMAC-SHA-256 under raw key bytes: the webhook's signature (bounce.js).
export async function hmacBytes(keyBytes, message) {
  const key = await crypto.subtle.importKey(
    "raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return sign(key, message);
}
