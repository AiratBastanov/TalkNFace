import { randomUUID } from 'node:crypto';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import Driver from 'better-sqlite3';
import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import type { CanonicalAction, ScenarioDefinition } from '@arena/contracts';
import { DEFAULT_SETTINGS, DraftSchema, ContextPublicationSchema } from '@arena/contracts/context-config';
import type { Settings, Draft } from '@arena/contracts/context-config';
import { S1, S2 } from '@arena/scenarios';
import { createInitialState, transition, evaluateAuthority, evaluateConstraints, evaluateUtility, validateScenario, selectCounteroffer } from '@arena/domain';
import { compileSettings, deriveDefinition, LIMITS } from '../src/context/compiler.ts';
import { ContextService } from '../src/context/service.ts';
import { buildApp } from '../src/app.ts';
import { openDatabase } from '../src/database.ts';
import { ArenaRepository, hashBody } from '../src/repositories/arena-repository.ts';
import { SessionService } from '../src/services/session-service.ts';
import { FeedbackService, compareReports } from '../src/feedback/service.ts';
import { g2Migration } from '../src/migration-g2.ts';
import { feedbackMigration } from '../src/migration-feedback.ts';
import { WEB_ROOT } from '../src/paths.ts';
import { temporaryDatabase } from './helpers.ts';

// Independent app examples and arithmetic, no ML/evaluation fixtures.
const neutral = { tone: 'neutral' as const, acknowledgementFactId: null, argumentId: null, contradictsFactId: null, evidenceRefs: [] };
const q = (id: string): CanonicalAction => ({ ...neutral, kind: 'question', primaryTopicId: id, secondaryTopicId: null });
const ack = (id: string): CanonicalAction => ({ ...neutral, kind: 'acknowledge', acknowledgementFactId: id });
const arg = (id: string): CanonicalAction => ({ ...neutral, kind: 'argument', argumentId: id });
const exit: CanonicalAction = { ...neutral, kind: 'walk_away' };
const terms = (values: Record<string, string>) => Object.entries(values).map(([issueId, valueId]) => ({ issueId, valueId }));
const supply = (price = '95', delivery = 'split40at7_rest14', prepay = '50') => terms({ PRICE: price, DELIVERY: delivery, PREPAY: prepay });
const workload = (help = '1') => terms({ SCOPE: 'full', DEADLINE: '2', HELP: help, DEFER_REPORT: '1' });
const offer = (t: ReturnType<typeof terms>): CanonicalAction => ({ ...neutral, kind: 'offer', terms: t, conditionalOn: [] });
const team: Settings = { sphere: 'team', topic: 'urgent', opponentRole: 'specialist', opponentGoals: 'protect_load', difficulty: 'normal', tone: 'neutral' };
function compiled(settings: Settings = DEFAULT_SETTINGS) {
  const c = compileSettings(settings); expect(c.validation.issues).toEqual([]); expect(c.definition).not.toBeNull(); return c.definition!;
}
function initial(d: ScenarioDefinition) { return createInitialState(d, { sessionId: randomUUID(), scenarioVersionId: randomUUID() }); }
function step(d: ScenarioDefinition, a: CanonicalAction) {
  const r = transition(d, initial(d), { requestId: randomUUID(), expectedRevision: 0, action: a });
  if (!r.ok) throw Error(JSON.stringify(r.errors)); return r;
}

