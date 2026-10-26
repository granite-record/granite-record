/*
 * A minimal client for SQL Server's wire protocol (TDS 7.4, MS-TDS), for the
 * live Worker's reads of the General Court's public SQL database: the three
 * SELECTs in sql.js and nothing else. The live layer's design (26 October
 * 2026), sections 2.1 and 7.1, is what it is held to.
 *
 *   const conn = await open(env, { connect });   // connect: cloudflare:sockets'
 *   const { columns, rows, bytes, ms } = await conn.query(sql);
 *   conn.close();
 *
 * `connect` is passed in rather than imported, so that node's tests can hand
 * it a socket of their own (tests/live/fake_tds.js); the Worker passes
 * cloudflare:sockets' own.
 *
 * WHAT IT REFUSES, so that it fails closed rather than guessing:
 *   - any host but 127.0.0.1 or ::1 unless env.ENV is "production", which only
 *     wrangler.toml's production vars set. The host itself is never in code.
 *   - encryption. A Worker cannot carry TLS inside TDS packets, so PRELOGIN
 *     declares ENCRYPT_NOT_SUP; a server that answers ON or REQ (it requires
 *     encryption) is left at once, BEFORE the login and its password are sent.
 *   - TDS older than 7.2, read from LOGINACK: DONE's row count is sized
 *     differently there.
 *   - every column type but NVARCHAR (0xE7) of a stated length. sql.js casts
 *     every output column to nvarchar(n), so a fixed-length INT4 or DATETIME,
 *     or an nvarchar(max), is an error rather than something to decode.
 *   - a reply larger than 8 MiB, a token it does not know, a reply cut short.
 *
 * EVERY STEP IS BOUNDED. Connecting and logging in get STEP_MS between them,
 * each statement STEP_MS, and none runs past `until`, the run's own deadline
 * (the design gives the SQL part of a run 45 s). A connection that never opens
 * fails at its deadline, not at the platform's.
 *
 * WHAT A TdsError's code means to the caller (the holds are design section 2.6):
 *   guard     the host is not loopback outside production: a configuration slip
 *   connect   no connection, no answer in time, or a login reply it cannot read
 *   encrypt   the server requires encryption: the November test's one no-go
 *   login     the server refused the published login (18456 and the like)
 *   database  error 4060, "Cannot open database": the database, not the
 *             password, so it is not held as a refused login (probe_db.py)
 *   version   the server speaks TDS older than 7.2
 *   query     a statement failed: the server's ERROR, no answer in time, a
 *             dropped connection, or a reply it cannot read
 *   type      a column came as anything but nvarchar(n)
 * After `query` from the server's own ERROR, or after `type`, the reply was
 * read whole and the connection can take the next statement; after a timeout
 * or a drop it is closed, and conn.open says so.
 *
 * LOGIN7 names this reader: application "graniterecord-live", client host
 * "graniterecord.org", so that the General Court's administrators can see who
 * is connected.
 */
import { SQL_LOGIN } from "./live.gen.js";

export const APP_NAME = "graniterecord-live";
export const CLIENT_HOST = "graniterecord.org";
export const STEP_MS = 15000;
const TDS_74 = 0x74000004;
const PACKET = 4096;
const MAX_REPLY = 8 * 1024 * 1024;
const LOOPBACK = new Set(["127.0.0.1", "::1"]);
const ENCRYPTION = { 0: "OFF", 1: "ON", 2: "NOT_SUP", 3: "REQ" };
const TDS_NAMES = { 0x74000004: "7.4", 0x730b0003: "7.3B", 0x730a0003: "7.3A", 0x72090002: "7.2",
                    0x71000001: "7.1", 0x71000000: "7.1", 0x70000000: "7.0" };
