// An R2 bucket in memory, answering as the Workers API does: get, put,
// delete and list; an etag that changes on every put; and a put with
// onlyIf.etagMatches that answers null when the object is missing or its
// etag differs. `uploaded` is the test's clock. Every operation is kept in
// `ops`, and `hooks.put` / `hooks.get` run before each, to stand in for a
// second run or a failing store.
export class FakeR2 {
  constructor({ clock = () => Date.now() } = {}) {
    this.objects = new Map();
    this.clock = clock;
    this.ops = [];
    this.hooks = {};
    this.n = 0;
  }

  _meta(key, o) {
    return { key, etag: o.etag, httpEtag: `"${o.etag}"`, uploaded: new Date(o.uploaded), size: o.body.length };
  }

  async get(key) {
    this.ops.push(["get", key]);
    if (this.hooks.get) await this.hooks.get(key);
    const o = this.objects.get(key);
    if (!o) return null;
    return { ...this._meta(key, o), text: async () => o.body, json: async () => JSON.parse(o.body) };
  }

  async put(key, value, opts = {}) {
    this.ops.push(["put", key]);
    if (this.hooks.put) await this.hooks.put(key, value, opts);
    const cur = this.objects.get(key);
    const want = opts.onlyIf && opts.onlyIf.etagMatches;
    if (want !== undefined && (!cur || cur.etag !== want)) return null;
    const o = { body: String(value), etag: `e${++this.n}`, uploaded: +this.clock() };
    this.objects.set(key, o);
    return this._meta(key, o);
  }

  async delete(keys) {
    for (const k of [].concat(keys)) {
      this.ops.push(["delete", k]);
      this.objects.delete(k);
    }
  }

  async list({ prefix = "", cursor, limit = 1000 } = {}) {
    this.ops.push(["list", prefix]);
    const keys = [...this.objects.keys()].filter(k => k.startsWith(prefix)).sort();
    const from = cursor ? Number(cursor) : 0;
    const page = keys.slice(from, from + limit);
    const truncated = from + limit < keys.length;
    return { objects: page.map(k => this._meta(k, this.objects.get(k))), truncated,
             cursor: truncated ? String(from + limit) : undefined, delimitedPrefixes: [] };
  }

  // For the tests: an object's body as JSON, or undefined; and an object put
  // as it would be at a given time.
  read(key) {
    const o = this.objects.get(key);
    return o ? JSON.parse(o.body) : undefined;
  }

  seed(key, value, uploaded = this.clock()) {
    const body = typeof value === "string" ? value : JSON.stringify(value);
    this.objects.set(key, { body, etag: `e${++this.n}`, uploaded: +uploaded });
  }

  puts(prefix = "") {
    return this.ops.filter(([op, k]) => op === "put" && k.startsWith(prefix)).map(([, k]) => k);
  }
}
