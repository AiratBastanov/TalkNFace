// Read-only parity check against the existing application contract.
import { readFileSync } from 'node:fs';
import { spawnSync } from 'node:child_process';
import { z } from 'zod';
import { PlayerMoveInterpretationSchema as schema } from '../../packages/contracts/src/g3.ts';
const fixture = JSON.parse(readFileSync('evals/local-qwen/a01-a16.json', 'utf8'));
const saved = JSON.parse(readFileSync('evals/local-qwen/interpretation.schema.json', 'utf8'));
if (JSON.stringify(z.toJSONSchema(schema)) !== JSON.stringify(saved)) throw new Error('Application schema drift');
const inputs = [];
for (const c of fixture.cases) {
  const valid = structuredClone(c.expected);
  valid.evidenceSpans = [{ start: 0, end: c.text.length }];
  if (valid.argument) valid.argument.evidenceSpan = { start: 0, end: c.text.length };
  if (valid.needsClarification) valid.clarification = c.source.expected.slice(0, 240);
  inputs.push(valid);
  for (const k of Object.keys(valid)) { const bad = structuredClone(valid); delete bad[k]; inputs.push(bad); }
  for (const v of [true, null, '1', 1.5]) inputs.push({ ...valid, schemaVersion: v });
  inputs.push({ ...valid, outcome: 'win' });
}
const python = process.platform === 'win32' ? '.venv-ml/Scripts/python.exe' : '.venv-ml/bin/python';
const code = "import json,sys; sys.path.insert(0,'ml/baseline'); from scoring import schema_errors; s=json.load(open('evals/local-qwen/interpretation.schema.json',encoding='utf-8')); print(json.dumps([not schema_errors(x,s) for x in json.load(sys.stdin)]))";
const child = spawnSync(python, ['-c', code], { input: JSON.stringify(inputs), encoding: 'utf8', windowsHide: true });
if (child.status !== 0) throw new Error(child.stderr);
const py = JSON.parse(child.stdout);
const mismatches = inputs.flatMap((x, i) => schema.safeParse(x).success === py[i] ? [] : [i]);
console.log(JSON.stringify({ compared: inputs.length, mismatches, schemaUnchanged: true }));
if (mismatches.length) process.exit(1);
