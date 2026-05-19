// Demo app — intentionally vulnerable for security scanning demonstration
// DO NOT deploy this to production. These patterns trigger CodeQL SAST rules.

const express = require("express");
const fs = require("fs");
const path = require("path");
const { exec } = require("child_process");
const _ = require("lodash");
const jwt = require("jsonwebtoken");
const ejs = require("ejs");
const marked = require("marked");
const yaml = require("js-yaml");
const axios = require("axios");
const forge = require("node-forge");
const minimist = require("minimist");

const app = express();

// ❌ CodeQL: js/hardcoded-credentials
const API_KEY = "sk_live_4eC39HqLyjWDarjtT1zdp7dc";
// eslint-disable-next-line no-unused-vars
const DB_PASSWORD = "super_secret_password_123";

// Simulated database query function
function queryDatabase (sql, callback) {
  // In a real app this would connect to a database
  callback(null, { rows: [], query: sql });
}

// ❌ CodeQL: js/sql-injection
// User input directly concatenated into SQL query
app.get("/api/users", (req, res) => {
  const userId = req.query.id;
  const query = "SELECT * FROM users WHERE id = " + userId;
  queryDatabase(query, (err, result) => {
    if (err) return res.status(500).send("Database error");
    res.json(result);
  });
});

// ❌ CodeQL: js/path-injection
// User input used in file path without sanitization
app.get("/api/files", (req, res) => {
  const fileName = req.query.file;
  const filePath = path.join(__dirname, "uploads", fileName);
  fs.readFile(filePath, "utf8", (err, data) => {
    if (err) return res.status(404).send("File not found");
    res.send(data);
  });
});

// ❌ CodeQL: js/reflected-xss
// User input rendered directly in HTML response without escaping
app.get("/search", (req, res) => {
  const query = req.query.q;
  res.send("<h1>Search results for: " + query + "</h1><p>No results found.</p>");
});

// ❌ CodeQL: js/command-line-injection
// User input passed directly to shell command
app.get("/api/list", (req, res) => {
  const directory = req.query.dir;
  // eslint-disable-next-line no-unused-vars
  exec("ls -la " + directory, (err, stdout, stderr) => {
    if (err) return res.status(500).send("Command failed");
    res.send("<pre>" + stdout + "</pre>");
  });
});

// Safe endpoint for comparison
app.get("/api/health", (req, res) => {
  res.json({ status: "ok", timestamp: new Date().toISOString() });
});

// Use lodash (vulnerable version) to demonstrate dependency scanning
app.get("/api/merge", (req, res) => {
  const defaults = { admin: false, role: "user" };
  const userInput = req.body || {};
  // lodash defaultsDeep is vulnerable to prototype pollution in 4.17.11
  const merged = _.defaultsDeep({}, userInput, defaults);
  res.json(merged);
});

// ❌ CodeQL: js/insecure-jwt + npm audit: jsonwebtoken@8.3.0 (CVE-2022-23529)
// Sign tokens with a weak secret; verify without algorithm restriction
app.post("/api/token", (req, res) => {
  const username = req.body.username;
  const token = jwt.sign({ user: username, admin: true }, "secret");
  res.json({ token });
});

app.get("/api/verify-token", (req, res) => {
  const token = req.query.token;
  // Verify without specifying algorithms — allows algorithm confusion attacks
  const decoded = jwt.verify(token, "secret");
  res.json(decoded);
});

// ❌ CodeQL: js/code-injection + npm audit: ejs@2.7.4 (CVE-2022-29078)
// User input passed directly as EJS template — server-side template injection
app.get("/api/render", (req, res) => {
  const template = req.query.template;
  const data = req.query.data || "World";
  const output = ejs.render(template, { name: data });
  res.send(output);
});

// ❌ CodeQL: js/xss + npm audit: marked@0.3.6 (CVE-2017-1000427)
// Render user-supplied markdown without sanitization
app.get("/api/preview", (req, res) => {
  const markdown = req.query.md;
  const html = marked(markdown);
  res.send("<html><body>" + html + "</body></html>");
});

// ❌ CodeQL: js/code-injection + npm audit: js-yaml@3.13.0
// Using yaml.load() (unsafe) instead of yaml.safeLoad() on user input
app.post("/api/parse-yaml", (req, res) => {
  const content = req.body.content;
  const parsed = yaml.load(content);
  res.json(parsed);
});

// ❌ CodeQL: js/request-forgery + npm audit: axios@0.21.0 (CVE-2021-3749)
// Fetch user-supplied URL without validation — SSRF vulnerability
app.get("/api/fetch", (req, res) => {
  const url = req.query.url;
  axios.get(url).then((response) => {
    res.json({ status: response.status, data: response.data });
  }).catch((err) => {
    res.status(500).json({ error: err.message });
  });
});

// ❌ npm audit: node-forge@0.9.0 (CVE-2022-24771, CVE-2022-24772)
// Generate RSA key pair with weak parameters
app.get("/api/generate-key", (req, res) => {
  const keypair = forge.pki.rsa.generateKeyPair({ bits: 512 });
  const publicKeyPem = forge.pki.publicKeyToPem(keypair.publicKey);
  res.json({ publicKey: publicKeyPem });
});

// ❌ npm audit: minimist@0.0.8 (CVE-2020-7598) — prototype pollution
// Parse arbitrary arguments — demonstrates transitive dependency vulnerability
const args = minimist(process.argv.slice(2));
console.log("Parsed CLI args:", args);

const PORT = process.env.PORT || 3000;

// Only start the HTTP server when run directly (not when imported by tests)
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Demo app listening on port ${PORT}`);
    console.log(`API Key: ${API_KEY}`); // ❌ Logging credentials
  });
}

module.exports = app;
