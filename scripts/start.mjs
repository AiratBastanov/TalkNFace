import './check-runtime.mjs';
import { existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const envFile = fileURLToPath(new URL('../.env', import.meta.url));
if (existsSync(envFile)) process.loadEnvFile(envFile);
// npm start always serves the production build, even if .env says development.
process.env.NODE_ENV = 'production';
await import('../apps/server/dist/main.js');
