import { hashPassword } from '../apps/server/src/access/password.ts';
import { checkPasswordLength, readAdminPassword } from './password-input.mjs';
if (process.versions.node.split('.')[0] !== '24') throw new Error('Node 24 is required.');

// Only the hash is written to stdout; no plaintext argument, file or log.
try {
  const password = await readAdminPassword(); checkPasswordLength(password);
  process.stdout.write(await hashPassword(password) + '\n');
} catch (error) {
  process.stderr.write(error instanceof Error ? error.message + '\n' : 'Cannot generate password hash.\n');
  process.exitCode = 1;
}
