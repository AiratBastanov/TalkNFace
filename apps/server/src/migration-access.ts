// Additive migration 5: historical negotiation records are not rewritten or claimed.
export const accessMigration = {
  version: 5, name: 'access_principals_sessions_ownership',
  sql: `CREATE TABLE access_principals (
    id TEXT PRIMARY KEY,
    created_at INTEGER NOT NULL
  ) STRICT;
  CREATE TABLE access_sessions (
    token_digest TEXT PRIMARY KEY,
    principal_id TEXT NOT NULL REFERENCES access_principals(id),
    role TEXT NOT NULL CHECK(role IN ('player', 'admin')),
    csrf_digest TEXT NOT NULL,
    credential_digest TEXT,
    created_at INTEGER NOT NULL,
    last_seen_at INTEGER NOT NULL,
    idle_expires_at INTEGER NOT NULL,
    absolute_expires_at INTEGER NOT NULL,
    revoked_at INTEGER,
    CHECK(idle_expires_at <= absolute_expires_at)
  ) STRICT;
  CREATE INDEX access_sessions_principal ON access_sessions(principal_id);
  CREATE TABLE session_owners (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id),
    principal_id TEXT NOT NULL REFERENCES access_principals(id)
  ) STRICT;
  CREATE INDEX session_owners_principal ON session_owners(principal_id);
  CREATE TRIGGER session_owner_immutable_update BEFORE UPDATE ON session_owners
    BEGIN SELECT RAISE(ABORT, 'Immutable ownership'); END;
  CREATE TRIGGER session_owner_immutable_delete BEFORE DELETE ON session_owners
    BEGIN SELECT RAISE(ABORT, 'Immutable ownership'); END;
  CREATE TABLE access_login_budget (
    id INTEGER PRIMARY KEY CHECK(id = 1),
    window_start INTEGER NOT NULL,
    attempts INTEGER NOT NULL CHECK(attempts >= 0)
  ) STRICT;`,
} as const;
