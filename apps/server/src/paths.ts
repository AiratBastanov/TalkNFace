import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

// src/ and dist/ have the same depth; paths do not depend on the shell's cwd.
export const PROJECT_ROOT = fileURLToPath(new URL('../../../', import.meta.url));
export const WEB_ROOT = resolve(PROJECT_ROOT, 'apps/web/dist');
