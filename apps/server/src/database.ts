import { mkdirSync } from 'node:fs';
import { dirname } from 'node:path';
import Database from 'better-sqlite3';
import { g2Migration } from './migration-g2.ts';

const migrations = [
  {
    version: 1,
    name: 'foundation_metadata',
    sql: 'CREATE TABLE foundation_metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL) STRICT;',
  },
  g2Migration,
] as const;

export function openDatabase(filename: string): Database.Database {
  mkdirSync(dirname(filename), { recursive: true });
  const db = new Database(filename, { timeout: 5_000 });
  try {
    db.pragma('foreign_keys = ON');
    db.pragma('journal_mode = WAL');
    db.transaction(() => {
      db.exec(`CREATE TABLE IF NOT EXISTS schema_migrations (
        version INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        applied_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
      ) STRICT;`);
      const applied = db.prepare<[], { version: number }>('SELECT version FROM schema_migrations ORDER BY version').all();
      if (applied.some((row) => !migrations.some((migration) => migration.version === row.version))) {
        throw new Error('Database schema is newer than this application');
      }
      const record = db.prepare('INSERT INTO schema_migrations (version, name) VALUES (?, ?)');
      for (const migration of migrations) {
        if (applied.some((row) => row.version === migration.version)) continue;
        db.exec(migration.sql);
        record.run(migration.version, migration.name);
      }
    }).immediate();
    return db;
  } catch (error) {
    db.close();
    throw error;
  }
}
