import { randomUUID } from 'node:crypto';
import Driver from 'better-sqlite3';
import { describe, expect, it } from 'vitest';
import { openDatabase } from '../src/database.ts';
import { temporaryDatabase } from './helpers.ts';

describe('real file SQLite foundation', () => {
  it('creates directories, applies the migration, and configures SQLite', () => {
    const temp = temporaryDatabase();
    const db = openDatabase(temp.filename);
    try {
      expect(db.pragma('foreign_keys', { simple: true })).toBe(1);
      expect(db.pragma('busy_timeout', { simple: true })).toBe(5000);
      expect(db.pragma('journal_mode', { simple: true })).toBe('wal');
      expect(db.prepare('SELECT version, name FROM schema_migrations').all())
        .toEqual([{ version: 1, name: 'foundation_metadata' }, { version: 2, name: 's1_sessions_turns' }, { version: 3, name: 'explicit_preparation' }, { version: 4, name: 'administrator_context_draft' }]);
      expect(db.prepare("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name").all())
        .toEqual([{ name: 'context_drafts' }, { name: 'context_requests' }, { name: 'foundation_metadata' }, { name: 'scenario_versions' }, { name: 'schema_migrations' }, { name: 'session_preparation' }, { name: 'sessions' }, { name: 'turns' }]);
    } finally { db.close(); temp.cleanup(); }
  });

  it('retains a sentinel and the original migration record across two reopenings', () => {
    const temp = temporaryDatabase();
    const sentinel = randomUUID();
    let db = openDatabase(temp.filename);
    try {
      db.prepare('INSERT INTO foundation_metadata (key, value) VALUES (?, ?)').run('g0-sentinel', sentinel);
      const migration = db.prepare('SELECT * FROM schema_migrations').all();
      for (let startup = 0; startup < 2; startup += 1) {
        db.close();
        expect(db.open).toBe(false);
        db = openDatabase(temp.filename);
        expect(db.prepare('SELECT value FROM foundation_metadata WHERE key = ?').get('g0-sentinel'))
          .toEqual({ value: sentinel });
        expect(db.prepare('SELECT * FROM schema_migrations').all()).toEqual(migration);
      }
    } finally { db.close(); temp.cleanup(); }
  });

  it('refuses a newer schema without deleting existing metadata', () => {
    const temp = temporaryDatabase();
    let db = openDatabase(temp.filename);
    try {
      db.prepare('INSERT INTO foundation_metadata (key, value) VALUES (?, ?)').run('keep', 'value');
      db.exec("INSERT INTO schema_migrations (version, name) VALUES (99, 'future')");
      db.close();
      expect(() => openDatabase(temp.filename)).toThrow('Database schema is newer');
      // Inspect with the same driver after the deliberate failure; do not run migrations.
      db = new Driver(temp.filename);
      expect(db.prepare('SELECT value FROM foundation_metadata WHERE key = ?').get('keep')).toEqual({ value: 'value' });
    } finally { if (db.open) db.close(); temp.cleanup(); }
  });
});
