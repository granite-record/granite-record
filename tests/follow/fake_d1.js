// A D1 database for the tests: node:sqlite in memory, with the real schema
// (workers/follow/schema.sql) applied, behind the part of D1's API the
// follow code uses -- prepare, bind, first, all, run, raw, batch, exec.
//
// Faithful where it matters to the guarantees: bind() refuses undefined as D1
// does, batch() is one transaction that rolls back whole, foreign keys are on
// (D1 enforces them), and RETURNING answers rows. failWhen lets a test make a
// statement throw, with whatever message it likes -- including one carrying
// an address, to prove no message reaches a log.

import { DatabaseSync } from "node:sqlite";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const SCHEMA = fileURLToPath(new URL("../../workers/follow/schema.sql", import.meta.url));

export class FakeD1 {
  constructor() {
    this.sql = new DatabaseSync(":memory:");
    this.sql.exec("PRAGMA foreign_keys = ON");
    this.sql.exec(readFileSync(SCHEMA, "utf8"));
    this.prepared = [];          // every statement's text, as written by the code
    this.failWhen = null;        // sql => Error | null
  }

  prepare(sql) {
    this.prepared.push(sql);
    return new FakeStatement(this, sql, []);
  }

  async batch(statements) {
    this.sql.exec("BEGIN");
    try {
      const out = statements.map(s => s._exec());
      this.sql.exec("COMMIT");
      return out;
    } catch (e) {
      this.sql.exec("ROLLBACK");
      throw e;
    }
  }

  async exec(text) {
    this.sql.exec(text);
    return { count: 1, duration: 0 };
  }

  // For the tests' own eyes: every row of a table, and every table.
  rows(table) {
    return this.sql.prepare(`SELECT * FROM ${table}`).all().map(r => ({ ...r }));
  }

  tables() {
    return this.sql.prepare("SELECT name FROM sqlite_master WHERE type = 'table' " +
      "AND name NOT LIKE 'sqlite_%' ORDER BY name").all().map(r => r.name);
  }

  columns(table) {
    return this.sql.prepare(`PRAGMA table_info(${table})`).all().map(r => r.name);
  }

  // Every value in every row of every table, as text.
  everyCell() {
    const out = [];
    for (const t of this.tables())
      for (const r of this.rows(t))
        for (const v of Object.values(r)) if (v !== null) out.push(String(v));
    return out;
  }
}

class FakeStatement {
  constructor(d1, sql, args) {
    this.d1 = d1;
    this.sql = sql;
    this.args = args;
  }

  bind(...args) {
    for (const a of args)
      if (a === undefined) throw new TypeError("D1_TYPE_ERROR: Type 'undefined' not supported");
    return new FakeStatement(this.d1, this.sql,
      args.map(a => (typeof a === "boolean" ? (a ? 1 : 0) : a)));
  }

  _exec() {
    const fail = this.d1.failWhen && this.d1.failWhen(this.sql, this.args);
    if (fail) throw fail;
    const st = this.d1.sql.prepare(this.sql);
    const rowsBack = /^\s*(SELECT|WITH|PRAGMA)\b/i.test(this.sql) || /\bRETURNING\b/i.test(this.sql);
    if (rowsBack) {
      const results = st.all(...this.args).map(r => ({ ...r }));
      return { results, success: true,
               meta: { changes: /\bRETURNING\b/i.test(this.sql) ? results.length : 0 } };
    }
    const r = st.run(...this.args);
    return { results: [], success: true,
             meta: { changes: Number(r.changes), last_row_id: Number(r.lastInsertRowid) } };
  }

  async first(column) {
    const rows = this._exec().results;
    if (!rows.length) return null;
    if (column === undefined) return rows[0];
    if (!(column in rows[0])) throw new Error("D1_COLUMN_NOTFOUND");
    return rows[0][column];
  }

  async all() { return this._exec(); }
  async run() { return this._exec(); }
  async raw() { return this._exec().results.map(r => Object.values(r)); }
}
