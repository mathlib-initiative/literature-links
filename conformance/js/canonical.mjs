// A reference canonical writer in JavaScript, written from docs/annotations.md
// section 10 and nothing else.  It writes any JSON value; it does not sort
// record arrays, sorted sets or keyed lists (that is `canonicalize` in the
// Python package, and the conformance cases are already-ordered values).
//
//   - object keys sorted by UTF-16 code units (what `<` on strings compares),
//     emitted by this writer, never by JSON.stringify, which moves
//     integer-like keys first;
//   - numbers as ECMAScript Number::toString, which `String(x)` is (RFC 8785);
//     -0 is written 0;
//   - strings escaped as JSON.stringify does;
//   - two-space indent, one member or element per line, ": " after a key,
//     {} and [] for empty containers, LF line ends, a final newline.

/** Compare two strings by UTF-16 code units: the section 10 order. */
export function compareUtf16(a, b) {
  return a < b ? -1 : a > b ? 1 : 0;
}

/** The canonical text of `value`, final newline included. */
export function canonical(value) {
  return emit(value, 0) + "\n";
}

function emit(value, depth) {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("NaN and Infinity are not JSON");
    return Object.is(value, -0) ? "0" : String(value);
  }
  if (typeof value === "string") return JSON.stringify(value);
  const pad = "  ".repeat(depth + 1);
  const close = "  ".repeat(depth);
  if (Array.isArray(value)) {
    if (value.length === 0) return "[]";
    return "[\n" + value.map((v) => pad + emit(v, depth + 1)).join(",\n") + "\n" + close + "]";
  }
  if (typeof value === "object") {
    const keys = Object.keys(value).sort(compareUtf16);
    if (keys.length === 0) return "{}";
    return "{\n" + keys.map((k) => pad + JSON.stringify(k) + ": " + emit(value[k], depth + 1)).join(",\n")
      + "\n" + close + "}";
  }
  throw new TypeError(`${typeof value} is not JSON`);
}
