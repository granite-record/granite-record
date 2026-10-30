// A fake SQL Server for tests/live/: it speaks TDS 7.4 on the loopback address
// alone -- PRELOGIN, LOGIN7, SQL_BATCH, and replies of nvarchar columns split
// into 4,096-byte packets as a real server splits them -- and keeps what each
// client sent, decoded, for a test to read. Its answers are the test's own: a
// function of the SQL it was sent. It can also misbehave on purpose: answer
// that encryption is required, or leave the encryption option out; refuse the
// login, or accept it with no LOGINACK; answer with an ERROR or a fixed-length
// INT4 column, two result sets, no DONE, or packets of the wrong type; say it
// speaks TDS 7.1; fall silent; or drop the connection halfway through a reply.
// And it holds the client to the packet size: one longer than the size in
// force (4,096 until the login's answer sets another) ends the connection.
//
// nodeConnect() is the client's side of the wire: node's net socket in the
// shape cloudflare:sockets' connect() returns ({readable, writable, opened,
// closed, close}), so workers/live/tds.js is tested as the Worker runs it.
import net from "node:net";

const COLLATION = Buffer.from([0x09, 0x04, 0xd0, 0x00, 0x34]);

const u16 = n => { const b = Buffer.alloc(2); b.writeUInt16LE(n); return b; };
const u32 = n => { const b = Buffer.alloc(4); b.writeUInt32LE(n >>> 0); return b; };
const bvarchar = s => Buffer.concat([Buffer.from([s.length]), Buffer.from(s, "utf16le")]);
const usvarchar = s => Buffer.concat([u16(s.length), Buffer.from(s, "utf16le")]);
const lengthed = (token, body) => Buffer.concat([Buffer.from([token]), u16(body.length), body]);

export function done(status = 0x10, count = 0, token = 0xfd) {
  const b = Buffer.alloc(13);
  b[0] = token;
  b.writeUInt16LE(status, 1);
  b.writeUInt16LE(0xc1, 3);                                   // CurCmd: SELECT
  b.writeBigUInt64LE(BigInt(count), 5);
  return b;
}

export function message(token, { number, message: text, state = 1, cls = 14 }) {
  return lengthed(token, Buffer.concat([u32(number), Buffer.from([state, cls]), usvarchar(text),
                                        bvarchar("FAKE\\SQLEXPRESS"), bvarchar(""), u32(1)]));
}

function envchange(type, now, was) {
  return lengthed(0xe3, Buffer.concat([Buffer.from([type]), bvarchar(now), bvarchar(was)]));
}

function loginack(tds, [major, minor, build]) {
  const v = Buffer.alloc(4);
  v.writeUInt32BE(tds >>> 0);
  return lengthed(0xad, Buffer.concat([Buffer.from([1]), v, bvarchar("Microsoft SQL Server"),
                                       Buffer.from([major, minor, build >> 8, build & 0xff])]));
}

// A result set: columns [{name, type: "nvarchar" | "int4", len}], rows of
// strings (or numbers for int4), null for NULL; NBCROW when `nbc` and a row
// has a NULL in it, otherwise a plain ROW with the NULL as length 0xffff.
// Ended by a DONE of `status` (0x10, the count is good; 0x11, more to come),
// or by none when `done` is false.
export function resultSet(columns, rows, { nbc = true, order = false, done: ends = true, status = 0x10 } = {}) {
  const parts = [Buffer.from([0x81]), u16(columns.length)];
  for (const c of columns) {
    parts.push(u32(0), u16(0x0009));
    if (c.type === "int4") parts.push(Buffer.from([0x38]));
    else parts.push(Buffer.from([0xe7]), u16(c.len === "max" ? 0xffff : (c.len || 100) * 2), COLLATION);
    parts.push(bvarchar(c.name || ""));
  }
  if (order) parts.push(Buffer.from([0xa9]), u16(2), u16(1));
  for (const row of rows) {
    const nulls = nbc && row.some(v => v === null);
    if (nulls) {
      const map = Buffer.alloc(Math.ceil(columns.length / 8));
      row.forEach((v, i) => { if (v === null) map[i >> 3] |= 1 << (i & 7); });
      parts.push(Buffer.from([0xd2]), map);
    } else {
      parts.push(Buffer.from([0xd1]));
    }
    row.forEach((v, i) => {
      if (columns[i].type === "int4") { parts.push(u32(v)); return; }
      if (v === null) { if (!nulls) parts.push(u16(0xffff)); return; }
      const s = Buffer.from(String(v), "utf16le");
      parts.push(u16(s.length), s);
    });
  }
  if (ends) parts.push(done(status, rows.length));
  return Buffer.concat(parts);
}

