export type HealthResponse = { status: 'ok' };
export type ReadinessResponse = { status: 'ready' } | { status: 'not_ready' };
export * from './common.ts';
export * from './action.ts';
export * from './scenario.ts';
export * from './event.ts';
export * from './outcome.ts';
export * from './session.ts';
export * from './projection.ts';