const TYPES = { 0x26: "INTN", 0x30: "INT1", 0x34: "INT2", 0x38: "INT4", 0x7f: "INT8", 0x32: "BIT",
                0x3d: "DATETIME", 0x6f: "DATETIMN", 0x28: "DATE", 0x2a: "DATETIME2", 0x6a: "DECIMALN",
                0x6c: "NUMERICN", 0xa7: "varchar", 0xaf: "char", 0xef: "nchar", 0x23: "text", 0x63: "ntext" };
const UTF16 = new TextDecoder("utf-16le");

export class TdsError extends Error {
  constructor(code, message, extra = {}) {
    super(message);
    this.name = "TdsError";
    this.code = code;
    Object.assign(this, extra);
  }
}

// Where to connect, or a guard error before anything is asked.
export function target(env) {
  const hostname = String(env?.SQL_HOST ?? "");
  const port = Number(env?.SQL_PORT);
  if (!hostname || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new TdsError("guard", "SQL_HOST and SQL_PORT are not both set");
  }
  if (!LOOPBACK.has(hostname) && env?.ENV !== "production") {
    throw new TdsError("guard", `${hostname} is not the loopback address, and ENV is not "production": ` +
                                "only wrangler.toml's production vars may name another host");
  }
  return { hostname, port };
}

export async function open(env, { connect, login = SQL_LOGIN, until = Infinity, ms = STEP_MS } = {}) {
  const { hostname, port } = target(env);
  const t0 = Date.now();
  const stop = Math.min(until, t0 + ms);
  const info = { prelogin: null, tds: null, server: null, connect_ms: null, login_ms: null };
  let wire;
  try {
    wire = new Wire(connect({ hostname, port }, { secureTransport: "off", allowHalfOpen: false }));
    await wire.within(wire.socket.opened, stop, "login", "connecting");
    info.connect_ms = Date.now() - t0;
    await wire.send(0x12, prelogin(), stop, "login");
    info.prelogin = readPrelogin((await wire.reply(stop, "login")).body);
    if (info.prelogin.encryption !== "NOT_SUP" && info.prelogin.encryption !== "OFF") {
      throw new TdsError("encrypt", `the server answered encryption ${info.prelogin.encryption}, and this ` +
                                    "reader cannot encrypt inside TDS: it stopped before sending the login");
    }
    await wire.send(0x10, login7({ server: hostname, ...login }), stop, "login");
    const got = parse((await wire.reply(stop, "login")).body, "login");
    const [first] = got.errors;
    if (first) {
      const code = got.errors.some(e => e.number === 4060) ? "database" : "login";
      throw new TdsError(code, `the server refused the login: ${first.number} ${first.message}`,
                         { number: first.number });
    }
    if (!got.ack) throw new TdsError("connect", "the login reply carried no LOGINACK");
    info.tds = TDS_NAMES[got.ack.tds] || `0x${got.ack.tds.toString(16)}`;
    info.server = { program: got.ack.program, version: got.ack.version };
    if (got.ack.tds >>> 24 < 0x72) {
      throw new TdsError("version", `the server speaks TDS ${info.tds}, older than 7.2`);
    }
    if (got.size) wire.resize(got.size);
    info.login_ms = Date.now() - t0 - info.connect_ms;
    return new Connection(wire, info);
  } catch (e) {
    wire?.close();
    const err = e instanceof TdsError ? e : new TdsError("connect", `could not connect: ${e?.message || e}`);
    err.info = info;
    throw err;
  }
}

class Connection {
  constructor(wire, info) { this.wire = wire; this.info = info; }
  get open() { return !this.wire.dead; }
  close() { this.wire.close(); }

  async query(sql, { until = Infinity, ms = STEP_MS } = {}) {
    if (this.wire.dead) throw new TdsError("query", "the connection has closed");
    const t0 = Date.now();
    const stop = Math.min(until, t0 + ms);
    await this.wire.send(0x01, batch(sql), stop, "statement");
    const { body, bytes } = await this.wire.reply(stop, "statement");
    const got = parse(body, "statement");
    if (got.size) this.wire.resize(got.size);
    const [first] = got.errors;
    if (first) {
      throw new TdsError("query", `the server refused the statement: ${first.number} ${first.message}`,
                         { number: first.number, bytes });
    }
    return { columns: got.columns || [], rows: got.rows, bytes, ms: Date.now() - t0 };
  }
}