// Text columns, as the live Worker's casts make every column.
export const text = (...names) => names.map(name => ({ name, type: "nvarchar", len: 400 }));

function packets(payload, size, type = 0x04) {
  const out = [];
  const room = size - 8;
  for (let at = 0, id = 1; at < payload.length || at === 0; at += room, id++) {
    const body = payload.subarray(at, at + room);
    const head = Buffer.alloc(8);
    head[0] = type;
    head[1] = at + room >= payload.length ? 0x01 : 0x00;
    head.writeUInt16BE(8 + body.length, 2);
    head.writeUInt16BE(0x0035, 4);
    head[6] = id & 0xff;
    out.push(head, body);
    if (at + room >= payload.length) break;
  }
  return Buffer.concat(out);
}

export function decodePrelogin(b) {
  const opts = {};
  for (let at = 0; b[at] !== 0xff; at += 5) opts[b[at]] = b.subarray(b.readUInt16BE(at + 1), b.readUInt16BE(at + 1) + b.readUInt16BE(at + 3));
  return { encryption: opts[1]?.[0], options: Object.keys(opts).map(Number) };
}

// LOGIN7, field by field, per MS-TDS 2.2.6.4, the password unscrambled.
export function decodeLogin7(b) {
  const field = i => b.subarray(b.readUInt16LE(36 + i * 4), b.readUInt16LE(36 + i * 4) + b.readUInt16LE(38 + i * 4) * 2);
  const str = i => field(i).toString("utf16le");
  const password = Buffer.from(field(2).map(x => { const y = x ^ 0xa5; return ((y << 4) & 0xf0) | (y >> 4); }));
  return {
    length: b.readUInt32LE(0), bytes: b.length, tds: b.readUInt32LE(4), packet: b.readUInt32LE(8),
    flags: [b[24], b[25], b[26], b[27]], lcid: b.readUInt32LE(32),
    host: str(0), user: str(1), password: password.toString("utf16le"), app: str(3), server: str(4),
    library: str(6), language: str(7), database: str(8),
  };
}

