export const g2Migration = {
  version: 2,
  name: 's1_sessions_turns',
  sql: `
    CREATE TABLE scenario_versions (
      id TEXT PRIMARY KEY,
      template_id TEXT NOT NULL,
      schema_version INTEGER NOT NULL,
      engine_version TEXT NOT NULL,
      rubric_version TEXT NOT NULL,
      config_fingerprint TEXT NOT NULL,
      definition_hash TEXT NOT NULL UNIQUE,
      definition_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      published_at TEXT NOT NULL
    ) STRICT;
    CREATE TRIGGER scenario_version_immutable_update BEFORE UPDATE ON scenario_versions
      BEGIN SELECT RAISE(ABORT, 'Immutable scenario version'); END;
    CREATE TRIGGER scenario_version_immutable_delete BEFORE DELETE ON scenario_versions
      BEGIN SELECT RAISE(ABORT, 'Immutable scenario version'); END;
    CREATE TABLE sessions (
      id TEXT PRIMARY KEY,
      scenario_version_id TEXT NOT NULL REFERENCES scenario_versions(id),
      revision INTEGER NOT NULL CHECK(revision BETWEEN 0 AND 8),
      phase TEXT NOT NULL,
      state_json TEXT NOT NULL,
      mode TEXT NOT NULL CHECK(mode = 'DEMO_FALLBACK'),
      replay_of TEXT REFERENCES sessions(id),
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      terminal_at TEXT
    ) STRICT;
    CREATE INDEX sessions_version ON sessions(scenario_version_id);
    CREATE TABLE turns (
      session_id TEXT NOT NULL REFERENCES sessions(id),
      turn_number INTEGER NOT NULL CHECK(turn_number BETWEEN 1 AND 8),
      request_id TEXT NOT NULL,
      request_body_hash TEXT NOT NULL,
      action_json TEXT NOT NULL,
      events_json TEXT NOT NULL,
      public_response_json TEXT NOT NULL,
      state_after_json TEXT NOT NULL,
      created_at TEXT NOT NULL,
      PRIMARY KEY(session_id, turn_number),
      UNIQUE(session_id, request_id)
    ) STRICT;
  `,
} as const;
