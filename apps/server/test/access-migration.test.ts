import { randomUUID } from 'node:crypto';
import Driver from 'better-sqlite3';
import { expect, it } from 'vitest';
import { S1, S2, walkAway } from '@arena/scenarios';
import { DEFAULT_SETTINGS } from '@arena/contracts/context-config';
import { g2Migration } from '../src/migration-g2.ts';
import { feedbackMigration } from '../src/migration-feedback.ts';
import { contextMigration } from '../src/migration-context.ts';
import { openDatabase } from '../src/database.ts';
import { buildApp } from '../src/app.ts';
import { parseEnv } from '../src/env.ts';
import { ArenaRepository } from '../src/repositories/arena-repository.ts';
import { SessionService } from '../src/services/session-service.ts';
import { FeedbackService } from '../src/feedback/service.ts';
import { ContextService } from '../src/context/service.ts';
import { AccessClient, testPasswordHash } from './access-client.ts';
import { temporaryDatabase } from './helpers.ts';

it.each([2, 3, 4])('migration %i -> 5 preserves old bytes/records/reports, never claims old UUIDs, and creates new owned attempts', async version => {
  const temp = temporaryDatabase();
  let db = new Driver(temp.filename.replace('nested', '.')); // disposable parent already exists
  const filename = db.name;
  let app: Awaited<ReturnType<typeof buildApp>> | undefined;
  try {
    db.pragma('foreign_keys = ON');
    db.exec(`CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY, name TEXT NOT NULL, applied_at TEXT NOT NULL DEFAULT 'historical') STRICT;
      CREATE TABLE foundation_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL) STRICT;
      INSERT INTO foundation_metadata VALUES('sentinel','unchanged');
      INSERT INTO schema_migrations(version,name) VALUES(1,'foundation_metadata');`);
    for (const m of [g2Migration, feedbackMigration, contextMigration].filter(m => m.version <= version)) {
      db.exec(m.sql); db.prepare('INSERT INTO schema_migrations(version,name) VALUES(?,?)').run(m.version, m.name);
    }
    const repository = new ArenaRepository(db), sessions = new SessionService(repository), feedback = new FeedbackService(repository);
    const ids: string[] = [], reports: unknown[] = [], publications: string[] = [];
    for (const scenario of [S1, S2]) {
      const publication = repository.publish(scenario); publications.push(publication.id);
      const active = sessions.create(publication.id); ids.push(active.projection.sessionId);
      let terminal = sessions.create(publication.id); ids.push(terminal.projection.sessionId);
      if (version >= 3) feedback.savePreparation(terminal.projection.sessionId, { expectedRevision: 0, goal: 'target',
        acknowledgedAlternative: true, ownBoundary: scenario.participants[0].batna.utility });
      terminal = sessions.playTurn(terminal.projection.sessionId, { requestId: randomUUID(), expectedRevision: 0, action: walkAway() });
      if (version >= 3) reports.push(feedback.report(terminal.projection.sessionId, 1));
    }
    if (version >= 4) {
      const context = new ContextService(repository), old = context.get();
      context.save({ requestId: randomUUID(), expectedRevision: old.revision, settingsHash: old.settingsHash, settings: { ...DEFAULT_SETTINGS, tone: 'friendly' } });
    }
    const tables = ['foundation_metadata', 'scenario_versions', 'sessions', 'turns', ...(version >= 3 ? ['session_preparation'] : []),
      ...(version >= 4 ? ['context_drafts', 'context_requests'] : [])];
    const snapshots = Object.fromEntries(tables.map(table => [table, JSON.stringify(db.prepare('SELECT * FROM ' + table).all())]));
    const migrations = db.prepare('SELECT * FROM schema_migrations ORDER BY version').all();
    db.close(); db = openDatabase(filename);
    for (const table of tables) expect(JSON.stringify(db.prepare('SELECT * FROM ' + table).all()) === snapshots[table], table + ' unchanged').toBe(true);
    expect(db.prepare('SELECT * FROM schema_migrations WHERE version <= ? ORDER BY version').all(version)).toEqual(migrations);
    expect(db.prepare('SELECT version FROM schema_migrations ORDER BY version').all()).toEqual([1, 2, 3, 4, 5].map(version => ({ version })));
    expect(db.prepare('SELECT count(*) n FROM session_owners').get()).toEqual({ n: 0 });
    const upgradedFeedback = new FeedbackService(new ArenaRepository(db));
    if (version >= 3) expect([upgradedFeedback.report(ids[1]!, 1), upgradedFeedback.report(ids[3]!, 1)]).toEqual(reports);
    app = await buildApp(parseEnv({ NODE_ENV: 'test', DATABASE_PATH: filename, ADMIN_PASSWORD_HASH: testPasswordHash }), { database: db });
    const player = new AccessClient(app), admin = new AccessClient(app); await player.bootstrap(); await admin.bootstrap(); await admin.login();
    for (const client of [player, admin]) for (const id of ids) {
      for (const suffix of ['', '/result', '/feedback?revision=1']) expect((await client.send('/api/sessions/' + id + suffix)).statusCode).toBe(404);
      expect((await client.send({ method: 'POST', url: '/api/sessions/' + id + '/replay', payload: {} })).statusCode).toBe(404);
    }
    const fresh = await player.send({ method: 'POST', url: '/api/sessions', payload: { scenarioVersionId: publications[0] } });
    expect(fresh.statusCode).toBe(201);
    expect(db.prepare('SELECT count(*) n FROM sessions').get()).toEqual({ n: 5 });
    expect(db.prepare('SELECT count(*) n FROM session_owners').get()).toEqual({ n: 1 });
    for (const id of ids) expect(db.prepare('SELECT * FROM session_owners WHERE session_id = ?').get(id)).toBeUndefined();
  } finally { if (app) await app.close(); else if (db.open) db.close(); temp.cleanup(); }
});
