import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { validateFile } from "../schema_validate.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const fixturesDir = path.join(__dirname, "fixtures");
const validatorPath = path.join(__dirname, "..", "null_validate.py");

const structuralValidFixtures = [
  ["valid", "access_blind_spot.json"],
  ["valid", "permission_changed.json"],
  ["valid", "verification_failure.json"],
  ["valid", "ledger.jsonl"],
  ["invalid", "access_blind_spot_claims_verified.json"],
  ["invalid", "stale_record_hash.json"],
  ["invalid", "broken_chain.jsonl"],
];

const structuralInvalidFixtures = [["invalid", "structural_missing_schema_version.json"]];

const semanticValidFixtures = [
  ["valid", "access_blind_spot.json"],
  ["valid", "permission_changed.json"],
  ["valid", "verification_failure.json"],
  ["valid", "ledger.jsonl"],
];

const semanticInvalidFixtures = [
  [
    ["invalid", "access_blind_spot_claims_verified.json"],
    "ACCESS_BLIND_SPOT cannot claim verification success",
  ],
  [["invalid", "stale_record_hash.json"], "record_hash mismatch"],
  [["invalid", "broken_chain.jsonl"], "previous_record_hash mismatch"],
];

test("Ajv 2020-12 accepts structurally valid fixtures", async () => {
  for (const [category, name] of structuralValidFixtures) {
    const targetPath = path.join(fixturesDir, category, name);
    const result = await validateFile(targetPath);
    assert.equal(result.valid, true, `${name} should pass schema validation`);
  }
});

test("Ajv 2020-12 rejects structurally invalid fixtures", async () => {
  for (const [category, name] of structuralInvalidFixtures) {
    const targetPath = path.join(fixturesDir, category, name);
    const result = await validateFile(targetPath);
    assert.equal(result.valid, false, `${name} should fail schema validation`);
    assert.match(result.errors.join("\n"), /required property 'schema_version'/);
  }
});

test("semantic validator accepts valid fixtures and ledger continuity", () => {
  for (const [category, name] of semanticValidFixtures) {
    const targetPath = path.join(fixturesDir, category, name);
    const result = spawnSync("python", [validatorPath, targetPath], {
      encoding: "utf8",
    });
    assert.equal(result.status, 0, result.stdout || result.stderr);
    assert.match(result.stdout, /^VALID/m);
  }
});

test("semantic validator rejects invalid semantic fixtures", () => {
  for (const [[category, name], expectedMessage] of semanticInvalidFixtures) {
    const targetPath = path.join(fixturesDir, category, name);
    const result = spawnSync("python", [validatorPath, targetPath], {
      encoding: "utf8",
    });
    assert.notEqual(result.status, 0, `${name} should fail semantic validation`);
    assert.match(result.stdout, /^INVALID/m);
    assert.match(result.stdout, new RegExp(expectedMessage.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")));
  }
});
