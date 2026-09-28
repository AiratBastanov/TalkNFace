import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import { expect, it } from 'vitest';
import { validPasswordHash, verifyPassword } from '../src/access/password.ts';

it('local generator reads UTF-8 password from stdin, outputs only a supported salted hash and rejects wrong password', async () => {
  const password = 'Пароль-' + randomBytes(24).toString('base64url');
  const output = execFileSync(process.execPath, ['scripts/admin-password.mjs', '--stdin'], {
    input: password, encoding: 'utf8', timeout: 10_000, windowsHide: true,
  }).trim();
  expect(validPasswordHash(output)).toBe(true); expect(output.includes(password)).toBe(false);
  expect(await verifyPassword(password, output)).toBe(true); expect(await verifyPassword(password + 'x', output)).toBe(false);
});
