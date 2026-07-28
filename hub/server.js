#!/usr/bin/env node
/*
 * Hub de Projetos - servidor local (somente 127.0.0.1).
 * Fallback em Node.js, equivalente ao server.py. Sem dependencias externas.
 *
 * Uso: node server.js   (ou pelo Iniciar.bat)
 */
"use strict";

const http = require("http");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");

const BASE = __dirname;
const DATA = path.join(BASE, "data");
const HOST = "127.0.0.1";
const PORT = parseInt(process.env.HUB_PORT || "4577", 10);

const SLUG_RE = /^[a-z0-9][a-z0-9_-]*$/;

const DEFAULT_COLUMNS = [
  { id: "agora", title: "Agora", color: "#ef4444", cards: [] },
  { id: "depois", title: "Depois", color: "#f59e0b", cards: [] },
  { id: "inspiracao", title: "Inspiracao", color: "#8b5cf6", cards: [] },
  { id: "erros", title: "Erros pra ver", color: "#ec4899", cards: [] },
  { id: "feito", title: "Feito", color: "#22c55e", cards: [] },
];

const CTYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".ico": "image/x-icon",
};

function nowIso() {
  const d = new Date();
  const pad = (n) => String(n).padStart(2, "0");
  const off = -d.getTimezoneOffset();
  const sign = off >= 0 ? "+" : "-";
  const oh = pad(Math.floor(Math.abs(off) / 60));
  const om = pad(Math.abs(off) % 60);
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T` +
    `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}${sign}${oh}:${om}`;
}

function readJson(p, def) {
  try { return JSON.parse(fs.readFileSync(p, "utf-8")); }
  catch (e) { return def; }
}
function writeJson(p, obj) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  const tmp = p + ".tmp";
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2), "utf-8");
  fs.renameSync(tmp, p);
}
function readText(p, def) {
  try { return fs.readFileSync(p, "utf-8"); } catch (e) { return def; }
}
function writeText(p, content) {
  fs.mkdirSync(path.dirname(p), { recursive: true });
  fs.writeFileSync(p, content, "utf-8");
}
function slugify(name) {
  let s = (name || "").trim().toLowerCase();
  s = s.normalize("NFD").replace(/[̀-ͯ]/g, "");
  s = s.replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
  return s || "projeto";
}
function safeSlug(s) { return SLUG_RE.test(s || "") ? s : null; }

const projectsFile = () => path.join(DATA, "projects.json");
const loadProjects = () => readJson(projectsFile(), { projects: [] });
const saveProjects = (st) => writeJson(projectsFile(), st);
const projectDir = (slug) => path.join(DATA, slug);

function findProject(slug) {
  const st = loadProjects();
  const proj = st.projects.find((p) => p.id === slug) || null;
  return { st, proj };
}

function sendJson(res, obj, status = 200) {
  const body = Buffer.from(JSON.stringify(obj), "utf-8");
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Content-Length": body.length,
    "Cache-Control": "no-store",
  });
  res.end(body);
}
function sendError(res, status, msg) { sendJson(res, { error: msg }, status); }

// App de pagina unica: por seguranca so servimos o index.html.
// Assim ninguem (nem outra pagina local) consegue puxar server.js
// ou os arquivos de segredos via GET direto.
function serveStatic(res, urlPath) {
  if (urlPath === "/" || urlPath === "" || urlPath === "/index.html") {
    const target = path.join(BASE, "index.html");
    if (!fs.existsSync(target)) return sendError(res, 404, "index.html nao encontrado");
    const body = fs.readFileSync(target);
    res.writeHead(200, { "Content-Type": "text/html; charset=utf-8", "Content-Length": body.length, "Cache-Control": "no-store" });
    return res.end(body);
  }
  return sendError(res, 404, "nao encontrado");
}

function readBody(req) {
  return new Promise((resolve) => {
    let data = "";
    req.on("data", (c) => (data += c));
    req.on("end", () => {
      if (!data) return resolve({});
      try { resolve(JSON.parse(data)); } catch (e) { resolve({}); }
    });
  });
}

function getResource(res, slug, resource) {
  const { proj } = findProject(slug);
  if (!proj) return sendError(res, 404, "projeto nao encontrado");
  const d = projectDir(slug);
  if (resource === "board") return sendJson(res, readJson(path.join(d, "board.json"), { columns: DEFAULT_COLUMNS }));
  if (resource === "notes") return sendJson(res, { content: readText(path.join(d, "notes.md"), "") });
  if (resource === "secrets") return sendJson(res, readJson(path.join(d, "secrets.local.json"), { keys: [] }));
  return sendError(res, 404, "recurso desconhecido");
}

async function putResource(req, res, slug, resource) {
  const { st, proj } = findProject(slug);
  if (!proj) return sendError(res, 404, "projeto nao encontrado");
  const d = projectDir(slug);
  const body = await readBody(req);
  if (resource === "board") writeJson(path.join(d, "board.json"), body);
  else if (resource === "notes") writeText(path.join(d, "notes.md"), body.content || "");
  else if (resource === "secrets") writeJson(path.join(d, "secrets.local.json"), { keys: body.keys || [] });
  else return sendError(res, 404, "recurso desconhecido");
  proj.updatedAt = nowIso();
  saveProjects(st);
  sendJson(res, { ok: true, updatedAt: proj.updatedAt });
}

async function createProject(req, res) {
  const body = await readBody(req);
  const name = (body.name || "").trim();
  if (!name) return sendError(res, 400, "nome obrigatorio");
  const st = loadProjects();
  const existing = new Set(st.projects.map((p) => p.id));
  let base = slugify(name), slug = base, i = 2;
  while (existing.has(slug)) { slug = `${base}-${i}`; i++; }
  const proj = {
    id: slug, name, description: body.description || "",
    repoPath: body.repoPath || "", repoUrl: body.repoUrl || "",
    color: body.color || "#3b82f6", createdAt: nowIso(), updatedAt: nowIso(),
  };
  st.projects.push(proj);
  saveProjects(st);
  const d = projectDir(slug);
  writeJson(path.join(d, "board.json"), { columns: DEFAULT_COLUMNS });
  writeText(path.join(d, "notes.md"), `# ${name}\n\n`);
  writeJson(path.join(d, "secrets.example.json"),
    { keys: [{ id: "exemplo", label: "Nome da chave", value: "cole-o-valor-aqui", notes: "" }] });
  sendJson(res, proj, 201);
}

