import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ConfigurationError, parseEnv } from '../src/env.ts';
import { PROJECT_ROOT } from '../src/paths.ts';

describe('server environment', () => {
  it('starts with safe defaults and no credentials', () => {
    expect(parseEnv({})).toEqual({ NODE_ENV: 'development', HOST: '127.0.0.1', PORT: 3000,
      DATABASE_PATH: resolve(PROJECT_ROOT, 'data/arena.sqlite') });
  });

  it('accepts explicit settings and returns a typed port and deterministic file path', () => {
    expect(parseEnv({ NODE_ENV: 'production', HOST: '0.0.0.0', PORT: '4321', DATABASE_PATH: './data/custom.sqlite' }))
      .toEqual({ NODE_ENV: 'production', HOST: '0.0.0.0', PORT: 4321, DATABASE_PATH: resolve(PROJECT_ROOT, 'data/custom.sqlite') });
  });

  it.each(['0', '-1', '65536', '3.5', '', 'invalid'])('rejects invalid PORT %j without echoing it', (PORT) => {
    expect(() => parseEnv({ PORT })).toThrow('Invalid configuration: PORT');
  });

  it.each(['', '  ', ':memory:', 'file:test.sqlite', 'data/', 'bad\0path'])('rejects invalid database path %j', (DATABASE_PATH) => {
    expect(() => parseEnv({ DATABASE_PATH })).toThrow('Invalid configuration: DATABASE_PATH');
  });

  it('rejects invalid environment and host without disclosing supplied values', () => {
    expect(() => parseEnv({ NODE_ENV: 'private-value', HOST: 'http://localhost' }))
      .toThrow(new ConfigurationError('Invalid configuration: NODE_ENV, HOST'));
  });
});
