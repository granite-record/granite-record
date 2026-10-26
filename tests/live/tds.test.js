// The live Worker's TDS client (workers/live/tds.js) against a fake SQL Server
// on the loopback address (fake_tds.js): login, a batch, replies over many
// packets, two statements on one connection, the server's errors, a dropped
// connection, a silent server, forced encryption (stopped before the password
// is sent), the loopback guard. No test reaches anything but 127.0.0.1.
// preflight runs this file (_live_tds).
import { test } from "node:test";
import assert from "node:assert/strict";
import net from "node:net";
import { APP_NAME, CLIENT_HOST, TdsError, open } from "../../workers/live/tds.js";
import { SQL_LOGIN } from "../../workers/live/live.gen.js";
import { nodeConnect, startFakeTds, text } from "./fake_tds.js";

const local = port => ({ SQL_HOST: "127.0.0.1", SQL_PORT: String(port) });

async function withFake(opts, fn) {
  const fake = await startFakeTds(opts);
  try { return await fn(fake); } finally { await fake.close(); }
}

async function refusal(promise) {
  try { await promise; } catch (e) { return e; }
  assert.fail("expected a refusal");
}

test("it logs in with the published login, names itself, and reads a batch", () =>
  withFake({ answer: () => ({ columns: text("a", "b"), rows: [["H", "14"], ["S", "3"]] }) }, async fake => {
    const conn = await open(local(fake.port), { connect: nodeConnect });
    assert.equal(conn.info.prelogin.encryption, "NOT_SUP");
    assert.equal(conn.info.prelogin.version, "15.0.4096.0");
    assert.equal(conn.info.tds, "7.4");
    assert.deepEqual(conn.info.server, { program: "Microsoft SQL Server", version: "15.0.4096" });
    assert.ok(conn.info.connect_ms >= 0 && conn.info.login_ms >= 0);
    const res = await conn.query("SELECT 1");
    conn.close();
    assert.deepEqual(res.columns, ["a", "b"]);
    assert.deepEqual(res.rows, [["H", "14"], ["S", "3"]]);
    assert.ok(res.bytes > 8 && res.ms >= 0);
    assert.deepEqual(fake.seen.batches, ["SELECT 1"]);
    assert.equal(fake.seen.prelogin[0].encryption, 0x02, "PRELOGIN declares ENCRYPT_NOT_SUP");
  }));

test("LOGIN7, decoded field by field, carries the published login and names this reader", () =>
  withFake({}, async fake => {
    (await open(local(fake.port), { connect: nodeConnect })).close();
    const [l] = fake.seen.login7;
    assert.equal(l.length, l.bytes, "the declared length is the payload's");
    assert.equal(l.tds, 0x74000004);
    assert.equal(l.packet, 4096);
    assert.deepEqual(l.flags, [0xe0, 0x03, 0x00, 0x00]);
    assert.equal(l.lcid, 0x0409);
    assert.equal(l.host, CLIENT_HOST);
    assert.equal(l.host, "graniterecord.org");
    assert.equal(l.app, APP_NAME);
    assert.equal(l.app, "graniterecord-live");
    assert.equal(l.library, "graniterecord-live");
    assert.equal(l.server, "127.0.0.1");
    assert.equal(l.language, "");
    assert.deepEqual({ database: l.database, user: l.user, password: l.password }, SQL_LOGIN);
  }));

test("a reply over many 4,096-byte packets, with NBCROW and ORDER, reads whole", () => {
  const rows = Array.from({ length: 3000 }, (_, i) => ["H", String(i), i % 7 ? String(10000 + i) : null, "1"]);
  return withFake({ answer: () => ({ columns: text("b", "s", "m", "v"), rows, order: true }) }, async fake => {
    const conn = await open(local(fake.port), { connect: nodeConnect });
    const res = await conn.query("SELECT ballots");
    conn.close();
    assert.equal(res.rows.length, 3000);
    assert.deepEqual(res.rows, rows);
    assert.ok(res.bytes > 20 * 4096, `${res.bytes} bytes is not many packets`);
  });
});

test("a statement longer than a packet is sent in several, and arrives whole", () =>
  withFake({}, async fake => {
    const sql = `SELECT ${"x".repeat(5000)}`;
    const conn = await open(local(fake.port), { connect: nodeConnect });
    await conn.query(sql);
    conn.close();
    assert.equal(fake.seen.batches[0], sql);
  }));

