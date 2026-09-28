// Forward migration 4. Publications, sessions, old migrations and training contracts are untouched.
export const contextMigration = {
  version: 4, name: 'administrator_context_draft',
  sql: `CREATE TABLE context_drafts (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    revision INTEGER NOT NULL CHECK (revision >= 0),
    settings_hash TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    validation_json TEXT,
    definition_json TEXT
  ) STRICT;
  CREATE TABLE context_requests (
    request_id TEXT PRIMARY KEY,
    body_hash TEXT NOT NULL,
    response_json TEXT NOT NULL
  ) STRICT;
  CREATE TRIGGER context_request_immutable_update BEFORE UPDATE ON context_requests
  BEGIN SELECT RAISE(ABORT, 'context request is immutable'); END;
  CREATE TRIGGER context_request_immutable_delete BEFORE DELETE ON context_requests
  BEGIN SELECT RAISE(ABORT, 'context request is immutable'); END;`,
} as const;