// ---- the socket: packets out, whole replies in, every wait bounded ----------
class Wire {
  constructor(socket) {
    this.socket = socket;
    this.reader = socket.readable.getReader();
    this.writer = socket.writable.getWriter();
    this.buf = new Uint8Array(0);
    this.size = PACKET;
    this.dead = false;
  }

  resize(n) { if (Number.isInteger(n) && n >= 512 && n <= 32767) this.size = n; }

  close() {
    if (this.dead) return;
    this.dead = true;
    for (const stop of [() => this.reader.cancel(), () => this.socket.close()]) {
      try { Promise.resolve(stop()).catch(() => {}); } catch { /* already closed */ }
    }
  }

  fail(phase, why) {
    this.close();
    return new TdsError(phase === "login" ? "connect" : "query", why);
  }

  within(p, until, phase, doing) {
    const real = Promise.resolve(p).catch(e => { throw this.fail(phase, `${doing}: ${e?.message || e}`); });
    real.catch(() => {});
    let timer;
    const late = new Promise((_, no) => {
      timer = setTimeout(() => no(this.fail(phase, `no answer in time while ${doing}`)),
                         Math.max(0, until - Date.now()));
    });
    return Promise.race([real, late]).finally(() => clearTimeout(timer));
  }

  async send(type, payload, until, phase) {
    const room = this.size - 8;
    const packets = [];
    for (let at = 0, id = 1; at < payload.length; at += room, id++) {
      const body = payload.subarray(at, at + room);
      const p = new Uint8Array(8 + body.length);
      p[0] = type;
      p[1] = at + room >= payload.length ? 0x01 : 0x00;           // end of message
      p[2] = p.length >> 8;
      p[3] = p.length & 0xff;
      p[6] = id & 0xff;
      p.set(body, 8);
      packets.push(p);
    }
    await this.within(this.writer.write(concat(packets)), until, phase, "sending");
  }

  async need(n, until, phase) {
    while (this.buf.length < n) {
      const { value, done } = await this.within(this.reader.read(), until, phase, "waiting for the server");
      if (done) throw this.fail(phase, "the server closed the connection");
      this.buf = this.buf.length ? concat([this.buf, value]) : value;
    }
  }

  take(n) {
    const out = this.buf.subarray(0, n);
    this.buf = this.buf.subarray(n);
    return out;
  }

  async reply(until, phase) {
    const parts = [];
    let bytes = 0;
    for (;;) {
      await this.need(8, until, phase);
      const head = this.take(8);
      const len = (head[2] << 8) | head[3];
      if (head[0] !== 0x04 || len < 8) throw this.fail(phase, `a packet of type ${head[0]}, length ${len}`);
      bytes += len;
      if (bytes > MAX_REPLY) throw this.fail(phase, "a reply larger than 8 MiB");
      await this.need(len - 8, until, phase);
      parts.push(this.take(len - 8));
      if (head[1] & 0x01) return { body: concat(parts), bytes };
    }
  }
}

// ---- what is sent ------------------------------------------------------------
function prelogin() {
  const opts = [[0x00, new Uint8Array(6)],         // VERSION: the client's, none to declare
                [0x01, Uint8Array.of(0x02)],       // ENCRYPTION: ENCRYPT_NOT_SUP
                [0x02, Uint8Array.of(0x00)],       // INSTOPT: the default instance
                [0x03, new Uint8Array(4)],         // THREADID
                [0x04, Uint8Array.of(0x00)]];      // MARS: off
  const head = opts.length * 5 + 1;
  const out = new Uint8Array(head + opts.reduce((n, [, d]) => n + d.length, 0));
  let at = head;
  opts.forEach(([token, data], i) => {
    out.set([token, at >> 8, at & 0xff, data.length >> 8, data.length & 0xff], i * 5);
    out.set(data, at);
    at += data.length;
  });
  out[head - 1] = 0xff;
  return out;
}

