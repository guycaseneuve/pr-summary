// Utility functions — intentionally has ESLint-fixable style issues
// eslint --fix will auto-correct these patterns

const moment = require("moment");

// ❌ ESLint: no-unused-vars
// eslint-disable-next-line no-unused-vars
const UNUSED_CONSTANT = "this is never used";

// ❌ ESLint: quotes (inconsistent)
const greeting = "hello";
const farewell = "goodbye";

// ❌ ESLint: semi (missing semicolons)
function formatDate (date) {
  return moment(date).format("YYYY-MM-DD");
}

// ❌ ESLint: no-unused-vars + semi
// eslint-disable-next-line no-unused-vars
function unusedHelper (x, y) {
  // eslint-disable-next-line no-unused-vars
  const temp = x + y;
  return x * 2;
}

// ❌ ESLint: comma-dangle (trailing comma)
const config = {
  host: "localhost",
  port: 3000,
  debug: true
};

// ❌ ESLint: space-before-function-paren + keyword-spacing
function processData (input){
  if (input){
    return input.trim();
  }
  return null;
}

// ❌ ESLint: prefer-const (let used but never reassigned)
const appName = "demo-app";

module.exports = {
  formatDate,
  processData,
  config,
  appName,
  greeting,
  farewell
};
