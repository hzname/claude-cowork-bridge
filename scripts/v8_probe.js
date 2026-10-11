// v8_probe.js — probe IndexedDB/blob files for V8-serialized values (IndexedDB stores values
// as V8 structured-clone data; blobs under ...indexeddb.blob/).
//
// Usage (run with a runtime whose V8 matches the data's format version —
// e.g. the source app's own Electron binary in node mode):
//   ELECTRON_RUN_AS_NODE=1 "<app>\claude.exe" v8_probe.js <file> [file ...]
// Or with a plain node if it supports the data's format version (node v26.7: v13-v15 only).
// Writes JSON dumps to OUT_DIR (default: <tmp>/v8_probe_out).
// If every file prints "NO v8" or "invalid or unsupported version", the runtime's V8 does not
// match the data — try the app's own runtime; check the header byte pair (ff <ver>) of the file.

const fs = require("fs");
const v8 = require("v8");
const path = require("path");

const OUT = process.env.OUT_DIR || path.join(process.env.TEMP || "/tmp", "v8_probe_out");
try { fs.mkdirSync(OUT, { recursive: true }); } catch (e) {}

console.log("runtime v8:", process.versions.v8, "| node:", process.versions.node, "| electron:", process.versions.electron || "-");

const files = process.argv.slice(2);
if (files.length === 0) {
  console.log("usage: node v8_probe.js <file> [file ...]");
  process.exit(1);
}

let lastErr = "";
function tryDeserialize(buf) {
  for (let off = 0; off <= 96; off++) {
    try {
      return { off, v: v8.deserialize(buf.subarray(off)) };
    } catch (e) {
      if (e && e.message) lastErr = e.message;
    }
  }
  return null;
}

let okCount = 0;
for (const f of files) {
  let buf;
  try {
    buf = fs.readFileSync(f);
  } catch (e) {
    console.log(f, "READ ERR", e.message);
    continue;
  }
  const base = path.basename(f).replace(/[^A-Za-z0-9._-]/g, "_");
  const res = tryDeserialize(buf);
  if (!res) {
    const head = buf.subarray(0, 4).toString("hex");
    console.log(f, "NO v8 deserialize (len " + buf.length + ", head " + head + ", last error: " + lastErr.slice(0, 80) + ")");
    continue;
  }
  okCount++;
  const { off, v } = res;
  let desc;
  try {
    desc = JSON.stringify(v, (k, val) => {
      if (typeof val === "bigint") return val.toString();
      if (val instanceof Map) return { __mapEntries: Array.from(val.entries()).slice(0, 2000) };
      if (val instanceof Set) return { __setEntries: Array.from(val).slice(0, 2000) };
      if (val instanceof ArrayBuffer) return { __bin: val.byteLength };
      if (ArrayBuffer.isView(val)) return { __view: val.constructor.name, __bin: val.byteLength };
      return val;
    });
  } catch (e) {
    desc = "JSON err: " + e.message;
  }
  if (desc.length > 45000000) desc = desc.slice(0, 45000000);
  const outPath = path.join(OUT, base + ".json");
  fs.writeFileSync(outPath, desc);
  console.log(f, "| offset", off, "| ctor", (v && v.constructor && v.constructor.name) || typeof v, "| jsonLen", desc.length, "| saved", outPath);
  try {
    if (v && typeof v === "object") {
      console.log("   shape:", Array.isArray(v) ? "ARRAY len=" + v.length : Object.keys(v).slice(0, 40).join(", "));
    }
  } catch (e) {}
}
console.log("done; deserialized:", okCount, "of", files.length);