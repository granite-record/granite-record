// schema/session.votes.json, checked by hand: the part of JSON Schema the
// file uses (its description lists it), the same rule as
// src/pages/build_live_session.py's check(). Both run tests/live/
// schema_cases.json (schema.test.js and preflight), so they cannot drift.
import { readFileSync } from "node:fs";

export const SCHEMA = JSON.parse(readFileSync(new URL("../../schema/session.votes.json", import.meta.url), "utf8"));

const is = (v, t) => ({
  object: v !== null && typeof v === "object" && !Array.isArray(v), array: Array.isArray(v),
  string: typeof v === "string", boolean: typeof v === "boolean", null: v === null,
  integer: Number.isInteger(v), number: typeof v === "number" && Number.isFinite(v),
})[t];

// Throws an Error naming the place where `doc` breaks `schema`.
export function check(doc, schema = SCHEMA, root = schema, where = "$") {
  if (schema.$ref) {
    if (!schema.$ref.startsWith("#/$defs/")) throw new Error(`${where}: unknown $ref ${schema.$ref}`);
    return check(doc, root.$defs[schema.$ref.split("/").pop()], root, where);
  }
  if ("const" in schema && doc !== schema.const) throw new Error(`${where}: ${JSON.stringify(doc)} is not ${JSON.stringify(schema.const)}`);
  if (schema.enum && !schema.enum.includes(doc)) throw new Error(`${where}: ${JSON.stringify(doc)} is not one of ${JSON.stringify(schema.enum)}`);
  if (schema.type) {
    const types = [].concat(schema.type);
    if (!types.some(t => is(doc, t))) throw new Error(`${where}: ${JSON.stringify(doc)} is not ${types.join("/")}`);
  }
  if (typeof doc === "string" && schema.pattern && !new RegExp(schema.pattern, "u").test(doc)) {
    throw new Error(`${where}: ${JSON.stringify(doc)} does not match ${schema.pattern}`);
  }
  if (Number.isInteger(doc) && "minimum" in schema && doc < schema.minimum) throw new Error(`${where}: ${doc} is below ${schema.minimum}`);
  if (is(doc, "object")) {
    for (const k of schema.required || []) if (!(k in doc)) throw new Error(`${where}: no ${k}`);
    const props = schema.properties || {};
    const extra = "additionalProperties" in schema ? schema.additionalProperties : true;
    for (const [k, v] of Object.entries(doc)) {
      if (Object.hasOwn(props, k)) check(v, props[k], root, `${where}.${k}`);
      else if (extra === false) throw new Error(`${where}: ${k} is not a field of this shape`);
      else if (extra && typeof extra === "object") check(v, extra, root, `${where}.${k}`);
    }
  }
  if (Array.isArray(doc) && schema.items) doc.forEach((v, i) => check(v, schema.items, root, `${where}[${i}]`));
}
