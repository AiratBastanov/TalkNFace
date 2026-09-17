import { mkdirSync, mkdtempSync, rmSync } from 'node:fs';
import { join, resolve, sep } from 'node:path';
import { PROJECT_ROOT } from '../src/paths.ts';

export function temporaryDatabase() {
  const base = resolve(PROJECT_ROOT, '.tmp');
  mkdirSync(base, { recursive: true });
  const directory = mkdtempSync(join(base, 'g0-test-'));
  return {
    directory,
    filename: join(directory, 'nested', 'foundation.sqlite'),
    cleanup() {
      if (!resolve(directory).startsWith(base + sep)) throw new Error('Unsafe test cleanup path');
      rmSync(directory, { recursive: true, force: true });
    },
  };
}
