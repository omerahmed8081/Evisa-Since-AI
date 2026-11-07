#!/usr/bin/env node
/**
 * Start the backend (FastAPI) and the frontend (Vite) with one command.
 *
 *   npm run dev              both (frontend starts once the API answers /api/health)
 *   npm run dev:backend      only the API
 *   npm run dev:frontend     only the web app
 *
 * Output of both is shown in this terminal, prefixed with [api] / [web]. Ctrl+C stops both, and if one of them
 * exits, the other is stopped too. No extra packages needed; works on Linux, macOS and Windows.
 *
 * Settings (environment variables, all optional):
 *   PYTHON        Python to run the API with. Default: backend/.venv if it exists, otherwise `python`/`python3`
 *                 on PATH (e.g. an activated conda env).
 *   API_PORT      default 8000
 *   WEB_PM        package manager for the frontend: npm | bun. Default: npm if it is v11+, otherwise bun if
 *                 installed (npm 10 can't install this frontend).
 */
import { spawn, spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const BACKEND = path.join(ROOT, "backend");
const FRONTEND = path.join(ROOT, "frontend");
const IS_WIN = process.platform === "win32";
const API_PORT = process.env.API_PORT || "8000";
const what = process.argv[2] || "all"; // all | backend | frontend

const color = process.stdout.isTTY && !process.env.NO_COLOR;
const paint = (code, s) => (color ? `\x1b[${code}m${s}\x1b[0m` : s);
const TAG = { api: paint("36", "[api]"), web: paint("35", "[web]"), dev: paint("33", "[dev]") };
const log = (msg) => console.log(`${TAG.dev} ${msg}`);
const fail = (msg) => {
  console.error(`${TAG.dev} ${paint("31", "error:")} ${msg}`);
  process.exit(1);
};

function works(cmd, args) {
  const r = spawnSync(cmd, args, { encoding: "utf8", shell: IS_WIN });
  if (r.status !== 0) return null;
  return (r.stdout || r.stderr || "").trim() || "ok"; // success may print nothing
}

// ---------- backend ----------
function findPython() {
  if (process.env.PYTHON) return process.env.PYTHON;
  const venv = IS_WIN
    ? path.join(BACKEND, ".venv", "Scripts", "python.exe")
    : path.join(BACKEND, ".venv", "bin", "python");
  if (existsSync(venv)) return venv;
  for (const cand of IS_WIN ? ["python", "py"] : ["python", "python3"]) {
    if (works(cand, ["--version"])) return cand;
  }
  return null;
}

function checkBackend() {
  const py = findPython();
  if (!py) fail("No Python found. Activate your environment (venv/conda) or set PYTHON=/path/to/python.");
  if (!works(py, ["-c", "import fastapi, uvicorn, neo4j"])) {
    fail(`'${py}' can't import fastapi/uvicorn/neo4j. Install the backend requirements into it:\n` +
         `      ${py} -m pip install -r backend/requirements.txt`);
  }
  if (!existsSync(path.join(BACKEND, ".env"))) {
    log(paint("33", "warning: backend/.env not found (copy backend/.env.example and fill in the keys)"));
  }
  return py;
}

// ---------- frontend ----------
function findBun() {
  if (works("bun", ["--version"])) return "bun";
  // bun's installer puts it in ~/.bun/bin, which a terminal opened before the install doesn't have on PATH
  const home = process.env.HOME || process.env.USERPROFILE || "";
  const local = path.join(home, ".bun", "bin", IS_WIN ? "bun.exe" : "bun");
  return existsSync(local) && works(local, ["--version"]) ? local : null;
}

function pickPackageManager() {
  const wanted = process.env.WEB_PM;
  if (wanted) return wanted;
  const npmV = works("npm", ["-v"]);
  if (npmV && Number(npmV.split(".")[0]) >= 11) return "npm";
  const bun = findBun();
  if (bun) {
    if (npmV) log(`npm ${npmV} can't install this frontend (needs npm 11+); using bun.`);
    return bun;
  }
  if (npmV) fail(`npm ${npmV} is too old for this frontend. Install Node 24 (comes with npm 11): nvm install 24 && nvm use 24   (or install bun)`);
  fail("Neither npm nor bun found. Install Node.js 22.12+ (see frontend/README.md).");
}

function checkFrontend() {
  const nodeMajor = Number(process.versions.node.split(".")[0]);
  const nodeMinor = Number(process.versions.node.split(".")[1]);
  if (nodeMajor < 22 || (nodeMajor === 22 && nodeMinor < 12)) {
    fail(`Node ${process.versions.node} is too old; the frontend needs 22.12+. Run: nvm install 24 && nvm use 24`);
  }
  const pm = pickPackageManager();
  if (!existsSync(path.join(FRONTEND, "node_modules"))) {
    log(`frontend/node_modules missing: running '${pm} install' first…`);
    const r = spawnSync(pm, ["install"], { cwd: FRONTEND, stdio: "inherit", shell: IS_WIN });
    if (r.status !== 0) fail(`'${pm} install' failed in frontend/`);
  }
  return pm;
}

// ---------- process handling ----------
const children = [];
let stopping = false;

function prefixLines(stream, tag, out) {
  let buf = "";
  stream.on("data", (chunk) => {
    buf += chunk.toString();
    const lines = buf.split(/\r?\n/);
    buf = lines.pop();
    for (const line of lines) out.write(`${tag} ${line}\n`);
  });
  stream.on("end", () => buf && out.write(`${tag} ${buf}\n`));
}

function run(name, cmd, args, cwd, extraEnv = {}) {
  const child = spawn(cmd, args, {
    cwd,
    env: { ...process.env, ...(color ? { FORCE_COLOR: "1" } : {}), PYTHONUNBUFFERED: "1", ...extraEnv },
    shell: IS_WIN,
    detached: !IS_WIN, // own process group, so Ctrl+C also stops uvicorn's reloader / vite's children
  });
  prefixLines(child.stdout, TAG[name], process.stdout);
  prefixLines(child.stderr, TAG[name], process.stderr);
  child.on("exit", (code, signal) => {
    if (!stopping) {
      log(`${name} stopped (${signal || `exit code ${code}`}); stopping the rest.`);
      stopAll(code ?? 1);
    }
  });
  children.push(child);
  return child;
}

function kill(child) {
  if (child.exitCode !== null || child.signalCode !== null) return;
  try {
    if (IS_WIN) spawnSync("taskkill", ["/pid", String(child.pid), "/t", "/f"], { stdio: "ignore" });
    else process.kill(-child.pid, "SIGTERM");
  } catch {
    /* already gone */
  }
}

function stopAll(code = 0) {
  if (stopping) return;
  stopping = true;
  children.forEach(kill);
  setTimeout(() => process.exit(code), 1500).unref();
  Promise.all(children.map((c) => new Promise((r) => (c.exitCode !== null ? r() : c.on("exit", r))))).then(() =>
    process.exit(code),
  );
}

process.on("SIGINT", () => {
  log("stopping…");
  stopAll(0);
});
process.on("SIGTERM", () => stopAll(0));

async function waitForApi(timeoutMs = 45000) {
  const url = `http://127.0.0.1:${API_PORT}/api/health`;
  const until = Date.now() + timeoutMs;
  while (Date.now() < until && !stopping) {
    try {
      const res = await fetch(url);
      if (res.ok) return true;
    } catch {
      /* not up yet */
    }
    await new Promise((r) => setTimeout(r, 700));
  }
  return false;
}

// ---------- main ----------
const py = what !== "frontend" ? checkBackend() : null;
const pm = what !== "backend" ? checkFrontend() : null;

if (py) {
  log(`API  → http://localhost:${API_PORT}  (docs: /docs)   python: ${py}`);
  run("api", py, ["-m", "uvicorn", "api.main:app", "--reload", "--port", API_PORT], BACKEND);
}

if (pm) {
  if (py) {
    log("waiting for the API to answer /api/health…");
    if (!(await waitForApi())) log(paint("33", "API not answering yet; starting the frontend anyway."));
  }
  log(`Web  → http://localhost:8080   (${pm})`);
  run("web", pm, ["run", "dev"], FRONTEND, { VITE_API_BASE_URL: `http://localhost:${API_PORT}` });
}
