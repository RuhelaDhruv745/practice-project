// Generate src/types/api.ts from the backend OpenAPI schema.
// Source: first CLI argument (URL or file path), else
// ${VITE_API_BASE_URL or http://localhost:8000}/openapi.json.
import { execFileSync } from "node:child_process";

const base = (process.env.VITE_API_BASE_URL || "http://localhost:8000").replace(/\/+$/, "");
const source = process.argv[2] || `${base}/openapi.json`;

execFileSync(
  process.execPath,
  ["node_modules/openapi-typescript/bin/cli.js", source, "-o", "src/types/api.ts"],
  { stdio: "inherit" },
);
