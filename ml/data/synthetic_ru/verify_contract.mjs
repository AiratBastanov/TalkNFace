// Read-only: validate dataset/context rows directly with the checked-in Zod schemas.
import { readFileSync } from 'node:fs';
import { z } from 'zod';
import { PlayerMoveInterpretationSchema } from '../../../packages/contracts/src/g3.ts';
import { InterpretationContextSchema } from '../../../packages/ai/src/context.ts';
const root = (process.argv[2] ?? 'ml/data/synthetic_ru')+'/';
const saved = JSON.parse(readFileSync('evals/local-qwen/interpretation.schema.json','utf8'));
if (JSON.stringify(saved)!==JSON.stringify(z.toJSONSchema(PlayerMoveInterpretationSchema))) {
  throw new Error('LOCAL_DATASET_BLOCKED_CONTRACT_CONTRADICTION: saved schema drift');
}
const registry=JSON.parse(readFileSync(root+'contexts.json','utf8'));
for (const entry of Object.values(registry)) InterpretationContextSchema.parse(entry.publicContext);
const rows=['train','dev','internal_test'].flatMap(s=>readFileSync(root+s+'.jsonl','utf8').trim().split('\n').map(JSON.parse));
rows.push(...JSON.parse(readFileSync(process.argv[3] ?? 'evals/local-qwen/dev-ru-v1.json','utf8')).cases);
for (const row of rows) {
  PlayerMoveInterpretationSchema.parse(row.expected);
  for (const span of row.expected.evidenceSpans) {
    const quote=row.text.slice(span.start,span.end);
    if (!quote || !quote.isWellFormed()) throw new Error('UTF-16 span failure: '+row.id);
  }
}
console.log(JSON.stringify({authority:'checked-in Zod',schemaParity:true,rows:rows.length,contexts:Object.keys(registry).length,valid:true}));
