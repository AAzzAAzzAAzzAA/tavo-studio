#!/usr/bin/env node

// Short-lived prompt-field EJS worker for tavo_prompt_lab.py.
// It intentionally exposes only Tavo's documented prompt helpers and JSON state.

import vm from "node:vm";

const MAX_STDIN_BYTES = 20 * 1024 * 1024;
const MAX_ERROR_CHARS = 512;
const FORBIDDEN_CODE = [
  /\b__tavoLab[A-Za-z0-9_]*/,
  /\b(?:process|require|module|exports|globalThis|Function|eval|WebAssembly|fetch|XMLHttpRequest|WebSocket|EventSource|Deno|Bun)\s*(?:[.([])/,
  /\bimport\s*(?:\(|[\s{*])/,
  /(?:^|[.\[])\s*(?:constructor|__proto__|prototype)\b/,
];

function fail(kind, message) {
  const safe = String(message || kind)
    .replace(/[\r\n\t]+/g, " ")
    .slice(0, MAX_ERROR_CHARS);
  process.stdout.write(JSON.stringify({ ok: false, error: { kind, message: safe } }));
}

function validateRequest(value) {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error("request must be an object");
  }
  if (typeof value.template !== "string") {
    throw new Error("template must be a string");
  }
  if (!value.state || typeof value.state !== "object" || Array.isArray(value.state)) {
    throw new Error("state must be an object");
  }
  for (const scope of ["chat", "global"]) {
    const item = value.state[scope];
    if (!item || typeof item !== "object" || Array.isArray(item)) {
      throw new Error(`state.${scope} must be an object`);
    }
  }
  if (!value.constants || typeof value.constants !== "object" || Array.isArray(value.constants)) {
    throw new Error("constants must be an object");
  }
  if (!Number.isInteger(value.timeoutMs) || value.timeoutMs < 1 || value.timeoutMs > 2000) {
    throw new Error("timeoutMs must be an integer from 1 to 2000");
  }
  if (!Number.isInteger(value.maxOutputChars) || value.maxOutputChars < 1) {
    throw new Error("maxOutputChars must be a positive integer");
  }
  if (!Number.isInteger(value.maxTraceItems) || value.maxTraceItems < 1) {
    throw new Error("maxTraceItems must be a positive integer");
  }
}

function policyCheck(code) {
  for (const pattern of FORBIDDEN_CODE) {
    if (pattern.test(code)) {
      throw Object.assign(new Error("template uses an API outside the prompt-only EJS boundary"), {
        kind: "policy",
      });
    }
  }
}

function protectLiteralRegions(template) {
  const literals = [];
  let counter = 0;
  const token = (value) => {
    let marker;
    do {
      marker = `\uE000TAVO_EJS_LITERAL_${counter++}\uE001`;
    } while (template.includes(marker));
    literals.push([marker, value]);
    return marker;
  };
  let protectedTemplate = template.replace(
    /<#escape-ejs>([\s\S]*?)<\/\#escape-ejs>/g,
    (_match, value) => token(value),
  );
  if (protectedTemplate.includes("<#escape-ejs>") || protectedTemplate.includes("</#escape-ejs>")) {
    throw Object.assign(new Error("unbalanced <#escape-ejs> block"), { kind: "syntax" });
  }
  protectedTemplate = protectedTemplate.replace(/<%%([\s\S]*?)%%>/g, (_match, value) =>
    token(`<%${value}%>`),
  );
  return { template: protectedTemplate, literals };
}

function compileTemplate(source) {
  const protectedValue = protectLiteralRegions(source);
  const template = protectedValue.template;
  const lines = [
    "(() => {",
    "'use strict';",
    "const __tavoLabOut = [];",
    "let __tavoLabOutputChars = 0;",
    "const __tavoLabAppend = (value) => {",
    "  const text = value === null || value === undefined ? '' : String(value);",
    "  __tavoLabOutputChars += text.length;",
    "  if (__tavoLabOutputChars > __tavoLabLimits.maxOutputChars) throw new Error('EJS output exceeds the configured field limit');",
    "  __tavoLabOut.push(text);",
    "};",
    "const __tavoLabEscape = (value) => {",
    "  const text = value === null || value === undefined ? '' : String(value);",
    "  return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/\"/g, '&quot;').replace(/'/g, '&#39;');",
    "};",
    "const print = (...values) => __tavoLabAppend(values.map((value) => value === null || value === undefined ? '' : String(value)).join(''));",
  ];

  let cursor = 0;
  while (cursor < template.length) {
    const open = template.indexOf("<%", cursor);
    if (open < 0) {
      lines.push(`__tavoLabAppend(${JSON.stringify(template.slice(cursor))});`);
      break;
    }
    if (open > cursor) {
      lines.push(`__tavoLabAppend(${JSON.stringify(template.slice(cursor, open))});`);
    }
    const normalClose = template.indexOf("%>", open + 2);
    if (normalClose < 0) {
      throw Object.assign(new Error("unclosed EJS tag"), { kind: "syntax" });
    }
    const trimClose = normalClose > open + 2 && template[normalClose - 1] === "-";
    const bodyEnd = trimClose ? normalClose - 1 : normalClose;
    const tag = template.slice(open + 2, bodyEnd);
    const prefix = tag[0] || "";
    const body = ["-", "=", "#", "_"].includes(prefix) ? tag.slice(1) : tag;
    if (prefix !== "#") {
      policyCheck(body);
    }
    if (prefix === "-") {
      lines.push(`__tavoLabAppend((${body}));`);
    } else if (prefix === "=") {
      lines.push(`__tavoLabAppend(__tavoLabEscape((${body})));`);
    } else if (prefix === "#") {
      // Comment: intentionally omitted.
    } else {
      lines.push(body);
    }
    cursor = normalClose + 2;
    if (trimClose) {
      if (template.startsWith("\r\n", cursor)) cursor += 2;
      else if (template[cursor] === "\n" || template[cursor] === "\r") cursor += 1;
    }
  }
  lines.push("return __tavoLabOut.join('');", "})()");
  return { code: lines.join("\n"), literals: protectedValue.literals };
}

function bootstrapSource(payload) {
  const encoded = JSON.stringify(JSON.stringify(payload));
  return `
"use strict";
const __tavoLabPayload = JSON.parse(${encoded});
const __tavoLabState = __tavoLabPayload.state;
const __tavoLabLimits = __tavoLabPayload.limits;
const __tavoLabTrace = [];
const __tavoLabDangerousPathParts = new Set(["__proto__", "prototype", "constructor"]);
const __tavoLabPathParts = (path) => {
  const value = String(path == null ? "" : path).replace(/\\[(\\d+)\\]/g, ".$1");
  const parts = value.split(".").filter(Boolean);
  if (!parts.length || parts.some((part) => __tavoLabDangerousPathParts.has(part))) throw new Error("invalid variable path");
  return parts;
};
const __tavoLabHasAt = (root, path) => {
  let current = root;
  for (const part of __tavoLabPathParts(path)) {
    if (current === null || current === undefined || !Object.prototype.hasOwnProperty.call(Object(current), part)) return false;
    current = current[part];
  }
  return true;
};
const __tavoLabGetAt = (root, path) => {
  let current = root;
  for (const part of __tavoLabPathParts(path)) current = current[part];
  return current;
};
const __tavoLabSetAt = (root, path, value) => {
  const parts = __tavoLabPathParts(path);
  let current = root;
  for (let index = 0; index < parts.length - 1; index++) {
    const part = parts[index];
    const nextIsIndex = /^\\d+$/.test(parts[index + 1]);
    if (!current[part] || typeof current[part] !== "object") current[part] = nextIsIndex ? [] : {};
    current = current[part];
  }
  current[parts[parts.length - 1]] = value;
  return value;
};
const __tavoLabUnsetAt = (root, path) => {
  const parts = __tavoLabPathParts(path);
  let current = root;
  for (let index = 0; index < parts.length - 1; index++) {
    const part = parts[index];
    if (!current || typeof current !== "object" || !Object.prototype.hasOwnProperty.call(current, part)) return false;
    current = current[part];
  }
  if (!current || typeof current !== "object") return false;
  return delete current[parts[parts.length - 1]];
};
const __tavoLabClone = (value) => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
const __tavoLabScopeName = (scope) => {
  if (scope === undefined || scope === null || scope === "" || scope === "cache") return null;
  if (scope === "global") return "global";
  if (["chat", "local", "message", "initial"].includes(scope)) return "chat";
  throw new Error("invalid variable scope");
};
const __tavoLabRecord = (item) => {
  if (__tavoLabTrace.length >= __tavoLabLimits.maxTraceItems) throw new Error("EJS variable trace limit exceeded");
  __tavoLabTrace.push(item);
};
function getvar(key, fallbackOrOptions) {
  let requestedScope = null;
  let hasDefault = arguments.length >= 2;
  let fallback = fallbackOrOptions;
  if (fallbackOrOptions && typeof fallbackOrOptions === "object" && !Array.isArray(fallbackOrOptions)) {
    requestedScope = __tavoLabScopeName(fallbackOrOptions.scope);
    hasDefault = Object.prototype.hasOwnProperty.call(fallbackOrOptions, "defaults") || Object.prototype.hasOwnProperty.call(fallbackOrOptions, "default");
    fallback = Object.prototype.hasOwnProperty.call(fallbackOrOptions, "defaults") ? fallbackOrOptions.defaults : fallbackOrOptions.default;
  }
  const scopes = requestedScope ? [requestedScope] : ["chat", "global"];
  for (const scope of scopes) {
    if (__tavoLabHasAt(__tavoLabState[scope], key)) {
      const value = __tavoLabGetAt(__tavoLabState[scope], key);
      __tavoLabRecord({ channel: "ejs", op: "get", key: String(key), requestedScope, resolvedScope: scope, found: true });
      return value;
    }
  }
  __tavoLabRecord({ channel: "ejs", op: "get", key: String(key), requestedScope, resolvedScope: null, found: false });
  return hasDefault ? fallback : "";
}
const setvar = (key, value, options) => {
  const scope = __tavoLabScopeName(options && options.scope) || "chat";
  __tavoLabSetAt(__tavoLabState[scope], key, __tavoLabClone(value));
  __tavoLabRecord({ channel: "ejs", op: "set", key: String(key), scope });
  return value;
};
const __tavoLabChangevar = (op, key, amount, options) => {
  const scope = __tavoLabScopeName(options && options.scope) || "chat";
  const current = __tavoLabHasAt(__tavoLabState[scope], key) ? Number(__tavoLabGetAt(__tavoLabState[scope], key)) : 0;
  const delta = Number(amount === undefined ? 1 : amount);
  if (!Number.isFinite(delta)) throw new Error("variable increment must be finite");
  const next = (Number.isFinite(current) ? current : 0) + delta;
  __tavoLabSetAt(__tavoLabState[scope], key, next);
  __tavoLabRecord({ channel: "ejs", op, key: String(key), scope });
  return next;
};
const incvar = (key, amount = 1, options) => __tavoLabChangevar("inc", key, amount, options);
const decvar = (key, amount = 1, options) => __tavoLabChangevar("dec", key, -Number(amount === undefined ? 1 : amount), options);
const delvar = (key, options) => {
  const scope = __tavoLabScopeName(options && options.scope) || "chat";
  const removed = __tavoLabUnsetAt(__tavoLabState[scope], key);
  __tavoLabRecord({ channel: "ejs", op: "delete", key: String(key), scope, removed });
  return removed;
};
const _ = Object.freeze({
  get: (object, path, fallback) => __tavoLabHasAt(object, path) ? __tavoLabGetAt(object, path) : fallback,
  has: (object, path) => __tavoLabHasAt(object, path),
  set: (object, path, value) => __tavoLabSetAt(object, path, value),
  unset: (object, path) => __tavoLabUnsetAt(object, path),
  cloneDeep: (value) => __tavoLabClone(value),
});
const charName = String(__tavoLabPayload.constants.charName || "");
const userName = String(__tavoLabPayload.constants.userName || "");
const lastUserMessage = String(__tavoLabPayload.constants.lastUserMessage || "");
const lastCharMessage = String(__tavoLabPayload.constants.lastCharMessage || "");
const characterId = __tavoLabPayload.constants.characterId == null ? "" : __tavoLabPayload.constants.characterId;
`;
}

async function readStdin() {
  const chunks = [];
  let size = 0;
  for await (const chunk of process.stdin) {
    size += chunk.length;
    if (size > MAX_STDIN_BYTES) throw new Error("request exceeds worker input limit");
    chunks.push(chunk);
  }
  return Buffer.concat(chunks).toString("utf8");
}

try {
  const raw = await readStdin();
  const request = JSON.parse(raw);
  validateRequest(request);
  const compiled = compileTemplate(request.template);
  const context = vm.createContext(Object.create(null), {
    name: "tavo-prompt-lab-ejs",
    codeGeneration: { strings: false, wasm: false },
  });
  const payload = {
    state: request.state,
    constants: request.constants,
    limits: {
      maxOutputChars: request.maxOutputChars,
      maxTraceItems: request.maxTraceItems,
    },
  };
  vm.runInContext(bootstrapSource(payload), context, { timeout: request.timeoutMs });
  let output = vm.runInContext(compiled.code, context, { timeout: request.timeoutMs });
  for (const [marker, literal] of compiled.literals) output = output.split(marker).join(literal);
  if (output.length > request.maxOutputChars) throw new Error("EJS output exceeds the configured field limit");
  const snapshot = JSON.parse(
    vm.runInContext("JSON.stringify({ state: __tavoLabState, trace: __tavoLabTrace })", context, {
      timeout: request.timeoutMs,
    }),
  );
  process.stdout.write(JSON.stringify({ ok: true, output, state: snapshot.state, trace: snapshot.trace }));
} catch (error) {
  fail(error && error.kind ? error.kind : "runtime", error && error.message ? error.message : error);
}