function login7({ server, user, password, database }) {
  // HostName, UserName, Password, AppName, ServerName, (extension), CltIntName, Language, Database
  const fields = [CLIENT_HOST, user, password, APP_NAME, server, "", APP_NAME, "", database].map(ucs2);
  fields[2] = fields[2].map(b => (((b << 4) & 0xf0) | (b >> 4)) ^ 0xa5);
  const FIXED = 94;
  const out = new Uint8Array(FIXED + fields.reduce((n, f) => n + f.length, 0));
  const v = new DataView(out.buffer);
  v.setUint32(0, out.length, true);
  v.setUint32(4, TDS_74, true);
  v.setUint32(8, PACKET, true);
  out.set([0xe0, 0x03, 0x00, 0x00], 24);           // option flags 1 and 2, type flags, option flags 3
  v.setUint32(32, 0x0409, true);                   // client LCID
  let at = FIXED;
  fields.forEach((f, i) => {
    v.setUint16(36 + i * 4, at, true);
    v.setUint16(38 + i * 4, f.length / 2, true);
    out.set(f, at);
    at += f.length;
  });
  for (const ib of [78, 82, 86]) v.setUint16(ib, at, true);   // SSPI, AtchDBFile, ChangePassword: empty
  return out;
}

function batch(sql) {
  const text = ucs2(sql);
  const out = new Uint8Array(22 + text.length);
  const v = new DataView(out.buffer);
  v.setUint32(0, 22, true);                        // ALL_HEADERS: one transaction descriptor
  v.setUint32(4, 18, true);
  v.setUint16(8, 2, true);
  v.setUint32(18, 1, true);                        // outstanding requests
  out.set(text, 22);
  return out;
}

// ---- what is read ------------------------------------------------------------
function readPrelogin(body) {
  const r = new Bytes(body, "login");
  const opts = {};
  for (let token = r.u8(); token !== 0xff; token = r.u8()) opts[token] = [r.u16be(), r.u16be()];
  const option = (token, n) => {
    const o = opts[token];
    return o && o[1] >= n && o[0] + o[1] <= body.length ? body.subarray(o[0], o[0] + o[1]) : null;
  };
  const v = option(0x00, 6);
  const e = option(0x01, 1);
  if (!e) throw r.bad("a PRELOGIN answer with no encryption option");
  return { version: v ? `${v[0]}.${v[1]}.${(v[2] << 8) | v[3]}.${(v[4] << 8) | v[5]}` : null,
           encryption: ENCRYPTION[e[0]] || `0x${e[0].toString(16)}` };
}