// The fake. Options:
//   encryption  PRELOGIN's answer: 2 not supported (the default), 0 off, 1 on, 3 required,
//               or "none" to leave the encryption option out of the answer
//   tds         LOGINACK's TDS version (0x74000004)
//   loginack    false: accept the login with no LOGINACK in the answer
//   login       (decoded LOGIN7) => null to accept, or [{number, message}] to refuse
//   answer      (sql, n) => {columns, rows, nbc, order, done, sets, packetType}
//               | {error: {number, message}} | {drop: true} | {silent: true}
//               (done: false leaves the DONE out; sets: 2 sends the result set
//               twice; packetType sends the reply in packets of another type)
//   silent      "prelogin" or "login": never answer that message
//   packet      the packet size it splits replies into, and sets at the login (4096)
// `seen.packets` is every packet the client sent, {type, length}; `seen.oversize`
// the lengths of any longer than the size in force, each of which ended its
// connection.
export async function startFakeTds(opts = {}) {
  const seen = { connections: 0, prelogin: [], login7: [], batches: [], afterRefusal: 0, raw: [],
                 packets: [], oversize: [] };
  const sockets = new Set();
  const size = opts.packet || 4096;
  const server = net.createServer(sock => {
    sockets.add(sock);
    sock.on("close", () => sockets.delete(sock));
    sock.on("error", () => {});
    seen.connections++;
    let buf = Buffer.alloc(0);
    let parts = [];
    let refused = false;
    let limit = 4096;                              // until the login's answer sets `size`
    sock.on("data", d => {
      seen.raw.push(Buffer.from(d));
      if (refused) { seen.afterRefusal += d.length; return; }
      buf = Buffer.concat([buf, d]);
      while (buf.length >= 8 && buf.length >= buf.readUInt16BE(2)) {
        const len = buf.readUInt16BE(2);
        const type = buf[0];
        const eom = buf[1] & 0x01;
        seen.packets.push({ type, length: len });
        if (len > limit) { seen.oversize.push(len); sock.destroy(); return; }
        parts.push(buf.subarray(8, len));
        buf = buf.subarray(len);
        if (!eom) continue;
        const body = Buffer.concat(parts);
        parts = [];
        const said = handle(sock, type, body);
        if (said === "logged in") limit = size;
        refused = said === "refused";
        if (refused) { seen.afterRefusal += buf.length; return; }
      }
    });
  });

  function handle(sock, type, body) {
    if (type === 0x12) {
      seen.prelogin.push(decodePrelogin(body));
      if (opts.silent === "prelogin") return;
      const enc = opts.encryption ?? 0x02;
      const data = [[0x00, Buffer.from([15, 0, 0x10, 0x00, 0, 0])], [0x01, Buffer.from([enc === "none" ? 0 : enc])],
                    [0x02, Buffer.from([0])], [0x03, Buffer.alloc(0)], [0x04, Buffer.from([0])]]
        .filter(([t]) => !(t === 0x01 && enc === "none"));
      const head = data.length * 5 + 1;
      let at = head;
      const index = Buffer.alloc(head);
      data.forEach(([t, d], i) => {
        index[i * 5] = t; index.writeUInt16BE(at, i * 5 + 1); index.writeUInt16BE(d.length, i * 5 + 3);
        at += d.length;
      });
      index[head - 1] = 0xff;
      sock.write(packets(Buffer.concat([index, ...data.map(d => d[1])]), size));
      // A server that requires encryption now waits for a TLS handshake; this
      // one counts every byte that comes instead, which must be none.
      return enc === 0x01 || enc === 0x03 ? "refused" : undefined;
    }
    if (type === 0x10) {
      const login = decodeLogin7(body);
      seen.login7.push(login);
      if (opts.silent === "login") return;
      const errors = opts.login ? opts.login(login) : null;
      if (errors && errors.length) {
        sock.write(packets(Buffer.concat([...errors.map(e => message(0xaa, e)), done(0x02, 0)]), size));
        return;
      }
      sock.write(packets(Buffer.concat([
        envchange(1, login.database, "master"),
        message(0xab, { number: 5701, message: `Changed database context to '${login.database}'.`, cls: 0 }),
        envchange(4, String(size), "4096"),
        ...(opts.loginack === false ? [] : [loginack(opts.tds ?? 0x74000004, [15, 0, 4096])]),
        done(0x00, 0),
      ]), size));
      return "logged in";
    }
    if (type === 0x01) {
      const sql = body.subarray(body.readUInt32LE(0)).toString("utf16le");
      // A batch of SET statements, as other drivers send after the login,
      // returns no result set: a real server answers it with a bare DONE.
      if (/^\s*set\s/i.test(sql)) { sock.write(packets(done(0x00, 0), size)); return; }
      seen.batches.push(sql);
      const a = opts.answer ? opts.answer(sql, seen.batches.length) : { columns: text("x"), rows: [["1"]] };
      if (a.silent) return;
      if (a.error) {
        sock.write(packets(Buffer.concat([message(0xaa, a.error), done(0x02, 0)]), size));
        return;
      }
      const set = a.sets === 2 ? Buffer.concat([resultSet(a.columns, a.rows, { ...a, status: 0x11 }),
                                                resultSet(a.columns, a.rows, a)])
        : resultSet(a.columns, a.rows, a);
      const whole = packets(set, size, a.packetType ?? 0x04);
      if (a.drop) { sock.write(whole.subarray(0, Math.min(whole.length - 1, size + 100))); sock.destroy(); return; }
      sock.write(whole);
      return;
    }
    sock.destroy();
  }

  await new Promise(ok => server.listen(0, "127.0.0.1", ok));
  return {
    port: server.address().port,
    seen,
    close: () => new Promise(ok => { for (const s of sockets) s.destroy(); server.close(() => ok()); }),
  };
}

// node's socket in cloudflare:sockets' shape.
export function nodeConnect({ hostname, port }) {
  const sock = net.connect({ host: hostname, port });
  const opened = new Promise((ok, no) => {
    sock.once("connect", () => ok({ remoteAddress: hostname }));
    sock.once("error", no);
  });
  opened.catch(() => {});
  const closed = new Promise(ok => sock.once("close", ok));
  const readable = new ReadableStream({
    start(c) {
      sock.on("data", d => c.enqueue(new Uint8Array(d)));
      const end = () => { try { c.close(); } catch { /* already */ } };
      sock.on("end", end);
      sock.on("close", end);
      sock.on("error", e => { try { c.error(e); } catch { /* already */ } });
    },
    cancel() { sock.destroy(); },
  });
  const writable = new WritableStream({
    write: chunk => new Promise((ok, no) => sock.write(chunk, e => (e ? no(e) : ok()))),
    close() { sock.end(); },
    abort() { sock.destroy(); },
  });
  return { readable, writable, opened, closed, close() { sock.destroy(); return closed; } };
}
