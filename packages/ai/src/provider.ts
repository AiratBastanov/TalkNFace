import type { AIFailureCode, PlayerMoveInterpretation } from '@arena/contracts/g3';
import type { InterpretationContext } from './context.ts';

export type Usage = { inputTokens: number; outputTokens: number; reasoningTokens: number };
export type ResultEnvelope<T> = {
  provider: 'openai' | 'fake'; model: 'gpt-6-astra' | 'fake'; requestId: string | null; latencyMs: number; usage: Usage | null;
} & ({ status: 'ok'; data: T } | { status: 'refusal' | 'timeout' | 'rate_limited' | 'unavailable' | 'invalid'; code: AIFailureCode });
export type OperationRequest<T> = { input: T; schemaVersion: 1; deadline: number; signal: AbortSignal; repair?: boolean };
type Contract = { input: unknown; output: unknown };
type FutureOperations = { generateScenario: Contract; generateOpponentReply: Contract; explainFeedback: Contract };
type Unimplemented = { [K in keyof FutureOperations]: { input: never; output: never } };
type Operation<C extends Contract> = (request: OperationRequest<C['input']>) => Promise<ResultEnvelope<C['output']>>;
// Future operations can acquire their own contracts at their authorized gates. No placeholder live implementation.
export interface AIProvider<F extends FutureOperations = Unimplemented> {
  readonly provider: 'openai' | 'fake';
  readonly model: 'gpt-6-astra' | 'fake';
  interpretPlayerMove(request: OperationRequest<{ context: InterpretationContext; text: string }>): Promise<ResultEnvelope<PlayerMoveInterpretation>>;
  generateScenario?: Operation<F['generateScenario']>;
  generateOpponentReply?: Operation<F['generateOpponentReply']>;
  explainFeedback?: Operation<F['explainFeedback']>;
}