function parse(body, phase) {
  const r = new Bytes(body, phase);
  const out = { ack: null, size: null, errors: [], columns: null, rows: [], done: false };
  while (r.left() > 0) {
    const token = r.u8();
    if (token === 0x81) {                                         // COLMETADATA
      if (out.columns) throw r.bad("a second result set");
      out.columns = columns(r);
    } else if (token === 0xd1 || token === 0xd2) {                // ROW, NBCROW
      if (!out.columns) throw r.bad("a row before its columns");
      out.rows.push(row(r, out.columns.length, token === 0xd2));
    } else if (token === 0xa9) {                                  // ORDER
      r.skip(r.u16());
    } else if (token === 0x79) {                                  // RETURNSTATUS
      r.skip(4);
    } else if (token === 0xe3) {                                  // ENVCHANGE
      const end = r.end(r.u16());
      if (r.u8() === 4) out.size = Number(r.bvarchar());          // the packet size
      r.at = end;
    } else if (token === 0xaa || token === 0xab) {                // ERROR, INFO
      const end = r.end(r.u16());
      const m = { number: r.u32(), state: r.u8(), class: r.u8(), message: r.usvarchar() };
      r.at = end;
      if (token === 0xaa) out.errors.push(m);
    } else if (token === 0xad) {                                  // LOGINACK
      const end = r.end(r.u16());
      r.skip(1);
      const tds = r.u32be();
      const program = r.bvarchar();
      const [major, minor, hi, lo] = r.bytes(4);
      out.ack = { tds, program, version: `${major}.${minor}.${(hi << 8) | lo}` };
      r.at = end;
    } else if (token === 0xfd || token === 0xfe || token === 0xff) { // DONE, DONEPROC, DONEINPROC
      const status = r.u16();
      r.skip(2);
      r.skip(r.left() >= 8 ? 8 : 4);                              // the row count: 8 bytes from 7.2
      if (token === 0xfd && !(status & 0x01)) out.done = true;
    } else {
      throw r.bad(`token 0x${token.toString(16)}, which this reader does not read`);
    }
  }
  if (!out.done) throw r.bad("a reply that ended without its DONE");
  return out;
}

function columns(r) {
  const n = r.u16();
  const names = [];
  for (let i = 0; n !== 0xffff && i < n; i++) {
    r.skip(6);                                                    // UserType, Flags
    const type = r.u8();
    if (type !== 0xe7) {
      throw new TdsError("type", `column ${i + 1} came as ${TYPES[type] || "type 0x" + type.toString(16)}; ` +
                                 "this reader takes nvarchar(n) alone, so cast it in the SQL");
    }
    if (r.u16() === 0xffff) throw new TdsError("type", `column ${i + 1} came as nvarchar(max); cast it to nvarchar(n)`);
    r.skip(5);                                                    // collation
    names.push(r.bvarchar());
  }
  return names;
}

function row(r, n, nbc) {
  const nulls = nbc ? r.bytes(Math.ceil(n / 8)) : null;
  const out = [];
  for (let i = 0; i < n; i++) {
    if (nulls && nulls[i >> 3] & (1 << (i & 7))) { out.push(null); continue; }
    const len = r.u16();
    out.push(len === 0xffff ? null : r.ucs2(len));
  }
  return out;
}

class Bytes {
  constructor(u8, phase) {
    this.u = u8;
    this.v = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    this.at = 0;
    this.phase = phase;
  }
  left() { return this.u.length - this.at; }
  end(n) { if (this.at + n > this.u.length) throw this.bad("a reply cut short"); return this.at + n; }
  take(n) { const at = this.at; this.at = this.end(n); return at; }
  u8() { return this.u[this.take(1)]; }
  u16() { return this.v.getUint16(this.take(2), true); }
  u16be() { return this.v.getUint16(this.take(2), false); }
  u32() { return this.v.getUint32(this.take(4), true); }
  u32be() { return this.v.getUint32(this.take(4), false); }
  skip(n) { this.take(n); }
  bytes(n) { const at = this.take(n); return this.u.subarray(at, at + n); }
  ucs2(n) { return UTF16.decode(this.bytes(n)); }
  bvarchar() { return this.ucs2(this.u8() * 2); }
  usvarchar() { return this.ucs2(this.u16() * 2); }
  bad(why) {
    return new TdsError(this.phase === "login" ? "connect" : "query", `the server's reply could not be read: ${why}`);
  }
}

function ucs2(s) {
  const out = new Uint8Array(s.length * 2);
  for (let i = 0; i < s.length; i++) {
    out[2 * i] = s.charCodeAt(i) & 0xff;
    out[2 * i + 1] = s.charCodeAt(i) >> 8;
  }
  return out;
}

function concat(parts) {
  const out = new Uint8Array(parts.reduce((n, p) => n + p.length, 0));
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}
