import { z } from 'zod';
import type { FastifyInstance } from 'fastify';
import { BasicResultSchema, CreateSessionSchema, EmptyBodySchema, PlayTurnSchema,
  SessionParamsSchema, SessionViewSchema } from '@arena/contracts/g2';
import { PublishedCatalogScenarioSchema as PublishedScenarioSchema, ReferenceCatalogSchema as ReferenceListSchema,
  CatalogReferenceSchema as ReferencePreviewSchema, PublishedCatalogSchema as ScenarioListSchema } from '@arena/contracts/catalog';
import { ApiError } from '../api-error.ts';
import { referencePreview, SessionService } from '../services/session-service.ts';
import { referenceDefinition, referenceDefinitions } from '../services/reference-catalog.ts';
import { AccessErrorSchema as ApiErrorSchema } from '@arena/contracts/access';
import type { AccessBoundary } from '../access/boundary.ts';

function input<T>(schema: z.ZodType<T>, value: unknown): T {
  const result = schema.safeParse(value);
  if (!result.success) throw new ApiError(400, 'INVALID_REQUEST', 'Некорректный запрос. Проверьте выбранное действие.');
  return result.data;
}
export function registerG2Routes(app: FastifyInstance, service: SessionService, access: AccessBoundary) {
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
    return ReferenceListSchema.parse(referenceDefinitions().map(referencePreview));
  });
  const referenceKey = (params: unknown) => input(z.strictObject({ key: z.string().min(1).max(32) }), params).key;
  app.get('/api/admin/reference-scenarios/:key', async request => {
    input(EmptyBodySchema, request.query);
    return ReferencePreviewSchema.parse(referencePreview(referenceDefinition(referenceKey(request.params))));
  });
  app.post('/api/admin/reference-scenarios/:key/publish', async request => {
    input(EmptyBodySchema, request.query); input(EmptyBodySchema, request.body);
    return PublishedScenarioSchema.parse(service.publish(referenceKey(request.params)));
  });
  app.get('/api/scenarios', async request => {
    input(EmptyBodySchema, request.query);
    return ScenarioListSchema.parse(service.scenarios());
  });
  app.post('/api/sessions', async (request, reply) => {
    input(EmptyBodySchema, request.query);
    const body = input(CreateSessionSchema, request.body);
    return reply.code(201).send(SessionViewSchema.parse(access.createOwned(request, () => service.create(body.scenarioVersionId))));
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
    return reply.code(201).send(SessionViewSchema.parse(access.createOwned(request, () => service.replay(id))));
  });
  app.get('/api/sessions/:sessionId/result', async request =>
    BasicResultSchema.parse(service.result(sessionId(request.params, request.query))));
}