describe('six real configuration effects and bounded common-engine proof', () => {
  it('sphere changes issue units, interests and physically feasible packages', () => {
    const a = compiled(), b = compiled(team);
    expect(a.issues.map(i => i.id)).toEqual(['PRICE','DELIVERY','PREPAY']);
    expect(b.issues.map(i => i.unit)).toEqual(['часов работы','рабочих дней','6 часов ресурса','6 часов ресурса']);
    expect(b.participants[1].interests).not.toEqual(a.participants[1].interests);
    expect(evaluateConstraints(b, workload('0')).feasible).toBe(false);
  });
  it('topic admits all14 only for planned supply; both settings have playable target witnesses', () => {
    const a = compiled(), b = compiled({ ...DEFAULT_SETTINGS, topic: 'planned' });
    const t = supply('110', 'all14', '0');
    expect(evaluateConstraints(a, t).feasible).toBe(false); expect(evaluateConstraints(b, t).feasible).toBe(true);
    expect(b.facts.find(f => f.id === 'launch-bound')?.text).toContain('день 14');
  });
  it('difficulty changes actual first-offer acceptance and disclosure, with unchanged rubric', () => {
    const easy = compiled({ ...DEFAULT_SETTINGS, difficulty: 'beginner' }), normal = compiled();
    expect(step(easy, offer(supply())).state.outcome?.family).toBe('MUTUAL_GAIN'); // supplier27 >= 20+8-2=26
    expect(step(normal, offer(supply())).events.some(e => e.payload.type === 'offer_rejected_aspiration')).toBe(true); // 27 <33
    const advanced = compiled({ ...DEFAULT_SETTINGS, difficulty: 'advanced' });
    expect(step(normal,q('logistics')).state.knownFactIds).toContain('logistics-saving'); //54 >=45
    expect(step(advanced,q('logistics')).state.knownFactIds).not.toContain('logistics-saving'); //54 <55
    expect(easy.evaluation).toEqual(normal.evaluation);
  });
  it('tone changes actual disclosure and skeptical repair strength', () => {
    const neutralD = compiled(), skeptical = compiled({ ...DEFAULT_SETTINGS, tone: 'skeptical' });
    expect(step(neutralD,q('logistics')).state.knownFactIds).toContain('logistics-saving');
    expect(step(skeptical,q('logistics')).state.knownFactIds).not.toContain('logistics-saving');
    expect(step(neutralD,ack('launch-bound')).state.tension).toBe(16);
    expect(step(skeptical,ack('launch-bound')).state.tension).toBe(28);
    expect(initial(compiled({ ...DEFAULT_SETTINGS,tone:'friendly' })).trust).toBe(60);
  });
  it('role changes S1 authority for the identical package, and S2 ability to originate a helper', () => {
    const director = compiled(), manager = compiled({ ...DEFAULT_SETTINGS, opponentRole:'account_manager' });
    expect(evaluateAuthority(director,'opponent',supply(),'accept').feasible).toBe(true);
    expect(evaluateAuthority(manager,'opponent',supply(),'accept').feasible).toBe(false);
    expect(step(manager,offer(supply())).events.some(e=>e.payload.type==='offer_rejected_authority')).toBe(true);
    const specialist=compiled(team), lead=compiled({...team,opponentRole:'team_lead'});
    expect(evaluateAuthority(specialist,'opponent',workload(),'propose').feasible).toBe(false);
    expect(evaluateAuthority(lead,'opponent',workload(),'propose').feasible).toBe(true);
    const rejected=workload('0');
    expect(selectCounteroffer(specialist,initial(specialist),rejected)?.terms.find(t=>t.issueId==='HELP')?.valueId).toBe('0');
    expect(selectCounteroffer(lead,initial(lead),rejected)?.terms.find(t=>t.issueId==='HELP')?.valueId).toBe('1');
  });
  it('goals change complete utility/BATNA data coherently in both valid families', () => {
    const cash=compiled(), margin=compiled({...DEFAULT_SETTINGS,opponentGoals:'margin'});
    expect(evaluateUtility(cash,'opponent',supply())).toBe(27); //95-80-8+20
    expect(evaluateUtility(margin,'opponent',supply())).toBe(25); //95-80-8+18
    expect(margin.participants[1].reservation).toBe(22); expect(margin.participants[1].batna.utility).toBe(22);
    const protect=compiled(team), deliver=compiled({...team,opponentGoals:'deliver_scope'});
    expect(evaluateUtility(protect,'opponent',workload())).toBe(30);
    expect(evaluateUtility(deliver,'opponent',workload())).toBe(38);
    expect(deliver.participants[1].reservation).toBe(27); expect(deliver.participants[1].batna.utility).toBe(27);
  });
  for (const [name, settings] of [
    ['supplier base', DEFAULT_SETTINGS], ['planned margin friendly', {...DEFAULT_SETTINGS,topic:'planned',opponentGoals:'margin',tone:'friendly'}],
    ['account manager beginner', {...DEFAULT_SETTINGS,opponentRole:'account_manager',difficulty:'beginner'}],
    ['skeptical advanced', {...DEFAULT_SETTINGS,tone:'skeptical',difficulty:'advanced'}],
    ['team base',team],['team lead delivery', {...team,opponentRole:'team_lead',opponentGoals:'deliver_scope',difficulty:'advanced'}],
  ] as [string,Settings][]) it(name + ': distinct acceptable committed witness traces plus target and exit', () => {
    const d=compiled(settings); expect(validateScenario(d).valid).toBe(true);
    const packages: string[]=[]; let target=false;
    for(const trace of d.validation.witnessTraces) {
      let state=initial(d);
      for(const a of trace.actions) {const r=transition(d,state,{requestId:randomUUID(),expectedRevision:state.revision,action:a});expect(r.ok).toBe(true);if(r.ok)state=r.state;}
      expect(['MUTUAL_GAIN','ACCEPTABLE_PARTIAL']).toContain(state.outcome?.family);
      target ||= state.outcome?.family==='MUTUAL_GAIN'; packages.push(JSON.stringify(state.agreementOffer?.terms));
      expect(trace.actions.length).toBeLessThanOrEqual(8);
    }
    expect(new Set(packages).size).toBe(2);expect(target).toBe(true);
    expect(step(d,exit).state.outcome?.family).toBe('NO_AGREEMENT');expect(LIMITS.offersPerTemplate).toBe(64);
  });
  for(const [name,settings] of [
    ['cross-family role',{...DEFAULT_SETTINGS,opponentRole:'specialist'}],
    ['cross-family goals',{...team,opponentGoals:'margin'}],
    ['missing choices',{...team,topic:null,opponentRole:null,opponentGoals:null}],
    ['unavailable helper / locked target',{...team,topic:'reprioritize'}],
    ['manager margin cannot reach target62',{...DEFAULT_SETTINGS,opponentRole:'account_manager',opponentGoals:'margin'}],
  ] as [string,Settings][]) it('rejects '+name+' without correction',()=>{
    const before=structuredClone(settings),r=compileSettings(settings);
    expect(r.definition).toBeNull();expect(r.validation.status).toBe('invalid');expect(settings).toEqual(before);
    expect(r.validation.issues[0]?.fields.length).toBeGreaterThan(0);
  });
  it('separates package feasibility from reachability under the current aspiration policy',()=>{
    const settings:Settings={...DEFAULT_SETTINGS,opponentRole:'account_manager',difficulty:'advanced',tone:'friendly'};
    const math=validateScenario(deriveDefinition(settings));
    expect(math.valid).toBe(true);expect(math.coverage?.playerTargetReaching).toBeGreaterThan(0);
    const proof=compileSettings(settings);expect(proof.validation.status).toBe('invalid');expect(proof.definition).toBeNull();
    expect(proof.validation.issues[0]?.fields).toContain('difficulty');
  });
  it('retains immutable frozen references, deterministic semantic identity and strict validation',()=>{
    const before=[hashBody(S1),hashBody(S2)];const a=compiled(),b=compiled();
    expect(a).toEqual(b);expect(a.templateId).not.toBe(S1.templateId);expect(a.configFingerprint).not.toBe(S1.configFingerprint);
    expect(compiled({...DEFAULT_SETTINGS,tone:'friendly'}).configFingerprint).not.toBe(a.configFingerprint);
    a.participants[1].utility.unary[0]!.cells[0]!.utility=999;
    expect([hashBody(S1),hashBody(S2)]).toEqual(before);
    const broken=deriveDefinition(DEFAULT_SETTINGS);broken.participants[1].utility.unary[0]!.cells.pop();
    expect(validateScenario(broken).valid).toBe(false);
    expect(compileSettings({...DEFAULT_SETTINGS,formula:'process.exit()'}).definition).toBeNull();
  });
});

