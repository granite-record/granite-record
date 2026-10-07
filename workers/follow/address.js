/*
 * A reader's address, and the private links that stand in for a login.
 *
 * WHAT IS KEPT. An address is stored only sealed: AES-GCM under
 * FOLLOW_ADDRESS_KEY, with a fresh nonce each time and the address's lookup
 * hash bound in as additional data, so a sealed address copied onto another
 * row will not open. Beside it is the lookup hash: HMAC-SHA-256 under
 * FOLLOW_LOOKUP_KEY of the address in lower case, which finds a second
 * sign-up of the same address without opening anything. Neither key is in
 * this repository; both are secrets set on Cloudflare (README.md).
 *
 * A LINK IS A RANDOM TOKEN, AND ONLY ITS HASH IS KEPT. 32 random bytes,
 * written as 43 characters of base64url, travel in an email and nowhere else;
 * the database holds their SHA-256. A token is put after a "#" in every link,
 * which a browser never sends to a server, so it is in no request address and
 * so in no log line; the page's own script reads it and posts it.
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

async function importKey(b64, usage) {
  const cacheKey = usage + ":" + b64;
  if (imported.has(cacheKey)) return imported.get(cacheKey);
  let raw;
  try { raw = b64Decode(b64); } catch { throw new ConfigError(); }
  if (raw.length !== 32) throw new ConfigError();
  const key = usage === "aes"
    ? await crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"])
    : await crypto.subtle.importKey("raw", raw, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
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
  const key = await lookupKey(env);
  const sig = await crypto.subtle.sign("HMAC", key, enc.encode(address.toLowerCase()));
  return hex(sig);
}

export async function sealAddress(env, address, hmac) {
  const key = await addressKey(env);
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv, additionalData: enc.encode(hmac) }, key, enc.encode(address));
  return `v1.${b64urlEncode(iv)}.${b64urlEncode(new Uint8Array(ct))}`;
}

export async function openAddress(env, sealed, hmac) {
  const [v, iv, ct] = String(sealed).split(".");
  if (v !== "v1" || !iv || !ct) throw new ConfigError();
  const key = await addressKey(env);
  const pt = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: b64urlDecode(iv), additionalData: enc.encode(hmac) },
    key, b64urlDecode(ct));
  return dec.decode(pt);
}

// ---- tokens ------------------------------------------------------------------------
export const TOKEN = /^[A-Za-z0-9_-]{43}$/;

export function newToken() {
  return b64urlEncode(crypto.getRandomValues(new Uint8Array(32)));
}

export async function hashToken(token) {
  return hex(await crypto.subtle.digest("SHA-256", enc.encode(String(token))));
}

// HMAC-SHA-256 under raw key bytes: the webhook's signature (bounce.js).
export async function hmacBytes(keyBytes, message) {
  const key = await crypto.subtle.importKey(
    "raw", keyBytes, { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(message)));
}