test("a smaller packet size the server sets is the one the client sends in", () =>
  withFake({ packet: 512, answer: () => ({ columns: text("x"), rows: [["y".repeat(900)]] }) }, async fake => {
    const sql = `SELECT ${"z".repeat(700)}`;
    const conn = await open(local(fake.port), { connect: nodeConnect });
    const res = await conn.query(sql);
    conn.close();
    assert.equal(fake.seen.batches[0], sql);
    assert.equal(res.rows[0][0], "y".repeat(900));
  }));

test("two statements on one connection", () =>
  withFake({ answer: (sql, n) => ({ columns: text("n"), rows: [[String(n)]] }) }, async fake => {
    const conn = await open(local(fake.port), { connect: nodeConnect });
    const a = await conn.query("SELECT 1");
    const b = await conn.query("SELECT 2");
    conn.close();
    assert.deepEqual([a.rows, b.rows], [[["1"]], [["2"]]]);
    assert.equal(fake.seen.connections, 1);
    assert.deepEqual(fake.seen.batches, ["SELECT 1", "SELECT 2"]);
  }));

for (const [enc, name] of [[0x03, "REQ"], [0x01, "ON"]]) {
  test(`encryption ${name} stops the client before LOGIN7: the password is never sent`, () =>
    withFake({ encryption: enc }, async fake => {
      const e = await refusal(open(local(fake.port), { connect: nodeConnect }));
      assert.ok(e instanceof TdsError);
      assert.equal(e.code, "encrypt");
      assert.equal(e.info.prelogin.encryption, name);
      await new Promise(ok => setTimeout(ok, 100));
      assert.equal(fake.seen.login7.length, 0, "no LOGIN7 reached the server");
      assert.equal(fake.seen.afterRefusal, 0, "nothing at all followed the PRELOGIN");
      const sent = Buffer.concat(fake.seen.raw);
      assert.equal(sent.indexOf(Buffer.from(SQL_LOGIN.password, "utf16le")), -1);
      assert.equal(sent.indexOf(Buffer.from(SQL_LOGIN.user, "utf16le")), -1);
    }));
}

test("encryption OFF, against a client that supports none, is no encryption: the login goes ahead", () =>
  withFake({ encryption: 0x00 }, async fake => {
    (await open(local(fake.port), { connect: nodeConnect })).close();
    assert.equal(fake.seen.login7.length, 1);
  }));

test("a refused login is `login`; 4060, the database not the password, is `database`", async () => {
  await withFake({ login: () => [{ number: 18456, message: "Login failed for user 'publicuser'." }] }, async fake => {
    const e = await refusal(open(local(fake.port), { connect: nodeConnect }));
    assert.equal(e.code, "login");
    assert.equal(e.number, 18456);
    assert.match(e.message, /Login failed/);
  });
  await withFake({ login: () => [
    { number: 4060, message: 'Cannot open database "NHLegislatureDB" requested by the login. The login failed.' },
    { number: 18456, message: "Login failed for user 'publicuser'." }] }, async fake => {
    const e = await refusal(open(local(fake.port), { connect: nodeConnect }));
    assert.equal(e.code, "database");
  });
});

test("the server's ERROR is `query`, and the connection takes the next statement", () =>
  withFake({ answer: (sql) => sql === "SELECT bad"
    ? { error: { number: 207, message: "Invalid column name 'Yeas'." } }
    : { columns: text("x"), rows: [["ok"]] } }, async fake => {
    const conn = await open(local(fake.port), { connect: nodeConnect });
    const e = await refusal(conn.query("SELECT bad"));
    assert.equal(e.code, "query");
    assert.equal(e.number, 207);
    assert.ok(conn.open);
    assert.deepEqual((await conn.query("SELECT good")).rows, [["ok"]]);
    conn.close();
  }));

test("a fixed-length INT4 column is `type`, and so is nvarchar(max); neither is guessed at", () =>
  withFake({ answer: (sql) => sql === "SELECT int"
    ? { columns: [{ name: "n", type: "int4" }], rows: [[5]] }
    : sql === "SELECT max" ? { columns: [{ name: "m", type: "nvarchar", len: "max" }], rows: [] }
      : { columns: text("x"), rows: [["after"]] } }, async fake => {
    const conn = await open(local(fake.port), { connect: nodeConnect });
    const e = await refusal(conn.query("SELECT int"));
    assert.equal(e.code, "type");
    assert.match(e.message, /INT4/);
    assert.equal((await refusal(conn.query("SELECT max"))).code, "type");
    assert.deepEqual((await conn.query("SELECT next")).rows, [["after"]], "the reply was read whole");
    conn.close();
  }));