describe('real Fastify + file-backed SQLite admin transactions',()=>{
  let temp: ReturnType<typeof temporaryDatabase>,db:ReturnType<typeof openDatabase>,app:Awaited<ReturnType<typeof buildApp>>;
  beforeEach(async()=>{temp=temporaryDatabase();db=openDatabase(temp.filename);app=await buildApp({NODE_ENV:'development',HOST:'127.0.0.1',PORT:3000,DATABASE_PATH:temp.filename},{database:db});});
  afterEach(async()=>{await app.close();temp.cleanup();});
  const bind=(d:Draft)=>({expectedRevision:d.revision,settingsHash:d.settingsHash,requestId:randomUUID()});
  async function get(){return DraftSchema.parse((await app.inject('/api/admin/context-draft')).json());}
  async function post(op:string,body:unknown){return app.inject({method:'POST',url:'/api/admin/context-draft/'+op,payload:body as object});}
  async function save(settings:Settings){const d=await get(),r=await post('save',{...bind(d),settings});expect(r.statusCode,r.body).toBe(200);return DraftSchema.parse(r.json());}
  async function validated(settings=DEFAULT_SETTINGS){const d=await save(settings),r=await post('validate',bind(d));expect(r.statusCode,r.body).toBe(200);return DraftSchema.parse(r.json());}
  async function published(settings=DEFAULT_SETTINGS){const d=await validated(settings),r=await post('publish',{...bind(d),candidateHash:d.validation!.candidateHash,approved:true});expect(r.statusCode,r.body).toBe(200);return ContextPublicationSchema.parse(r.json()).publication;}
  it('requires current validation and explicit approval; exact idempotent publication survives changed drafts',async()=>{
    let d=await get();
    expect((await post('publish',{...bind(d),candidateHash:'a'.repeat(64),approved:true})).statusCode).toBe(409);
    d=await validated();const c={...bind(d),candidateHash:d.validation!.candidateHash,approved:true};
    expect((await post('publish',{...c,approved:false})).statusCode).toBe(400);
    const a=await post('publish',c);expect(a.statusCode,a.body).toBe(200);
    expect((await post('publish',c)).json()).toEqual(a.json()); // response lost to client
    await save({...DEFAULT_SETTINGS,tone:'friendly'});
    expect((await post('publish',c)).json()).toEqual(a.json());
    expect((await post('publish',{...c,candidateHash:'b'.repeat(64)})).statusCode).toBe(409);
    expect(new ArenaRepository(db).versions()).toHaveLength(1);
  });
  it('changed settings invalidate approval; stale save, validation and publication never overwrite',async()=>{
    const d=await validated(),c={...bind(d),settings:{...DEFAULT_SETTINGS,tone:'friendly'}};
    const r=await post('save',c);expect(r.statusCode).toBe(200);expect(r.json().validation).toBeNull();
    expect((await post('save',c)).json()).toEqual(r.json());
    expect((await post('save',{...c,settings:DEFAULT_SETTINGS})).statusCode).toBe(409);
    expect((await post('save',{...bind(d),settings:DEFAULT_SETTINGS})).statusCode).toBe(409);
    expect((await post('validate',bind(d))).statusCode).toBe(409);
    expect((await post('publish',{...bind(d),candidateHash:d.validation!.candidateHash,approved:true})).statusCode).toBe(409);
    expect((await get()).settings.tone).toBe('friendly');expect(new ArenaRepository(db).versions()).toHaveLength(0);
  });
  it('rechecks revision atomically when another SQLite connection saves during publication preparation',async()=>{
    const d=await validated(),repo=new ArenaRepository(db),service=new ContextService(repo),other=openDatabase(temp.filename);
    const original=repo.immediate.bind(repo);
    repo.immediate=<T>(work:()=>T):T=>{
      new ContextService(new ArenaRepository(other)).save({...bind(d),settings:{...DEFAULT_SETTINGS,tone:'friendly'}});
      return original(work);
    };
    try {expect(()=>service.publish({...bind(d),candidateHash:d.validation!.candidateHash,approved:true})).toThrow(/другой вкладке/);}
    finally {other.close();}
    expect(repo.versions()).toHaveLength(0);
  });
  it('rechecks exact revision after validation if another SQLite connection changes the draft',async()=>{
    const d=await get(),repo=new ArenaRepository(db),service=new ContextService(repo),other=openDatabase(temp.filename);
    const original=repo.immediate.bind(repo);
    repo.immediate=<T>(work:()=>T):T=>{
      new ContextService(new ArenaRepository(other)).save({...bind(d),settings:{...DEFAULT_SETTINGS,tone:'friendly'}});
      return original(work);
    };
    try{expect(()=>service.validate(bind(d))).toThrow(/другой вкладке/);}finally{other.close();}
    expect((await get()).validation).toBeNull();expect((await get()).settings.tone).toBe('friendly');
  });
  it('rejects client validity flags and user-supplied definitions even with a current draft binding',async()=>{
    const d=await validated();
    const r=await post('publish',{...bind(d),approved:true,candidateHash:d.validation!.candidateHash,valid:true,definition:S1});
    expect(r.statusCode).toBe(400);expect(new ArenaRepository(db).versions()).toHaveLength(0);
  });
  it('refuses approvals from an older compiler policy',async()=>{
    const d=await validated();const old={...d.validation,compilerVersion:'old-policy'};
    db.prepare('UPDATE context_drafts SET validation_json=?').run(JSON.stringify(old));
    expect((await get()).validation).toBeNull();
    expect((await post('publish',{...bind(d),candidateHash:d.validation!.candidateHash,approved:true})).statusCode).toBe(409);
  });
  it('invalid combinations remain saved/editable with affected-field messages and no private data',async()=>{
    const d=await validated({...team,topic:'reprioritize'});expect(d.validation?.status).toBe('invalid');
    expect((await get()).settings).toEqual({...team,topic:'reprioritize'});
    expect(JSON.stringify(d)).not.toMatch(/witnessTraces|opponentUtility|utility|definition_json|config-proof/);
    expect(d.validation?.issues[0]?.fields).toContain('topic');
  });
  for(const settings of [
    {...DEFAULT_SETTINGS,opponentGoals:'__proto__'}, {...DEFAULT_SETTINGS,topic:'<script>alert(1)</script>'},
    {...DEFAULT_SETTINGS,difficulty:999}, {...DEFAULT_SETTINGS,unknown:true}, {...DEFAULT_SETTINGS,opponentGoals:{formula:'1+1'}},
  ])it('strict server settings reject '+JSON.stringify(settings),async()=>{
    const d=await get();expect((await post('save',{...bind(d),settings})).statusCode).toBe(400);expect(await get()).toEqual(d);
  });
  it('malformed JSON, oversize input and unknown query fields are safe and nonpersistent',async()=>{
    const before=await get();
    for(const payload of ['{"x":NaN}', '{"x":', JSON.stringify({x:'x'.repeat(5000)})]) {
      const r=await app.inject({method:'POST',url:'/api/admin/context-draft/save',payload,headers:{'content-type':'application/json'}});
      expect(r.statusCode).toBe(400);expect(r.body).not.toMatch(/stack|SELECT|SyntaxError/);
    }
    expect((await app.inject('/api/admin/context-draft?private=true')).statusCode).toBe(400);expect(await get()).toEqual(before);
  });
  it('configured version A, committed report, active replay and draft survive B publication and restart',async()=>{
    const a=await published({...DEFAULT_SETTINGS,topic:'planned'}),repo=new ArenaRepository(db),sessions=new SessionService(repo),feedback=new FeedbackService(repo);
    let s=sessions.create(a.id);
    feedback.savePreparation(s.projection.sessionId,{expectedRevision:0,goal:'target',ownBoundary:55,acknowledgedAlternative:true});
    for(const action of [q('logistics'),ack('logistics-saving'),arg('logistics-argument'),q('payment'),offer(supply())])s=sessions.playTurn(s.projection.sessionId,{requestId:randomUUID(),expectedRevision:s.projection.revision,action});
    expect(s.result?.playerUtility).toBe(64);
    const report=feedback.report(s.projection.sessionId,s.projection.revision),row=repo.version(a.id),turns=repo.turns(s.projection.sessionId);
    expect(report.overall.score).toBe(100);
    let replay=sessions.replay(s.projection.sessionId);replay=sessions.playTurn(replay.projection.sessionId,{requestId:randomUUID(),expectedRevision:0,action:q('logistics')});
    const b=await published({...team,opponentRole:'team_lead',opponentGoals:'deliver_scope'});expect(b.id).not.toBe(a.id);
    let other=sessions.create(b.id);other=sessions.playTurn(other.projection.sessionId,{requestId:randomUUID(),expectedRevision:0,action:exit});
    expect(compareReports(feedback.report(other.projection.sessionId,1),report).comparable).toBe(false);
    const draft=await get();
    await app.close();db=openDatabase(temp.filename);app=await buildApp({NODE_ENV:'development',HOST:'127.0.0.1',PORT:3000,DATABASE_PATH:temp.filename},{database:db});
    const restored=new ArenaRepository(db);
    expect(restored.version(a.id)).toEqual(row);expect(restored.turns(s.projection.sessionId)).toEqual(turns);expect(await get()).toEqual(draft);
    expect(new FeedbackService(restored).report(s.projection.sessionId,s.projection.revision)).toEqual(report);
    expect(new SessionService(restored).get(replay.projection.sessionId)).toEqual(replay);
    expect(replay.scenarioVersionId).toBe(a.id);
    expect(()=>db.prepare('UPDATE scenario_versions SET definition_json=? WHERE id=?').run('{}',a.id)).toThrow();
  });
  it('configured public preview, player DTO and bundle exclude private facts/tables/witnesses',async()=>{
    const p=await published({...team,opponentGoals:'deliver_scope'}),d=compiled({...team,opponentGoals:'deliver_scope'});
    const s=new SessionService(new ArenaRepository(db)).create(p.id);
    const json=JSON.stringify([p,await get(),s]);
    expect(json).not.toMatch(/witnessTraces|opponentUtility|opponentBatna|resourceAuthorizations|"trust"|"tension"|"utility":\s*\{/);
    for(const f of d.facts.filter(f=>f.visibility==='hidden'))expect(json).not.toContain(f.text);
    expect(json).not.toContain(d.participants[1].privateBrief);
    const bundle=readdirSync(join(WEB_ROOT,'assets')).filter(f=>f.endsWith('.js')).map(f=>readFileSync(join(WEB_ROOT,'assets',f),'utf8')).join('');
    for(const f of d.facts.filter(f=>f.visibility==='hidden'))expect(bundle).not.toContain(f.text);
    expect(bundle).not.toContain('Может согласовать цену от 90');expect(bundle).not.toContain('цену только от 100');
    expect(bundle).not.toContain('configured-path-');expect(bundle).not.toContain('config-proof');
  });
});

for(const migration of [2,3])it('migration '+migration+' data upgrade preserves reference versions, active attempts and feedback',async()=>{
  const temp=temporaryDatabase();let db=new Driver(temp.filename.replace('nested/','').replace('nested\\',''));
  // The fixture is new independent app data, created at exactly the historical schema.
  const filename=db.name;
  try {
    db.exec("CREATE TABLE schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,applied_at TEXT NOT NULL DEFAULT 'legacy') STRICT; CREATE TABLE foundation_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL) STRICT; INSERT INTO schema_migrations(version,name) VALUES(1,'foundation_metadata')");
    db.exec(g2Migration.sql);db.prepare('INSERT INTO schema_migrations(version,name) VALUES(2,?)').run(g2Migration.name);
    if(migration===3){db.exec(feedbackMigration.sql);db.prepare('INSERT INTO schema_migrations(version,name) VALUES(3,?)').run(feedbackMigration.name);}
    const repo=new ArenaRepository(db),sessions=new SessionService(repo),feedback=new FeedbackService(repo);
    const oldVersions=[repo.publish(S1),repo.publish(S2)];const saved:ReturnType<SessionService['get']>[]=[];const reports:ReturnType<FeedbackService['report']>[]=[];
    for(const v of oldVersions) {
      let s=sessions.create(v.id);
      if(migration===3)feedback.savePreparation(s.projection.sessionId,{expectedRevision:0,goal:'target',ownBoundary:v.template_id===S1.templateId?55:25,acknowledgedAlternative:true});
      s=sessions.playTurn(s.projection.sessionId,{requestId:randomUUID(),expectedRevision:0,action:exit});saved.push(s);
      if(migration===3)reports.push(feedback.report(s.projection.sessionId,1));
      saved.push(sessions.replay(s.projection.sessionId));
    }
    const turns=db.prepare('SELECT * FROM turns ORDER BY session_id').all();db.close();db=openDatabase(filename);
    const after=new ArenaRepository(db);
    expect(db.prepare('SELECT version FROM schema_migrations ORDER BY version').all()).toEqual([1,2,3,4].map(version=>({version})));
    expect(after.versions().sort((a,b)=>a.id.localeCompare(b.id))).toEqual(oldVersions.sort((a,b)=>a.id.localeCompare(b.id)));
    expect(db.prepare('SELECT * FROM turns ORDER BY session_id').all()).toEqual(turns);
    for(const s of saved)expect(new SessionService(after).get(s.projection.sessionId)).toEqual(s);
    for(const r of reports)expect(new FeedbackService(after).report(r.sessionId,r.terminalRevision)).toEqual(r);
  }finally{db.close();temp.cleanup();}
});