async function patchProject(req, res, slug) {
  const { st, proj } = findProject(slug);
  if (!proj) return sendError(res, 404, "projeto nao encontrado");
  const body = await readBody(req);
  for (const f of ["name", "description", "repoPath", "repoUrl", "color"]) {
    if (f in body) proj[f] = body[f];
  }
  proj.updatedAt = nowIso();
  saveProjects(st);
  sendJson(res, proj);
}

function rmrf(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true });
}
function deleteProject(res, slug) {
  const { st, proj } = findProject(slug);
  if (!proj) return sendError(res, 404, "projeto nao encontrado");
  st.projects = st.projects.filter((p) => p.id !== slug);
  saveProjects(st);
  rmrf(projectDir(slug));
  sendJson(res, { ok: true });
}

const server = http.createServer(async (req, res) => {
  const urlPath = (req.url || "/").split("?")[0];
  if (!urlPath.startsWith("/api/")) return serveStatic(res, urlPath);
  const parts = urlPath.split("/").filter(Boolean); // ['api', ...]
  const m = req.method;

  if (m === "GET" && parts.length === 2 && parts[1] === "projects") return sendJson(res, loadProjects());
  if (m === "POST" && parts.length === 2 && parts[1] === "projects") return createProject(req, res);

  if (parts.length === 3 && parts[0] === "api" && parts[1] === "projects") {
    const slug = safeSlug(parts[2]);
    if (!slug) return sendError(res, 400, "id invalido");
    if (m === "PATCH") return patchProject(req, res, slug);
    if (m === "DELETE") return deleteProject(res, slug);
  }
  if (parts.length === 4 && parts[0] === "api" && parts[1] === "projects") {
    const slug = safeSlug(parts[2]);
    if (!slug) return sendError(res, 400, "id invalido");
    if (m === "GET") return getResource(res, slug, parts[3]);
    if (m === "PUT") return putResource(req, res, slug, parts[3]);
  }
  sendError(res, 404, "rota nao encontrada");
});

fs.mkdirSync(DATA, { recursive: true });
if (!fs.existsSync(projectsFile())) saveProjects({ projects: [] });

server.listen(PORT, HOST, () => {
  const url = `http://${HOST}:${PORT}/`;
  console.log("=".repeat(56));
  console.log("  Hub de Projetos rodando localmente");
  console.log(`  Abra no navegador: ${url}`);
  console.log("  (Somente nesta maquina. Nada exposto na internet.)");
  console.log("  Para encerrar: feche esta janela.");
  console.log("=".repeat(56));
  const cmd = process.platform === "win32" ? `start "" "${url}"`
    : process.platform === "darwin" ? `open "${url}"` : `xdg-open "${url}"`;
  setTimeout(() => exec(cmd, () => {}), 800);
});

server.on("error", (e) => {
  console.log(`Nao consegui abrir a porta ${PORT}: ${e.message}`);
  console.log("Talvez o app ja esteja aberto. Feche a janela antiga e tente de novo.");
});
