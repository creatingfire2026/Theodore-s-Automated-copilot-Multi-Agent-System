const GENESIS_HASH = "0".repeat(64);
const WITNESS_ID = "a7-protected-dissent";
const encoder = new TextEncoder();
const ROW_FIELDS = [
  "seq", "kind", "dissent_id", "target", "reason", "author", "ts",
  "dissent_row_hash", "signature",
];

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
  });
}

function canonical(value) {
  const ordered = Object.fromEntries(Object.keys(value).sort().map((key) => [key, value[key]]));
  return JSON.stringify(ordered);
}

function decodeB64(value) {
  const raw = atob(value);
  return Uint8Array.from(raw, (char) => char.charCodeAt(0));
}

function encodeB64(value) {
  let raw = "";
  for (const byte of new Uint8Array(value)) raw += String.fromCharCode(byte);
  return btoa(raw);
}

async function sha256Hex(bytes) {
  const digest = new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
  return Array.from(digest, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

async function verifyEd25519(publicKeyB64, signatureB64, payload) {
  const key = await crypto.subtle.importKey(
    "raw", decodeB64(publicKeyB64), { name: "Ed25519" }, false, ["verify"],
  );
  return crypto.subtle.verify("Ed25519", key, decodeB64(signatureB64), encoder.encode(canonical(payload)));
}

async function signCheckpoint(checkpoint, env) {
  if (!env.WITNESS_PRIVATE_KEY_PKCS8_B64) throw new Error("witness signing key is not configured");
  const key = await crypto.subtle.importKey(
    "pkcs8", decodeB64(env.WITNESS_PRIVATE_KEY_PKCS8_B64),
    { name: "Ed25519" }, false, ["sign"],
  );
  const signature = await crypto.subtle.sign("Ed25519", key, encoder.encode(canonical(checkpoint)));
  return { checkpoint, signature: encodeB64(signature) };
}

function genesis() {
  return {
    seq: 0,
    head_hash: GENESIS_HASH,
    prev_hash: GENESIS_HASH,
    witness_id: WITNESS_ID,
    ts: "1970-01-01T00:00:00.000Z",
  };
}

async function validateRow(row, current, txn, env) {
  if (!row || typeof row !== "object" || !Number.isSafeInteger(row.seq) || row.seq < 1) {
    throw new Error("malformed row sequence");
  }
  for (const key of [...ROW_FIELDS.filter((key) => key !== "seq"), "prev_hash", "row_hash"]) {
    if (typeof row[key] !== "string") throw new Error("malformed row field: " + key);
  }
  if (row.seq !== current.seq + 1 || row.prev_hash !== current.head_hash) {
    throw new Error("stale or forked witness advancement");
  }
  if (!/^[0-9a-f]{64}$/.test(row.prev_hash) || !/^[0-9a-f]{64}$/.test(row.row_hash)) {
    throw new Error("malformed row hash");
  }
  const rowPayload = Object.fromEntries(ROW_FIELDS.map((key) => [key, row[key]]));
  const material = new Uint8Array([
    ...encoder.encode(canonical(rowPayload)),
    ...encoder.encode(row.prev_hash),
  ]);
  if (await sha256Hex(material) !== row.row_hash) throw new Error("row hash mismatch");

  if (row.kind === "dissent") {
    if (row.author !== "A7" || row.dissent_row_hash !== "") throw new Error("invalid A7 dissent identity");
    if (await txn.get("dissent:" + row.dissent_id)) throw new Error("duplicate dissent ID");
    const payload = {
      kind: "dissent", dissent_id: row.dissent_id, target: row.target,
      reason: row.reason, author: row.author, ts: row.ts,
    };
    if (!await verifyEd25519(env.A7_PUBLIC_KEY_RAW_B64, row.signature, payload)) {
      throw new Error("A7 dissent signature invalid");
    }
    await txn.put("dissent:" + row.dissent_id, row.row_hash);
  } else if (row.kind === "receipt") {
    const dissentHash = await txn.get("dissent:" + row.dissent_id);
    if (!dissentHash || dissentHash !== row.dissent_row_hash) throw new Error("receipt does not reference a witnessed dissent");
    if (await txn.get("cleared:" + row.dissent_row_hash)) throw new Error("duplicate human receipt");
    const payload = {
      kind: "receipt", dissent_id: row.dissent_id, dissent_row_hash: row.dissent_row_hash,
      target: row.target, reason: row.reason, author: row.author, ts: row.ts,
    };
    if (!await verifyEd25519(env.HUMAN_PUBLIC_KEY_RAW_B64, row.signature, payload)) {
      throw new Error("human receipt signature invalid");
    }
    await txn.put("cleared:" + row.dissent_row_hash, true);
  } else {
    throw new Error("unknown witness row kind");
  }
}

export class DissentWitness {
  constructor(state, env) {
    this.state = state;
    this.env = env;
  }

  async fetch(request) {
    const url = new URL(request.url);
    try {
      if (request.method === "GET" && url.pathname === "/checkpoint") {
        let checkpoint = await this.state.storage.get("checkpoint");
        if (!checkpoint) {
          checkpoint = genesis();
          await this.state.storage.put("checkpoint", checkpoint);
        }
        return json(await signCheckpoint(checkpoint, this.env));
      }

      if (request.method === "POST" && url.pathname === "/advance") {
        const body = await request.json();
        const row = body && body.row;
        const checkpoint = await this.state.storage.transaction(async (txn) => {
          const current = (await txn.get("checkpoint")) || genesis();

          // A retry after a lost HTTP response is idempotent, but a conflicting
          // row at the same sequence is never accepted.
          if (row && row.seq === current.seq && row.row_hash === current.head_hash) {
            const saved = await txn.get("row:" + row.seq);
            if (!saved || saved.row_hash !== row.row_hash) throw new Error("conflicting idempotent retry");
            return current;
          }

          await validateRow(row, current, txn, this.env);
          const next = {
            seq: row.seq,
            head_hash: row.row_hash,
            prev_hash: row.prev_hash,
            witness_id: WITNESS_ID,
            ts: new Date().toISOString(),
          };
          await txn.put("row:" + row.seq, row);
          await txn.put("checkpoint", next);
          return next;
        });
        return json(await signCheckpoint(checkpoint, this.env));
      }

      return json({ ok: false, error: "not found" }, 404);
    } catch (error) {
      return json({ ok: false, error: String(error && error.message || "witness failure").slice(0, 200) }, 409);
    }
  }
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    if (!["GET", "POST"].includes(request.method)) return json({ ok: false, error: "method not allowed" }, 405);
    if (!["/v1/checkpoint", "/v1/advance"].includes(url.pathname)) return json({ ok: false, error: "not found" }, 404);
    const id = env.DISSENT_WITNESS.idFromName(WITNESS_ID);
    const stub = env.DISSENT_WITNESS.get(id);
    const body = request.method === "GET" ? undefined : await request.arrayBuffer();
    const internal = new Request("https://dissent-witness.internal" + url.pathname.replace("/v1", ""), {
      method: request.method,
      headers: request.headers,
      body,
    });
    return stub.fetch(internal);
  },
};