test("LOGINACK older than TDS 7.2 is refused", () =>
  withFake({ tds: 0x71000001 }, async fake => {
    const e = await refusal(open(local(fake.port), { connect: nodeConnect }));
    assert.equal(e.code, "version");
    assert.match(e.message, /7\.1/);
  }));

test("a connection dropped halfway through a reply is `query`, and the connection is closed", () =>
  withFake({ answer: () => ({ columns: text("x"), rows: Array.from({ length: 2000 }, (_, i) => [String(i)]), drop: true }) },
    async fake => {
      const conn = await open(local(fake.port), { connect: nodeConnect });
      const e = await refusal(conn.query("SELECT many"));
      assert.equal(e.code, "query");
      assert.match(e.message, /closed/);
      assert.equal(conn.open, false);
      assert.equal((await refusal(conn.query("SELECT again"))).code, "query");
    }));

test("a server that never answers fails inside the deadline", async () => {
  await withFake({ silent: "prelogin" }, async fake => {
    const t0 = Date.now();
    const e = await refusal(open(local(fake.port), { connect: nodeConnect, ms: 300 }));
    const took = Date.now() - t0;
    assert.equal(e.code, "connect");
    assert.ok(took >= 250 && took < 1500, `${took} ms`);
  });
  await withFake({ answer: () => ({ silent: true }) }, async fake => {
    const conn = await open(local(fake.port), { connect: nodeConnect });
    const t0 = Date.now();
    const e = await refusal(conn.query("SELECT 1", { ms: 300 }));
    const took = Date.now() - t0;
    assert.equal(e.code, "query");
    assert.ok(took >= 250 && took < 1500, `${took} ms`);
    assert.equal(conn.open, false);
  });
});

test("the run's own deadline bounds the login however long a step may take", () =>
  withFake({ silent: "login" }, async fake => {
    const t0 = Date.now();
    const e = await refusal(open(local(fake.port), { connect: nodeConnect, until: t0 + 250 }));
    assert.equal(e.code, "connect");
    assert.ok(Date.now() - t0 < 1500);
    assert.equal(fake.seen.login7.length, 1);
  }));

test("an address that refuses, and one that never opens, each fail inside the deadline", async () => {
  const shut = net.createServer();
  await new Promise(ok => shut.listen(0, "127.0.0.1", ok));
  const port = shut.address().port;
  await new Promise(ok => shut.close(ok));
  const e1 = await refusal(open(local(port), { connect: nodeConnect, ms: 2000 }));
  assert.equal(e1.code, "connect");

  const hanging = () => ({ readable: new ReadableStream(), writable: new WritableStream(),
                           opened: new Promise(() => {}), close() {} });
  const t0 = Date.now();
  const e2 = await refusal(open(local(1433), { connect: hanging, ms: 300 }));
  assert.equal(e2.code, "connect");
  assert.ok(Date.now() - t0 < 1500);
});

test("a host other than loopback is refused without ENV production, before any connect", async () => {
  const asked = [];
  const connect = (where) => { asked.push(where); throw new Error("no network in a test"); };
  for (const env of [{ SQL_HOST: "192.0.2.1", SQL_PORT: "1433" },
                     { SQL_HOST: "192.0.2.1", SQL_PORT: "1433", ENV: "preview" },
                     { SQL_HOST: "localhost", SQL_PORT: "1433" },
                     { SQL_PORT: "1433" }, {}]) {
    const e = await refusal(open(env, { connect }));
    assert.equal(e.code, "guard", JSON.stringify(env));
  }
  assert.deepEqual(asked, [], "connect() was never called");
  // In production the same host is let through to connect(), which this test's refuses.
  const e = await refusal(open({ SQL_HOST: "192.0.2.1", SQL_PORT: "1433", ENV: "production" }, { connect }));
  assert.equal(e.code, "connect");
  assert.deepEqual(asked, [{ hostname: "192.0.2.1", port: 1433 }]);
});
