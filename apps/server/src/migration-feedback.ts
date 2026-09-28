// Forward-only, additive application data; frozen migrations 1 and 2 are unchanged.
export const feedbackMigration = {
  version: 3, name: 'explicit_preparation',
  sql: `CREATE TABLE session_preparation (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
    record_json TEXT NOT NULL
  ) STRICT;
  CREATE TRIGGER preparation_before_start BEFORE INSERT ON session_preparation
  WHEN (SELECT revision FROM sessions WHERE id = NEW.session_id) <> 0
  BEGIN SELECT RAISE(ABORT, 'preparation requires revision zero'); END;
  CREATE TRIGGER preparation_immutable_update BEFORE UPDATE ON session_preparation
  BEGIN SELECT RAISE(ABORT, 'preparation is immutable'); END;
  CREATE TRIGGER preparation_immutable_delete BEFORE DELETE ON session_preparation
  BEGIN SELECT RAISE(ABORT, 'preparation is immutable'); END;`,
} as const;
