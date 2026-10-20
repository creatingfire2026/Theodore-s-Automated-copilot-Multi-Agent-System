#!/usr/bin/env node
import { readFile } from "node:fs/promises";
import path from "node:path";
import process from "node:process";
import Ajv2020 from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const schemaPath = new URL("./null_application.schema.json", import.meta.url);

function loadJsonl(text) {
  const records = [];
  for (const [index, line] of text.split(/\r?\n/).entries()) {
    if (!line.trim()) {
      continue;
    }
    try {
      const record = JSON.parse(line);
      if (!record || typeof record !== "object" || Array.isArray(record)) {
        throw new Error("top-level JSON value must be an object");
      }
      records.push(record);
    } catch (error) {
      throw new Error(`Invalid JSON on line ${index + 1}: ${error.message}`);
    }
  }
  if (records.length === 0) {
    throw new Error("No JSON records found");
  }
  return records;
}

function normalizeRecords(document) {
  if (Array.isArray(document)) {
    if (document.length === 0) {
      throw new Error("Top-level JSON array must not be empty");
    }
    for (const [index, record] of document.entries()) {
      if (!record || typeof record !== "object" || Array.isArray(record)) {
        throw new Error(`Record ${index + 1}: top-level JSON value must be an object`);
      }
    }
    return document;
  }
  if (!document || typeof document !== "object") {
    throw new Error("Top-level JSON value must be an object or array of objects");
  }
  return [document];
}

export async function validateFile(targetPath) {
  const [schemaRaw, payloadRaw] = await Promise.all([
    readFile(schemaPath, "utf8"),
    readFile(targetPath, "utf8"),
  ]);

  const ajv = new Ajv2020({ allErrors: true, strict: false });
  addFormats(ajv);
  const validate = ajv.compile(JSON.parse(schemaRaw));

  const records =
    path.extname(targetPath) === ".jsonl"
      ? loadJsonl(payloadRaw)
      : normalizeRecords(JSON.parse(payloadRaw));

  const errors = [];
  for (const [index, record] of records.entries()) {
    if (!validate(record)) {
      for (const error of validate.errors ?? []) {
        const instancePath = error.instancePath || "/";
        errors.push(`Record ${index + 1}: ${instancePath} ${error.message}`);
      }
    }
  }

  return {
    valid: errors.length === 0,
    errors,
    recordCount: records.length,
  };
}

async function main(argv) {
  if (argv.length !== 1) {
    console.error("usage: schema_validate.mjs <application.json|ledger.jsonl>");
    return 2;
  }

  try {
    const result = await validateFile(argv[0]);
    if (!result.valid) {
      console.log("INVALID");
      for (const error of result.errors) {
        console.log(`- ${error}`);
      }
      return 1;
    }
    console.log("VALID");
    console.log(`records: ${result.recordCount}`);
    return 0;
  } catch (error) {
    console.log("INVALID");
    console.log(`- ${error.message}`);
    return 1;
  }
}

if (import.meta.url === `file://${process.argv[1]}`) {
  const exitCode = await main(process.argv.slice(2));
  process.exit(exitCode);
}
