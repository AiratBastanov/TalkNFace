import { z } from 'zod';
import type { FastifyInstance } from 'fastify';
import { ApiErrorSchema, BasicResultSchema, CreateSessionSchema, EmptyBodySchema, PlayTurnSchema,
  PublishedScenarioSchema, ReferenceListSchema, ReferencePreviewSchema, ScenarioListSchema, SessionParamsSchema, SessionViewSchema } from '@arena/contracts/g2';
import { ApiError } from '../api-error.ts';
import { referencePreview, SessionService } from '../services/session-service.ts';

function input<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) throw new ApiError(400, 'INVALID_REQUEST', 'Некорректный запрос. Проверьте выбранное действие.');
  return result.data;
}
export function registerG2Routes(app: FastifyInstance, service: SessionService) {
  app.setErrorHandler((error, _request, reply) => {
    if (error instanceof ApiError) return reply.code(error.status).send(ApiErrorSchema.parse(error.body));
    // Fastify JSON parser errors are malformed input, not internal diagnostics.
    if (error instanceof Error && 'statusCode' in error && typeof error.statusCode === 'number' && error.statusCode >= 400 && error.statusCode < 500) {
      return reply.code(400).send(ApiErrorSchema.parse({ code: 'INVALID_REQUEST', message: 'Некорректный формат запроса.' }));
    }
    app.log.error({ event: 'request.failed' }, 'Request failed');
    return reply.code(500).send(ApiErrorSchema.parse({ code: 'INTERNAL_ERROR', message: 'Не удалось сохранить или загрузить данные. Повторите попытку.' }));
  });
  // One strict Zod contract universe: validate outgoing DTOs at every HTTP boundary.
  app.get('/api/reference-scenarios', async request => {
    input(EmptyBodySchema, request.query);
    return ReferenceListSchema.parse([referencePreview()]);
  });
  app.get('/api/admin/reference-scenarios/s1', async request => {
    input(EmptyBodySchema, request.query);
    return ReferencePreviewSchema.parse(referencePreview());
  });
  app.post('/api/admin/reference-scenarios/s1/publish', async request => {
    input(EmptyBodySchema, request.query); input(EmptyBodySchema, request.body);
    return PublishedScenarioSchema.parse(service.publish());
  });
  app.get('/api/scenarios', async request => {
    input(EmptyBodySchema, request.query);
    return ScenarioListSchema.parse(service.scenarios());
  });
  app.post('/api/sessions', async (request, reply) => {
    input(EmptyBodySchema, request.query);
    const body = input(CreateSessionSchema, request.body);
    return reply.code(201).send(SessionViewSchema.parse(service.create(body.scenarioVersionId)));
  });
  const sessionId = (params: unknown, query: unknown) => {
    input(EmptyBodySchema, query);
    return input(SessionParamsSchema, params).sessionId;
  };
  app.get('/api/sessions/:sessionId', async request =>
    SessionViewSchema.parse(service.get(sessionId(request.params, request.query))));
  app.post('/api/sessions/:sessionId/turns', async request => {
    const id = sessionId(request.params, request.query);
    return SessionViewSchema.parse(service.playTurn(id, input(PlayTurnSchema, request.body)));
  });
  app.post('/api/sessions/:sessionId/replay', async (request, reply) => {
    const id = sessionId(request.params, request.query);
    input(EmptyBodySchema, request.body);
    return reply.code(201).send(SessionViewSchema.parse(service.replay(id)));
  });
  app.get('/api/sessions/:sessionId/result', async request =>
    BasicResultSchema.parse(service.result(sessionId(request.params, request.query))));
}
